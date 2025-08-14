import re
from multiprocessing import Pool, cpu_count

from .merge_dicts import merge_in_precedence
from .starter_index import StarterIndex
from .dictionary_lib import DictionaryMaxlength

try:
    from typing import List, Dict, Tuple, Optional, Iterable, Mapping
except ImportError:
    # Fallback for Python < 3.5
    List = list
    Dict = dict
    Tuple = tuple
    Iterable = list
    Mapping = dict


    def Optional(x):  # type: ignore
        return x

# Pre-compiled regex for better performance
STRIP_REGEX = re.compile(r"[!-/:-@\[-`{-~\t\n\v\f\r 0-9A-Za-z_著]")

DELIMITERS = frozenset(
    " \t\n\r!\"#$%&'()*+,-./:;<=>?@[\\]^_{}|~＝、。“”‘’『』「」﹁﹂—－（）《》〈〉？！…／＼︒︑︔︓︿﹀︹︺︙︐［﹇］﹈︕︖︰︳︴︽︾︵︶｛︷｝︸﹃﹄【︻】︼　～．，；：")

# Pre-computed punctuation mappings - fallback for older Python versions
try:
    PUNCT_S2T_MAP = str.maketrans({
        '“': '「',
        '”': '」',
        '‘': '『',
        '’': '』',
    })

    PUNCT_T2S_MAP = str.maketrans({
        '「': '“',
        '」': '”',
        '『': '‘',
        '』': '’',
    })
    HAS_MAKETRANS = True
except (AttributeError, TypeError):
    # Fallback for Python < 3.0
    HAS_MAKETRANS = False
    PUNCT_S2T_MAP = {
        '“': '「',
        '”': '」',
        '‘': '『',
        '’': '』',
    }

    PUNCT_T2S_MAP = {
        '「': '“',
        '」': '”',
        '『': '‘',
        '』': '’',
    }


class DictRefs:
    """
    A utility class that wraps up to 3 rounds of dictionary applications
    to be used in multi-pass segment-replacement conversions.
    """
    __slots__ = ['round_1', 'round_2', 'round_3', '_max_lengths']

    def __init__(self, round_1):
        """
        :param round_1: First list of dictionaries to apply (required)
        """
        self.round_1 = round_1
        self.round_2 = None
        self.round_3 = None
        self._max_lengths = None

    def with_round_2(self, round_2):
        """
        :param round_2: Second list of dictionaries (optional)
        :return: self (for chaining)
        """
        self.round_2 = round_2
        self._max_lengths = None  # Reset cache
        return self

    def with_round_3(self, round_3):
        """
        :param round_3: Third list of dictionaries (optional)
        :return: self (for chaining)
        """
        self.round_3 = round_3
        self._max_lengths = None  # Reset cache
        return self

    def _get_max_lengths(self):
        """Cache max lengths for each round to avoid recomputation"""
        if self._max_lengths is None:
            self._max_lengths = []
            for round_dicts in [self.round_1, self.round_2, self.round_3]:
                if round_dicts:
                    max_len = max((length for _, length in round_dicts), default=1)
                    self._max_lengths.append(max_len)
                else:
                    self._max_lengths.append(0)
        return self._max_lengths

    def apply_segment_replace(self, input_text, segment_replace):
        """
        Apply segment-based replacement using the configured rounds.

        :param input_text: The string to transform
        :param segment_replace: The function to apply per segment
        :return: Transformed string
        """
        max_lengths = self._get_max_lengths()

        output = segment_replace(input_text, self.round_1, max_lengths[0])
        if self.round_2:
            output = segment_replace(output, self.round_2, max_lengths[1])
        if self.round_3:
            output = segment_replace(output, self.round_3, max_lengths[2])
        return output


class OpenCC:
    """
    A pure-Python implementation of OpenCC for text conversion between
    different Chinese language variants using segmentation and replacement.
    """
    CONFIG_LIST = [
        "s2t", "t2s", "s2tw", "tw2s", "s2twp", "tw2sp", "s2hk", "hk2s",
        "t2tw", "tw2t", "t2twp", "tw2tp", "t2hk", "hk2t", "t2jp", "jp2t"
    ]

    def __init__(self, config=None):
        """
        Initialize OpenCC with a given config (default: s2t).

        :param config: Configuration name (optional)
        """
        self._last_error = None
        self._config_cache = {}
        self._fast_cache = {}
        self._merged_cache = {}
        self._starter_idx_cache = {}
        # id(dict) -> fingerprint tuple
        self._fp_cache: dict[int, tuple] = {}

        if config in self.CONFIG_LIST:
            self.config = config
        else:
            self._last_error = "Invalid config: {}".format(config) if config else None
            self.config = "s2t"

        try:
            self.dictionary = DictionaryMaxlength.new()
        except Exception as e:
            self._last_error = str(e)
            self.dictionary = DictionaryMaxlength()

        self.delimiters = DELIMITERS
        # Escape special regex characters in delimiters
        escaped_delimiters = ''.join(map(re.escape, self.delimiters))
        self.delimiter_regex = re.compile(f'[{escaped_delimiters}]')

    def set_config(self, config):
        """
        Set the conversion configuration.

        :param config: One of OpenCC.CONFIG_LIST
        """
        if config in self.CONFIG_LIST:
            self.config = config
        else:
            self._last_error = "Invalid config: {}".format(config)
            self.config = "s2t"

    def get_config(self):
        """
        Get the current conversion config.

        :return: Current config string
        """
        return self.config

    @classmethod
    def supported_configs(cls):
        """
        Return a list of supported conversion config strings.

        :return: List of config names
        """
        return cls.CONFIG_LIST

    def get_last_error(self):
        """
        Retrieve the last error message, if any.

        :return: Error string or None
        """
        return self._last_error

    def get_split_ranges(self, text: str, inclusive: bool = False) -> List[Tuple[int, int]]:
        """
        Split the input into ranges of text between delimiters using regex.

        If `inclusive` is True:
            - Each (start, end) range includes the delimiter (like forward mmseg).
        If `inclusive` is False:
            - Each (start, end) range excludes the delimiter.
            - Delimiters are returned as separate (start, end) segments.

        :param text: Input string
        :param inclusive: Whether to include delimiters in the same segment
        :return: List of (start, end) index pairs
        """
        ranges = []
        start = 0
        for match in self.delimiter_regex.finditer(text):
            delim_start, delim_end = match.start(), match.end()
            if inclusive:
                # Include delimiter in the same range
                ranges.append((start, delim_end))
            else:
                # Exclude delimiter from main segment, and add as its own
                if delim_start > start:
                    ranges.append((start, delim_start))
                ranges.append((delim_start, delim_end))
            start = delim_end

        if start < len(text):
            ranges.append((start, len(text)))

        return ranges

    @staticmethod
    def _make_fp(d: dict, maxlen: int) -> tuple:
        """
        Create a cheap, process-local fingerprint for a dictionary.

        The fingerprint is a tuple:
            ("id", id(d), len(d), maxlen)

        Parameters
        ----------
        d : dict
            Dictionary to fingerprint. Must remain immutable after this call
            for the fingerprint to stay valid.
        maxlen : int
            Maximum key length for this dictionary (precomputed).

        Returns
        -------
        tuple
            Process-local fingerprint tuple.
        """
        return "id", id(d), len(d), maxlen

    def _dict_fp(self, dict_tuple: tuple) -> tuple:
        """
        Return a cached fingerprint for a (dict, maxlen) tuple.

        Parameters
        ----------
        dict_tuple : tuple,
            Tuple of (dict, maxlen) as stored in DictionaryMaxlength fields.

        Returns
        -------
        tuple
            Cached fingerprint, or a newly created one if not yet cached.

        Notes
        -----
        - Uses `id(dict)` as the cache key, making the result process-local.
        - Assumes dictionaries are immutable after build; if mutated, the
          fingerprint may be stale.
        """
        d, max_len = dict_tuple
        k = id(d)
        fp = self._fp_cache.get(k)
        if fp is not None:
            return fp
        fp = self._make_fp(d, max_len)
        self._fp_cache[k] = fp
        return fp

    def segment_replace(
            self,
            text: str,
            dictionaries: List[Tuple[Dict[str, str], int]],
            max_word_length: int
    ) -> str:
        """
        Perform dictionary-based greedy replacement on segmented text.

        This method:
          1. Splits the input string into segments based on predefined delimiters.
          2. Applies greedy maximum-length replacement within each segment using
             the provided dictionaries (in precedence order).
          3. Chooses the most efficient conversion path based on available indexes
             and workload size.

        Conversion paths
        ----------------
        * **Indexed fast path** — Used when a `StarterIndex` is available:
            - Merges all dictionaries into a single precedence-ordered map.
            - Uses the `StarterIndex` to skip impossible matches and speed up lookups.
            - Parallelizable with `convert_range_group_indexed`.
        * **Legacy path** — Used when no index is available:
            - Directly applies each dictionary in precedence order to each segment.
            - Parallelizable with `convert_range_group`.

        Parallel execution
        ------------------
        Parallel processing is triggered when:
            - `len(ranges)` > 1,000 **and**
            - `len(text)` ≥ 1,000,000 characters.
        In this case, segments are split into up to 4 groups and processed
        in a multiprocessing pool.

        Parameters
        ----------
        text : str
            The input text to be converted.
        dictionaries : list of (dict, int)
            Sequence of dictionaries and their respective maximum key lengths.
            The order determines replacement precedence (last overrides first).
        max_word_length : int
            Global maximum match length, capped by actual dictionary contents.

        Returns
        -------
        str
            The converted text after all replacements.

        Notes
        -----
        - The indexed fast path is only possible if:
            * A prebuilt `StarterIndex` is present in `self.dictionary` and has
              `global_cap >= max_word_length`, or
            * A new `StarterIndex` can be built from `dictionaries` without error.
        - A per-call `dict_sig` fingerprint is computed to cache merged maps
          and starter indexes for reuse.
        - Falls back to the legacy path if index construction fails.
        - For a single segment equal to the whole text, conversion is done in one
          call without splitting overhead.

        See Also
        --------
        OpenCC.convert_segment_indexed : Indexed segment conversion.
        OpenCC.convert_segment         : Legacy segment conversion.
        StarterIndex.build             : Index construction from dictionaries.
        """
        if not text:
            return text

        # ----- Fast-path prep: merged precedence map + starter index -----
        active_dicts = [d for (d, _m) in dictionaries]
        dict_sig = tuple(self._dict_fp(dict_tuple) for dict_tuple in dictionaries)

        cap_from_dicts = max((maxlen for _, maxlen in dictionaries), default=0)
        global_cap = min(max_word_length, cap_from_dicts) if cap_from_dicts else max_word_length

        fast_key = (dict_sig, global_cap)
        _fast = self._fast_cache.get(fast_key)

        if _fast is None:
            # 1) merged map
            merged_map = self._merged_cache.get(dict_sig)
            if merged_map is None:
                merged_map = merge_in_precedence(active_dicts)
                self._merged_cache[dict_sig] = merged_map

            # 2) starter index
            idx_key = (dict_sig, global_cap)
            starter_idx = self._starter_idx_cache.get(idx_key)
            if starter_idx is None:
                idx = None
                # Try to reuse prebuilt global index if sufficient
                if getattr(self, "dictionary", None):
                    try:
                        idx = self.dictionary.try_get_starter_index()
                        if idx and getattr(idx, "global_cap", 0) < global_cap:
                            idx = None
                    except (TypeError, KeyError, ValueError):
                        idx = None

                if idx is None:
                    try:
                        starter_idx = StarterIndex.build(active_dicts, global_cap)
                    except (TypeError, KeyError, ValueError):
                        starter_idx = None
                else:
                    starter_idx = idx

                self._starter_idx_cache[idx_key] = starter_idx

            _fast = (merged_map, starter_idx, global_cap)
            self._fast_cache[fast_key] = _fast

        merged_map, starter_idx, global_cap = _fast
        fast_ok = starter_idx is not None

        # ----- Split into segments -----
        ranges = self.get_split_ranges(text, inclusive=True)

        # Single segment → straight convert
        if len(ranges) == 1 and ranges[0] == (0, len(text)):
            if fast_ok:
                return OpenCC.convert_segment_indexed(text, merged_map, starter_idx, global_cap)
            else:
                return OpenCC.convert_segment(text, dictionaries, max_word_length)

        # Parallel threshold
        total_length = len(text)
        use_parallel = len(ranges) > 1_000 and total_length >= 1_000_000

        if use_parallel:
            group_count = min(4, max(1, cpu_count()))
            groups = chunk_ranges(ranges, group_count)

            with Pool(processes=group_count) as pool:
                if fast_ok:
                    results = pool.map(
                        convert_range_group_indexed,
                        [(text, group, merged_map, starter_idx, global_cap) for group in groups]
                    )
                else:
                    results = pool.map(
                        convert_range_group,
                        [(text, group, dictionaries, max_word_length, OpenCC.convert_segment) for group in groups]
                    )
            return "".join(results)

        # Serial path
        if fast_ok:
            return "".join(
                OpenCC.convert_segment_indexed(text[s:e], merged_map, starter_idx, global_cap)
                for (s, e) in ranges
            )
        else:
            return "".join(
                OpenCC.convert_segment(text[s:e], dictionaries, max_word_length)
                for (s, e) in ranges
            )

    @staticmethod
    def convert_segment(segment: str, dictionaries, max_word_length: int) -> str:
        """
        Apply dictionary replacements to a text segment using greedy max-length matching.

        :param segment: Text segment to convert
        :param dictionaries: List of (dict, max_length) tuples
        :param max_word_length: Maximum matching word length
        :return: Converted string
        """
        if not segment or (len(segment) == 1 and segment in DELIMITERS):
            return segment

        result = []
        i = 0
        n = len(segment)

        while i < n:
            remaining = n - i
            best_match = None
            best_length = 0

            # Try matches from longest to shortest
            for length in range(min(max_word_length, remaining), 0, -1):
                end = i + length
                word = segment[i:end]

                # Check all dictionaries for this word
                for dict_data, max_len in dictionaries:
                    if max_len < length:
                        continue

                    match = dict_data.get(word)
                    if match is not None:
                        best_match = match
                        best_length = length
                        break

                if best_match:
                    break

            if best_match is not None:
                result.append(best_match)
                i += best_length
            else:
                result.append(segment[i])
                i += 1

        return ''.join(result)

    @staticmethod
    def convert_segment_indexed(
            segment: str,
            merged_map: dict,
            starter_index: StarterIndex,
            global_cap: int
    ) -> str:
        """
        Convert a single text segment using the indexed fast path.

        This method applies greedy maximum-length matching using:
          * A single precedence-merged replacement map (`merged_map`)
          * A `StarterIndex` providing:
              - A per-starter length bitmask
              - A per-starter maximum length (`cap`)
          * The `global_cap` limit, to avoid over-matching beyond configured max length

        Algorithm
        ---------
        1. Skip processing for empty strings or single-character delimiters.
        2. For each character position `i` in the segment:
           a. Look up `(mask, cap)` from the starter index using the current codepoint.
           b. If `mask == 0` or `cap == 0`, append the character as-is and advance 1.
           c. Otherwise:
              - Compute `cap_here = min(remaining_length, cap, global_cap)`
              - Restrict `mask` to lengths ≤ `cap_here`
              - Try lengths from longest to shortest by:
                  * Extracting the substring
                  * Looking it up in `merged_map`
                  * On first match, append replacement, advance `i` by length, break
              - If no match found, append current character and advance 1.
        3. Join and return all collected output parts.

        Parameters
        ----------
        segment : str
            The text segment to convert (no delimiters inside).
        merged_map : dict[str, str]
            Precedence-merged dictionary mapping source strings to replacements.
        starter_index : StarterIndex
            Index providing possible match lengths per starting codepoint.
        global_cap : int
            Global maximum match length (1–64).

        Returns
        -------
        str
            Converted segment with replacements applied.

        Notes
        -----
        - `starter_index` is expected to be built from the same dictionaries that
          produced `merged_map`.
        - This is an O(n) scan with constant-time candidate filtering via bitmask.
        - Bit order in the mask: bit 0 = length 1, bit 1 = length 2, ..., bit 63 = length 64.
        - Falls back to character-by-character copying if no possible matches.
        """
        # Fast skip for trivial cases
        if not segment or (len(segment) == 1 and segment in DELIMITERS):
            return segment

        get = merged_map.get
        seg = segment
        out = []
        i, n = 0, len(seg)

        while i < n:
            cp0 = ord(seg[i])
            mask, cap = starter_index.get_mask_cap(cp0)
            if mask == 0 or cap == 0:
                out.append(seg[i])
                i += 1
                continue

            rem = n - i
            cap_here = min(rem, cap, global_cap)

            # Restrict mask to feasible lengths only
            m = mask & ((1 << cap_here) - 1)
            matched = False
            while m:
                # Highest set bit index = longest candidate length
                L = m.bit_length()
                s = seg[i:i + L]
                repl = get(s)
                if repl is not None:
                    out.append(repl)
                    i += L
                    matched = True
                    break
                # Clear the bit for length L and try shorter
                m &= (1 << (L - 1)) - 1

            if not matched:
                out.append(seg[i])
                i += 1

        return "".join(out)

    def _get_dict_refs(self, config_key: str) -> Optional[DictRefs]:
        """Get cached DictRefs for a config to avoid recreation"""
        if config_key in self._config_cache:
            return self._config_cache[config_key]

        refs = None
        d = self.dictionary

        if config_key == "s2t":
            refs = DictRefs([d.st_phrases, d.st_characters])
        elif config_key == "t2s":
            refs = DictRefs([d.ts_phrases, d.ts_characters])
        elif config_key == "s2tw":
            refs = (DictRefs([d.st_phrases, d.st_characters])
                    .with_round_2([d.tw_variants]))
        elif config_key == "tw2s":
            refs = (DictRefs([d.tw_variants_rev_phrases, d.tw_variants_rev])
                    .with_round_2([d.ts_phrases, d.ts_characters]))
        elif config_key == "s2twp":
            refs = (DictRefs([d.st_phrases, d.st_characters])
                    .with_round_2([d.tw_phrases])
                    .with_round_3([d.tw_variants]))
        elif config_key == "tw2sp":
            refs = (DictRefs([d.tw_phrases_rev, d.tw_variants_rev_phrases, d.tw_variants_rev])
                    .with_round_2([d.ts_phrases, d.ts_characters]))
        elif config_key == "s2hk":
            refs = (DictRefs([d.st_phrases, d.st_characters])
                    .with_round_2([d.hk_variants]))
        elif config_key == "hk2s":
            refs = (DictRefs([d.hk_variants_rev_phrases, d.hk_variants_rev])
                    .with_round_2([d.ts_phrases, d.ts_characters]))

        # ------------ Newly added configs ------------
        elif config_key == "t2tw":
            # Traditional → Taiwan standard (variants only)
            refs = DictRefs([d.tw_variants])
        elif config_key == "t2twp":
            # Traditional → Taiwan standard with phrases
            refs = (DictRefs([d.tw_phrases])
                    .with_round_2([d.tw_variants]))
        elif config_key == "tw2t":
            # Taiwan standard → Generic Traditional (reverse)
            refs = DictRefs([d.tw_variants_rev_phrases, d.tw_variants_rev])
        elif config_key == "tw2tp":
            # Taiwan standard → Generic Traditional with phrase reverse
            refs = (DictRefs([d.tw_variants_rev_phrases, d.tw_variants_rev])
                    .with_round_2([d.tw_phrases_rev]))
        elif config_key == "t2hk":
            # Traditional → Hong Kong standard
            refs = DictRefs([d.hk_variants])
        elif config_key == "hk2t":
            # Hong Kong standard → Generic Traditional (reverse)
            refs = DictRefs([d.hk_variants_rev_phrases, d.hk_variants_rev])
        elif config_key == "t2jp":
            # Traditional → Japanese forms (Shinjitai + JP variants)
            refs = DictRefs([d.jp_variants])
        elif config_key == "jp2t":
            # Japanese Shinjitai → Traditional
            refs = DictRefs([d.jps_phrases, d.jps_characters, d.jp_variants_rev])

        if refs:
            self._config_cache[config_key] = refs
        return refs

    @staticmethod
    def _convert_punctuation_legacy(text, punct_map):
        """
        (Fallback punctuation conversion for older Python versions)
        Convert between Simplified and Traditional punctuation styles.

        :param text: Input text
        :param punct_map: Conversion punctuation map
        :return: Text with punctuation converted
        """
        result = []
        for char in text:
            result.append(punct_map.get(char, char))
        return ''.join(result)

    def s2t(self, input_text, punctuation=False):
        """
        Convert Simplified Chinese to Traditional Chinese.

        :param input_text: The source string in Simplified Chinese
        :param punctuation: Whether to convert punctuation
        :return: Transformed string in Traditional Chinese
        """
        refs = self._get_dict_refs("s2t")
        output = refs.apply_segment_replace(input_text, self.segment_replace)

        if punctuation:
            if HAS_MAKETRANS:
                return output.translate(PUNCT_S2T_MAP)
            else:
                return self._convert_punctuation_legacy(output, PUNCT_S2T_MAP)
        return output

    def t2s(self, input_text, punctuation=False):
        """
        Convert Traditional Chinese to Simplified Chinese.

        :param input_text: The source string in Traditional Chinese
        :param punctuation: Whether to convert punctuation
        :return: Transformed string in Simplified Chinese
        """
        refs = self._get_dict_refs("t2s")
        output = refs.apply_segment_replace(input_text, self.segment_replace)

        if punctuation:
            if HAS_MAKETRANS:
                return output.translate(PUNCT_T2S_MAP)
            else:
                return self._convert_punctuation_legacy(output, PUNCT_T2S_MAP)
        return output

    def s2tw(self, input_text, punctuation=False):
        """
        Convert Simplified Chinese to Traditional Chinese (Taiwan Standard).

        :param input_text: The source string
        :param punctuation: Whether to convert punctuation
        :return: Transformed string in Taiwan Traditional Chinese
        """
        refs = self._get_dict_refs("s2tw")
        output = refs.apply_segment_replace(input_text, self.segment_replace)

        if punctuation:
            if HAS_MAKETRANS:
                return output.translate(PUNCT_S2T_MAP)
            else:
                return self._convert_punctuation_legacy(output, PUNCT_S2T_MAP)
        return output

    def tw2s(self, input_text, punctuation=False):
        """
        Convert Traditional Chinese (Taiwan) to Simplified Chinese.

        :param input_text: The source string in Taiwan Traditional Chinese
        :param punctuation: Whether to convert punctuation
        :return: Transformed string in Simplified Chinese
        """
        refs = self._get_dict_refs("tw2s")
        output = refs.apply_segment_replace(input_text, self.segment_replace)

        if punctuation:
            if HAS_MAKETRANS:
                return output.translate(PUNCT_T2S_MAP)
            else:
                return self._convert_punctuation_legacy(output, PUNCT_T2S_MAP)
        return output

    def s2twp(self, input_text, punctuation=False):
        """
        Convert Simplified Chinese to Traditional (Taiwan) using phrases + variants.

        :param input_text: The source string
        :param punctuation: Whether to convert punctuation
        :return: Transformed string
        """
        refs = self._get_dict_refs("s2twp")
        output = refs.apply_segment_replace(input_text, self.segment_replace)

        if punctuation:
            if HAS_MAKETRANS:
                return output.translate(PUNCT_S2T_MAP)
            else:
                return self._convert_punctuation_legacy(output, PUNCT_S2T_MAP)
        return output

    def tw2sp(self, input_text, punctuation=False):
        """
        Convert Traditional (Taiwan) with phrases to Simplified Chinese.

        :param input_text: The source string
        :param punctuation: Whether to convert punctuation
        :return: Transformed string
        """
        refs = self._get_dict_refs("tw2sp")
        output = refs.apply_segment_replace(input_text, self.segment_replace)

        if punctuation:
            if HAS_MAKETRANS:
                return output.translate(PUNCT_T2S_MAP)
            else:
                return self._convert_punctuation_legacy(output, PUNCT_T2S_MAP)
        return output

    def s2hk(self, input_text, punctuation=False):
        """
        Convert Simplified Chinese to Traditional (Hong Kong Standard).

        :param input_text: Simplified Chinese input
        :param punctuation: Whether to convert punctuation
        :return: Transformed string
        """
        refs = self._get_dict_refs("s2hk")
        output = refs.apply_segment_replace(input_text, self.segment_replace)

        if punctuation:
            if HAS_MAKETRANS:
                return output.translate(PUNCT_S2T_MAP)
            else:
                return self._convert_punctuation_legacy(output, PUNCT_S2T_MAP)
        return output

    def hk2s(self, input_text, punctuation=False):
        """
        Convert Traditional (Hong Kong) to Simplified Chinese.

        :param input_text: Hong Kong Traditional Chinese input
        :param punctuation: Whether to convert punctuation
        :return: Simplified Chinese output
        """
        refs = self._get_dict_refs("hk2s")
        output = refs.apply_segment_replace(input_text, self.segment_replace)

        if punctuation:
            if HAS_MAKETRANS:
                return output.translate(PUNCT_T2S_MAP)
            else:
                return self._convert_punctuation_legacy(output, PUNCT_T2S_MAP)
        return output

    def t2tw(self, input_text: str) -> str:
        """
        Convert Traditional Chinese to Taiwan Standard Traditional Chinese.
        """
        refs = self._get_dict_refs("t2tw")
        return refs.apply_segment_replace(input_text, self.segment_replace)

    def t2twp(self, input_text: str) -> str:
        """
        Convert Traditional Chinese to Taiwan Standard using phrase and variant mappings.
        """
        refs = self._get_dict_refs("t2twp")
        return refs.apply_segment_replace(input_text, self.segment_replace)

    def tw2t(self, input_text: str) -> str:
        """
        Convert Taiwan Traditional to general Traditional Chinese.
        """
        refs = self._get_dict_refs("tw2t")
        return refs.apply_segment_replace(input_text, self.segment_replace)

    def tw2tp(self, input_text: str) -> str:
        """
        Convert Taiwan Traditional to Traditional with phrase reversal.
        """
        refs = self._get_dict_refs("tw2tp")
        return refs.apply_segment_replace(input_text, self.segment_replace)

    def t2hk(self, input_text: str) -> str:
        """
        Convert Traditional Chinese to Hong Kong variant.
        """
        refs = self._get_dict_refs("t2hk")
        return refs.apply_segment_replace(input_text, self.segment_replace)

    def hk2t(self, input_text: str) -> str:
        """
        Convert Hong Kong Traditional to standard Traditional Chinese.
        """
        refs = self._get_dict_refs("hk2t")
        return refs.apply_segment_replace(input_text, self.segment_replace)

    def t2jp(self, input_text: str) -> str:
        """
        Convert japanese Kyujitai  to Japanese Shinjitai.
        """
        refs = self._get_dict_refs("t2jp")
        return refs.apply_segment_replace(input_text, self.segment_replace)

    def jp2t(self, input_text: str) -> str:
        """
        Convert Japanese Shinjitai (modern Kanji) to Kyujitai.
        """
        refs = self._get_dict_refs("jp2t")
        return refs.apply_segment_replace(input_text, self.segment_replace)

    def convert(self, input_text: str, punctuation: bool = False) -> str:
        """
        Automatically dispatch to the appropriate conversion method based on `self.config`.

        :param input_text: The string to convert
        :param punctuation: Whether to apply punctuation conversion
        :return: Converted string or error message
        """
        if not input_text:
            self._last_error = "Input text is empty"
            return ""

        config = self.config.lower()
        try:
            if config == "s2t":
                return self.s2t(input_text, punctuation)
            elif config == "s2tw":
                return self.s2tw(input_text, punctuation)
            elif config == "s2twp":
                return self.s2twp(input_text, punctuation)
            elif config == "s2hk":
                return self.s2hk(input_text, punctuation)
            elif config == "t2s":
                return self.t2s(input_text, punctuation)
            elif config == "t2tw":
                return self.t2tw(input_text)
            elif config == "t2twp":
                return self.t2twp(input_text)
            elif config == "t2hk":
                return self.t2hk(input_text)
            elif config == "tw2s":
                return self.tw2s(input_text, punctuation)
            elif config == "tw2sp":
                return self.tw2sp(input_text, punctuation)
            elif config == "tw2t":
                return self.tw2t(input_text)
            elif config == "tw2tp":
                return self.tw2tp(input_text)
            elif config == "hk2s":
                return self.hk2s(input_text, punctuation)
            elif config == "hk2t":
                return self.hk2t(input_text)
            elif config == "jp2t":
                return self.jp2t(input_text)
            elif config == "t2jp":
                return self.t2jp(input_text)
            else:
                self._last_error = f"Invalid config: {config}"
                return self._last_error
        except Exception as e:
            self._last_error = f"Conversion failed: {e}"
            return self._last_error

    def st(self, input_text: str) -> str:
        """
        Convert Simplified Chinese characters only (no phrases).
        """
        if not input_text:
            return input_text

        dict_data = [self.dictionary.st_characters]
        # return self.convert_segment(input_text, dict_data, 1)
        return self.convert_segment(input_text, dict_data, 1)

    def ts(self, input_text: str) -> str:
        """
        Convert Traditional Chinese characters only (no phrases).
        """
        if not input_text:
            return input_text

        dict_data = [self.dictionary.ts_characters]
        return self.convert_segment(input_text, dict_data, 1)

    def zho_check(self, input_text: str) -> int:
        """
        Heuristically determine whether input text is Simplified or Traditional Chinese.

        :param input_text: Input string
        :return: 0 = unknown, 1 = traditional, 2 = simplified
        """
        if not input_text:
            return 0

        stripped = STRIP_REGEX.sub("", input_text)
        strip_text = stripped[:100]

        if strip_text != self.ts(strip_text):
            return 1
        elif strip_text != self.st(strip_text):
            return 2
        else:
            return 0


def chunk_ranges(ranges: List[Tuple[int, int]], group_count: int) -> List[List[Tuple[int, int]]]:
    """
    Split a list of (start, end) index ranges into evenly sized chunks.

    This function divides the input list of ranges into approximately equal-sized sublists,
    useful for distributing work across multiple worker processes or threads.

    :param ranges: A list of (start, end) index tuples representing text segments.
    :param group_count: Number of groups to divide the ranges into (typically the number of worker processes).
    :return: A list of range groups, each being a list of (start, end) tuples.
    """
    chunk_size = (len(ranges) + group_count - 1) // group_count
    return [ranges[i:i + chunk_size] for i in range(0, len(ranges), chunk_size)]


def convert_range_group(args):
    """
    Convert a group of text segments using the provided conversion function.

    This function is designed for use with multiprocessing. It processes a group of
    (start, end) index ranges from the original input text, applies the dictionary-based
    segment conversion to each, and joins the results.

    :param args: A tuple containing:
        - text: The original input string.
        - group_ranges: A list of (start, end) index tuples for this group.
        - dictionaries: A list of (dictionary, max_length) tuples.
        - max_word_length: The maximum matching length used for dictionary lookup.
        - convert_segment_fn: A callable function to convert each segment.
    :return: A string representing the converted result for the group.
    """
    text, group_ranges, dictionaries, max_word_length, convert_segment_fn = args
    return ''.join(
        convert_segment_fn(text[start:end], dictionaries, max_word_length)
        for start, end in group_ranges
    )


def convert_range_group_indexed(args: Tuple[
    str,  # text
    Iterable[Tuple[int, int]],  # group of (start, end)
    Mapping[str, str],  # merged_map
    "StarterIndex",  # starter_index
    int  # global_cap
]) -> str:
    """
    Convert one group of (start, end) ranges using the indexed fast path.

    Parameters
    ----------
    args : tuple
        (text, group, merged_map, starter_index, global_cap)
        - text: The full input text.
        - group: Iterable of (start, end) indices into `text` for this worker.
        - merged_map: Precedence-merged replacement map (str -> str).
        - starter_index: StarterIndex instance for fast prefix pruning.
        - global_cap: Maximum phrase length (capped to the index's global cap).

    Returns
    -------
    str
        Concatenated converted text for all ranges in `group`, in order.

    Notes
    -----
    - This function is intended to be executed in a worker process.
    - `starter_index` must be pickleable to cross process boundaries; if it isn't,
      pass its serialized blob and rebuild it in the worker.
    """
    text, group, merged_map, starter_index, global_cap = args

    # Local binds to avoid repeated global lookups in tight loops
    convert_seg = OpenCC.convert_segment_indexed
    append: List[str] = []
    a = append.append
    for s, e in group:
        a(convert_seg(text[s:e], merged_map, starter_index, global_cap))
    return "".join(append)
