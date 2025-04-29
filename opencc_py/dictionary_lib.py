from pathlib import Path
from typing import Dict, Tuple
import cbor2
import zstandard as zstd


class DictionaryMaxlength:
    def __init__(self):
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

    @classmethod
    def new(cls):
        return cls.from_zstd()

    @classmethod
    def from_zstd(cls):
        path = Path(__file__).parent / "dicts" / "dictionary_maxlength.zstd"
        with open(path, "rb") as f:
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(f.read())
        data = cbor2.loads(decompressed)
        instance = cls()
        instance.__dict__.update(data)
        return instance

    @classmethod
    def from_cbor(cls):
        path = Path(__file__).parent / "dicts" / "dictionary_maxlength.cbor"
        with open(path, "rb") as f:
            data = cbor2.load(f)
        instance = cls()
        instance.__dict__.update(data)
        return instance

    @classmethod
    def from_json(cls):
        import json
        path = Path(__file__).parent / "dicts" / "dictionary_maxlength.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        instance = cls()
        instance.__dict__.update(data)
        return instance

    @classmethod
    def from_dicts(cls):
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
        dictionary = {}
        max_length = 1

        for line in content.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                phrase, translation = parts[0], parts[1]
                dictionary[phrase] = translation
                max_length = max(max_length, len(phrase))
            else:
                print(f"Invalid line format: {line}")

        return dictionary, max_length

    def serialize_to_cbor(self, path: str):
        with open(path, "wb") as f:
            cbor2.dump(self.__dict__, f)

    @classmethod
    def deserialize_from_cbor(cls, path: str):
        with open(path, "rb") as f:
            data = cbor2.load(f)
        instance = cls()
        instance.__dict__.update(data)
        return instance

    def save_compressed(self, path: str):
        cbor_data = cbor2.dumps(self.__dict__)
        with open(path, "wb") as f:
            cctx = zstd.ZstdCompressor(level=19)
            f.write(cctx.compress(cbor_data))

    @classmethod
    def load_compressed(cls, path: str):
        with open(path, "rb") as f:
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(f.read())
        data = cbor2.loads(decompressed)
        instance = cls()  # Create an instance of the class
        instance.__dict__.update(data)  # Update instance with the loaded data
        return instance

    def serialize_to_json(self, path: str):
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)
