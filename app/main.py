"""Streamlit conversational UI."""
from pathlib import Path
import os
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from app.workflow.graph import ask

st.set_page_config(page_title="DarGlobal AI Assistant", page_icon="🏙️", layout="centered")
st.markdown("""<style>
.stApp{background:#f7f8fa}.hero{padding:1.35rem 1.5rem;border-radius:18px;
background:linear-gradient(120deg,#142735,#36556b);color:white;margin-bottom:1rem}
.hero h1{color:white;margin:0}.hero p{opacity:.88;margin:.45rem 0 0}
</style>""", unsafe_allow_html=True)
st.markdown("<div class='hero'><h1>DarGlobal AI Assistant</h1><p>Ask about public DarGlobal projects and Wasalt listings. Answers include source links when indexed evidence is available.</p></div>", unsafe_allow_html=True)
with st.sidebar:
    st.subheader("Example questions")
    for question in ["What is DarGlobal?", "Tell me about AIDA in Oman",
                     "What properties are listed for sale in Riyadh?",
                     "What amenities are available for this project?"]:
        if st.button(question, use_container_width=True):
            st.session_state.pending_question = question
    st.caption("Property ads may be supplied by third parties. Confirm listing details with the advertiser.")
    if not (Path(os.getenv("CHROMA_PATH", "chroma_db")) / "chroma.sqlite3").exists():
        st.info("No source documents are indexed yet. The assistant will avoid guessing.")
    st.caption("Model: OpenRouter free-model router")
if "messages" not in st.session_state:
    st.session_state.messages = []
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.markdown(f"[{source['source']}: {source['title']}]({source['url']})")
question = st.chat_input("Ask about projects, locations, or properties")
if st.session_state.get("pending_question"):
    question = st.session_state.pop("pending_question")
if question:
    history = st.session_state.messages[-8:]
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Searching indexed public sources…"):
            result = ask(question, history)
        st.markdown(result["answer"])
        sources = result.get("sources", [])
        if sources:
            with st.expander("Sources"):
                for source in sources:
                    st.markdown(f"[{source['source']}: {source['title']}]({source['url']})")
    st.session_state.messages.append({"role": "assistant", "content": result["answer"], "sources": sources})
