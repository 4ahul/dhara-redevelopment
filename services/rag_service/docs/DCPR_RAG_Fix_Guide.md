# DCPR RAG Accuracy Fix Guide

## Why You're Getting Inaccurate Results

After reviewing your full pipeline — Milvus indexing, query expansion, multi-search,
synthesis, and answer generation — here are the **7 root causes**, ranked by impact.

---

## Root Cause 1 — Table Data Truncated in Synthesis [CRITICAL]

**Where:** `_synthesize_all()` — line ~1749

**Problem:** The synthesis step passes only `r.text[:500]` from only 5 documents.
A DCPR FSI table is typically **800–2000 characters**. Half the table is cut off
before the synthesis LLM even sees it. The result: `fsi_data.base_fsi = "See documents"`
instead of the actual value.

**Fix:** Raise to `r.text[:1200]` from `local_results[:10]`.

```python
# BEFORE
f"[Local {i + 1}] Source: {r.source}, Page: {r.page}\n{r.text[:500]}"
for i, r in enumerate(local_results[:5])

# AFTER
f"[Local {i + 1}] Source: {r.source or 'DCPR 2034'}, Page: {r.page}\n{r.text[:1200]}"
for i, r in enumerate(local_results[:10])
```

---

## Root Cause 2 — Answer Context Window Too Narrow [CRITICAL]

**Where:** `_generate_dynamic_answer()` and `_stream_dynamic_answer()`

**Problem:**
- Non-streaming: `r.text[:1800]` from 10 docs
- Streaming: `r.text[:1800]` from only **8** docs

Many DCPR tables (parking schedules, FSI by road width, margin tables) exceed 1800
characters. A chunk that contains exactly the answer row gets silently cut off.

**Fix:** Raise to `r.text[:2500]` from 12 docs in both functions.

```python
# BEFORE (both functions)
f"[Doc {i + 1}] Source: {r.source}, Page: {r.page}\n{r.text[:1800]}"
for i, r in enumerate(local_results[:10])   # or [:8] in stream version

# AFTER (both functions)
f"[Doc {i + 1}] Source: {r.source}, Page: {r.page}\n{r.text[:2500]}"
for i, r in enumerate(local_results[:12])
```

---

## Root Cause 3 — HNSW Recall Too Low [HIGH]

**Where:** `_search_local()` — line ~962

**Problem:** `ef=128` with `limit=10`. The HNSW `ef` parameter is the candidate pool
size during graph traversal. When `ef` is only 13× the limit, many relevant nodes
are never visited. DCPR chunks about the same regulation (e.g., FSI for R2 zone)
may be scattered across the graph and missed.

**Fix:** Raise `ef` to 256 and `limit` to 20 (re-rank to 12 afterward).

```python
# BEFORE
search_params = {"metric_type": "COSINE", "params": {"ef": 128}}
...
limit=k,

# AFTER
search_params = {"metric_type": "COSINE", "params": {"ef": 256}}
...
limit=max(k, 20),
```

---

## Root Cause 4 — Table Chunks Not Prioritized [HIGH]

**Where:** `_search_local()` — return block

**Problem:** The `chunk_type` field is stored in Milvus but never used. Chunks tagged
`"table"` or `"table_row"` contain the exact numbers the user is asking for, but they
rank below prose chunks that merely *mention* the topic.

**Fix:** Add a score boost for table chunks before returning from `_search_local`.

```python
chunk_type = entity.get("chunk_type", "text")
raw_score  = hit.distance

if chunk_type in ("table", "table_row", "schedule"):
    raw_score = min(raw_score + 0.08, 1.0)
elif chunk_type in ("heading", "regulation_header"):
    raw_score = min(raw_score + 0.03, 1.0)
```

---

## Root Cause 5 — Multi-Query Fusion Is Naive [MEDIUM]

**Where:** `_multi_search()` — final sort

**Problem:** After deduplication, results are sorted by raw cosine score. A chunk
that appears in the top-10 for **three** different query variants (a very strong signal
of relevance) gets no credit for that. A chunk with a slightly higher cosine score
from a single query will beat it.

**Fix:** Reciprocal Rank Fusion (RRF). For each chunk, record its rank in each
query's result list. Final score = `0.6 × cosine + 0.4 × normalized_RRF`.

```python
K_RRF = 60
for r in results_list:
    ranks = query_ranks[r.text.strip()]          # list of ranks across queries
    rrf_raw  = sum(1.0 / (K_RRF + rank) for rank in ranks)
    rrf_norm = rrf_raw / max_possible_rrf
    r.score  = 0.6 * r.score + 0.4 * rrf_norm
```

---

## Root Cause 6 — Query Expansion Capped at 5 [MEDIUM]

**Where:** `_expand_queries()` — last line

**Problem:** `return queries[:5]` — only 5 query variants are searched. The DCPR
document references the same regulation in many ways ("Regulation 33(7)", "Clause 33
sub-clause 7", "Table 13A", "R2 zone FSI", etc.). With only 5 queries you miss
several valid entry points into the table you need.

**Fix:** One line change.

```python
# BEFORE
return queries[:5]

# AFTER
return queries[:8]
```

---

## Root Cause 7 — Chunking Splits Table Rows [HIGH — requires re-index]

**Where:** `index_pipeline.py` → `chunk_document()`

**Problem:** If your chunker splits on newline boundaries, a DCPR pipe-separated
table gets split in the middle of a row. Neither chunk has a complete row. The
embedding of a half-row is semantically noisy — it retrieves but the answer isn't there.

**Fix (recommended):** Add a "table-aware" chunking rule:

```python
def should_split_here(line_a: str, line_b: str) -> bool:
    """Never split between two pipe-table rows."""
    if "|" in line_a and "|" in line_b:
        return False   # both are table rows — keep together
    return True
```

Also increase chunk size and overlap:
```
CHUNK_SIZE    = 800   (from ~400–512)
CHUNK_OVERLAP = 200   (from ~50–100)
```

After changing these settings, re-run:
```bash
python -m scripts.index_dcpr_only --drop
```

---

## Quick-Apply Summary

| Fix | File | Change |
|-----|------|--------|
| 1 — Synthesis truncation | `intelligent_rag.py` | `_synthesize_all`: 5→10 docs, 500→1200 chars |
| 2 — Answer context | `intelligent_rag.py` | `_generate_dynamic_answer` + `_stream`: 10/8→12 docs, 1800→2500 chars |
| 3 — HNSW recall | `intelligent_rag.py` | `_search_local`: ef 128→256, limit → max(k,20) |
| 4 — Table boost | `intelligent_rag.py` | `_search_local`: +0.08 score for table chunks |
| 5 — RRF fusion | `intelligent_rag.py` | `_multi_search`: add RRF scoring |
| 6 — Query cap | `intelligent_rag.py` | `_expand_queries`: `[:5]` → `[:8]` |
| 7 — Chunk splitting | `index_pipeline.py` | Table-aware chunker + re-index |

Fixes 1–6 require **no re-indexing** and can be applied immediately.
Fix 7 requires a re-index but gives the highest long-term accuracy gain.

The patch file `rag_improvements_patch.py` contains ready-to-use replacement
functions for fixes 1–5. Apply them via monkey-patching (for quick testing) or
by copying the method bodies into `intelligent_rag.py` directly.
