#!/usr/bin/env python3
"""
LangGraph-based RAG System with LangSmith Observability
Uses LangGraph for agent orchestration and LangSmith for tracing
"""

import json
import logging
import os
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

# Load environment
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ[key] = val

# LangGraph imports
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langsmith import Client as LangSmithClient

# LangSmith imports
from langsmith import traceable

# LLM imports
from openai import OpenAI

# ==================== LANGSMITH SETUP ====================


def setup_langsmith():
    """Initialize LangSmith for observability"""
    langsmith_api_key = os.environ.get("LANGSMITH_API_KEY")
    project_name = os.environ.get("LANGSMITH_PROJECT", "dhara-rag")

    if not langsmith_api_key:
        logger.warning("LangSmith API key not found - observability disabled")
        return None

    # Set environment variables
    os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = project_name
    os.environ["LANGSMITH_TRACING"] = "true"

    client = LangSmithClient()
    logger.info(f"LangSmith enabled - project: {project_name}")
    return client


# ==================== STATE DEFINITION ====================


class AgentState(TypedDict):
    """State for LangGraph agent"""

    messages: list[BaseMessage]
    question: str
    intent: str | None
    topic: str | None
    local_results: list[dict] | None
    web_results: list[dict] | None
    vertex_results: list[dict] | None
    synthesis: dict | None
    answer: str | None
    confidence: float | None
    sources: list[dict]
    metadata: dict


# ==================== RAG TOOLS ====================


class RAGTools:
    """Tools for the RAG agent"""

    def __init__(self):
        self.openai_client = OpenAI()
        self.milvus_client = None
        self._init_milvus()

    def _init_milvus(self):
        """Initialize Milvus connection"""
        try:
            from pymilvus import Collection, connections

            connections.connect(host="localhost", port="19530")
            self.milvus_client = Collection("dcpr_knowledge")
            logger.info("Milvus connected")
        except Exception as e:
            logger.warning(f"Milvus not available: {e}")

    @traceable(name="classify_intent", run_type="chain")
    def classify_intent(self, question: str) -> dict:
        """Classify user intent and extract entities"""
        prompt = f"""Analyze this question and extract:
1. Intent (explain, calculate, compare, recommend, find)
2. Topic (FSI, parking, margins, etc.)
3. Key entities mentioned

Question: {question}

Return JSON with: intent, topic, entities[]"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        try:
            return json.loads(response.choices[0].message.content)
        except Exception:
            return {"intent": "explain", "topic": "general", "entities": []}

    @traceable(name="search_local", run_type="retriever")
    def search_local(self, query: str, topic: str, k: int = 10) -> list[dict]:
        """Search local Milvus vector store"""
        if not self.milvus_client:
            return [{"text": "Milvus not available", "score": 0}]

        try:
            from langchain_openai import OpenAIEmbeddings
            from pymilvus import Collection

            embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
            query_embedding = embeddings.embed_query(query)

            collection = Collection("dcpr_knowledge")
            collection.load()

            results = collection.search(
                data=[query_embedding],
                anns_field="vector",
                param={"metric_type": "IP", "params": {}},
                limit=k,
                output_fields=["text", "metadata"],
            )

            return [{"text": r.entity.get("text", ""), "score": r.distance} for r in results[0]]
        except Exception as e:
            return [{"text": f"Error: {e}", "score": 0}]

    @traceable(name="search_web", run_type="tool")
    def search_web(self, query: str) -> list[dict]:
        """Search web for information"""
        # Using Tavily or similar
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
            results = client.search(query=query, max_results=5)
            return [{"text": r["content"], "url": r["url"]} for r in results]
        except Exception:
            # Fallback to DuckDuckGo
            try:
                from duckduckgo import DDGS

                ddgs = DDGS()
                results = ddgs.text(query, max_results=5)
                return [{"text": r["body"], "url": r["href"]} for r in results]
            except Exception:
                return [{"text": "Web search not available", "url": ""}]

    @traceable(name="synthesize_answer", run_type="chain")
    def synthesize_answer(
        self, question: str, local_context: str, web_context: str, vertex_context: str
    ) -> dict:
        """Synthesize answer from all sources"""
        prompt = f"""You are a helpful urban planning consultant. Answer the user's question directly.

Question: {question}

Local DCPR Documents:
{local_context[:2000]}

Web Search Results:
{web_context[:1500]}

Other Context:
{vertex_context[:1000]}

Instructions:
1. Give a direct, conversational answer first
2. If you need more details (like road width), ask a clarifying question
3. Don't show "N/A" or empty table cells
4. Use simple formatting
5. Add sources at the end
"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful urban planning consultant.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        answer = response.choices[0].message.content
        confidence = 0.7  # Default confidence

        # Calculate confidence based on source availability
        if local_context and "not available" not in local_context.lower():
            confidence += 0.2
        if web_context:
            confidence += 0.1
        confidence = min(confidence, 0.95)

        return {"answer": answer, "confidence": confidence}


# ==================== LANGRAPH AGENT ====================


class LangGraphRAG:
    """LangGraph-based RAG Agent with observability"""

    def __init__(self):
        logger.info("=" * 60)
        logger.info("INITIALIZING LANGGRAPH RAG WITH LANGSMITH")
        logger.info("=" * 60)

        # Setup LangSmith
        self.langsmith = setup_langsmith()

        # Initialize tools
        self.tools = RAGTools()

        # Build the graph
        self.graph = self._build_graph()

        logger.info("LangGraph RAG initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine"""

        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("search_web", self._web_search_node)
        workflow.add_node("synthesize", self._synthesize_node)

        # Set entry point
        workflow.set_entry_point("classify")

        # Add edges
        workflow.add_edge("classify", "retrieve")
        workflow.add_edge("retrieve", "search_web")
        workflow.add_edge("search_web", "synthesize")
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    def _classify_node(self, state: AgentState) -> AgentState:
        """Classify intent and extract entities"""
        question = state["question"]
        result = self.tools.classify_intent(question)

        return {
            **state,
            "intent": result.get("intent", "explain"),
            "topic": result.get("topic", "general"),
        }

    def _retrieve_node(self, state: AgentState) -> AgentState:
        """Retrieve from local vector store"""
        question = state["question"]
        topic = state.get("topic", "general")

        results = self.tools.search_local(question, topic, k=10)
        "\n\n".join([r["text"][:500] for r in results[:6]])

        return {
            **state,
            "local_results": results,
            "sources": [{"type": "local", "text": r["text"][:200]} for r in results[:3]],
        }

    def _web_search_node(self, state: AgentState) -> AgentState:
        """Search the web"""
        question = state["question"]

        results = self.tools.search_web(question)

        return {
            **state,
            "web_results": results,
            "sources": state["sources"]
            + [{"type": "web", "text": r["text"][:200]} for r in results[:2]],
        }

    def _synthesize_node(self, state: AgentState) -> AgentState:
        """Synthesize final answer"""
        question = state["question"]

        local_text = "\n\n".join([r["text"][:500] for r in (state.get("local_results") or [])[:6]])
        web_text = "\n\n".join([r["text"][:300] for r in (state.get("web_results") or [])[:3]])

        result = self.tools.synthesize_answer(question, local_text, web_text, "")

        return {
            **state,
            "answer": result["answer"],
            "confidence": result["confidence"],
            "metadata": {
                "topic": state.get("topic"),
                "intent": state.get("intent"),
                "sources_count": len(state.get("sources", [])),
            },
        }

    @traceable(name="query", run_type="chain")
    def query(self, question: str, stream: bool = False) -> dict:
        """Query the RAG agent"""
        initial_state = {
            "messages": [HumanMessage(content=question)],
            "question": question,
            "sources": [],
        }

        result = self.graph.invoke(initial_state)

        return {
            "answer": result.get("answer", "No answer generated"),
            "confidence": result.get("confidence", 0),
            "sources": result.get("sources", []),
            "metadata": result.get("metadata", {}),
        }

    def stream_query(self, question: str):
        """Stream query results"""
        initial_state = {
            "messages": [HumanMessage(content=question)],
            "question": question,
            "sources": [],
        }

        for event in self.graph.stream(initial_state):
            for node_name, node_output in event.items():
                if node_name == "synthesize" and node_output.get("answer"):
                    yield node_output["answer"]


# ==================== MAIN ====================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LangGraph RAG with LangSmith")
    parser.add_argument("question", nargs="?", default="What is FSI for residential in Pune?")
    parser.add_argument("--stream", action="store_true", help="Stream the response")

    args = parser.parse_args()

    # Initialize agent
    agent = LangGraphRAG()

    if args.stream:
        for _chunk in agent.stream_query(args.question):
            pass
    else:
        agent.query(args.question)


if __name__ == "__main__":
    main()
