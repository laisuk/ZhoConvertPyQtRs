from array import array
from typing import Dict, Iterable, Mapping, Tuple
import base64, struct, io

Mask64 = int


class StarterIndex:
    """
    An index structure mapping the *first character* (starter) of dictionary keys
    to a bitmask of possible match lengths and the maximum match length observed.

    This enables O(1) lookups to quickly rule out impossible matches in a
    greedy maximum-length replacement algorithm.

    Attributes
    ----------
    bmp_mask : array('Q')
        Bitmask per BMP (Basic Multilingual Plane) codepoint, where bit (L-1) is set if
        a dictionary entry of length L starts with that codepoint.
    bmp_cap : array('H')
        Maximum starting length (UTF-16 units) for each BMP codepoint.
    astral_mask : dict[int, Mask64]
        Bitmask for astral-plane starters (codepoints > 0xFFFF).
    astral_cap : dict[int, int]
        Maximum starting length for astral-plane starters.
    global_cap : int
        Maximum match length allowed for any starter, capped at 64.
    """

    __slots__ = ("bmp_mask", "bmp_cap", "astral_mask", "astral_cap", "global_cap")

    def __init__(self, global_cap: int = 64):
        """
        Initialize an empty starter index.

        Parameters
        ----------
        global_cap : int, optional
            Global maximum match length. Values are clamped to [1, 64].
        """
        self.bmp_mask = array("Q", [0] * 0x10000)
        self.bmp_cap = array("H", [0] * 0x10000)
        self.astral_mask: Dict[int, Mask64] = {}
        self.astral_cap: Dict[int, int] = {}
        self.global_cap = min(max(1, global_cap), 64)

    @staticmethod
    def _bit(L: int) -> Mask64:
        """
        Compute the bit position for a given match length.

        Parameters
        ----------
        L : int
            Match length in UTF-16 units (1-based).

        Returns
        -------
        int
            Mask with the (L-1)-th bit set.
        """
        return 1 << (L - 1)

    def _mark(self, cp: int, L: int) -> None:
        """
        Record a dictionary entry's starting codepoint and length in the index.

        Parameters
        ----------
        cp : int
            Unicode codepoint of the entry's first character.
        L : int
            Length of the entry in UTF-16 units.
        """
        if not (1 <= L <= self.global_cap):
            return
        b = self._bit(L)
        if 0 <= cp <= 0xFFFF:
            self.bmp_mask[cp] |= b
            if L > self.bmp_cap[cp]:
                self.bmp_cap[cp] = L
        else:
            self.astral_mask[cp] = self.astral_mask.get(cp, 0) | b
            if L > self.astral_cap.get(cp, 0):
                self.astral_cap[cp] = L

    @classmethod
    def build(cls, dicts: Iterable[Mapping[str, str]], global_cap: int) -> "StarterIndex":
        """
        Construct a starter index from one or more dictionaries.

        Parameters
        ----------
        dicts : iterable of mapping
            Iterable of dictionaries whose keys are candidate phrases.
        global_cap : int
            Global maximum match length, capped at 64.

        Returns
        -------
        StarterIndex
            Populated index ready for lookups.
        """
        idx = cls(global_cap=min(global_cap, 64))
        for d in dicts:
            for k in d.keys():
                if not k:
                    continue
                idx._mark(ord(k[0]), len(k))
        return idx

    def get_mask_cap(self, cp: int) -> Tuple[Mask64, int]:
        """
        Get the bitmask and max length for a given starter codepoint.

        Parameters
        ----------
        cp : int
            Unicode codepoint.

        Returns
        -------
        tuple
            (mask, cap) where:
            - mask: 64-bit integer with bits representing possible match lengths
            - cap:  maximum match length for this starter
        """
        if 0 <= cp <= 0xFFFF:
            return int(self.bmp_mask[cp]), int(self.bmp_cap[cp])
        return int(self.astral_mask.get(cp, 0)), int(self.astral_cap.get(cp, 0))


def _pack_base64_Q(arr: array) -> str:
    """Pack an array('Q') into base64 (little-endian)."""
    buf = io.BytesIO()
    buf.write(struct.pack("<" + "Q" * len(arr), *arr))
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _pack_base64_H(arr: array) -> str:
    """Pack an array('H') into base64 (little-endian)."""
    buf = io.BytesIO()
    buf.write(struct.pack("<" + "H" * len(arr), *arr))
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _unpack_base64_Q(b64: str) -> array:
    """Unpack a base64 string into array('Q') (little-endian)."""
    raw = base64.b64decode(b64)
    count = len(raw) // 8
    vals = struct.unpack("<" + "Q" * count, raw)
    return array("Q", vals)


def _unpack_base64_H(b64: str) -> array:
    """Unpack a base64 string into array('H') (little-endian)."""
    raw = base64.b64decode(b64)
    count = len(raw) // 2
    vals = struct.unpack("<" + "H" * count, raw)
    return array("H", vals)


def pack_index_blob(idx: StarterIndex) -> dict:
    """
    Serialize a StarterIndex into a JSON-friendly dict.

    Parameters
    ----------
    idx : StarterIndex
        The index to serialize.

    Returns
    -------
    dict
        Dictionary containing packed arrays and metadata.
    """
    return {
        "schema": 1,
        "global_cap": idx.global_cap,
        "bmp_mask": _pack_base64_Q(idx.bmp_mask),
        "bmp_cap": _pack_base64_H(idx.bmp_cap),
        "astral_mask": {str(cp): int(m) for cp, m in idx.astral_mask.items()},
        "astral_cap": {str(cp): int(c) for cp, c in idx.astral_cap.items()},
    }


def unpack_index_blob(blob: dict) -> StarterIndex:
    """
    Deserialize a JSON-friendly dict into a StarterIndex.

    Parameters
    ----------
    blob : dict
        Dictionary in the format produced by pack_index_blob().

    Returns
    -------
    StarterIndex
        Reconstructed index object.
    """
    idx = StarterIndex(global_cap=int(blob["global_cap"]))
    idx.bmp_mask = _unpack_base64_Q(blob["bmp_mask"])
    idx.bmp_cap = _unpack_base64_H(blob["bmp_cap"])
    idx.astral_mask = {int(k): int(v) for k, v in blob.get("astral_mask", {}).items()}
    idx.astral_cap = {int(k): int(v) for k, v in blob.get("astral_cap", {}).items()}
    return idx
