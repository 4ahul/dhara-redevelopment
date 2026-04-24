#!/usr/bin/env python3
"""
Enhanced Intelligent RAG System with Dynamic Knowledge Graph
Builds knowledge graph from DCPR document parsing
"""

import os
import re
import json
import uuid
import warnings
import time
import threading
import hashlib
import dataclasses
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Set, Any
from collections import defaultdict, OrderedDict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures._base import TimeoutError

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Optional imports with proper error handling
try:
    import requests
except ImportError:
    requests = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except ImportError:
    QdrantClient = None
    qmodels = None

try:
    from pymilvus import connections, Collection
except ImportError:
    connections = None
    Collection = None

try:
    from langchain_openai import OpenAIEmbeddings
except ImportError:
    OpenAIEmbeddings = None

env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ[key] = val


# House rules applied to every DCPR answer prompt. Keeps citation/table/brevity
# behavior consistent across streaming + non-streaming generators.
DCPR_ANSWER_RULES = """MANDATORY ANSWER RULES:
1. SCOPE — MUMBAI DCPR 2034 ONLY: You are an expert on DCPR 2034 for
   Mumbai. The retrieved excerpts are Mumbai DCPR 2034 only. If the
   question is about another city, another regulation (UDCPR, Pune),
   or a non-DCPR topic (property valuation, legal advice, market
   rates without a regulatory angle), reply in one line: "I cover
   only DCPR 2034 for Mumbai. Please ask within that scope." and
   stop. Do not attempt to answer from general knowledge.
2. ASKED-FACT BOUNDARY: Answer only the literal fact the user asked
   for. Include at most one short sentence of directly dependent
   context if the asked fact makes no sense without it. DO NOT
   volunteer adjacent regulations, tables, or limits that the user
   did not ask about.
   NEGATIVE EXAMPLE: If the user asks "TDR rates per ASR for
   generating and receiving plots", do NOT include FSI ceilings by
   road width (3 for 12m, 4 for 18m, 5 for 27m). Those are adjacent
   regulations. Answer only the TDR rate question. If the rate is
   not in the excerpts, say "Not specified in the retrieved DCPR
   excerpts." and stop.
3. DCPR-NATIVE UNITS ONLY: Quote every dimension, area, height, and
   width in the exact unit used in the DCPR excerpt. Never convert
   between metres and feet, or between sq.m and sq.ft. If the
   excerpt says "1.2 m × 1.0 m", the answer says "1.2 m × 1.0 m".
   NEGATIVE EXAMPLE: If the user asks "Minimum Toilet dimensions
   allowed" and the excerpt specifies the dimension in metres, do
   NOT answer "3' × 4' (approximately 12 sq. ft.)". Quote the
   metres value verbatim.
4. COMPARISON TABLE FOR MULTI-VARIANT REGULATIONS: When the
   retrieved excerpts describe ONE regulation with multiple variants
   (by space type, user type, building type, or similar) AND the
   user's question is broad enough to span those variants, render
   the answer as a GITHUB-FLAVORED MARKDOWN TABLE using PIPE syntax
   with one row per variant. Do NOT use tabs, spaces, or plain
   columns — the output MUST use the `|` character as the column
   separator and a `|---|---|` separator row under the header.
   REQUIRED FORMAT (copy this syntax exactly, replacing the
   placeholder text):
   | Variant | Requirement |
   |---|---|
   | <variant 1 name> | <value> |
   | <variant 2 name> | <value> |
   Do NOT use a table when only one variant applies or the user's
   question targets a single variant.
   TABLE COMPLETENESS: When a table depends on combining multiple
   contributing fields (e.g. Base FSI + TDR + Premium + Ancillary →
   Total), include every contributing field or omit the table
   entirely. Never fill missing cells with "N/A", "Varies", or
   "Available on request".
   POSITIVE EXAMPLE: "Parking requirement for educational institutes"
   spans office, assembly hall, visitor — render as a pipe-syntax
   markdown table.
   NEGATIVE EXAMPLE: "FSI for a 1000 sq.m plot on 12 m road" — one
   variant applies; use a prose sentence.
5. INLINE CITATION: Only emit a citation tag when you have BOTH a
   specific regulation/clause number AND a specific page number
   from the excerpts. The tag format is exactly:
   "— as per DCPR 2034, Regulation <X>, p.<N>"
   (or "Clause <X>" if that's how the excerpt labels it). The
   regulation number MUST come from the excerpt text; the page
   number MUST come from the [Doc N] header. NEVER emit the tag
   with empty slots (no "Regulation , p.." and no "p.0"). If you
   don't have both values, write the sentence with no citation tag.
6. "NOT SPECIFIED" SENTENCES GET NO CITATION: If you are saying
   the answer is not in the excerpts, do not append any citation
   tag to that sentence.
7. READ THE TABLES: Before saying "not specified", scan every
   excerpt for tables/schedules. DCPR tables frequently span
   multiple lines with pipe-separated cells; margins/FSI/parking
   are almost always in tables keyed to building height, plot
   size, or road width. Quote the exact row before stating the
   answer.
8. NO FABRICATION — VERBATIM ONLY: Every numeric value, unit,
   regulation/clause number, and page number in your answer MUST
   appear VERBATIM in the provided [Doc N] excerpts. Before you
   state any number, locate its exact substring in an excerpt; if
   you cannot, you are fabricating. Do not infer values from
   training knowledge, do not convert to more familiar units, do
   not approximate, do not "fill in" plausible values. The
   following counts as fabrication and is forbidden:
   - Quoting a number the user's question implies but the excerpts
     don't contain.
   - Quoting a number from a related table/regulation when the
     exact entity the user asked about has no row in the excerpts.
   - Using general building-code knowledge (ASHRAE, NBC, IS codes,
     training-data heuristics) as a fallback.
   If no excerpt contains the specific numeric value for the asked
   entity, reply with the single sentence: "Not specified in the
   retrieved DCPR excerpts." with no citation tag, and stop. Do
   not pad with context, do not suggest what it "might be", do not
   name an adjacent regulation as a consolation.
9. RAG IS THE SOURCE OF TRUTH: The DCPR excerpts are authoritative.
   Web search results are supplementary context only — use them
   for broader framing but NEVER let a web result override,
   contradict, or replace a value from the DCPR excerpts. If DCPR
   and web disagree, follow DCPR. If the DCPR excerpts do not
   contain the value, do not substitute a web number. Web results
   never earn a "— as per DCPR 2034..." citation; cite them as
   [Web N] only.
10. BREVITY: Target ≤6 short sentences plus one citation (tables
    excepted — table rows don't count toward the sentence limit).
    No section headers. No closing filler."""


@dataclass
class QueryContext:
    original_query: str
    intent: str
    entities: List[str]
    clauses: List[str]
    topic: str
    subtopics: List[str]
    is_compound: bool
    compound_parts: List[str]
    location: Optional[str] = None
    units: Dict[str, str] = field(default_factory=dict)
    needs_market_data: bool = False
    needs_regulatory_data: bool = True
    is_technical: bool = False


@dataclass
class SearchResult:
    query: str
    text: str
    score: float
    clauses: List[str]
    tables: List[str]
    relevance_tags: List[str]
    source: str = ""
    page: int = 0
    language: str = "en"
    doc_type: str = "other"
    result_type: str = "local"  # "local" or "web"
    web_url: str = ""


@dataclass
class ClauseInfo:
    clause_id: str
    text: str
    related_clauses: Set[str] = field(default_factory=set)
    tables: Set[str] = field(default_factory=set)
    topics: Set[str] = field(default_factory=set)


class DynamicKnowledgeGraph:
    """Dynamically builds knowledge graph from DCPR document"""

    def __init__(self):
        self.clauses: Dict[str, ClauseInfo] = {}
        self.tables: Dict[str, str] = {}
        self.topic_to_clauses: Dict[str, Set[str]] = defaultdict(set)
        self.clause_relationships: Dict[str, List[str]] = defaultdict(list)
        self._initialized = False

    def build_from_chunks(self, chunks: List[str]):
        """Extract knowledge graph from ALL document chunks"""
        if self._initialized:
            return

        clause_pattern = re.compile(
            r"(?:Clause|Regulation|Rule|Sub-section|धारा|नियम|कलम|उपधारा)\s*(\d+(?:\([\w]+\))?)",
            re.IGNORECASE,
        )
        table_pattern = re.compile(
            r"(?:Table|तालिका)\s*(?:No\.?\s*)?(\d+[a-zA-Z]?)", re.IGNORECASE
        )

        cross_ref_pattern = re.compile(
            r"(?:Clause|Regulation|Table|धारा|नियम|तालिका)\s*(\d+(?:\([\w]+\))?)[,;\s]*(?:and|&|,|आणि|तथा)\s*(?:Clause|Regulation|Table|धारा|नियम|तालिका)?\s*(\d+(?:\([\w]+\))?)",
            re.IGNORECASE,
        )

        # Process ALL chunks
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            clauses_in_chunk = clause_pattern.findall(chunk)
            tables_in_chunk = table_pattern.findall(chunk)
            cross_refs = cross_ref_pattern.findall(chunk)

            for clause in clauses_in_chunk:
                clause_key = (
                    f"Clause {clause}" if not clause.startswith("Clause") else clause
                )
                if clause_key not in self.clauses:
                    self.clauses[clause_key] = ClauseInfo(
                        clause_id=clause_key, text=chunk[:500]
                    )

                self.clauses[clause_key].tables.update(
                    [f"Table {t}" for t in tables_in_chunk]
                )

                for ref1, ref2 in cross_refs:
                    ref1_key = (
                        f"Clause {ref1}" if not ref1.startswith("Clause") else ref1
                    )
                    ref2_key = (
                        f"Clause {ref2}" if not ref2.startswith("Clause") else ref2
                    )
                    self.clauses[clause_key].related_clauses.add(ref1_key)
                    self.clauses[clause_key].related_clauses.add(ref2_key)
                    self.clause_relationships[ref1_key].append(ref2_key)
                    self.clause_relationships[ref2_key].append(ref1_key)

            for table in tables_in_chunk:
                table_key = f"Table {table}"
                if table_key not in self.tables:
                    self.tables[table_key] = chunk[:500]

            if (i + 1) % 500 == 0:
                logger.info(
                    f"  KG Progress: {i + 1}/{total} chunks, {len(self.clauses)} clauses"
                )

        self._extract_topics(chunks)
        self._initialized = True
        logger.info(
            f"  KG Complete: {len(self.clauses)} clauses, {len(self.tables)} tables"
        )

    def _extract_topics(self, chunks: List[str]):
        """Extract topics from chunks using keyword clustering"""
        topic_keywords = {
            "FSI": [
                "fsi",
                "floor space index",
                "built-up area",
                "built up",
                "फ्लोर स्पेस इंडेक्स",
                "एफएसआय",
                "एफएसआई",
            ],
            "Parking": [
                "parking",
                "vehicle",
                "car park",
                "parking space",
                "वाहनतळ",
                "पार्किंग",
            ],
            "Open Space": [
                "open space",
                "marginal",
                "setback",
                "osr",
                "मोकळी जागा",
                "अंतर",
            ],
            "Redevelopment": [
                "redevelopment",
                "reconstruction",
                "rebuilding",
                "पुनर्विकास",
                "पुनर्बांधकाम",
            ],
            "Premium": [
                "premium",
                "premium charge",
                "additional fsi",
                "प्रीमियम",
                "अतिरिक्त एफएसआय",
            ],
            "Height": ["height", "storey", "stories", "stilt", "उंची", "मजला"],
            "Rehabilitation": [
                "rehabilitation",
                "tenant",
                "occupier",
                "rehousing",
                "पुनर्वसन",
                "भाडेकरू",
            ],
            "TDR": ["tdr", "transferable", "development rights", "हस्तांतरणीय विकास हक्क"],
            "Margins": ["marginal distance", "margin", "setback", "अंतर", "सेटबॅक"],
            "Loading": ["loading", "unloading", "bay", "लोडिंग", "उतरणी"],
        }

        for i, chunk in enumerate(chunks):
            chunk_lower = chunk.lower()
            for clause in list(self.clauses.keys()):
                if clause in chunk:
                    for topic, keywords in topic_keywords.items():
                        if any(kw in chunk_lower for kw in keywords):
                            self.clauses[clause].topics.add(topic)
                            self.topic_to_clauses[topic].add(clause)

    def get_related(self, clause_or_term: str) -> List[str]:
        """Get related clauses for a given clause or term"""
        clause_key = (
            clause_or_term
            if clause_or_term.startswith("Clause")
            else f"Clause {clause_or_term}"
        )
        related = set()

        if clause_key in self.clauses:
            related.update(self.clauses[clause_key].related_clauses)
            for topic in self.clauses[clause_key].topics:
                related.update(self.topic_to_clauses.get(topic, set()))

        related.discard(clause_key)
        return list(related)[:15]

    def get_clauses_by_topic(self, topic: str) -> List[str]:
        """Get all clauses related to a topic"""
        return list(self.topic_to_clauses.get(topic, set()))

    def get_clause_info(self, clause_id: str) -> Optional[ClauseInfo]:
        return self.clauses.get(
            clause_id if clause_id.startswith("Clause") else f"Clause {clause_id}"
        )


class ConversationMemory:
    """Simple conversation memory with optional Redis persistence."""

    def __init__(self, session_id: str = ""):
        self.session_id = session_id
        self.messages: List[Dict] = []
        self.query_count = 0
        # Try to restore from Redis if session_id is provided
        if session_id:
            self._load_from_redis()

    def _redis_key(self) -> str:
        return f"mem:{self.session_id}"

    def _load_from_redis(self):
        try:
            cached = SessionRAG._get_from_cache(self._redis_key())
            if cached and isinstance(cached, list):
                self.messages = cached
        except Exception:
            pass

    def _persist_to_redis(self):
        if self.session_id:
            try:
                SessionRAG._set_in_cache(self._redis_key(), self.messages, ttl=86400)
            except Exception:
                pass

    def add(self, role: str, content: str):
        self.messages.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )
        self._persist_to_redis()

    def get_history(self, last_k: int = 10) -> List[Dict]:
        return self.messages[-last_k * 2 :]

    def get_context_for_query(self, current_query: str) -> str:
        if len(self.messages) < 2:
            return ""
        recent = self.messages[-6:]
        parts = []
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content'][:150]}...")
        return "\n".join(parts)

    def clear(self):
        self.messages = []
        self._persist_to_redis()


class SessionManager:
    """Manage multiple RAG sessions"""

    _sessions: OrderedDict = OrderedDict()
    _lock = threading.Lock()
    _knowledge_graph: Optional[DynamicKnowledgeGraph] = None
    _chunks: List[str] = []
    _MAX_SESSIONS: int = int(os.environ.get("MAX_RAG_SESSIONS", "200"))

    @classmethod
    def initialize_knowledge_graph(cls, chunks: List[str]):
        """Initialize knowledge graph from document chunks"""
        if cls._knowledge_graph is None:
            cls._knowledge_graph = DynamicKnowledgeGraph()
            cls._chunks = chunks
            cls._knowledge_graph.build_from_chunks(chunks)
            logger.info(
                f"[OK] Knowledge graph built: {len(cls._knowledge_graph.clauses)} clauses, {len(cls._knowledge_graph.tables)} tables"
            )

    @classmethod
    def get_knowledge_graph(cls) -> DynamicKnowledgeGraph:
        if cls._knowledge_graph is None:
            # Initialize it first so we never return None
            cls._knowledge_graph = DynamicKnowledgeGraph()

            try:
                # Read texts from vector cache for KG building
                vector_dir = Path("data/vectors")
                if vector_dir.exists():
                    caches = list(vector_dir.glob("*.json"))
                    if caches:
                        cache = caches[0]
                        logger.info(f"Loading knowledge graph from {cache.name}...")
                        data = json.loads(cache.read_text())
                        if isinstance(data, list):
                            texts = [d.get("text", "") for d in data if d.get("text")]
                            cls.initialize_knowledge_graph(texts)
                    else:
                        logger.warning("No vector cache found for knowledge graph.")
            except Exception as e:
                logger.error(f"Error loading knowledge graph: {e}", exc_info=True)

        return cls._knowledge_graph

    @classmethod
    def get_or_create_session(
        cls, session_id: Optional[str] = None
    ) -> Tuple["SessionRAG", str]:
        with cls._lock:
            if session_id and session_id in cls._sessions:
                # LRU touch: move to most-recently-used end
                cls._sessions.move_to_end(session_id)
                return cls._sessions[session_id], session_id

            new_id = session_id or str(uuid.uuid4())[:8]
            if new_id not in cls._sessions:
                # Evict least-recently-used session if at capacity
                if len(cls._sessions) >= cls._MAX_SESSIONS:
                    cls._sessions.popitem(last=False)
                cls._sessions[new_id] = SessionRAG(session_id=new_id)
            return cls._sessions[new_id], new_id

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        with cls._lock:
            if session_id in cls._sessions:
                del cls._sessions[session_id]
                return True
            return False

    @classmethod
    def list_sessions(cls) -> List[Dict]:
        with cls._lock:
            return [
                {"session_id": sid, "query_count": rag.query_count}
                for sid, rag in cls._sessions.items()
            ]


class SessionRAG:
    """RAG instance for a single session"""

    _reranker = None
    _reranker_checked = False
    _vs_failed = False
    _llm_warmed = False

    # Shared vectorstore and embeddings — one instance for all sessions
    _vectorstore = None
    _embeddings = None
    _vs_lock = threading.Lock()

    # In-process LRU embedding cache
    _embed_cache: OrderedDict = OrderedDict()
    _embed_cache_lock = threading.Lock()
    _EMBED_CACHE_MAX = 512

    # Search result cache for repeated queries
    _search_cache: OrderedDict = OrderedDict()
    _SEARCH_CACHE_MAX = 50
    _search_cache_lock = threading.Lock()

    # Redis cache configuration
    _redis_client = None
    _CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))  # Default 1 hour

    # In-memory cache for queries with history (short TTL)
    _qctx_cache: OrderedDict = OrderedDict()
    _QCTX_CACHE_MAX = 100
    _QCTX_CACHE_TTL = 300  # 5 minutes for in-memory cache

    @classmethod
    def _get_redis_client(cls):
        """Get or create Redis client."""
        if cls._redis_client is None:
            redis_url = os.environ.get("REDIS_URL", "")
            if redis_url:
                try:
                    import redis

                    cls._redis_client = redis.from_url(redis_url, decode_responses=True)
                    # Test connection
                    cls._redis_client.ping()
                    logger.info("[Redis] Connected to Redis cache")
                except Exception as e:
                    logger.warning(f"[Redis] Connection failed: {e}")
                    cls._redis_client = False  # Mark as failed to avoid retry
            else:
                cls._redis_client = False
        return cls._redis_client if cls._redis_client else None

    @classmethod
    def _get_from_cache(cls, key: str):
        """Get value from Redis cache."""
        client = cls._get_redis_client()
        if client:
            try:
                import json

                data = client.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass
        return None

    @classmethod
    def _set_in_cache(cls, key: str, value, ttl: int = None):
        """Set value in Redis cache with optional TTL override."""
        client = cls._get_redis_client()
        if client:
            try:
                import json

                client.setex(
                    key, ttl if ttl is not None else cls._CACHE_TTL, json.dumps(value)
                )
            except Exception:
                pass

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.query_count = 0
        self._client = None
        self._llm = None
        self._memory = ConversationMemory(session_id=session_id)
        self._knowledge_graph = SessionManager.get_knowledge_graph()
        self._init_llm()
        self._init_embeddings()  # Pre-warm shared embeddings if not yet done
        if os.environ.get("ENABLE_RERANKER", "false").lower() == "true":
            self._init_reranker()

    @classmethod
    def _init_embeddings(cls):
        """Pre-warm shared embeddings on startup for faster first query."""
        if cls._embeddings is not None:
            return

        if OpenAIEmbeddings is None:
            logger.warning("[Embeddings] langchain-openai not installed")
            return

        try:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if api_key and api_key.startswith("sk-"):
                embedding_model = os.environ.get(
                    "EMBEDDING_MODEL", "text-embedding-3-small"
                )
                cls._embeddings = OpenAIEmbeddings(
                    model=embedding_model, api_key=api_key
                )
                cls._embeddings.embed_query("test")
                logger.info(f"[OK] Shared embeddings pre-warmed ({embedding_model})")
        except Exception as e:
            logger.warning(f"[Embeddings] Pre-warm failed: {e}")

    def _init_llm(self):
        """Initialize LLM - Ollama primary, OpenAI fallback"""
        api_key = os.environ.get("OPENAI_API_KEY", "")

        # Use Ollama if API key is empty or placeholder (not valid)
        if not api_key or api_key in ["", "sk-placeholder", "sk-proj-"]:
            self._model = os.environ.get("MODEL", "glm4:latest")
            self._use_openai = False
            logger.info(f"[OK] LLM initialized: {self._model} (Ollama)")
            return

        # Try OpenAI if key is provided and valid
        if OpenAI is None:
            self._model = os.environ.get("MODEL", "glm4:latest")
            self._use_openai = False
            logger.info(
                f"[OK] LLM initialized: {self._model} (Ollama fallback - OpenAI package missing)"
            )
            return

        try:
            test_client = OpenAI(api_key=api_key)
            test_client.models.list()
            self._model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            self._use_openai = True
            logger.info(f"[OK] LLM initialized: {self._model} (OpenAI)")
        except Exception as e:
            # Fallback to Ollama on any error
            self._model = os.environ.get("MODEL", "glm4:latest")
            self._use_openai = False
            logger.info(f"[OK] LLM initialized: {self._model} (Ollama fallback - {e})")

    @classmethod
    def _init_reranker(cls):
        """Initialize multilingual reranker model (supports en/mr/hi)."""
        if cls._reranker is None and not cls._reranker_checked:
            cls._reranker_checked = True
            if CrossEncoder is None:
                logger.warning(
                    "Reranker warning: sentence-transformers package missing"
                )
                return
            try:
                logger.info(
                    "Loading multilingual reranker (BAAI/bge-reranker-v2-m3)..."
                )
                # Try multilingual reranker first (best for en/mr/hi)
                try:
                    cls._reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
                    logger.info(
                        "[OK] Multilingual reranker loaded (bge-reranker-v2-m3)"
                    )
                except Exception:
                    # Fallback to English-only
                    cls._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                    logger.info("[OK] Reranker loaded (ms-marco fallback)")
            except Exception as e:
                logger.warning(f"Reranker warning (could be memory or CPU limit): {e}")
                cls._reranker = None

    @property
    def client(self):
        if self._client is None:
            if self._use_openai:
                if OpenAI is None:
                    raise ImportError("OpenAI package is required for OpenAI models")
                api_key = os.environ.get("OPENAI_API_KEY", "")
                self._client = OpenAI(api_key=api_key)
            else:
                from langchain_ollama import ChatOllama

                self._client = ChatOllama(model=self._model)
        return self._client

    def _search_web(self, query: str) -> tuple:
        """Search web using SerpApi (primary text) + DuckDuckGo (extra sources, if enabled)."""
        api_key = os.environ.get("SERP_API_KEY", "")
        ddg_enabled = os.environ.get("ENABLE_DDG", "true").lower() == "true"

        with ThreadPoolExecutor(max_workers=2) as executor:
            serp_future = (
                executor.submit(self._search_serpapi, query, api_key)
                if api_key
                else None
            )
            ddg_future = (
                executor.submit(self._search_duckduckgo, query) if ddg_enabled else None
            )

            # Get SerpApi results (primary)
            serp_text, serp_sources = "", []
            if serp_future:
                try:
                    serp_text, serp_sources = serp_future.result(timeout=10)
                except Exception:
                    pass

            # Get DuckDuckGo results (extra sources)
            ddg_text, ddg_sources = "", []
            if ddg_future:
                try:
                    ddg_text, ddg_sources = ddg_future.result(timeout=6)
                except Exception:
                    pass

        combined_text = serp_text or ddg_text
        combined_sources = serp_sources + ddg_sources

        return combined_text, combined_sources[:10]

    def _search_serpapi(self, query: str, api_key: str) -> tuple:
        """Search using SerpApi Google AI Mode. Returns (text, sources_list)."""
        try:
            from serpapi import Client

            client = Client(api_key=api_key)
            results = client.search({"engine": "google_ai_mode", "q": query})

            snippets = []
            sources = []

            if "text_blocks" in results:
                for block in results["text_blocks"][:5]:
                    text = block.get("text", "")
                    if text:
                        snippets.append(text[:500])
                        sources.append(
                            {"title": "Google AI", "url": "", "snippet": text[:200]}
                        )

            if "reconstructed_markdown" in results:
                markdown = results["reconstructed_markdown"]
                if markdown and not snippets:
                    snippets.append(markdown[:1000])

            logger.info(
                f"[Web search] SerpApi returned {len(snippets)} snippets, {len(sources)} sources"
            )
            return "\n\n".join(snippets), sources

        except ImportError:
            logger.warning("[Web search] SerpApi library not installed")
            return "", []
        except Exception as e:
            logger.warning(f"[Web search] SerpApi error: {e}")
            return "", []

    def _search_duckduckgo(self, query: str) -> tuple:
        """Search using DuckDuckGo Instant Answer API (free). Returns (text, sources_list)."""
        try:
            import requests

            # Use DuckDuckGo HTML search (more reliable than instant answer API)
            params = {
                "q": query,
                "kl": "in-en",  # India region
                "kd": "-1",
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            # Try the lite version which is easier to parse
            response = requests.get(
                "https://lite.duckduckgo.com/lite/",
                params=params,
                headers=headers,
                timeout=5,
            )

            if response.status_code != 200:
                logger.warning(
                    f"[Web search] DuckDuckGo returned {response.status_code}"
                )
                return "", []

            # Parse results from HTML
            from html.parser import HTMLParser

            class DDLiteParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self.current = {}
                    self.capture = None
                    self.depth = 0

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == "a" and "href" in attrs_dict:
                        href = attrs_dict["href"]
                        if href.startswith("http") and "duckduckgo" not in href:
                            self.current["url"] = href
                            self.capture = "title"
                    elif (
                        tag == "td" and attrs_dict.get("class", "") == "result-snippet"
                    ):
                        self.capture = "snippet"

                def handle_data(self, data):
                    data = data.strip()
                    if data and self.capture == "title":
                        self.current["title"] = data
                        self.capture = None
                    elif data and self.capture == "snippet":
                        self.current["snippet"] = data
                        if "url" in self.current:
                            self.results.append(self.current.copy())
                        self.current = {}
                        self.capture = None

            parser = DDLiteParser()
            parser.feed(response.text)

            snippets = []
            sources = []
            for r in parser.results[:5]:
                title = r.get("title", "Unknown")
                url = r.get("url", "")
                snippet = r.get("snippet", "")
                snippets.append(f"[{title}] {url}\n{snippet}")
                sources.append({"title": title, "url": url, "snippet": snippet[:200]})

            logger.info(
                f"[Web search] DuckDuckGo returned {len(snippets)} snippets, {len(sources)} sources"
            )
            return "\n\n".join(snippets), sources

        except Exception as e:
            # Suppress connection/timeout errors — expected on cloud hosts (datacenter IP blocks)
            err = str(e).lower()
            if "timeout" not in err and "connect" not in err:
                logger.warning(f"[Web search] DuckDuckGo error: {e}")
            return "", []

    @property
    def vectorstore(self):
        # Fast path: already initialized
        if SessionRAG._vectorstore is not None:
            return SessionRAG._vectorstore
        if SessionRAG._vs_failed:
            return None
        # Slow path: initialize once with double-checked locking
        with SessionRAG._vs_lock:
            if SessionRAG._vectorstore is not None:
                return SessionRAG._vectorstore
            if SessionRAG._vs_failed:
                return None
            if connections is None or Collection is None:
                logger.warning("Vectorstore warning: pymilvus package missing")
                SessionRAG._vs_failed = True
                return None
            try:
                use_lite = os.environ.get("USE_MILVUS_LITE", "false").lower() == "true"
                milvus_host = os.environ.get("MILVUS_HOST", "localhost")
                milvus_port = os.environ.get("MILVUS_PORT", "19530")
                milvus_token = os.environ.get("MILVUS_TOKEN", "")

                if use_lite:
                    # Milvus Lite initialization
                    from milvus_lite import MilvusClient
                    db_path = os.path.join(os.environ.get("DATA_DIR", "data"), "milvus_local.db")
                    logger.info(f"Using Milvus Lite with DB: {db_path}")
                    # Map 'default' alias to the local file for LangChain compatibility
                    connections.connect(alias="default", uri=db_path)
                elif milvus_token:
                    # Cloud connection logic
                    connections.connect(
                        alias="default",
                        host=milvus_host,
                        port=milvus_port,
                        token=milvus_token,
                        secure=True,
                        timeout=30,
                    )
                else:
                    # Standard local docker
                    connections.connect(
                        alias="default", host=milvus_host, port=milvus_port, timeout=15
                    )
                collection_name = os.environ.get("MILVUS_COLLECTION", "dcpr_knowledge")
                vs = Collection(collection_name)
                vs.load()
                SessionRAG._vectorstore = vs
                logger.info(
                    f"[OK] Connected to Milvus collection '{collection_name}' (shared connection)"
                )
            except Exception as e:
                logger.warning(f"Vectorstore connection failed: {e}")
                SessionRAG._vs_failed = True
        return SessionRAG._vectorstore

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding vector with LRU in-process cache + Redis overflow."""
        key = hashlib.sha256(text.encode()).hexdigest()[:16]

        # 1. In-process LRU cache
        with SessionRAG._embed_cache_lock:
            if key in SessionRAG._embed_cache:
                SessionRAG._embed_cache.move_to_end(key)
                return list(SessionRAG._embed_cache[key])

        # 2. Redis cache
        cached = self._get_from_cache(f"emb:{key}")
        if cached:
            with SessionRAG._embed_cache_lock:
                if len(SessionRAG._embed_cache) >= SessionRAG._EMBED_CACHE_MAX:
                    SessionRAG._embed_cache.popitem(last=False)
                SessionRAG._embed_cache[key] = cached
            return cached

        # 3. Compute via API (cache miss)
        if SessionRAG._embeddings is None:
            raise RuntimeError("Embeddings not initialized")
        vec = SessionRAG._embeddings.embed_query(text)
        self._set_in_cache(f"emb:{key}", vec, ttl=86400)  # 24h TTL
        with SessionRAG._embed_cache_lock:
            if len(SessionRAG._embed_cache) >= SessionRAG._EMBED_CACHE_MAX:
                SessionRAG._embed_cache.popitem(last=False)
            SessionRAG._embed_cache[key] = vec
        return vec

    def _search_local(
        self,
        query: str,
        k: int = 10,
        doc_type_filter: str = None,
        precomputed_vector: List[float] = None,
    ):
        """Search local Milvus with full metadata schema."""
        try:
            if not self.vectorstore:
                return []

            query_vec = (
                precomputed_vector
                if precomputed_vector is not None
                else self._get_embedding(query)
            )

            # HNSW search params
            search_params = {"metric_type": "COSINE", "params": {"ef": 256}}

            # Filter by doc_type if specified
            expr = None
            if doc_type_filter:
                expr = f'doc_type == "{doc_type_filter}"'

            # Retrieve metadata alongside text so the synthesizer can cite source + page
            results = self.vectorstore.search(
                data=[query_vec],
                anns_field="embedding",
                param=search_params,
                limit=max(k, 20),
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
                    chunk_type = entity.get("chunk_type", "text")
                    base_score = hit.distance
                    if chunk_type in ("table", "table_row", "schedule"):
                        base_score += 0.08
                    output.append(
                        SearchResult(
                            query=query,
                            text=entity.get("text", ""),
                            score=base_score,
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
                logger.warning(f"[SEARCH] Schema error: collection may need reindexing")
                return []
            logger.warning(f"[SEARCH] Error: {err_msg[:100]}")
            return []

    def _fast_analyze_query(self, question: str) -> Optional[QueryContext]:
        """Fast rule-based analysis for common technical queries - no LLM needed."""
        import re

        q = question.lower()

        # Extract units from question
        units = {}

        # Area extraction
        area_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(sq\.?\s*ft|sqr?\s*ft|sq\.?\s*m|sqm)", q
        )
        if area_match:
            value = float(area_match.group(1))
            unit = area_match.group(2)
            if "sqm" in unit or "sq m" in unit:
                units["sq_m"] = value
            else:
                units["sq_ft"] = value

        # Road width extraction
        road_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|meter|metre)", q)
        if road_match:
            units["road_width"] = float(road_match.group(1))

        # Building height extraction
        height_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:m|meter|metre|mt|mt\.)\s*(?:high|height)", q
        )
        if not height_match:
            height_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|meter|metre)\s*$", q)
        if height_match:
            units["building_height"] = float(height_match.group(1))

        # Determine topic
        topic = "general"
        if "fsi" in q:
            topic = "FSI"
        elif "margin" in q or "setback" in q:
            topic = "Margins"
        elif "parking" in q:
            topic = "Parking"
        elif "height" in q:
            topic = "Building Height"
        elif "tdr" in q:
            topic = "TDR"
        elif "premium" in q:
            topic = "Premium FSI"
        elif "ground coverage" in q:
            topic = "Ground Coverage"

        # Detect location
        location = "Mumbai"
        if any(loc in q for loc in ["mumbai", "navi mumbai", "thane", "nagpur"]):
            location = next(
                loc.title()
                for loc in ["mumbai", "navi mumbai", "thane", "nagpur"]
                if loc in q
            )

        # Determine intent
        intent = "technical_lookup"
        if any(
            word in q
            for word in [
                "invest",
                "roi",
                "profit",
                "return",
                "market",
                "rate",
                "price",
                "cost",
            ]
        ):
            intent = "feasibility_analysis"

        return QueryContext(
            original_query=question,
            intent=intent,
            entities=[],
            clauses=[],
            topic=topic,
            subtopics=[],
            is_compound=False,
            compound_parts=[],
            location=location,
            units=units,
            needs_market_data="market" in q or "rate" in q or "price" in q,
            needs_regulatory_data=True,
            is_technical=True,
        )

    def _analyze_query(self, question: str, history_context: str = "") -> QueryContext:
        """Analyze query to extract intent, entities, topic, location and units"""
        import time

        # Check if query is likely technical (cacheable)
        question_lower = question.lower()
        is_likely_technical = any(
            kw in question_lower
            for kw in [
                "fsi",
                "margin",
                "setback",
                "parking",
                "height",
                "tdr",
                "premium",
                "road width",
                "ground coverage",
                "basement",
                "stilt",
                "regulations",
            ]
        )

        # FAST PATH: Skip LLM for simple well-known technical queries
        # These patterns are common and don't need LLM analysis
        if is_likely_technical:
            fast_context = self._fast_analyze_query(question)
            if fast_context:
                # Cache the fast result
                qctx_key = f"qctx:{hashlib.sha256(question.lower().strip().encode()).hexdigest()[:16]}"
                self._set_in_cache(qctx_key, dataclasses.asdict(fast_context), ttl=7200)
                return fast_context

        # Cache context-free analyses (deterministic for same question + no history)
        # Also cache technical queries regardless of history (they're deterministic)
        if not history_context or is_likely_technical:
            qctx_key = f"qctx:{hashlib.sha256(question.lower().strip().encode()).hexdigest()[:16]}"
            cached = self._get_from_cache(qctx_key)
            if cached:
                try:
                    return QueryContext(**cached)
                except Exception:
                    pass  # fall through to LLM call if cached data is stale
        elif history_context:
            # Use in-memory cache for queries with history
            qctx_key = f"qctx:{hashlib.sha256((question.lower() + history_context[:100]).encode()).hexdigest()[:16]}"
            with SessionRAG._vs_lock:
                if qctx_key in SessionRAG._qctx_cache:
                    cached = SessionRAG._qctx_cache[qctx_key]
                    # Check TTL (stored as tuple: (data, timestamp))
                    if (
                        isinstance(cached, tuple)
                        and time.time() - cached[1] < SessionRAG._QCTX_CACHE_TTL
                    ):
                        try:
                            return QueryContext(**cached[0])
                        except Exception:
                            pass
                    elif isinstance(cached, dict):
                        try:
                            return QueryContext(**cached)
                        except Exception:
                            pass

        prompt = f"""Analyze this query about urban planning/real estate in India:

Query: {question}
History: {history_context}

Return JSON with:
- "intent": "technical_lookup" (for margins, FSI, parking, height, or specific rules), "feasibility_analysis" (for ROI, investment, or general project viability), or "explain".
- "is_technical": true if the query is about specific regulations, numbers, or rules.
- "entities": Key entities mentioned - include ALL of: Mumbai area/locality names (Andheri, Bandra, Goregaon, Borivali, etc.), FSI, TDR, Premium, Scheme numbers (33(7B), 33(11), etc.), road widths, zone types (residential, commercial, industrial).
- "topic": Main topic (e.g., "Side Margins", "FSI", "Parking", "TDR", "Premium", "Plot Feasibility", "Market Analysis").
- "subtopics": Related topics.
- "location": Specific area/locality mentioned in Mumbai (e.g., "Andheri", "Bandra", "Goregaon"). Extract city only if explicitly stated. Default to "Mumbai" if not specified.
- "units": Extract area, building height, and road width from query. Convert sq ft to sq m.
   Example: if query has "2000 sq ft", return {{"original": "2000 sq ft", "sq_m": 185.8, "road_width": null}}
   Example: if query has "12m road", return {{"road_width": 12}}
   Example: if query has "15m height", return {{"building_height": 15}}
- "is_compound": true if multiple questions.
- "compound_parts": list of sub-questions if compound.
- "needs_market_data": true ONLY if query explicitly asks about prices, rates, ROI, investment potential, or current market conditions.
- "needs_regulatory_data": true if query asks about FSI, regulations, permissions, compliance, zoning rules.

IMPORTANT: If the query is about "side margins", "setbacks", "height limits", or "FSI tables", it is a TECHNICAL lookup.
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
            data = json.loads(response.choices[0].message.content)
            entities = data.get("entities", [])
            if isinstance(entities, bool) or entities is None:
                entities = []
            elif isinstance(entities, str):
                entities = [entities]
            elif isinstance(entities, dict):
                entities = list(entities.values())
            elif not isinstance(entities, list):
                entities = []

            subtopics = data.get("subtopics", [])
            if isinstance(subtopics, bool) or subtopics is None:
                subtopics = []
            elif isinstance(subtopics, str):
                subtopics = [subtopics]
            elif not isinstance(subtopics, list):
                subtopics = []

            compound_parts = data.get("compound_parts", [])
            if isinstance(compound_parts, bool) or compound_parts is None:
                compound_parts = []
            elif isinstance(compound_parts, str):
                compound_parts = [compound_parts]
            elif not isinstance(compound_parts, list):
                compound_parts = []

            units = data.get("units", {})
            if isinstance(units, bool) or units is None:
                units = {}
            elif isinstance(units, str):
                try:
                    units = json.loads(units)
                except:
                    units = {}
            elif not isinstance(units, dict):
                units = {}

            result = QueryContext(
                original_query=question,
                intent=str(data.get("intent", "explain"))
                if data.get("intent")
                else "explain",
                entities=entities,
                clauses=[],
                topic=str(data.get("topic", "general"))
                if data.get("topic")
                else "general",
                subtopics=subtopics,
                is_compound=bool(data.get("is_compound", False)),
                compound_parts=compound_parts,
                location=str(data.get("location", "Mumbai"))
                if data.get("location")
                else "Mumbai",
                units=units,
                needs_market_data=bool(data.get("needs_market_data", False)),
                needs_regulatory_data=bool(data.get("needs_regulatory_data", True)),
                is_technical=bool(data.get("is_technical", False)),
            )
            if not history_context:
                self._set_in_cache(qctx_key, dataclasses.asdict(result), ttl=7200)
            else:
                # Cache in memory for queries with history
                import time

                with SessionRAG._vs_lock:
                    SessionRAG._qctx_cache[qctx_key] = (
                        dataclasses.asdict(result),
                        time.time(),
                    )
                    # Evict old entries if cache is full
                    if len(SessionRAG._qctx_cache) > SessionRAG._QCTX_CACHE_MAX:
                        SessionRAG._qctx_cache.popitem(last=False)
            return result
        except Exception as e:
            logger.error(f"Query analysis error: {e}", exc_info=True)
            return QueryContext(
                original_query=question,
                intent="explain",
                entities=[],
                clauses=[],
                topic="general",
                subtopics=[],
                is_compound=False,
                compound_parts=[],
                location="Mumbai",
                units={},
                needs_market_data=False,
                needs_regulatory_data=True,
                is_technical=False,
            )

    def _expand_queries(self, context: QueryContext) -> List[str]:
        """Expand query for better retrieval using location, units, and language."""
        queries = [context.original_query]

        location = context.location or "Mumbai"
        reg_type = "DCPR 2034"

        # Detect if query is in Devanagari script
        query_str = str(context.original_query) if context.original_query else ""
        has_devanagari = any("\u0900" <= c <= "\u097f" for c in query_str)

        # If Devanagari query, also add English equivalent terms
        if has_devanagari:
            devanagari_to_english = {
                "एफएसआय": "FSI",
                "एफएसआई": "FSI",
                "फ्लोर स्पेस इंडेक्स": "FSI",
                "पार्किंग": "parking",
                "वाहनतळ": "parking",
                "प्रीमियम": "premium",
                "अतिरिक्त": "additional",
                "पुनर्विकास": "redevelopment",
                "हस्तांतरणीय": "transferable",
                "उंची": "height",
                "मजला": "storey",
                "अंतर": "marginal distance",
                "सेटबॅक": "setback",
                "तालिका": "table",
                "धारा": "clause",
                "नियम": "regulation",
                "कलम": "clause",
                "निवासी": "residential",
                "व्यावसायिक": "commercial",
            }
            eng_terms = []
            for dev, eng in devanagari_to_english.items():
                query_str = (
                    str(context.original_query).lower()
                    if context.original_query
                    else ""
                )
                if dev in query_str:
                    eng_terms.append(eng)
            if eng_terms:
                queries.append(f"{' '.join(eng_terms)} {reg_type}")
            # Also add the query with just English terms
            queries.append(f"{reg_type} {context.topic} regulations")

        # Extract locality names from entities (e.g., Andheri, Bandra)
        entity_list = context.entities if isinstance(context.entities, list) else []
        entity_list = [e for e in entity_list if isinstance(e, str)]
        localities = [e for e in entity_list if e and len(e) > 2 and e[0].isupper()]

        # Topic-prioritized expansion terms. Leading with the detected topic
        # keeps retrieval on-topic — otherwise generic FSI expansions drown
        # margins/parking/height queries.
        topic_terms = {
            "Margins": [
                "side and rear marginal open space",
                "marginal distance height of building",
                "setback Clause 41",
            ],
            "Parking": ["parking requirement", "vehicle parking Table", "car parking"],
            "Building Height": [
                "height of building",
                "maximum permissible height",
                "height regulation",
            ],
            "TDR": ["TDR", "transferable development rights"],
            "Premium FSI": ["premium FSI", "additional FSI on payment of premium"],
            "Ground Coverage": ["ground coverage", "buildable area"],
            "FSI": ["FSI", "floor space index", "permissible FSI"],
            "Dimensions": [
                "Table 14 minimum size width habitable room Clause 37",
                "bathroom water closet W.C. minimum size sq.m width m",
                "kitchen habitable room minimum dimensions Clause 37",
            ],
        }.get(context.topic, ["FSI", "parking", "marginal distance"])

        # Dimension keyword fallback — the query-analysis LLM does not
        # always label room-dimension questions as topic="Dimensions", so
        # keyword-match the original query and force the Clause 37 /
        # Table 14 expansions into the retrieval set. This surfaces the
        # authoritative minimum-size-and-width table for WC, bathroom,
        # kitchen, habitable room, and classroom queries.
        dim_keywords = (
            "toilet", "bathroom", "water closet", "w.c", "urinal",
            "kitchen", "habitable room", "minimum size", "minimum width",
            "minimum dimension", "room size", "room dimension",
        )
        qs = str(context.original_query or "").lower()
        if any(kw in qs for kw in dim_keywords):
            dim_terms = [
                "Table 14 minimum size width habitable room Clause 37",
                "bathroom water closet W.C. minimum size sq.m width m",
                "kitchen habitable room minimum dimensions Clause 37",
            ]
            for term in dim_terms:
                if term not in topic_terms:
                    topic_terms = [term, *topic_terms]

        for term in topic_terms[:3]:
            queries.append(f"{term} {reg_type}")
            if localities:
                queries.append(f"{term} {localities[0]} {reg_type}")

        # Topic-specific queries
        if context.topic:
            queries.append(f"{context.topic} {reg_type} regulations")
            if localities:
                queries.append(f"{context.topic} {localities[0]}")

        # Entity queries
        if entity_list:
            for entity in entity_list[:3]:
                if isinstance(entity, str):
                    queries.append(f"{entity} {reg_type}")

        # Unit-based query (CRITICAL for FSI)
        if context.units and "sq_m" in context.units:
            sq_m = context.units["sq_m"]
            queries.append(f"FSI for plot area {sq_m} sq m {reg_type}")
            queries.append(f"FSI table for plots up to {sq_m} sq m")

        # Road width queries
        if context.units and "road_width" in context.units:
            rw = context.units["road_width"]
            queries.append(f"FSI road width {rw} meters {reg_type}")

        return queries[:8]

    def _multi_search(
        self, queries: List[str], context: QueryContext, k: int
    ) -> List[SearchResult]:
        """Search multiple queries with batched embedding and combine results."""
        all_results = []
        seen_texts = set()

        unique_queries = list(dict.fromkeys(queries))  # preserve order, deduplicate

        # Pre-compute embeddings: check cache per query, batch-embed all misses in one API call
        query_vecs: Dict[str, List[float]] = {}
        misses: List[str] = []
        for q in unique_queries:
            key = hashlib.sha256(q.encode()).hexdigest()[:16]
            with SessionRAG._embed_cache_lock:
                if key in SessionRAG._embed_cache:
                    SessionRAG._embed_cache.move_to_end(key)
                    query_vecs[q] = list(SessionRAG._embed_cache[key])
                    continue
            cached = self._get_from_cache(f"emb:{key}")
            if cached:
                query_vecs[q] = cached
                with SessionRAG._embed_cache_lock:
                    if len(SessionRAG._embed_cache) >= SessionRAG._EMBED_CACHE_MAX:
                        SessionRAG._embed_cache.popitem(last=False)
                    SessionRAG._embed_cache[key] = cached
            else:
                misses.append(q)

        if misses and SessionRAG._embeddings is not None:
            try:
                vecs = SessionRAG._embeddings.embed_documents(misses)
                for q, vec in zip(misses, vecs):
                    query_vecs[q] = vec
                    key = hashlib.sha256(q.encode()).hexdigest()[:16]
                    self._set_in_cache(f"emb:{key}", vec, ttl=86400)
                    with SessionRAG._embed_cache_lock:
                        if len(SessionRAG._embed_cache) >= SessionRAG._EMBED_CACHE_MAX:
                            SessionRAG._embed_cache.popitem(last=False)
                        SessionRAG._embed_cache[key] = vec
            except Exception as e:
                logger.error(f"[Embed] Batch embed error: {e}", exc_info=True)

        for query in queries:
            try:
                results = self._search_local(
                    query, k=k, precomputed_vector=query_vecs.get(query)
                )
                for rank, r in enumerate(results):
                    if r.text and r.text not in seen_texts:
                        seen_texts.add(r.text)
                        r.relevance_tags = [context.topic]
                        r.query = query
                        r.rank_in_query = rank
                        all_results.append(r)
            except Exception as e:
                logger.error(f"Search error for '{query}': {e}", exc_info=True)

        # Reciprocal Rank Fusion (RRF) - combines results from multiple queries
        # A chunk appearing in multiple query results gets higher score
        K_RRF = 60
        rrf_scores: Dict[str, float] = {}
        text_to_result: Dict[str, SearchResult] = {}

        for r in all_results:
            if r.text not in text_to_result:
                text_to_result[r.text] = r

        # Calculate RRF scores based on rank position in each query's results
        for r in all_results:
            rank = getattr(r, 'rank_in_query', 0)
            query_key = r.query if hasattr(r, 'query') else 'unknown'
            rrf_scores[r.text] = rrf_scores.get(r.text, 0) + 1.0 / (rank + K_RRF)

        # Combine cosine scores with RRF (0.6 cosine + 0.4 RRF)
        max_rrf = max(rrf_scores.values()) if rrf_scores else 1.0
        combined_results = []
        for text, rrf_score in rrf_scores.items():
            r = text_to_result[text]
            normalized_rrf = rrf_score / max_rrf if max_rrf > 0 else 0
            combined_score = 0.6 * r.score + 0.4 * normalized_rrf
            combined_results.append((combined_score, r))

        combined_results.sort(key=lambda x: x[0], reverse=True)
        fused_results = [r for _, r in combined_results[:k * 2]]

        return fused_results

    def _rerank_results(
        self, question: str, results: List[SearchResult]
    ) -> List[SearchResult]:
        """Re-rank results using cross-encoder with pre-filtering and timeout guard."""
        if not self._reranker or not results:
            return results

        # Pre-filter: rerank candidates above lower threshold, cap at 25 for better recall
        candidates = [r for r in results if r.score > 0.20][:25]
        if not candidates:
            candidates = results[:25]  # keep top-25 if all below threshold

        try:
            pairs = [(question, r.text) for r in candidates]
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(self._reranker.predict, pairs)
                try:
                    scores = future.result(timeout=2.0)
                except TimeoutError:
                    logger.warning("[Rerank] Timeout — falling back to cosine scores")
                    return results  # return original order on timeout
            for i, r in enumerate(candidates):
                r.score = float(scores[i])
            candidates.sort(key=lambda x: x.score, reverse=True)
            # Append any results that were filtered out, keeping their original order
            filtered_out = [r for r in results if r not in candidates]
            return candidates + filtered_out
        except Exception as e:
            logger.error(f"Rerank error: {e}", exc_info=True)
            return results

    def query(self, question: str, k: int = 20) -> Dict:
        """Main query method with parallel RAG + web search retrieval."""
        question = str(question)
        start_time = time.time()
        self.query_count += 1
        thought_process = []

        logger.info(f"[QUERY] Processing: {question}")

        # Check cache first (Redis or in-memory fallback)
        cache_key = (
            f"query:{hashlib.sha256(question.lower().strip().encode()).hexdigest()}"
        )

        # Try Redis cache first
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.info(f"[CACHE HIT] Returning cached response for: {question}")
            return cached_result

        thought_process.append(f"Received query: '{question}'")

        history_context = self._memory.get_context_for_query(question)
        if history_context:
            thought_process.append("Retrieved conversation history for context.")

        # 1. Analyze Query
        thought_process.append("Analyzing query intent and extracting entities...")
        context = self._analyze_query(question, history_context)
        thought_process.append(
            f"Detected intent: {context.intent}, Topic: {context.topic}"
        )

        # 2. Parallel Retrieval: RAG + Web Search concurrently
        search_queries = self._expand_queries(context)
        web_enabled = os.environ.get("ENABLE_WEB_SEARCH", "true").lower() == "true"

        thought_process.append("Executing parallel retrieval (RAG + Web Search)...")

        # Web search timeout (seconds)
        WEB_SEARCH_TIMEOUT = int(
            os.environ.get("WEB_SEARCH_TIMEOUT", "8")
        )  # Slightly longer for multiple searches

        max_workers = 4 if web_enabled else 2
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Main RAG search
            rag_future = executor.submit(self._multi_search, search_queries, context, k)

            # Web search (only if enabled)
            web_future = (
                executor.submit(self._search_web, question) if web_enabled else None
            )

            # Proactive enhanced web search for market/investment data
            enhanced_web_query = f"{context.location} {context.topic} property rates price per sqft 2025 2026 investment commercial IT parks yields"
            enhanced_web_future = (
                executor.submit(self._search_web, enhanced_web_query)
                if web_enabled
                else None
            )

            # Specific yield search
            yield_query = f"{context.location} commercial property rental yields percentage IT companies 2025"
            yield_future = (
                executor.submit(self._search_web, yield_query) if web_enabled else None
            )

            # Wait for local RAG
            local_results = rag_future.result()
            thought_process.append(
                f"Retrieved {len(local_results)} local candidate chunks."
            )

            # Collect all web results
            web_context = ""
            web_sources = []

            # 1. Main web search result
            if web_enabled and web_future:
                try:
                    main_web_text, main_web_srcs = web_future.result(
                        timeout=WEB_SEARCH_TIMEOUT
                    )
                    if main_web_text:
                        web_context += main_web_text + "\n\n"
                        web_sources.extend(main_web_srcs)
                except Exception as e:
                    logger.warning(f"[Web Search] Main search error: {e}")

            # 2. Enhanced web search result
            if web_enabled and enhanced_web_future:
                try:
                    enh_web_text, enh_web_srcs = enhanced_web_future.result(
                        timeout=WEB_SEARCH_TIMEOUT
                    )
                    if enh_web_text:
                        web_context += enh_web_text + "\n\n"
                        web_sources.extend(enh_web_srcs)
                        thought_process.append(
                            "Enhanced market data retrieved via web."
                        )
                except Exception:
                    pass

            # 3. Yield search result
            if web_enabled and yield_future:
                try:
                    yld_web_text, yld_web_srcs = yield_future.result(
                        timeout=WEB_SEARCH_TIMEOUT
                    )
                    if yld_web_text:
                        web_context += yld_web_text + "\n\n"
                        web_sources.extend(yld_web_srcs)
                except Exception:
                    pass

            if web_enabled and web_sources:
                logger.info(
                    f"\n[Web Search] Found {len(web_sources)} total sources (Parallelized)"
                )
                thought_process.append(
                    f"Web search completed. Found {len(web_sources)} sources."
                )
            elif web_enabled:
                thought_process.append("Web search returned no results or timed out.")
            else:
                thought_process.append(
                    "Web search disabled via ENABLE_WEB_SEARCH setting."
                )

        # 3. Re-rank combined results (local + web)
        if self._reranker and (local_results or web_context):
            thought_process.append("Re-ranking combined results...")
            all_for_rerank = list(local_results)
            if web_context and web_sources:
                # Add web results as SearchResult for reranking
                for ws in web_sources[:3]:
                    all_for_rerank.append(
                        SearchResult(
                            query=question,
                            text=ws.get("snippet", ""),
                            score=0.5,
                            clauses=[],
                            tables=[],
                            relevance_tags=["web"],
                            result_type="web",
                            web_url=ws.get("url", ""),
                        )
                    )
            reranked = self._rerank_results(question, all_for_rerank)
            # Split back: local ones keep their metadata, web ones stay at bottom
            local_results = [r for r in reranked if r.result_type == "local"]
            web_reranked = [r for r in reranked if r.result_type == "web"]

        # 4. Synthesis & Comparison
        thought_process.append("Synthesizing information from sources...")
        synthesis = self._synthesize_all(question, local_results, web_context, context)

        # 5. Generate Dynamic Answer with citations
        thought_process.append("Generating final response...")
        answer = self._generate_dynamic_answer(
            question, local_results, web_context, synthesis, context
        )

        confidence = self._calculate_confidence(local_results, synthesis)
        all_clauses = list(set([c for r in local_results for c in r.clauses]))
        all_tables = list(set([t for r in local_results for t in r.tables]))
        suggestions = self._generate_suggestions(question, context, all_clauses)

        self._memory.add("user", question)
        self._memory.add("assistant", answer)

        total_time = time.time() - start_time
        logger.info(f"[QUERY COMPLETE] Total time: {total_time:.2f}s")

        return {
            "query": question,
            "answer": answer,
            "session_id": self.session_id,
            "thought_process": thought_process,
            "sources": [
                {
                    "text": r.text[:300],
                    "score": r.score,
                    "source": r.source,
                    "page": r.page,
                    "doc_type": r.doc_type,
                    "result_type": r.result_type,
                    "web_url": r.web_url,
                }
                for r in local_results[:5]
            ],
            "web_sources": web_sources[:5] if web_sources else [],
            "clauses_found": all_clauses[:15],
            "tables_found": all_tables[:10],
            "suggestions": suggestions,
            "confidence": confidence,
            "conversation_history": self._memory.get_history(),
            "total_time": total_time,
            "retrieval_stats": {
                "local_results": len(local_results),
                "web_results": len(web_sources) if web_sources else 0,
                "queries_expanded": len(search_queries),
            },
        }

        # Store in Redis cache
        self._set_in_cache(cache_key, results)

        return results

    def _synthesize_all(
        self, question: str, local_results: List, web_context: str, context: Dict
    ) -> Dict:
        # Extract query parameters for conditional lookups
        import re

        area_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft|sqr?\s*ft|sq\.?\s*m)", question.lower()
        )
        road_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|meter)", question.lower())

        query_params = {
            "area_sqft": float(area_match.group(1)) if area_match else None,
            "road_width_m": float(road_match.group(1)) if road_match else None,
            "location": "mumbai" if "mumbai" in question.lower() else None,
        }

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
{web_context if web_context else "No web search results."}

INSTRUCTIONS:
- If area and road_width are detected, look up the relevant FSI tables in the documents
- Identify which regulation/table applies
- Compare local vs web sources

Return JSON:
{{
  "comparison": "Brief comparison of sources",
  "key_parameters": {{
    "area": "detected or estimated from question",
    "road_width": "detected or assumed standard (9m default)",
    "zone_type": "detected or residential default"
  }},
  "applicable_regulations": ["list of regulation numbers that apply"],
  "fsi_data": {{
    "base_fsi": "value from tables",
    "max_fsi": "maximum allowed",
    "premium_fsi": "if applicable"
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
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Synthesis error: {e}", exc_info=True)
            return {
                "comparison": "Error in synthesis",
                "key_parameters": {},
                "applicable_regulations": [],
                "fsi_data": {},
                "missing_info": [],
            }

    def stream_query(self, question: str, k: int = 10):
        """Streaming version with parallel RAG + web search retrieval."""
        import time

        question = str(question)
        self.query_count += 1
        thought_steps = []

        t0 = time.time()
        history_context = self._memory.get_context_for_query(question)
        t1 = time.time()
        logger.debug(f"[TIMING] Memory context: {t1 - t0:.2f}s")

        context = self._analyze_query(question, history_context)
        t2 = time.time()
        logger.debug(f"[TIMING] Query analysis: {t2 - t1:.2f}s")
        thought_steps.append(
            f"Identified intent: {context.intent}, topic: {context.topic}"
        )
        yield json.dumps({"type": "thought_process", "steps": thought_steps}) + "\n"

        # 2. Expand queries
        search_queries = self._expand_queries(context)
        t3 = time.time()
        logger.debug(f"[TIMING] Query expansion: {t3 - t2:.2f}s")
        thought_steps.append(f"Expanded to {len(search_queries)} search queries")
        yield json.dumps({"type": "thought_process", "steps": thought_steps}) + "\n"

        # 3. Parallel Retrieval: RAG + Web Search concurrently
        thought_steps.append("Executing parallel retrieval (RAG + Web Search)...")
        yield json.dumps({"type": "thought_process", "steps": thought_steps}) + "\n"

        web_enabled = os.environ.get("ENABLE_WEB_SEARCH", "true").lower() == "true"

        # Check search result cache first
        cache_key = hashlib.sha256(
            ("+".join(sorted(search_queries)) + str(k)).encode()
        ).hexdigest()[:16]

        # Check cache briefly
        cached_local = None
        with SessionRAG._search_cache_lock:
            cached_local = SessionRAG._search_cache.get(cache_key)

        max_workers = 4 if web_enabled else 2
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # RAG search (only if not cached)
            rag_future = None
            if cached_local is None:
                rag_future = executor.submit(
                    self._multi_search, search_queries, context, k
                )

            # Web search (only if enabled)
            if web_enabled:
                logger.debug("[Web Search] Submitting parallel web search...")
                web_future = executor.submit(self._search_web, question)

                # Additional market web search
                enhanced_web_query = f"{context.location} {context.topic} property rates price per sqft 2025 2026 investment"
                enhanced_future = executor.submit(self._search_web, enhanced_web_query)

                # Specific yield search
                yield_query = f"{context.location} commercial property rental yields percentage 2025"
                yield_future = executor.submit(self._search_web, yield_query)
            else:
                web_future = None
                enhanced_future = None
                yield_future = None

            # Get RAG results
            if cached_local is not None:
                local_results = cached_local
                logger.debug(f"[TIMING] Multi-search RAG: cached (0.00s)")
            else:
                t4 = time.time()
                local_results = rag_future.result()
                t5 = time.time()
                logger.debug(f"[TIMING] Multi-search RAG: {t5 - t4:.2f}s")
                logger.info(
                    f"[RAG] Retrieved {len(local_results)} chunks from vector store"
                )
                # Cache the results briefly
                with SessionRAG._search_cache_lock:
                    if len(SessionRAG._search_cache) >= SessionRAG._SEARCH_CACHE_MAX:
                        SessionRAG._search_cache.popitem(last=False)
                    SessionRAG._search_cache[cache_key] = local_results

            thought_steps.append(f"Found {len(local_results)} local results")

            # Get Web results
            web_context = ""
            web_sources = []
            if web_enabled:
                try:
                    # 1. Main web search
                    if web_future:
                        res1_text, res1_srcs = web_future.result(timeout=8)
                        if res1_text:
                            web_context += res1_text + "\n\n"
                            web_sources.extend(res1_srcs)

                    # 2. Enhanced search
                    if enhanced_future:
                        res2_text, res2_srcs = enhanced_future.result(timeout=8)
                        if res2_text:
                            web_context += res2_text + "\n\n"
                            web_sources.extend(res2_srcs)

                    # 3. Yield search
                    if yield_future:
                        res3_text, res3_srcs = yield_future.result(timeout=8)
                        if res3_text:
                            web_context += res3_text + "\n\n"
                            web_sources.extend(res3_srcs)

                except Exception as e:
                    logger.warning(f"[Web Search] Error: {e}")
            else:
                thought_steps.append(
                    "Web search disabled via ENABLE_WEB_SEARCH setting."
                )

        # 4. Rerank combined results
        # Skip reranking if: reranker not loaded OR technical query with high score
        skip_rerank = (
            not self._reranker  # Reranker not enabled
            or (
                context.is_technical and local_results and local_results[0].score > 0.7
            )  # Already relevant
        )
        if not self._reranker:
            pass
        elif skip_rerank:
            logger.debug(f"[TIMING] Reranking: skipped (technical query, high score)")
        elif local_results:
            thought_steps.append("Reranking results...")
            yield json.dumps({"type": "thought_process", "steps": thought_steps}) + "\n"
            t6 = time.time()
            local_results = self._rerank_results(question, local_results)
            t7 = time.time()
            logger.debug(f"[TIMING] Reranking: {t7 - t6:.2f}s")

        # 5. Synthesis
        thought_steps.append("Synthesizing answer from sources...")
        yield json.dumps({"type": "thought_process", "steps": thought_steps}) + "\n"

        # CRITICAL: Compute synthesis before yielding metadata/starting stream
        synthesis = self._synthesize_all(question, local_results, web_context, context)

        # Yield metadata
        metadata = {
            "type": "metadata",
            "session_id": self.session_id,
            "sources": [
                {
                    "text": r.text[:200],
                    "source": r.source,
                    "page": r.page,
                    "doc_type": r.doc_type,
                }
                for r in local_results[:5]
            ],
            "web_sources": web_sources[:5] if web_sources else [],
            "comparison": synthesis.get("comparison", ""),
            "thought_process": thought_steps,
        }
        yield json.dumps(metadata) + "\n"

        # Stream the Answer
        full_answer = ""
        for chunk in self._stream_dynamic_answer(
            question, local_results, web_context, synthesis, context, web_sources
        ):
            full_answer += chunk
            yield json.dumps({"type": "content", "content": chunk}) + "\n"

        # Finalize
        self._memory.add("user", question)
        self._memory.add("assistant", full_answer)

        final_data = {
            "type": "final",
            "confidence": self._calculate_confidence(local_results, synthesis),
            "suggestions": self._generate_suggestions(
                question,
                context,
                list(set([c for r in local_results for c in r.clauses])),
            ),
            "thought_process": thought_steps,
        }
        yield json.dumps(final_data) + "\n"

    def _generate_dynamic_answer(
        self,
        question: str,
        local_results: List[SearchResult],
        web_context: str,
        synthesis: Dict,
        context: QueryContext,
        web_sources: List[Dict] = None,
    ) -> str:
        """Generate answer with proper citations from source metadata."""
        # Build context with source metadata for each result. Keep per-doc text
        # long enough for DCPR tables (margins/FSI tables often exceed 800 chars).
        # Use a wider window (10) than the old 6 so tables that rerank below
        # the top few still reach the model.
        local_text = "\n\n".join(
            [
                f"[Doc {i + 1}] Source: {r.source}, Page: {r.page}\n{r.text[:2500]}"
                for i, r in enumerate(local_results[:12])
                if r.text
            ]
        )

        # Build citations with actual source info - include web titles
        citations = []
        for i, r in enumerate(local_results[:10]):
            if r.source:
                page_info = f", p.{r.page}" if r.page else ""
                citations.append(f"[Doc {i + 1}] {r.source}{page_info}")
            else:
                source_preview = r.text[:60].replace("\n", " ").strip() + "..."
                citations.append(f"[Doc {i + 1}] {source_preview}")

        # Build web source citations - use actual titles from search
        web_citations = []
        if web_sources:
            for i, s in enumerate(web_sources[:5]):
                title = s.get("title", "Unknown")[:40]
                url = s.get("url", "")
                web_citations.append(f"[Web {i + 1}] {title} - {url}")

        all_citations = citations + web_citations
        citations_text = (
            "\n".join(all_citations) if all_citations else "No sources available"
        )

        # Different prompts for different query types
        is_comparison = any(
            word in question.lower()
            for word in [
                "best",
                "top",
                "compare",
                "areas",
                "hubs",
                "list",
                "recommend",
                "vs",
                "versus",
            ]
        )
        # If it's technical, ALWAYS use the technical consultant persona, even if market data is needed
        is_market_analysis = (
            context.needs_market_data or context.intent == "feasibility_analysis"
        )

        if context.is_technical or context.intent == "technical_lookup":
            # Technical Regulatory Query (Like Google AI Search)
            prompt = f"""You are a senior Urban Planning Consultant on DCPR 2034 for Mumbai.
Provide a high-precision answer based strictly on the regulations.

Question: {question}
Location: {context.location or "Mumbai"}
Parameters: {context.units}

REGULATION EXCERPTS:
{local_text}

WEB CONTEXT:
{web_context[:2000] if web_context else "No web results"}

{DCPR_ANSWER_RULES}

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

{DCPR_ANSWER_RULES}

EXTRA (ranked-list formatting):
- One compact section per area with: price/sqft, key feature, rental yield.
- Cite web results as [Web N] inline at the end of each area block; for
  regulatory claims use the "— as per DCPR 2034..." inline citation.
- If a metric is missing for an area, omit that metric — do not write "Data
  not available" and do not fabricate numbers.
"""
        elif context.needs_market_data or context.intent == "feasibility_analysis":
            # Feasibility/Investment query - prioritize web data, give market specifics
            prompt = f"""You are a real estate investment advisor for Mumbai. Provide a focused feasibility analysis.

Question: {question}
Location: {context.location or "Mumbai"}

WEB SEARCH RESULTS (PRIORITY - include specific prices, rates, consultants):
{web_context[:3000] if web_context else "No web results"}

REGULATORY DATA (from local documents):
{local_text if local_text else "No local regulatory data"}

{DCPR_ANSWER_RULES}

EXTRA (feasibility formatting):
- Lead with one line of market data (price/sqft, yield) if web results contain
  it, then one line of regulatory position (FSI/permit) from DCPR excerpts.
- Cite web data as [Web N]; cite DCPR data using the inline "— as per DCPR
  2034, Regulation <X>, p.<N>" form.
- End with a single actionable next step — no multi-paragraph closers.
"""
        else:
            # Standard regulatory query
            prompt = f"""You are a Mumbai urban planning expert answering a DCPR 2034 question.

Question: {question}
Parameters: Area={context.units.get("original") if context.units else "not specified"}, Road Width={context.units.get("road_width", "9m (default)")}, Location={context.location or "Mumbai"}

DCPR 2034 Regulations:
{local_text[:2500]}

Web Search:
{web_context[:3000] if web_context else "None"}

{DCPR_ANSWER_RULES}

EXTRA:
- Open with the direct answer in one sentence.
- No LaTeX, no section headers, no "Conclusion" block. Markdown tables ARE allowed and REQUIRED when rule 4 (multi-variant comparison) applies.
"""
        try:
            # Use gpt-4o for best quality when OpenAI is available
            answer_model = "gpt-4o" if self._use_openai else self._model
            response = self.client.chat.completions.create(
                model=answer_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Mumbai DCPR 2034 expert. Answer ONLY what is asked, in under 6 short sentences, with exact numbers from the DCPR excerpts. End each factual paragraph with an inline citation of the form '— as per DCPR 2034, Regulation <X>, p.<N>'. For tables, include every field the final value depends on or omit the table entirely — never use placeholder values like 'Varies', 'N/A', or 'Available on request'. If data is missing, say so in one line.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            answer = response.choices[0].message.content.strip()

            # Add sources section if not already present
            if "Sources:" not in answer and citations:
                answer += "\n\n**Sources:**\n" + "\n".join(citations)

            return answer
        except Exception as e:
            return f"Error generating answer: {str(e)}"

    def _stream_dynamic_answer(
        self,
        question: str,
        local_results: List[SearchResult],
        web_context: str,
        synthesis: Dict,
        context: QueryContext,
        web_sources: List[Dict] = None,
    ):
        # Build context with source metadata so the model can cite inline.
        # Keep per-doc text long enough for DCPR tables.
        local_text = "\n\n".join(
            [
                f"[Doc {i + 1}] Source: {r.source or 'DCPR 2034'}, Page: {r.page}\n{r.text[:2500]}"
                for i, r in enumerate(local_results[:12])
            ]
        )

        # Pre-build citation footer (stream version)
        citations = []
        for i, r in enumerate(local_results[:6]):
            if r.source:
                page_info = f", p.{r.page}" if r.page else ""
                citations.append(f"[Doc {i + 1}] {r.source}{page_info}")

        # Different prompts for feasibility vs regulatory queries
        is_market_analysis = (
            context.needs_market_data or context.intent == "feasibility_analysis"
        )

        if context.is_technical or context.intent == "technical_lookup":
            # Technical Regulatory Query (Streaming)
            fsi_data = synthesis.get("fsi_data", {})
            query_params = synthesis.get("key_parameters", {})

            area_str = query_params.get("area", "Not specified")
            road_str = query_params.get("road_width", "9m (standard default)")
            base_fsi = fsi_data.get("base_fsi", "See documents")

            prompt = f"""You are a high-precision Urban Planning Expert answering a DCPR question.

Question: {question}
Parameters: Area={area_str}, Road={road_str}, Base FSI={base_fsi}

REGULATION EXCERPTS:
{local_text}

WEB RESULTS:
{web_context[:2500] if web_context else "None"}

{DCPR_ANSWER_RULES}

EXTRA:
- One-sentence direct answer first.
- No LaTeX, no section headers. Markdown tables ARE allowed and REQUIRED when rule 4 (multi-variant comparison) applies.
"""
        elif is_market_analysis:
            prompt = f"""You are a real estate investment advisor for Mumbai. Provide a focused feasibility analysis.

Question: {question}
Location: {context.location or "Mumbai"}

WEB SEARCH RESULTS (PRIORITY - include specific prices, rates, consultants):
{web_context[:3000] if web_context else "No web results"}

REGULATORY DATA:
{local_text if local_text else "No local regulatory data"}

{DCPR_ANSWER_RULES}

EXTRA (feasibility formatting):
- Start with one line of market data if present, then one line of regulatory
  position from DCPR.
- Cite web as [Web N]; cite DCPR using "— as per DCPR 2034, Regulation <X>, p.<N>".
- End with one actionable next step.
"""
        else:
            # Standard regulatory query
            fsi_data = synthesis.get("fsi_data", {})
            applicable_regs = synthesis.get("applicable_regulations", [])
            query_params = synthesis.get("key_parameters", {})

            regs_str = (
                ", ".join(applicable_regs) if applicable_regs else "See documents below"
            )
            area_str = query_params.get("area", "Not specified")
            road_str = query_params.get("road_width", "9m (standard default)")
            loc_str = query_params.get("location", "Mumbai (default)")
            base_fsi = fsi_data.get("base_fsi", "See documents")
            max_fsi = fsi_data.get("max_fsi", "See documents")
            prem_fsi = fsi_data.get("premium_fsi", "See documents")

            prompt = f"""You are an expert urban planning consultant for Mumbai. Answer using the DCPR 2034 excerpts below.

Question: {question}

Detected Parameters:
- Area: {area_str}
- Road Width: {road_str}
- Location: {loc_str}

Applicable Regulations: {regs_str}
FSI Data: Base={base_fsi}, Max={max_fsi}, Premium={prem_fsi}

DCPR 2034 Regulation Excerpts:
{local_text}

Web Search Results:
{web_context[:1000] if web_context else "None"}

{DCPR_ANSWER_RULES}

EXTRA:
- Prioritize DCPR excerpts over web. Fall back to web only when the excerpts
  don't cover the question, and cite as [Web N] in that case.
"""
        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful urban planning expert on DCPR 2034 for Mumbai. Keep answers short (≤6 short sentences). End each factual paragraph with an inline citation '— as per DCPR 2034, Regulation <X>, p.<N>'. For tables, include every contributing field or omit the table; never use 'Varies' / 'N/A' / 'Available on request'. No fabrication — if a value is missing, say so in one line.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                stream=True,
            )
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            yield f"\n\n[Streaming Error]: {str(e)}"

    def _calculate_confidence(
        self, results: List[SearchResult], synthesis: Dict = None
    ) -> float:
        if not results:
            return 0.0

        # Top result score
        top_score = results[0].score

        # Average top 5 scores
        avg_score = sum(r.score for r in results[:5]) / min(5, len(results))

        # Count results with decent relevance
        relevant_count = len([r for r in results if r.score > 0.3])
        count_factor = min(relevant_count / 5, 1.0) * 0.15

        # Number of unique clauses found
        total_clauses = len(set(c for r in results for c in r.clauses))
        clause_factor = min(total_clauses / 10, 1.0) * 0.15

        # Number of tables found
        total_tables = len(set(t for r in results for t in r.tables))
        table_factor = min(total_tables / 3, 1.0) * 0.1

        # Check if answer has specific values
        has_values = 0
        if synthesis:
            values = synthesis.get("key_technical_data", [])
            if values:
                has_values = 0.1

        # Final weighted confidence
        confidence = (
            top_score * 0.35
            + avg_score * 0.25
            + count_factor
            + clause_factor
            + table_factor
            + has_values
        )

        return round(min(confidence, 1.0), 2)

    def _generate_suggestions(
        self, question: str, context: QueryContext, clauses: List[str]
    ) -> List[str]:
        return [
            f"What are the requirements under {clauses[0]}?"
            if clauses
            else f"Requirements for {context.topic}",
            "What premiums apply?",
            "How does this compare to other schemes?",
            "What documents are needed?",
        ][:4]

    def reset_memory(self):
        self._memory.clear()


class IntelligentRAG:
    """Main RAG class with session support"""

    def __init__(self, session_id: Optional[str] = None):
        # We still have a default session if provided
        self._default_session_id = session_id

    def query(
        self, question: str, k: int = 10, session_id: Optional[str] = None
    ) -> Dict:
        # Use provided session_id or fall back to default
        question = str(question)
        sid = session_id or self._default_session_id
        session, _ = SessionManager.get_or_create_session(sid)
        return session.query(question, k)

    def stream_query(
        self, question: str, k: int = 10, session_id: Optional[str] = None
    ):
        """Streaming version of the query method"""
        question = str(question)
        sid = session_id or self._default_session_id
        session, _ = SessionManager.get_or_create_session(sid)

        # Start the generator
        for chunk in session.stream_query(question, k):
            yield chunk

    def reset_memory(self, session_id: Optional[str] = None):
        sid = session_id or self._default_session_id
        session, _ = SessionManager.get_or_create_session(sid)
        session.reset_memory()

    @classmethod
    def list_sessions(cls) -> List[Dict]:
        return SessionManager.list_sessions()

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        return SessionManager.delete_session(session_id)

    @classmethod
    def get_knowledge_graph_stats(cls) -> Dict:
        kg = SessionManager.get_knowledge_graph()
        return {
            "clauses": len(kg.clauses) if kg else 0,
            "tables": len(kg.tables) if kg else 0,
            "topics": len(kg.topic_to_clauses) if kg else 0,
        }


def format_result(result: Dict) -> str:
    output = ["=" * 70, f"QUERY: {result['query']}", "=" * 70]
    output.append(f"**Confidence:** {result.get('confidence', 0):.0%}")
    output.append(f"**Session:** {result.get('session_id', 'N/A')}")
    output.append("\n" + "=" * 70)
    output.append("ANSWER")
    output.append("=" * 70)
    output.append(result.get("answer", ""))
    output.append("\n" + "=" * 70)
    return "\n".join(output)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="DCPR RAG with Dynamic Knowledge Graph"
    )
    parser.add_argument("question", help="Your question")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--session", type=str, default=None)

    args = parser.parse_args()
    rag = IntelligentRAG(session_id=args.session)
    result = rag.query(args.question, k=args.k)
    logger.info(format_result(result))
    logger.info(f"\nKnowledge Graph: {result.get('knowledge_graph_stats', {})}")

