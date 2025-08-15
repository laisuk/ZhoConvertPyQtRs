from dataclasses import dataclass
from typing import Tuple, Dict, Any, Union, List, Optional

from opencc_purepy.starter_union import StarterUnion

DictSlot = Tuple[Dict[str, str], int]
StarterUnion = Any  # type: ignore
RoundInput = Union[
    None,
    DictSlot,
    List[DictSlot],
    StarterUnion,
]


@dataclass
class DictRefs:
    """
    Wrap up to 3 rounds of dictionary application for multi-pass conversion.

    Each round can be:
      - A list of `(dict, max_len)` slots (legacy shape), or
      - A single `(dict, max_len)` slot, or
      - A `StarterUnion` (we'll treat it as one merged slot)

    This keeps `segment_replace(text, dictionaries, max_word_length)` unchanged:
      - `dictionaries` is the list[List[(dict, max_len)]] for that round
      - `max_word_length` is computed from the provided round content
    """
    round_1: RoundInput
    round_2: Optional[RoundInput] = None
    round_3: Optional[RoundInput] = None

    # Cached normalized form: a list of (dictionaries, max_len) per round
    _norm: Optional[List[Tuple[List[DictSlot], int]]] = None

    # ----- Fluent builders -----
    def with_round_2(self, round_2: RoundInput) -> "DictRefs":
        self.round_2 = round_2
        self._norm = None
        return self

    def with_round_3(self, round_3: RoundInput) -> "DictRefs":
        self.round_3 = round_3
        self._norm = None
        return self

    # ----- Normalization -----
    @staticmethod
    def _as_slots_and_cap(inp: RoundInput) -> Tuple[List[DictSlot], int]:
        """
        Normalize a round input into (list_of_slots, max_len).
        """
        if inp is None:
            return [], 0

        # StarterUnion -> single merged slot
        if "StarterUnion" in str(type(inp)):
            u = inp  # type: ignore
            # If caller wants masks/caps, they should have built them already.
            return [(u.merged_map, int(u.cap))], int(u.cap)

        # Single (dict, max_len) slot
        if isinstance(inp, tuple) and len(inp) == 2 and isinstance(inp[0], dict):
            d, L = inp
            return [(d, int(L))], int(L)

        # List of slots
        if isinstance(inp, list):
            slots: List[DictSlot] = []
            max_len = 0
            for item in inp:
                if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], dict):
                    d, L = item
                    L = int(L)
                    slots.append((d, L))
                    if L > max_len:
                        max_len = L
                else:
                    raise TypeError(f"Round list contains non-slot entry: {type(item)}")
            return slots, max_len

        raise TypeError(f"Unsupported round input type: {type(inp)}")

    def _normalize(self) -> List[Tuple[List[DictSlot], int]]:
        if self._norm is not None:
            return self._norm
        rounds = [self.round_1, self.round_2, self.round_3]
        norm: List[Tuple[List[DictSlot], int]] = []
        for r in rounds:
            slots, cap = self._as_slots_and_cap(r)
            norm.append((slots, cap))
        self._norm = norm
        return norm

    # ----- Application -----
    def apply_segment_replace(self, input_text: str, segment_replace) -> str:
        """
        Apply segment-based replacement across up to three rounds.

        Parameters
        ----------
        input_text : str
            The string to transform.
        segment_replace : callable
            Signature: segment_replace(text: str, dictionaries: List[DictSlot], max_word_length: int) -> str
        """
        (r1_slots, r1_cap), (r2_slots, r2_cap), (r3_slots, r3_cap) = self._normalize()

        output = segment_replace(input_text, r1_slots, r1_cap)
        if r2_slots:
            output = segment_replace(output, r2_slots, r2_cap)
        if r3_slots:
            output = segment_replace(output, r3_slots, r3_cap)
        return output

    def apply_union_replace(self, input_text: str, segment_replace_union) -> str:
        """
        Apply up to 3 rounds using StarterUnion fast path.
        If a round is not a StarterUnion, it is merged into one on the fly.
        """
        # local import to avoid cycles if any
        # try:
        #     from .starter_union import StarterUnion
        # except Exception:
        #     StarterUnion = None  # type: ignore

        text = input_text
        for r in (self.round_1, self.round_2, self.round_3):
            if not r:
                continue
            # Already a union?
            if StarterUnion is not None and "StarterUnion" in str(type(r)):
                u = r
            else:
                # Normalize legacy inputs to a single union
                slots, cap = self._as_slots_and_cap(r)
                u = StarterUnion.merge_precedence(slots)  # type: ignore
            # Ensure masks/caps exist (no-op if already built)
            if not getattr(u, "_indexed", False):
                u.build_starter_index()
            text = segment_replace_union(text, u)
        return text
