
# Starter Index Integration Patch (opencc_purepy v1.2.0-pre)

This folder adds:
- `starter_index.py` — builds and (de)serializes the per-starter length mask + cap (Base64-packed BMP arrays).
- `merge_dicts.py` — merges dictionaries in precedence into a single mapping for O(1) lookups.
- `dictionary_lib.py` — minimally extended to **embed** and **load** an optional `starter_index` blob inside `dicts/dictionary_maxlength.json`.

Your existing runtime is unchanged. To enable the fast path, make the TWO edits below in `core.py`.

---

## 1) Imports (top of `core.py`)

Add after `from .dictionary_lib import DictionaryMaxlength`:

```python
from .starter_index import StarterIndex
from .merge_dicts import merge_in_precedence
```

## 2) Fast path in `OpenCC.segment_replace`

Right **before** this line:

```python
ranges = self.get_split_ranges(text, inclusive=False)
```

insert this block:

```python
# Prepare fast path (merged map + starter index)
try:
    active_dicts = [d for (d, _m) in dictionaries]
    merged_map = merge_in_precedence(active_dicts)
    global_cap = max((len(k) for d in active_dicts for k in d.keys()), default=max_word_length)
    idx = self.dictionary.try_get_starter_index() if hasattr(self, 'dictionary') else None
    if idx is None or idx.global_cap < global_cap:
        idx = StarterIndex.build(active_dicts, global_cap)
    _fast = (merged_map, idx, global_cap)
except Exception:
    _fast = None
```

Then replace the three occurrences of the legacy call:

- **Single-range fast return**

Replace:
```python
return OpenCC.convert_segment(text, dictionaries, max_word_length)
```
with:
```python
return (OpenCC.convert_segment_indexed(text, _fast[0], _fast[1], _fast[2])
        if _fast else OpenCC.convert_segment(text, dictionaries, max_word_length))
```

- **Serial branch inside `else`**

Replace:
```python
OpenCC.convert_segment(text[start:end], dictionaries, max_word_length)
```
with:
```python
(OpenCC.convert_segment_indexed(text[start:end], _fast[0], _fast[1], _fast[2])
 if _fast else OpenCC.convert_segment(text[start:end], dictionaries, max_word_length))
```

- **Parallel mapper target (keep grouping logic intact)**

Replace in the Pool `map` args:
```python
OpenCC.convert_segment
```
with:
```python
OpenCC.convert_segment_indexed if _fast else OpenCC.convert_segment
```

## 3) Add the new method inside class `OpenCC`

Place **inside the `OpenCC` class**, for example right before `def _get_dict_refs(...)`:

```python
    @staticmethod
    def convert_segment_indexed(segment: str, merged_map, starter_index: StarterIndex, global_cap: int) -> str:
        if not segment or (len(segment) == 1 and segment in DELIMITERS):
            return segment
        out = []
        i, n = 0, len(segment)
        while i < n:
            cp0 = ord(segment[i])
            mask, cap = starter_index.get_mask_cap(cp0)
            if mask == 0 or cap == 0:
                out.append(segment[i])
                i += 1
                continue
            rem = n - i
            cap_here = min(rem, cap, global_cap)
            matched = False
            L = cap_here
            while L >= 1:
                if (mask >> (L - 1)) & 1:
                    s = segment[i:i+L]
                    repl = merged_map.get(s)
                    if repl is not None:
                        out.append(repl)
                        i += L
                        matched = True
                        break
                L -= 1
            if not matched:
                out.append(segment[i])
                i += 1
        return "".join(out)
```

> Indentation must match other methods (4 spaces).

---

## Optional: Persist the index into JSON

At any time (e.g., in a one-off admin script), after loading `DictionaryMaxlength`, you can compute and embed the starter index:

```python
from opencc_purepy.dictionary_lib import DictionaryMaxlength
from opencc_purepy.starter_index import StarterIndex, pack_index_blob
from opencc_purepy.merge_dicts import merge_in_precedence

d = DictionaryMaxlength.from_json(Path(__file__).parent / "dicts" / "dictionary_maxlength.json")
active_dicts = [d.st_phrases[0], d.st_characters[0], d.ts_phrases[0], d.ts_characters[0],
                d.tw_variants[0], d.tw_variants_rev[0], d.hk_variants[0], d.hk_variants_rev[0],
                d.jp_variants[0], d.jp_variants_rev[0]]
global_cap = max((len(k) for dd in active_dicts for k in dd.keys()), default=1)
idx = StarterIndex.build(active_dicts, global_cap)
d.inject_starter_index(idx)
d.serialize_to_json(Path(__file__).parent / "dicts" / "dictionary_maxlength.json")
```

This writes a `"starter_index"` blob (Base64 BMP arrays + astral maps) into your JSON for fastest cold start.

---

## Notes

- The runtime remains **backward compatible** if `starter_index` is absent — it will build one lazily.
- Your existing parallel threshold ( >1000 segments and ≥1,000,000 chars ) is unchanged.
- Python uses full Unicode code points, so there’s no BMP/non-BMP correctness issue.

