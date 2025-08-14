
from typing import Iterable, Mapping, Dict

def merge_in_precedence(dicts: Iterable[Mapping[str, str]]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for d in dicts:
        merged.update(d)
    return merged
