"""Conditional RAG workflow: retrieve, answer if relevant, otherwise fallback."""
from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from app.rag.retriever import retrieve
from app.llm.openrouter import generate, OpenRouterError

class ChatState(TypedDict, total=False):
    question: str
    history: list
    docs: list
    sources: list
    answer: str
    clarification: bool

def retrieval_node(state):
    question = state.get("question", "").strip()
    if len(question) < 3:
        return {"docs": [], "sources": [], "clarification": True}
    docs = retrieve(question, state.get("history", []))
    sources, seen = [], set()
    for doc in docs:
        meta = doc["metadata"]
        url = meta.get("source_url")
        if url and url not in seen:
            seen.add(url)
            sources.append({"source": meta.get("source", "Source"), "url": url,
                            "title": meta.get("project_name") or url})
    return {"docs": docs, "sources": sources, "clarification": False}

def route(state):
    if state.get("clarification"): return "clarify"
    return "answer" if state.get("docs") else "fallback"

def answer_node(state):
    try:
        answer = generate(state["question"], state["docs"], state.get("history", []))
    except OpenRouterError as exc:
        answer = str(exc) + " The relevant source pages are listed below."
    return {"answer": answer}

def fallback_node(state):
    return {"answer": "I couldn't find verified information for that question in the indexed public sources. Please try a project name or open one of the official source pages below."}

def clarify_node(state):
    return {"answer": "Which project, property, or location are you asking about?"}

builder = StateGraph(ChatState)
builder.add_node("retrieve", retrieval_node)
builder.add_node("answer", answer_node)
builder.add_node("fallback", fallback_node)
builder.add_node("clarify", clarify_node)
builder.add_edge(START, "retrieve")
builder.add_conditional_edges("retrieve", route, {"answer": "answer", "fallback": "fallback", "clarify": "clarify"})
for node in ("answer", "fallback", "clarify"): builder.add_edge(node, END)
graph = builder.compile()

def ask(question, history=None):
    return graph.invoke({"question": question, "history": history or []})
