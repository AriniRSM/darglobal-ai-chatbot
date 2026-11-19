"""Conditional RAG workflow: retrieve, answer if relevant, otherwise fallback."""
import re
import os
from typing import Callable, TypedDict
from langgraph.graph import END, START, StateGraph
from app.rag.retriever import retrieve
from app.llm.openrouter import generate, generate_stream, OpenRouterError

class ChatState(TypedDict, total=False):
    question: str
    history: list
    docs: list
    sources: list
    answer: str
    clarification: bool
    capabilities: bool
    budget_limit: bool
    on_token: Callable[[str], None]

_CAPABILITY_QUESTION = re.compile(
    r"\b(?:what can you answer|what are your capabilities|what can you do|what can you help me with|how can you help|what do you know)\b",
    re.IGNORECASE,
)
_SOURCE_SCORE_MARGIN = float(os.getenv("SOURCE_SCORE_MARGIN", "0.12"))
_MAX_CITED_SOURCES = int(os.getenv("MAX_CITED_SOURCES", "3"))
_BUDGET_RECOMMENDATION = re.compile(
    r"\b(?:my budget|budget of|within (?:my|a) budget|afford|find (?:me )?(?:a )?property|"
    r"suitable property|recommend (?:me )?(?:a )?(?:property|home)|best (?:property|home) for me)\b",
    re.IGNORECASE,
)


def retrieval_node(state):
    question = state.get("question", "").strip()
    if _CAPABILITY_QUESTION.search(question):
        return {"docs": [], "sources": [], "clarification": False, "capabilities": True, "budget_limit": False}
    if _BUDGET_RECOMMENDATION.search(question):
        return {"docs": [], "sources": [], "clarification": False, "capabilities": False, "budget_limit": True}
    if len(question) < 3:
        return {"docs": [], "sources": [], "clarification": True, "capabilities": False}
    docs = retrieve(question, state.get("history", []))
    # Cite only sources close to the best matching chunk. This avoids showing
    # unrelated but technically above-threshold pages in the source panel.
    ranked_docs = sorted(docs, key=lambda doc: float(doc.get("score", 0)), reverse=True)
    best_score = float(ranked_docs[0].get("score", 0)) if ranked_docs else 0
    citation_floor = max(0.0, best_score - _SOURCE_SCORE_MARGIN)
    sources, selected_docs, seen = [], [], set()
    for doc in ranked_docs:
        if float(doc.get("score", 0)) < citation_floor:
            break
        meta = doc["metadata"]
        url = meta.get("source_url")
        if not url:
            continue
        if url not in seen:
            if len(sources) >= max(1, _MAX_CITED_SOURCES):
                continue
            seen.add(url)
            sources.append({"source": meta.get("source", "Source"), "url": url,
                            "title": meta.get("project_name") or url})
        selected_docs.append(doc)
    return {"docs": selected_docs, "sources": sources, "clarification": False, "capabilities": False}

def route(state):
    if state.get("capabilities"): return "capabilities"
    if state.get("budget_limit"): return "budget_limit"
    if state.get("clarification"): return "clarify"
    return "answer" if state.get("docs") else "fallback"

def answer_node(state):
    try:
        on_token = state.get("on_token")
        if callable(on_token):
            answer = generate_stream(state["question"], state["docs"], state.get("history", []), on_token=on_token)
        else:
            answer = generate(state["question"], state["docs"], state.get("history", []))
    except OpenRouterError:
        # Keep provider diagnostics and status codes out of the user-facing chat.
        answer = "I couldn't generate a response right now. Please try again shortly."
    return {"answer": answer}

def capabilities_node(state):
    return {"answer": (
        "I can help with DarGlobal’s company profile, projects, locations, published project details and announcements; "
        "Wasalt’s company background, services and public licensing information; and the REGA open-data catalog. "
        "I can summarize those public sources and link them. I don’t have live property inventory or current unit "
        "pricing, Wasalt property listings, or the underlying REGA statistical files."
    ), "sources": []}


def budget_limit_node(state):
    return {"answer": (
        "I can’t reliably match a budget to a currently available property because I don’t have live inventory or "
        "current unit pricing. I can compare publicly stated project locations, types, sizes and development details. "
        "For current DarGlobal prices and availability, contact the project sales team; for Wasalt listings, check Wasalt directly."
    ), "sources": []}


def fallback_node(state):
    return {"answer": "I couldn't find verified information for that question in the indexed public sources. Please try a project name or open one of the official source pages below."}

def clarify_node(state):
    return {"answer": "Which project, property, or location are you asking about?"}

builder = StateGraph(ChatState)
builder.add_node("retrieve", retrieval_node)
builder.add_node("answer", answer_node)
builder.add_node("fallback", fallback_node)
builder.add_node("clarify", clarify_node)
builder.add_node("capabilities", capabilities_node)
builder.add_node("budget_limit", budget_limit_node)
builder.add_edge(START, "retrieve")
builder.add_conditional_edges("retrieve", route, {"answer": "answer", "fallback": "fallback", "clarify": "clarify", "capabilities": "capabilities", "budget_limit": "budget_limit"})
for node in ("answer", "fallback", "clarify", "capabilities", "budget_limit"): builder.add_edge(node, END)
graph = builder.compile()

def ask(question, history=None, on_token=None):
    state = {"question": question, "history": history or []}
    if on_token:
        state["on_token"] = on_token
    return graph.invoke(state)
