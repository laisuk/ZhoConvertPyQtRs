from typing import Iterable, Mapping, Dict

def merge_in_precedence(dicts: Iterable[Mapping[str, str]]) -> Dict[str, str]:
    """
    Merge multiple dictionaries into one, respecting the order of precedence.

    Later dictionaries in the iterable override keys from earlier dictionaries.

    Parameters
    ----------
    dicts : iterable of mapping
        An iterable of dictionaries or mappings to merge.
        The first dictionary has the lowest precedence, the last has the highest.

    Returns
    -------
    dict
        A new dictionary containing all key-value pairs from `dicts`, with
        later dictionaries' entries overwriting earlier ones when keys collide.

    Examples
    --------
    >>> merge_in_precedence([{"a": "x"}, {"b": "y"}, {"a": "z"}])
    {'a': 'z', 'b': 'y'}

    Notes
    -----
    This is commonly used in dictionary-based text conversion to apply
    multiple replacement dictionaries in a fixed order, ensuring that
    higher-precedence mappings take effect last.
    """
    merged: Dict[str, str] = {}
    for d in dicts:
        merged.update(d)
    return merged
