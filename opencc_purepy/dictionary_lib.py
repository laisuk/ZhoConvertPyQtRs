from pathlib import Path
from typing import Dict, Tuple, Optional
from .starter_index import StarterIndex, unpack_index_blob


class DictionaryMaxlength:
    """
    A container for OpenCC-compatible dictionaries with each represented
    as a (dict, max_length) tuple to optimize the longest match lookup.
    """

    def __init__(self):
        """
        Initialize all supported dictionary attributes to empty dicts with max_length = 0.
        """
        self.st_characters: Tuple[Dict[str, str], int] = ({}, 0)
        self.st_phrases: Tuple[Dict[str, str], int] = ({}, 0)
        self.ts_characters: Tuple[Dict[str, str], int] = ({}, 0)
        self.ts_phrases: Tuple[Dict[str, str], int] = ({}, 0)
        self.tw_phrases: Tuple[Dict[str, str], int] = ({}, 0)
        self.tw_phrases_rev: Tuple[Dict[str, str], int] = ({}, 0)
        self.tw_variants: Tuple[Dict[str, str], int] = ({}, 0)
        self.tw_variants_rev: Tuple[Dict[str, str], int] = ({}, 0)
        self.tw_variants_rev_phrases: Tuple[Dict[str, str], int] = ({}, 0)
        self.hk_variants: Tuple[Dict[str, str], int] = ({}, 0)
        self.hk_variants_rev: Tuple[Dict[str, str], int] = ({}, 0)
        self.hk_variants_rev_phrases: Tuple[Dict[str, str], int] = ({}, 0)
        self.jps_characters: Tuple[Dict[str, str], int] = ({}, 0)
        self.jps_phrases: Tuple[Dict[str, str], int] = ({}, 0)
        self.jp_variants: Tuple[Dict[str, str], int] = ({}, 0)
        self.jp_variants_rev: Tuple[Dict[str, str], int] = ({}, 0)
        # Starter index (public key in JSON is 'starter_index'; private in-memory attr here)
        self._starter_index_blob: Optional[dict] = None
        self._starter_index_cache: Optional["StarterIndex"] = None  # unpacked cache

    def __repr__(self):
        count = sum(bool(v[0]) for v in self.__dict__.values())
        return "<DictionaryMaxlength with {} loaded dicts>".format(count)

    @classmethod
    def new(cls):
        """
        Shortcut to load from precompiled JSON for fast startup.
        :return: DictionaryMaxlength instance
        """
        return cls.from_json()

    @staticmethod
    def _as_tuple(value):
        """
        Normalize a JSON field into the internal (dict, max_length) tuple.

        Accepts either:
          - [ { ...map... }, max_length ]
          - { "map": { ... }, "maxlength": max_length }

        Returns: (dict, int) or ({}, 0) if unrecognized.
        """
        # list/tuple form
        if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], dict):
            return value[0], int(value[1])
        # object form
        if isinstance(value, dict) and "map" in value and "maxlength" in value:
            return value["map"], int(value["maxlength"])
        # fallback
        return {}, 0

    @classmethod
    def from_json(cls):
        """
        Load dictionary data from JSON, tolerant to multiple shapes:
        - Each dict field can be [map, max_length] OR {"map": ..., "maxlength": ...}.
        - Unknown/non-dictionary keys (e.g., 'starter_index', 'version') are ignored.
        """
        import json

        path = Path(__file__).parent / "dicts" / "dictionary_maxlength.json"
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # keep optional starter index blob (if present)
        starter_blob = raw_data.get("starter_index") if isinstance(raw_data, dict) else None

        instance = cls()

        # Only populate known dictionary fields; ignore extras in the JSON.
        field_names = [
            "st_characters", "st_phrases",
            "ts_characters", "ts_phrases",
            "tw_phrases", "tw_phrases_rev",
            "tw_variants", "tw_variants_rev", "tw_variants_rev_phrases",
            "hk_variants", "hk_variants_rev", "hk_variants_rev_phrases",
            "jps_characters", "jps_phrases",
            "jp_variants", "jp_variants_rev",
        ]

        for name in field_names:
            if name in raw_data:
                setattr(instance, name, cls._as_tuple(raw_data[name]))
            # else: keep constructor default ({}, 0)

        if starter_blob is not None:
            try:
                instance._starter_index_blob = starter_blob
            except (TypeError, KeyError, ValueError):  # narrow, expected failures
                # non-fatal: leave index to be rebuilt lazily if needed
                pass

        return instance

    @classmethod
    def from_dicts(cls):
        """
        Load dictionaries directly from text files in the 'dicts' folder.
        Each file should contain tab-separated mappings.
        :return: Populated DictionaryMaxlength instance
        """
        instance = cls()
        paths = {
            'st_characters': "STCharacters.txt",
            'st_phrases': "STPhrases.txt",
            'ts_characters': "TSCharacters.txt",
            'ts_phrases': "TSPhrases.txt",
            'tw_phrases': "TWPhrases.txt",
            'tw_phrases_rev': "TWPhrasesRev.txt",
            'tw_variants': "TWVariants.txt",
            'tw_variants_rev': "TWVariantsRev.txt",
            'tw_variants_rev_phrases': "TWVariantsRevPhrases.txt",
            'hk_variants': "HKVariants.txt",
            'hk_variants_rev': "HKVariantsRev.txt",
            'hk_variants_rev_phrases': "HKVariantsRevPhrases.txt",
            'jps_characters': "JPShinjitaiCharacters.txt",
            'jps_phrases': "JPShinjitaiPhrases.txt",
            'jp_variants': "JPVariants.txt",
            'jp_variants_rev': "JPVariantsRev.txt",
        }

        base = Path(__file__).parent / "dicts"
        for attr, filename in paths.items():
            content = (base / filename).read_text(encoding="utf-8")
            setattr(instance, attr, cls.load_dictionary_maxlength(content))

        return instance

    @staticmethod
    def load_dictionary_maxlength(content: str) -> Tuple[Dict[str, str], int]:
        """
        Load a dictionary from plain text and determine the max phrase length.

        :param content: Raw dictionary text (one mapping per line)
        :return: Tuple of dict and max key length
        """
        dictionary = {}
        max_length = 1

        for line in content.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                phrase, translation = parts[0], parts[1]
                dictionary[phrase] = translation
                max_length = max(max_length, len(phrase))
            else:
                import warnings
                warnings.warn("Ignoring malformed dictionary line: {}".format(line))

        return dictionary, max_length

    def serialize_to_json(self, path: str):
        """
        Serialize the current dictionary set to a stable JSON format.

        The output JSON has a fixed shape for consistency across builds:
          - Each dictionary field is serialized as a two-element array:
                [ {<mapping>}, <max_length:int> ]
            where:
              * The first element is a shallow copy of the mapping.
              * The second element is the maximum key length for that dictionary.
          - If a starter index blob is present (self._starter_index_blob),
            it is added under the public key `"starter_index"`.

        Fields are written in a fixed order to guarantee deterministic output:
            st_characters, st_phrases,
            ts_characters, ts_phrases,
            tw_phrases, tw_phrases_rev,
            tw_variants, tw_variants_rev, tw_variants_rev_phrases,
            hk_variants, hk_variants_rev, hk_variants_rev_phrases,
            jps_characters, jps_phrases,
            jp_variants, jp_variants_rev

        Parameters
        ----------
        path : str
            Filesystem path to write the serialized JSON file.

        Notes
        -----
        - `max_length` values are stored as plain integers.
        - Dictionaries are copied to avoid mutating the originals during serialization.
        - `starter_index` is optional and only included if `_starter_index_blob` exists.
        - Output JSON is compact: no extra whitespace, UTF-8 encoded, non-ASCII
          characters are written as-is (ensure_ascii=False).

        Example output
        --------------
        {
          "st_characters": [ {"你": "妳", "爱": "愛"}, 2 ],
          "st_phrases":    [ {"你好": "您好"}, 2 ],
          ...
          "starter_index": { "schema": 1, "global_cap": 64, ... }
        }
        """
        import json

        def as_array(tup):
            m, L = tup
            return [dict(m), int(L)]

        field_names = [
            "st_characters", "st_phrases",
            "ts_characters", "ts_phrases",
            "tw_phrases", "tw_phrases_rev",
            "tw_variants", "tw_variants_rev", "tw_variants_rev_phrases",
            "hk_variants", "hk_variants_rev", "hk_variants_rev_phrases",
            "jps_characters", "jps_phrases",
            "jp_variants", "jp_variants_rev",
        ]

        out = {name: as_array(getattr(self, name)) for name in field_names}

        blob = getattr(self, "_starter_index_blob", None)
        if blob is not None:
            out["starter_index"] = blob  # public key

        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    def try_get_starter_index(self) -> Optional["StarterIndex"]:
        """
        Retrieve the cached or stored starter index, if available.

        This method attempts to return a `StarterIndex` instance in the following order:
          1. If `_starter_index_cache` is already set, return it immediately.
          2. Otherwise, look for `_starter_index_blob` (serialized form).
             - If absent or empty, return `None`.
             - If present, attempt to deserialize it via `unpack_index_blob()`.
               On success, cache the result in `_starter_index_cache` and return it.
               On failure (TypeError, KeyError, ValueError), return `None`.

        Returns
        -------
        StarterIndex or None
            The deserialized starter index if available and valid, otherwise `None`.

        Notes
        -----
        - This is a lazy accessor; the starter index is only deserialized when first
          requested.
        - Failures are deliberately silenced for expected blob format errors.
        """
        if self._starter_index_cache is not None:
            return self._starter_index_cache
        blob = self._starter_index_blob
        if not blob:
            return None
        try:
            idx = unpack_index_blob(blob)
            self._starter_index_cache = idx
            return idx
        except (TypeError, KeyError, ValueError):  # narrow, expected failures
            return None

    def inject_starter_index(self, idx: "StarterIndex") -> None:
        """
        Store a `StarterIndex` in both serialized and cached form.

        This method takes a fully-built `StarterIndex` instance and:
          1. Serializes it into `_starter_index_blob` via `pack_index_blob()`.
             This ensures it will be included in `serialize_to_json()` output
             under the public key `"starter_index"`.
          2. Stores the original `StarterIndex` instance in `_starter_index_cache`
             for immediate in-memory reuse.

        Parameters
        ----------
        idx : StarterIndex
            The starter index to store.

        Notes
        -----
        - Uses a local import of `pack_index_blob` to avoid circular dependencies.
        - Overwrites any previously stored blob and cache.
        """
        from .starter_index import pack_index_blob  # local import to avoid cycles
        self._starter_index_blob = pack_index_blob(idx)
        self._starter_index_cache = idx
