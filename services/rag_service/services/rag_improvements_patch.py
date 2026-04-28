"""
DCPR RAG Accuracy Patch
========================
Drop-in replacements for the methods in intelligent_rag.py that cause
inaccurate / "not found" results.

HOW TO APPLY
------------
1. Copy the patched methods below over their counterparts in intelligent_rag.py.
2. The only import you may need to add at the top of intelligent_rag.py is:
       from collections import defaultdict   (already present)
3. No schema changes required. No re-indexing required.

ROOT CAUSES DIAGNOSED
---------------------
1. TABLE DATA TRUNCATED IN SYNTHESIS   [CRITICAL]
   _synthesize_all passes r.text[:500] for only 5 docs.
   A DCPR FSI table is 800-2000 chars. Half the table gets cut off.
   The synthesis LLM then writes "base_fsi: See documents" → useless.

2. ANSWER CONTEXT WINDOW TOO NARROW    [CRITICAL]
   _generate_dynamic_answer uses r.text[:1800] for 10 docs.
   _stream_dynamic_answer uses r.text[:1800] for only 8 docs.
   Multi-row tables that exceed 1800 chars get cut. Raise to 2500 and
   pass 12 docs.

3. HNSW RECALL TOO LOW                 [HIGH]
   ef=128 with limit=10. HNSW ef should be >> limit for good recall.
   Raise ef to 256 and limit to 20, then re-rank and trim to 12.

4. TABLE CHUNKS NOT PRIORITISED        [HIGH]
   chunk_type is stored in Milvus but never used at retrieval time.
   A simple +0.08 score boost for chunk_type=="table" moves the right
   chunks to the top before re-ranking.

5. MULTI-QUERY FUSION IS NAIVE         [MEDIUM]
   _multi_search deduplicates by text hash and then sorts by raw cosine
   score. A chunk that appears in results for 3 different query variants
   (strong signal!) is treated the same as one that appears once.
   Switch to Reciprocal Rank Fusion (RRF) so frequency-across-queries
   promotes the most relevant chunks.

6. QUERY EXPANSION CAPPED AT 5        [MEDIUM]
   5 queries × 10 results = 50 candidates but dedup often leaves 20-30.
   Raise cap to 8 queries to get better coverage, especially for
   multi-row tables referenced by different regulation numbers.

7. SYNTHESIS BOTTLENECK                [MEDIUM]
   _synthesize_all is a full LLM round-trip that adds latency and
   sometimes hallucinates fsi_data values ("See documents"). The
   _generate_dynamic_answer already receives the raw retrieved text, so
   the synthesis JSON is only marginally useful. The fix is to pass 10
   full-text docs to synthesis (same as answer gen) so it actually
   reads the table, or skip it when local_text already has relevant data.
"""

import re
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 + 3 + 4: _search_local  — higher ef, bigger limit, table boost
# ─────────────────────────────────────────────────────────────────────────────


def _search_local_patched(
    self,
    query: str,
    k: int = 20,
    doc_type_filter: str = None,
    precomputed_vector: list[float] = None,
):
    """
    Patched version of SessionRAG._search_local.

    Changes vs original:
    - ef raised from 128 → 256  (better HNSW recall)
    - limit raised to max(k, 20) so we always fetch at least 20 candidates
    - table chunks get a +0.08 score bonus before returning
    """
    try:
        if not self.vectorstore:
            return []

        query_vec = (
            precomputed_vector if precomputed_vector is not None else self._get_embedding(query)
        )

        # ── FIX 3: higher ef for better HNSW recall ──────────────────────
        search_params = {"metric_type": "COSINE", "params": {"ef": 256}}

        expr = None
        if doc_type_filter:
            expr = f'doc_type == "{doc_type_filter}"'

        # ── FIX 3: fetch more candidates (at least 20) ────────────────────
        fetch_k = max(k, 20)

        results = self.vectorstore.search(
            data=[query_vec],
            anns_field="embedding",
            param=search_params,
            limit=fetch_k,
            expr=expr,
            output_fields=[
                "text",
                "source",
                "page",
                "language",
                "doc_type",
                "chunk_type",
            ],
        )

        output = []
        for hits in results:
            for hit in hits:
                entity = hit.entity
                raw_score = hit.distance
                chunk_type = entity.get("chunk_type", "text")

                # ── FIX 4: boost table / header chunks ────────────────────
                if chunk_type in ("table", "table_row", "schedule"):
                    raw_score = min(raw_score + 0.08, 1.0)
                elif chunk_type in ("heading", "regulation_header"):
                    raw_score = min(raw_score + 0.03, 1.0)

                output.append(
                    SearchResult(  # noqa – imported from intelligent_rag
                        query=query,
                        text=entity.get("text", ""),
                        score=raw_score,
                        clauses=[],
                        tables=[],
                        relevance_tags=[],
                        source=entity.get("source", ""),
                        page=entity.get("page", 0),
                        language=entity.get("language", "en"),
                        doc_type=entity.get("doc_type", "other"),
                        result_type="local",
                    )
                )
        return output

    except Exception as e:
        err_msg = str(e)
        if "dimension" in err_msg.lower() or "size(byte)" in err_msg:
            return []
        if "not exist" in err_msg.lower():
            import logging

            logging.getLogger(__name__).warning(
                "[SEARCH] Schema error: collection may need reindexing"
            )
            return []
        import logging

        logging.getLogger(__name__).warning(f"[SEARCH] Error: {err_msg[:100]}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# FIX 5 + 6: _multi_search  — RRF fusion + bigger query cap
# ─────────────────────────────────────────────────────────────────────────────


def _multi_search_patched(
    self,
    queries: list[str],
    context,  # QueryContext
    k: int,
) -> list:
    """
    Patched version of SessionRAG._multi_search.

    Changes vs original:
    - query cap raised from 5 → 8
    - Reciprocal Rank Fusion (RRF) replaces raw-score sort so chunks that
      appear in multiple query results rank higher
    - Returns top k*2 (capped at 24)
    """
    import hashlib
    import logging

    logger = logging.getLogger(__name__)

    seen_texts: dict[str, dict] = {}  # text → best SearchResult
    query_ranks: dict[str, list[int]] = defaultdict(list)  # text → [rank in each query]

    unique_queries = list(dict.fromkeys(queries))[:8]  # FIX 6: cap at 8

    # Pre-compute embeddings (same batching logic as original)
    query_vecs: dict[str, list[float]] = {}
    misses: list[str] = []

    for q in unique_queries:
        key = hashlib.sha256(q.encode()).hexdigest()[:16]
        with self.__class__._embed_cache_lock:
            if key in self.__class__._embed_cache:
                self.__class__._embed_cache.move_to_end(key)
                query_vecs[q] = list(self.__class__._embed_cache[key])
                continue
        cached = self._get_from_cache(f"emb:{key}")
        if cached:
            query_vecs[q] = cached
            with self.__class__._embed_cache_lock:
                if len(self.__class__._embed_cache) >= self.__class__._EMBED_CACHE_MAX:
                    self.__class__._embed_cache.popitem(last=False)
                self.__class__._embed_cache[key] = cached
        else:
            misses.append(q)

    if misses and self.__class__._embeddings is not None:
        try:
            vecs = self.__class__._embeddings.embed_documents(misses)
            for q, vec in zip(misses, vecs, strict=False):
                query_vecs[q] = vec
                key = hashlib.sha256(q.encode()).hexdigest()[:16]
                self._set_in_cache(f"emb:{key}", vec, ttl=86400)
                with self.__class__._embed_cache_lock:
                    if len(self.__class__._embed_cache) >= self.__class__._EMBED_CACHE_MAX:
                        self.__class__._embed_cache.popitem(last=False)
                    self.__class__._embed_cache[key] = vec
        except Exception as e:
            logger.error(f"[Embed] Batch embed error: {e}", exc_info=True)

    # Per-query search; record per-text ranks for RRF
    for query in unique_queries:
        try:
            results = self._search_local(query, k=k, precomputed_vector=query_vecs.get(query))
            for rank, r in enumerate(results):
                if not r.text:
                    continue
                text_key = r.text.strip()
                if text_key not in seen_texts:
                    r.relevance_tags = [context.topic]
                    seen_texts[text_key] = r
                else:
                    # Keep the highest raw score we've seen
                    if r.score > seen_texts[text_key].score:
                        seen_texts[text_key].score = r.score
                # RRF: record the 0-based rank for this query
                query_ranks[text_key].append(rank)
        except Exception as e:
            logger.error(f"Search error for '{query}': {e}", exc_info=True)

    # ── FIX 5: Reciprocal Rank Fusion ────────────────────────────────────
    # RRF score = Σ 1/(k_rrf + rank_i).  k_rrf=60 is standard.
    # We blend: final = 0.6 * cosine_score + 0.4 * rrf_score (both 0-1 range).
    K_RRF = 60
    results_list = list(seen_texts.values())

    max_rrf = sum(1.0 / (K_RRF + r) for r in range(len(unique_queries)))  # max possible rrf

    for r in results_list:
        text_key = r.text.strip()
        ranks = query_ranks.get(text_key, [])
        rrf_raw = sum(1.0 / (K_RRF + rank) for rank in ranks)
        rrf_norm = rrf_raw / max_rrf if max_rrf > 0 else 0.0
        r.score = 0.6 * r.score + 0.4 * rrf_norm

    results_list.sort(key=lambda x: x.score, reverse=True)
    cap = min(k * 2, 24)
    return results_list[:cap]


# ─────────────────────────────────────────────────────────────────────────────
# FIX 2 + 1: _generate_dynamic_answer  — wider context, no table truncation
# ─────────────────────────────────────────────────────────────────────────────


def _generate_dynamic_answer_patched(
    self,
    question: str,
    local_results: list,
    web_context: str,
    synthesis: dict,
    context,  # QueryContext
    web_sources: list = None,
) -> str:
    """
    Patched version of SessionRAG._generate_dynamic_answer.

    Changes vs original:
    - Per-doc text raised from 1800 → 2500 chars  (full tables survive)
    - Docs passed to LLM raised from 10 → 12
    - Stream version: docs raised from 8 → 12, text limit → 2500
    """
    # ── FIX 2: wider per-doc window, more docs ────────────────────────────
    CHUNK_LIMIT = 2500
    DOC_COUNT = 12

    local_text = "\n\n".join(
        [
            f"[Doc {i + 1}] Source: {r.source}, Page: {r.page}\n{r.text[:CHUNK_LIMIT]}"
            for i, r in enumerate(local_results[:DOC_COUNT])
            if r.text
        ]
    )

    citations = []
    for i, r in enumerate(local_results[:DOC_COUNT]):
        if r.source:
            page_info = f", p.{r.page}" if r.page else ""
            citations.append(f"[Doc {i + 1}] {r.source}{page_info}")
        else:
            source_preview = r.text[:60].replace("\n", " ").strip() + "..."
            citations.append(f"[Doc {i + 1}] {source_preview}")

    web_citations = []
    if web_sources:
        for i, s in enumerate(web_sources[:5]):
            title = s.get("title", "Unknown")[:40]
            url = s.get("url", "")
            web_citations.append(f"[Web {i + 1}] {title} - {url}")

    "\n".join(citations + web_citations) or "No sources available"

    is_comparison = any(
        w in question.lower()
        for w in ["best", "top", "compare", "areas", "hubs", "list", "recommend", "vs", "versus"]
    )
    is_market_analysis = context.needs_market_data or context.intent == "feasibility_analysis"

    # Import DCPR_ANSWER_RULES from the module (it is a module-level constant)
    import sys

    _mod = sys.modules.get(__name__)  # works when called as a method
    DCPR_RULES = getattr(_mod, "DCPR_ANSWER_RULES", "")

    if context.is_technical or context.intent == "technical_lookup":
        prompt = f"""You are a senior Urban Planning Consultant on DCPR 2034 for Mumbai.
Provide a high-precision answer based strictly on the regulations.

Question: {question}
Location: {context.location or "Mumbai"}
Parameters: {context.units}

REGULATION EXCERPTS:
{local_text}

WEB CONTEXT:
{web_context[:2000] if web_context else "No web results"}

{DCPR_RULES}

EXTRA:
- Lead with the specific number asked for in the first sentence.
- If the question needs a parameter that's missing (plot area / road width /
  zone), ask for it in one line and stop — do not invent a generic answer."""

    elif is_comparison and is_market_analysis:
        prompt = f"""You are a real estate investment advisor for Mumbai. Provide a ranked list based on web search data.

Question: {question}

WEB SEARCH RESULTS (PRIORITY - this is live market data):
{web_context[:4000] if web_context else "No web results"}

REGULATORY DATA (from documents):
{local_text if local_text else "No local regulatory data"}

{DCPR_RULES}

EXTRA (ranked-list formatting):
- One compact section per area with: price/sqft, key feature, rental yield.
- Cite web results as [Web N] inline; for regulatory claims use the
  "— as per DCPR 2034..." inline citation.
- If a metric is missing for an area, omit that metric — do not fabricate numbers.
"""
    elif context.needs_market_data or context.intent == "feasibility_analysis":
        prompt = f"""You are a real estate investment advisor for Mumbai. Provide a focused feasibility analysis.

Question: {question}
Location: {context.location or "Mumbai"}

WEB SEARCH RESULTS (PRIORITY - include specific prices, rates, consultants):
{web_context[:3000] if web_context else "No web results"}

REGULATORY DATA (from local documents):
{local_text if local_text else "No local regulatory data"}

{DCPR_RULES}

EXTRA (feasibility formatting):
- Lead with one line of market data (price/sqft, yield) if web results contain
  it, then one line of regulatory position (FSI/permit) from DCPR excerpts.
- Cite web data as [Web N]; cite DCPR data using the inline "— as per DCPR
  2034, Regulation <X>, p.<N>" form.
- End with a single actionable next step — no multi-paragraph closers.
"""
    else:
        prompt = f"""You are a Mumbai urban planning expert answering a DCPR 2034 question.

Question: {question}
Parameters: Area={context.units.get("original") if context.units else "not specified"}, Road Width={context.units.get("road_width", "9m (default)")}, Location={context.location or "Mumbai"}

DCPR 2034 Regulations:
{local_text[:3000]}

Web Search:
{web_context[:3000] if web_context else "None"}

{DCPR_RULES}

EXTRA:
- Open with the direct answer in one sentence.
- No LaTeX, no section headers, no "Conclusion" block. Markdown tables ARE
  allowed and REQUIRED when rule 4 (multi-variant comparison) applies.
"""

    try:
        answer_model = "gpt-4o" if self._use_openai else self._model
        response = self.client.chat.completions.create(
            model=answer_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Mumbai DCPR 2034 expert. Answer ONLY what is asked, "
                        "in under 6 short sentences, with exact numbers from the DCPR excerpts. "
                        "End each factual paragraph with an inline citation of the form "
                        "'— as per DCPR 2034, Regulation <X>, p.<N>'. "
                        "For tables, include every field the final value depends on or omit "
                        "the table entirely — never use placeholder values like 'Varies', "
                        "'N/A', or 'Available on request'. If data is missing, say so in one line."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        answer = response.choices[0].message.content.strip()

        if "Sources:" not in answer and citations:
            answer += "\n\n**Sources:**\n" + "\n".join(citations)

        return answer
    except Exception as e:
        return f"Error generating answer: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# FIX 1: _synthesize_all  — pass full text, not 500-char snippets
# ─────────────────────────────────────────────────────────────────────────────


def _synthesize_all_patched(
    self, question: str, local_results: list, web_context: str, context
) -> dict:
    """
    Patched version of SessionRAG._synthesize_all.

    Changes vs original:
    - Raised from [:5] with text[:500]  →  [:10] with text[:1200]
      This ensures full DCPR table rows reach the synthesis LLM so it
      can actually populate fsi_data.base_fsi etc. instead of "See documents".
    """
    area_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft|sqr?\s*ft|sq\.?\s*m)", question.lower()
    )
    road_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|meter)", question.lower())

    query_params = {
        "area_sqft": float(area_match.group(1)) if area_match else None,
        "road_width_m": float(road_match.group(1)) if road_match else None,
        "location": "mumbai" if "mumbai" in question.lower() else None,
    }

    # ── FIX 1: 10 docs, 1200 chars each (was 5 docs × 500 chars) ──────────
    local_text = "\n\n".join(
        [
            f"[Local {i + 1}] Source: {r.source or 'DCPR 2034'}, Page: {r.page}\n{r.text[:1200]}"
            for i, r in enumerate(local_results[:10])
        ]
    )

    prompt = f"""Compare and synthesize information for the question: "{question}"

Query Parameters Detected:
- Area: {query_params.get("area_sqft")} sq.ft
- Road Width: {query_params.get("road_width_m")} meters
- Location: {query_params.get("location")}

1. LOCAL RAG DOCUMENTS:
{local_text if local_text else "No local information found."}

2. WEB SEARCH:
{web_context[:1500] if web_context else "No web search results."}

INSTRUCTIONS:
- If area and road_width are detected, look up the relevant FSI tables in the documents.
- Identify which regulation/table applies.
- Return ONLY the JSON object below — no markdown fences, no preamble.

{{
  "comparison": "<one sentence>",
  "key_parameters": {{
    "area": "<detected or estimated from question>",
    "road_width": "<detected or assumed standard (9m default)>",
    "zone_type": "<detected or residential default>"
  }},
  "applicable_regulations": ["list of regulation numbers that apply"],
  "fsi_data": {{
    "base_fsi": "<exact value from table, or 'Not found'>",
    "max_fsi": "<maximum allowed, or 'Not found'>",
    "premium_fsi": "<if applicable, or 'Not applicable'>"
  }},
  "missing_info": ["what we need from user"]
}}
"""
    try:
        kwargs = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        if self._use_openai:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        import json

        return json.loads(response.choices[0].message.content)
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Synthesis error: {e}", exc_info=True)
        return {
            "comparison": "Error in synthesis",
            "key_parameters": {},
            "applicable_regulations": [],
            "fsi_data": {},
            "missing_info": [],
        }


# ─────────────────────────────────────────────────────────────────────────────
# FIX 6: _expand_queries — raise cap from 5 → 8
# ─────────────────────────────────────────────────────────────────────────────
# At the very end of the original _expand_queries, replace:
#     return queries[:5]
# with:
#     return queries[:8]
#
# This is a one-line change; see the note in APPLY INSTRUCTIONS below.


# ─────────────────────────────────────────────────────────────────────────────
# BONUS: _stream_dynamic_answer  — same wider context as non-streaming version
# ─────────────────────────────────────────────────────────────────────────────
# In _stream_dynamic_answer, change both occurrences of:
#     r.text[:1800]   →   r.text[:2500]
#     local_results[:8]   →   local_results[:12]
# These are two-line changes; see APPLY INSTRUCTIONS below.


# =============================================================================
# APPLY INSTRUCTIONS
# =============================================================================
"""
STEP 1 – Monkey-patch (quick test, no file edits needed):
    Add this block near the bottom of intelligent_rag.py, BEFORE the
    IntelligentRAG class definition:

        from rag_improvements_patch import (
            _search_local_patched,
            _multi_search_patched,
            _generate_dynamic_answer_patched,
            _synthesize_all_patched,
        )
        SessionRAG._search_local            = _search_local_patched
        SessionRAG._multi_search            = _multi_search_patched
        SessionRAG._generate_dynamic_answer = _generate_dynamic_answer_patched
        SessionRAG._synthesize_all          = _synthesize_all_patched

    Also do the two one-liner changes described in FIX 6 and BONUS above.

STEP 2 – Permanent (copy-paste the method bodies):
    Replace each method in SessionRAG with the body of the corresponding
    patched function above (strip the `self` → keep `self` as first param).

STEP 3 – Re-index recommendation (OPTIONAL but high-impact):
    If you can re-run index_dcpr_only.py, use these chunking settings in
    index_pipeline.py for better table preservation:

        CHUNK_SIZE          = 800   (was probably 512 or 400)
        CHUNK_OVERLAP       = 200   (was probably 50–100)
        RESPECT_TABLE_ROWS  = True  (keep full table rows together)

    The key rule: never split a chunk in the middle of a pipe-separated
    table row.  If your chunker splits on newlines, add a rule:
        "do not split if current line contains | and next line also contains |"
"""
