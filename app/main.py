"""Elegant Streamlit landing page and centered DarGlobal/Wasalt chat experience."""
from pathlib import Path
import logging
import re
import time

import streamlit as st
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
from app.workflow.graph import ask

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Darglobal & Wasalt Chatbot - AI companion",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

IMAGE_URL = "/app/static/luxury-villa-illustrative.jpg"
FAQS = [
    "What does DarGlobal do?",
    "What projects does DarGlobal have in Saudi Arabia?",
    "Tell me about AIDA in Oman.",
    "What does Wasalt offer?",
    "How does Wasalt Auctions work?",
    "What can you help me with?",
]
WELCOME_TEXT = (
    "Hi, welcome! I’m your AI chatbot. Ask me questions about DarGlobal and Wasalt.\n\n"
    "I can help with DarGlobal’s company information, projects, locations, publicly stated features, and announcements; "
    "Wasalt’s company background, services, and public licensing information; and the REGA open-data catalog.\n\n"
    "I don’t have live property inventory or current unit pricing. DarGlobal’s project pages direct buyers to contact its "
    "sales team for current prices and availability, so I can’t match a budget to a currently available home."
)

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600&display=swap');
:root {{ --ink:#1d2524; --muted:#68716f; --sand:#e8e1d5; --gold:#b79763; --paper:#f8f7f3; }}
.stApp {{ background:var(--paper); color:var(--ink); font-family:'DM Sans',sans-serif; }}
[data-testid="stSidebar"] {{ display:none; }}
header[data-testid="stHeader"] {{ background:transparent; }}
div.block-container {{ max-width:1440px; padding:1.1rem 2rem 2rem; }}
.brandline {{ display:flex; justify-content:space-between; align-items:center; padding:.15rem .2rem 1rem; color:#6c706d; font-size:.74rem; letter-spacing:.17em; text-transform:uppercase; }}
.brandline span:last-child {{ color:#a88b5d; }}
.landing-photo {{ height:52vh; min-height:350px; max-height:650px; border-radius:8px; background-image:linear-gradient(0deg,rgba(22,26,23,.06),rgba(22,26,23,.02)),url('{IMAGE_URL}'); background-size:cover; background-position:center 54%; box-shadow:0 24px 65px rgba(46,42,33,.13); }}
.landing-copy {{ text-align:center; padding:1.35rem 1rem 6.1rem; }}
.eyebrow {{ color:#a78b5c; letter-spacing:.24em; font-size:.68rem; font-weight:700; text-transform:uppercase; margin:.2rem 0 .5rem; }}
.landing-copy h1 {{ font-family:'Playfair Display',Georgia,serif; font-size:clamp(2rem,4vw,3.5rem); font-weight:500; line-height:1.1; letter-spacing:-.025em; color:#212522; margin:0 auto .65rem; }}
.landing-copy p {{ color:#656b67; font-size:1rem; max-width:640px; margin:0 auto; line-height:1.7; }}
div[data-testid="stButton"] {{ display:flex; justify-content:center; }}
div[data-testid="stButton"] button {{ border:1px solid #b99c6b; border-radius:99px; color:#fff; background:#25332f; font-weight:600; letter-spacing:.03em; padding:.72rem 1.6rem; min-height:3.1rem; transition:all .2s ease; box-shadow:0 12px 30px rgba(29,37,36,.16); }}
div[data-testid="stButton"] button:hover {{ background:#344940; border-color:#d1b47f; color:#fff; transform:translateY(-1px); }}
.chat-launch-link {{ position:fixed; z-index:100; bottom:26px; left:50%; transform:translateX(-50%); min-width:255px; display:flex; justify-content:center; align-items:center; text-decoration:none !important; border:1px solid #b99c6b; border-radius:99px; color:#fff !important; background:#25332f; font-weight:600; letter-spacing:.03em; padding:.72rem 1.6rem; min-height:3.1rem; transition:all .2s ease; box-shadow:0 12px 30px rgba(29,37,36,.16); }}
.chat-launch-link:hover {{ background:#344940; border-color:#d1b47f; color:#fff !important; transform:translate(-50%,-1px); }}
.chat-brand {{ display:flex; justify-content:space-between; align-items:center; padding:.35rem .25rem 1rem; border-bottom:1px solid #e9e5dc; margin-bottom:1rem; }}
.chat-brand strong {{ font-family:'Playfair Display',Georgia,serif; font-size:1.35rem; font-weight:500; }}
.chat-brand small {{ color:#838681; font-size:.76rem; }}
.online-dot {{ display:inline-block; width:8px; height:8px; border-radius:100%; background:#6c9a72; margin-right:.4rem; }}
.st-key-chat_window {{ background:#fff; border:1px solid #e9e5dd; border-radius:14px; padding:1rem 1rem .5rem; box-shadow:0 18px 45px rgba(48,42,32,.07); min-height:570px; }}
.welcome-card {{ background:#f8f6f1; border:1px solid #eee8dc; border-radius:12px; padding:1rem 1.1rem; margin-bottom:1rem; }}
.welcome-card strong {{ font-family:'Playfair Display',Georgia,serif; font-size:1.05rem; font-weight:600; }}
.welcome-card p {{ color:#5f6763; font-size:.88rem; line-height:1.65; margin:.55rem 0 0; }}
.faq-title {{ color:#777c76; text-transform:uppercase; font-size:.68rem; letter-spacing:.15em; font-weight:700; margin:.7rem .2rem .55rem; }}
.st-key-faq_group div[data-testid="stButton"] button {{ color:#263630; background:#fff; border:1px solid #c2a675; box-shadow:none; min-height:2.55rem; padding:.45rem .8rem; font-size:.82rem; }}
.st-key-faq_group div[data-testid="stButton"] button:hover {{ background:#f5f1e8; color:#25332f; border-color:#a88b5d; }}
.st-key-conversation_messages {{ max-height:54vh; overflow-y:auto; padding:.15rem .15rem .6rem; }}
.st-key-chat_form {{ border-top:1px solid #eee9df; padding-top:.75rem; margin-top:.65rem; }}
div[data-testid="stForm"] {{ border:0; padding:0; }}
div[data-testid="stForm"] input {{ border-radius:999px; background:#f4f5f6; border:1px solid #ebe8e1; }}
div[data-testid="stForm"] button {{ min-width:3rem; min-height:2.65rem; border-radius:999px; padding:.4rem .8rem; color:#fff !important; -webkit-text-fill-color:#fff !important; }}
div[data-testid="stForm"] button svg, div[data-testid="stForm"] button [data-testid="stIconMaterial"] {{ color:#fff !important; fill:#fff !important; stroke:#fff !important; }}
div[data-testid="stExpander"] details > summary {{ color:#000 !important; }}
div[data-testid="stExpander"] details > summary * {{ color:#000 !important; -webkit-text-fill-color:#000 !important; }}
div[data-testid="stExpander"] details[open] > summary {{ background:#e7e7e7 !important; }}
div[data-testid="stExpander"] details[open] > summary:hover {{ background:#dedede !important; }}
.stApp [data-testid="stVerticalBlock"] > div {{ animation:none !important; transition:none !important; }}
.side-photo {{ height:620px; border-radius:12px; background-image:url('{IMAGE_URL}'); background-size:cover; background-position:center; box-shadow:0 18px 45px rgba(48,42,32,.13); }}
.side-photo.left {{ background-position:35% center; }}
.side-photo.right {{ background-position:72% center; }}
div[data-testid="stChatMessage"] {{ border-radius:12px; padding:.45rem .6rem; }}
div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"], div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] *, div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] strong {{ color:#000 !important; -webkit-text-fill-color:#000 !important; line-height:1.65; font-size:.92rem; }}
div[data-testid="stForm"] input {{ color:#000 !important; -webkit-text-fill-color:#000 !important; caret-color:#000 !important; }}
div[data-testid="stForm"] input::placeholder {{ color:#000 !important; -webkit-text-fill-color:#000 !important; opacity:1 !important; }}
div[data-testid="stChatInput"] {{ border-color:#ded8cb; background:#fff; border-radius:16px; }}
div[data-testid="stStatusWidget"] {{ border:1px solid #eee8dc; border-radius:12px; background:#faf9f6; }}
.chat-note {{ color:#858982; font-size:.72rem; text-align:center; padding:.3rem 0 .7rem; }}
.st-key-chat_home {{ justify-content:flex-end !important; }}
.st-key-chat_home div[data-testid="stButton"] button {{ color:#53615a; background:transparent; box-shadow:none; border-color:#e5dfd3; min-height:2.45rem; padding:.4rem 1rem; font-size:.8rem; }}
@media (max-width:900px) {{ div.block-container {{ padding:.8rem 1rem 1.5rem; }} .side-photo {{ height:470px; }} }}
@media (max-width:680px) {{ .side-photo {{ display:none; }} .landing-photo {{ height:43vh; min-height:270px; }} .landing-copy {{ padding-bottom:5.4rem; }} .brandline {{ font-size:.58rem; }} }}
</style>""", unsafe_allow_html=True)


requested_chat_open = st.query_params.get("view") == "chat"
if st.session_state.get("chat_open") != requested_chat_open:
    st.session_state.chat_open = requested_chat_open
    st.session_state.messages = []
    st.session_state.welcome_shown = False
    st.session_state.pop("pending_question", None)
if "messages" not in st.session_state:
    st.session_state.messages = []


def close_chat():
    st.session_state.chat_open = False
    st.query_params.clear()
    st.session_state.messages = []
    st.session_state.welcome_shown = False
    st.session_state.pop("pending_question", None)


def format_answer(text: str) -> str:
    """Keep currency from being interpreted as inline math by Streamlit Markdown."""
    return (text or "").replace("US$", "USD ").replace("$", "USD ")


if not st.session_state.chat_open:
    st.markdown("<div class='brandline'><span>DarGlobal · Wasalt</span><span>Property, with perspective</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='landing-photo' role='img' aria-label='Illustrative luxury home at sunset'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div class="landing-copy">
      <div class="eyebrow">A considered guide to exceptional places</div>
      <h1>Darglobal &amp; Wasalt Chatbot - AI companion</h1>
      <p>Explore DarGlobal’s business, announced developments and public updates, alongside Wasalt’s company background and services.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<a class="chat-launch-link" href="?view=chat">Click to chat with bot</a>', unsafe_allow_html=True)
else:
    page_label, page_action = st.columns([5, 1], vertical_alignment="center")
    with page_label:
        st.markdown("<div class='brandline'><span>DarGlobal · Wasalt</span><span>AI companion</span></div>", unsafe_allow_html=True)
    with page_action:
        st.button("← Home", key="chat_home", on_click=close_chat, use_container_width=True)
    left, center, right = st.columns([0.92, 2.25, 0.92], gap="large", vertical_alignment="top")
    with left:
        st.markdown("<div class='side-photo left' role='img' aria-label='Illustrative luxury residence'></div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='side-photo right' role='img' aria-label='Illustrative luxury residence'></div>", unsafe_allow_html=True)
    with center:
        with st.container(border=True, key="chat_window"):
            st.markdown("""
            <div class="chat-brand"><div><strong>DarGlobal &amp; Wasalt</strong><br><small>AI companion</small></div><div><span class="online-dot"></span><small>Here to help</small></div></div>
            """, unsafe_allow_html=True)
            conversation = st.container(height=480, key="conversation_messages")
            with conversation:
                if not st.session_state.messages:
                    with st.chat_message("assistant", avatar="🤖"):
                        if not st.session_state.get("welcome_shown", False):
                            def welcome_stream():
                                for part in re.findall(r"\S+\s*", WELCOME_TEXT):
                                    yield part
                                    time.sleep(0.018)
                            st.write_stream(welcome_stream())
                            st.session_state.welcome_shown = True
                        else:
                            st.markdown(WELCOME_TEXT)
                    st.session_state.messages.append({"role": "assistant", "content": WELCOME_TEXT, "sources": [], "intro": True})
                else:
                    for message in st.session_state.messages:
                        with st.chat_message(message["role"], avatar="🤖" if message["role"] == "assistant" else None):
                            st.markdown(format_answer(message["content"]))
                            if message.get("sources"):
                                with st.expander("Sources"):
                                    for source in message["sources"]:
                                        st.markdown(f"[{source['source']}: {source['title']}]({source['url']})")
                if not any(message["role"] == "user" for message in st.session_state.messages):
                    st.markdown("<div class='faq-title'>A few questions to get started</div>", unsafe_allow_html=True)
                    with st.container(key="faq_group"):
                        for row in range(0, len(FAQS), 2):
                            faq_left, faq_right = st.columns(2, gap="small")
                            for col, question in ((faq_left, FAQS[row]), (faq_right, FAQS[row + 1] if row + 1 < len(FAQS) else None)):
                                if question:
                                    with col:
                                        if st.button(question, key=f"faq_{row}_{question}", use_container_width=True):
                                            st.session_state.pending_question = question

            submitted = False
            question_text = ""
            with st.form("chat_form", clear_on_submit=True):
                input_col, send_col = st.columns([8, 1], vertical_alignment="center", gap="small")
                with input_col:
                    question_text = st.text_input("Message", placeholder="Ask about DarGlobal, a project, or Wasalt", label_visibility="collapsed")
                with send_col:
                    submitted = st.form_submit_button("➤", use_container_width=True)
            st.markdown("<div class='chat-note'>Answers are based on public information and may not reflect live pricing or availability.</div>", unsafe_allow_html=True)

            question = st.session_state.pop("pending_question", None)
            if submitted and question_text.strip():
                question = question_text.strip()
            if question:
                history = [message for message in st.session_state.messages if not message.get("intro")][-8:]
                with conversation:
                    with st.chat_message("user"):
                        st.markdown(question)
                    with st.chat_message("assistant", avatar="🤖"):
                        status_slot = st.empty()
                        response_box = st.empty()
                        with status_slot.status("Thinking through your question…", expanded=False) as status:
                            status.write("Putting together a helpful answer…")
                            token_buffer = []

                            def show_token(token):
                                token_buffer.append(token)
                                response_box.markdown(format_answer("".join(token_buffer)) + "▌")

                            try:
                                result = ask(question, history, on_token=show_token)
                                status.update(label="Response ready", state="complete", expanded=False)
                                final_answer = result["answer"]
                                sources = result.get("sources", [])
                            except Exception:
                                logger.exception("Chat response failed")
                                final_answer = "I couldn't complete that just now. Please try again in a moment."
                                sources = []
                        response_box.markdown(format_answer(final_answer))
                        if sources:
                            with st.expander("Sources"):
                                for source in sources:
                                    st.markdown(f"[{source['source']}: {source['title']}]({source['url']})")
                st.session_state.messages.extend([
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": final_answer, "sources": sources},
                ])
                st.rerun()
