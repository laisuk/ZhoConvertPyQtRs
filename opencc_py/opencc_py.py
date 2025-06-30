import re
from typing import List, Dict, Tuple
from .dictionary_lib import DictionaryMaxlength

DELIMITERS = set(
    " \t\n\r!\"#$%&'()*+,-./:;<=>?@[\\]^_{}|~＝、。“”‘’『』「」﹁﹂—－（）《》〈〉？！…／＼︒︑︔︓︿﹀︹︺︙︐［﹇］﹈︕︖︰︳︴︽︾︵︶｛︷｝︸﹃﹄【︻】︼　～．，；：")
STRIP_REGEX = re.compile(r"[!-/:-@\[-`{-~\t\n\v\f\r 0-9A-Za-z_]")


class DictRefs:
    def __init__(self, round_1):
        self.round_1 = round_1
        self.round_2 = None
        self.round_3 = None

    def with_round_2(self, round_2):
        self.round_2 = round_2
        return self

    def with_round_3(self, round_3):
        self.round_3 = round_3
        return self

    def apply_segment_replace(self, input_text, segment_replace):
        output = segment_replace(input_text, self.round_1)
        if self.round_2:
            output = segment_replace(output, self.round_2)
        if self.round_3:
            output = segment_replace(output, self.round_3)
        return output


class OpenCC:
    def __init__(self, config=None):
        _config_list = [
            "s2t", "t2s", "s2tw", "tw2s", "s2twp", "tw2sp", "s2hk", "hk2s", "t2tw", "tw2t", "t2twp", "tw2t", "tw2tp",
            "t2hk", "hk2t", "t2jp", "jp2t"
        ]
        self.config = config if config in _config_list else "s2t"
        self._last_error = None
        try:
            self.dictionary = DictionaryMaxlength.new()
            # self.dictionary = DictionaryMaxlength.from_dicts()
            # self.dictionary = DictionaryMaxlength.from_cbor()
            # self.dictionary = DictionaryMaxlength.from_json()
        except Exception as e:
            self._last_error = str(e)  # <- Use thread-safe setter
            self.dictionary = DictionaryMaxlength()

        self.delimiters = DELIMITERS

    def get_last_error(self):
        return self._last_error

    # def segment_replace(self, text: str, dictionaries: List[Tuple[Dict[str, str], int]]) -> str:
    #     max_word_length = max((length for _, length in dictionaries), default=1)
    #     split_chunks = self.split_string_inclusive(text)
    #     return "".join(self.convert_by(chunk, dictionaries, max_word_length) for chunk in split_chunks)

    def segment_replace(self, text: str, dictionaries: List[Tuple[Dict[str, str], int]]) -> str:
        max_word_length = max((length for _, length in dictionaries), default=1)
        ranges = self.get_split_ranges(text)
        return "".join(
            self.convert_by(list(text[start:end]), dictionaries, max_word_length)
            for start, end in ranges
        )

    def convert_by(self, text_chars: List[str], dictionaries, max_word_length: int) -> str:
        if not text_chars:
            return ""

        delimiters = self.delimiters  # Local variable for speed
        if len(text_chars) == 1 and text_chars[0] in delimiters:
            return text_chars[0]

        result = []
        i = 0
        text_chars_len = len(text_chars)
        while i < text_chars_len:
            best_match = None
            best_length = 0
            # Use local variable for dictionaries
            for length in range(min(max_word_length, text_chars_len - i), 0, -1):
                word = "".join(text_chars[i:i + length])
                for d, _ in dictionaries:
                    match = d.get(word)
                    if match is not None:
                        best_match = match
                        best_length = length
                        break
                if best_length:
                    break
            if not best_length:
                best_match = text_chars[i]
                best_length = 1
            result.append(best_match)
            i += best_length
        return "".join(result)

    # def split_string_inclusive(self, text: str) -> List[List[str]]:
    #     chunks = []
    #     current = []
    #     for ch in text:
    #         current.append(ch)
    #         if ch in self.delimiters:
    #             chunks.append(current)
    #             current = []
    #     if current:
    #         chunks.append(current)
    #     return chunks

    def get_split_ranges(self, text: str) -> List[Tuple[int, int]]:
        """
        Returns a list of (start, end) index tuples, where each tuple represents
        the start (inclusive) and end (exclusive) indices of a chunk in the text.
        """
        ranges = []
        start = 0
        for i, ch in enumerate(text):
            if ch in self.delimiters:
                ranges.append((start, i + 1))  # include the delimiter
                start = i + 1
        if start < len(text):
            ranges.append((start, len(text)))
        return ranges

    def s2t(self, input_text: str, punctuation: bool = False) -> str:
        if not input_text:
            self._last_error = "Input text is empty"
            return ""
        refs = DictRefs([
            self.dictionary.st_phrases,
            self.dictionary.st_characters
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return self.convert_punctuation(output, "s") if punctuation else output

    def t2s(self, input_text: str, punctuation: bool = False) -> str:
        refs = DictRefs([
            self.dictionary.ts_phrases,
            self.dictionary.ts_characters
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return self.convert_punctuation(output, "t") if punctuation else output

    def s2tw(self, input_text: str, punctuation: bool = False) -> str:
        refs = DictRefs([
            self.dictionary.st_phrases,
            self.dictionary.st_characters
        ]).with_round_2([
            self.dictionary.tw_variants
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return self.convert_punctuation(output, "s") if punctuation else output

    def tw2s(self, input_text: str, punctuation: bool = False) -> str:
        refs = DictRefs([
            self.dictionary.tw_variants_rev_phrases,
            self.dictionary.tw_variants_rev
        ]).with_round_2([
            self.dictionary.ts_phrases,
            self.dictionary.ts_characters
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return self.convert_punctuation(output, "t") if punctuation else output

    def s2twp(self, input_text: str, punctuation: bool = False) -> str:
        refs = DictRefs([
            self.dictionary.st_phrases,
            self.dictionary.st_characters
        ]).with_round_2([
            self.dictionary.tw_phrases
        ]).with_round_3([
            self.dictionary.tw_variants
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return self.convert_punctuation(output, "s") if punctuation else output

    def tw2sp(self, input_text: str, punctuation: bool = False) -> str:
        refs = DictRefs([
            self.dictionary.tw_phrases_rev,
            self.dictionary.tw_variants_rev_phrases,
            self.dictionary.tw_variants_rev
        ]).with_round_2([
            self.dictionary.ts_phrases,
            self.dictionary.ts_characters
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return self.convert_punctuation(output, "t") if punctuation else output

    def s2hk(self, input_text: str, punctuation: bool = False) -> str:
        refs = DictRefs([
            self.dictionary.st_phrases,
            self.dictionary.st_characters
        ]).with_round_2([
            self.dictionary.hk_variants
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return self.convert_punctuation(output, "s") if punctuation else output

    def hk2s(self, input_text: str, punctuation: bool = False) -> str:
        refs = DictRefs([
            self.dictionary.hk_variants_rev_phrases,
            self.dictionary.hk_variants_rev
        ]).with_round_2([
            self.dictionary.ts_phrases,
            self.dictionary.ts_characters
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return self.convert_punctuation(output, "t") if punctuation else output

    def t2tw(self, input_text: str) -> str:
        refs = DictRefs([
            self.dictionary.tw_variants
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return output

    def t2twp(self, input_text: str) -> str:
        refs = DictRefs([
            self.dictionary.tw_phrases
        ]).with_round_2([
            self.dictionary.tw_variants
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return output

    def tw2t(self, input_text: str) -> str:
        refs = DictRefs([
            self.dictionary.tw_variants_rev_phrases,
            self.dictionary.tw_variants_rev
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return output

    def tw2tp(self, input_text: str) -> str:
        refs = DictRefs([
            self.dictionary.tw_variants_rev_phrases,
            self.dictionary.tw_variants_rev
        ]).with_round_2([
            self.dictionary.tw_phrases_rev
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return output

    def t2hk(self, input_text: str) -> str:
        refs = DictRefs([
            self.dictionary.hk_variants
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return output

    def hk2t(self, input_text: str) -> str:
        refs = DictRefs([
            self.dictionary.hk_variants_rev_phrases,
            self.dictionary.hk_variants_rev
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return output

    def t2jp(self, input_text: str) -> str:
        refs = DictRefs([
            self.dictionary.jp_variants
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return output

    def jp2t(self, input_text: str) -> str:
        refs = DictRefs([
            self.dictionary.jps_phrases,
            self.dictionary.jps_characters,
            self.dictionary.jp_variants_rev
        ])
        output = refs.apply_segment_replace(input_text, self.segment_replace)
        return output

    def convert(self, input_text: str, punctuation: bool = False) -> str:
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
        dict_refs = [self.dictionary.st_characters]
        chars = list(input_text)  # converts str into list of chars
        return self.convert_by(chars, dict_refs, 1)

    def ts(self, input_text: str) -> str:
        dict_refs = [self.dictionary.ts_characters]
        chars = list(input_text)  # converts str into list of chars
        return self.convert_by(chars, dict_refs, 1)

    def zho_check(self, input_text: str) -> int:
        if not input_text:
            return 0

        stripped = STRIP_REGEX.sub("", input_text)
        max_chars = find_max_utf8_length(stripped, 200)
        strip_text = stripped[:max_chars]

        if strip_text != self.ts(strip_text):
            return 1
        elif strip_text != self.st(strip_text):
            return 2
        else:
            return 0

    @staticmethod
    def convert_punctuation(input_text: str, config: str) -> str:
        """
        Convert between Simplified and Traditional punctuation styles.

        :param input_text: Input text
        :param config: 's' for Simplified to Traditional, 't' for Traditional to Simplified
        :return: Text with punctuation converted
        """
        s2t = str.maketrans({
            '“': '「',
            '”': '」',
            '‘': '『',
            '’': '』',
        })

        t2s = str.maketrans({
            '「': '“',
            '」': '”',
            '『': '‘',
            '』': '’',
        })

        if config[0].lower() == 's':
            return input_text.translate(s2t)
        else:
            return input_text.translate(t2s)

def find_max_utf8_length(s: str, max_byte_count: int) -> int:
    encoded = s.encode('utf-8')
    if len(encoded) <= max_byte_count:
        return len(encoded)

    byte_count = max_byte_count
    while byte_count > 0 and (encoded[byte_count] & 0b11000000) == 0b10000000:
        byte_count -= 1
    return byte_count
