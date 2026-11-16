import hmac
import html
import os
import re
from collections import Counter
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from rag.chain import NOT_FOUND, answer, label  # noqa: E402  (after load_dotenv so env vars are read)
from rag.ingest import load_all  # noqa: E402
from rag.store import get_collection, rebuild_index, search  # noqa: E402

ROOT = Path(__file__).parent
DATA, STORE = ROOT / "data" / "courses", ROOT / "storage"

SUGGESTIONS = [
    ("🐳", "What does -p 5000:8000 mean in Docker?"),
    ("🐍", "What is a list comprehension?"),
    ("🗄️", "What is the difference between WHERE and HAVING?"),
]
CHIP_COLORS = ["#FFD93D", "#5EEAD4", "#7DD3FC", "#BEF264", "#FF9CC8"]
FILE_EMOJI = {"pdf": "📕", "docx": "📘", "csv": "📊", "txt": "📝"}
COURSE_EMOJI = [("docker", "🐳"), ("api", "🔌"), ("python", "🐍"), ("sql", "🗄️"), ("data", "📊"), ("ml", "🤖"), ("web", "🌐")]


def course_emoji(name: str) -> str:
    return next((e for k, e in COURSE_EMOJI if k in name.lower()), "📚")


st.set_page_config(page_title="Ask the course", page_icon="🎓", layout="wide")
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@600;800&family=Nunito:wght@400;600;700;800&display=swap');
:root { --ink:#1A1A2E; --bg:#F1EDFF; --pink:#FF5DA2; --yellow:#FFD93D; --mint:#5EEAD4; --sky:#7DD3FC; }

.stApp { background-color:var(--bg); background-image:radial-gradient(#1A1A2E26 1.2px, transparent 1.2px); background-size:24px 24px; }
.stApp, .stMarkdown p, .stMarkdown li, [data-testid="stChatInput"] textarea { font-family:'Nunito',sans-serif; font-size:1.05rem; line-height:1.65; }
h1, h2, h3, .brand { font-family:'Unbounded',sans-serif !important; letter-spacing:-0.03em; }
header[data-testid="stHeader"] { background:transparent; }
#MainMenu, footer { visibility:hidden; }
.block-container { max-width:880px; padding-top:2rem; padding-bottom:6rem; }

/* sidebar */
[data-testid="stSidebar"] { background:#fff; border-right:3px solid var(--ink); }
.brand { display:inline-block; background:var(--pink); color:#fff; font-size:1.1rem; font-weight:800; border:3px solid var(--ink);
         border-radius:14px; padding:.4rem .8rem; box-shadow:4px 4px 0 var(--ink); transform:rotate(-2deg); margin:.3rem 0 1.2rem; }
.shelf-title { font-weight:800; margin:.4rem 0 .2rem; }
.chip { display:inline-block; border:2px solid var(--ink); border-radius:999px; padding:.1rem .65rem; margin:.15rem .25rem .15rem 0; font-weight:700; font-size:.85rem; }
.status { font-weight:700; margin:.8rem 0; }
span[data-baseweb="tag"] { background:var(--yellow) !important; color:var(--ink) !important; border:2px solid var(--ink); border-radius:999px !important; font-weight:700; }

/* hero */
.stickers span { display:inline-grid; place-items:center; width:3.4rem; height:3.4rem; font-size:1.8rem; border:3px solid var(--ink);
                 border-radius:16px; box-shadow:4px 4px 0 var(--ink); margin-right:.7rem; }
.stickers span:nth-child(1) { background:var(--yellow); transform:rotate(-7deg); }
.stickers span:nth-child(2) { background:var(--mint); transform:rotate(4deg); }
.stickers span:nth-child(3) { background:var(--pink); transform:rotate(-3deg); }
.hero h1 { font-size:2.9rem; font-weight:800; line-height:1.08; margin:1.4rem 0 .8rem; }
.hero p { font-size:1.15rem; max-width:34rem; margin-bottom:1.8rem; font-weight:600; }

/* buttons */
.stButton > button { border:3px solid var(--ink); border-radius:16px; background:#fff; color:var(--ink); font:700 .95rem 'Nunito',sans-serif;
                     box-shadow:4px 4px 0 var(--ink); padding:.8rem .9rem; text-align:left; height:100%; transition:transform .1s, box-shadow .1s; }
.stButton > button:hover { transform:translate(-2px,-2px); box-shadow:6px 6px 0 var(--ink); border-color:var(--ink); color:var(--ink); }
.stButton > button:active { transform:translate(3px,3px); box-shadow:1px 1px 0 var(--ink); }
[data-testid="stHorizontalBlock"] > div:nth-child(1) .stButton > button { background:var(--yellow); }
[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button { background:var(--mint); }
[data-testid="stHorizontalBlock"] > div:nth-child(3) .stButton > button { background:var(--sky); }
[data-testid="stSidebar"] .stButton > button { background:#fff; text-align:center; }

/* chat */
[data-testid="stChatMessage"] { background:#fff; border:3px solid var(--ink); border-radius:18px; box-shadow:4px 4px 0 var(--ink); padding:1rem 1.2rem; margin:.7rem 0; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background:#FFD6E8; }
[data-testid="stChatInput"] > div { background:#fff; border:3px solid var(--ink); border-radius:18px; box-shadow:4px 4px 0 var(--ink); }

/* citations + sticky-note sources */
.cite { display:inline-block; min-width:1.45em; text-align:center; font:800 .75rem 'Nunito',sans-serif; background:var(--pink); color:#fff;
        border:2px solid var(--ink); border-radius:999px; padding:0 .3em; margin:0 .15em; vertical-align:super; }
[data-testid="stExpander"] { background:#FFF3A3; border:3px solid var(--ink); border-radius:14px; box-shadow:3px 3px 0 var(--ink); margin:.5rem 0; }
[data-testid="stExpander"] details { border:none; }
[data-testid="stExpander"] summary { font-weight:800; }
.note { font-size:1.02rem; line-height:1.8; }
.meta { display:flex; align-items:center; gap:.7rem; font-weight:700; font-size:.85rem; margin-bottom:.7rem; }
.meter { width:110px; height:10px; background:#fff; border:2px solid var(--ink); border-radius:999px; overflow:hidden; }
.meter i { display:block; height:100%; background:var(--mint); border-right:2px solid var(--ink); }
</style>
""",
    unsafe_allow_html=True,
)


PASSWORD = os.getenv("APP_PASSWORD")
if PASSWORD and not st.session_state.get("unlocked"):
    st.markdown("<div class='hero'><h1>🔒 Password, please</h1></div>", unsafe_allow_html=True)
    entered = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Enter password")
    if entered and hmac.compare_digest(entered, PASSWORD):
        st.session_state.unlocked = True
        st.rerun()
    elif entered:
        st.error("Wrong password 🙈")
    st.stop()


@st.cache_resource
def collection():
    return get_collection(STORE)


col = collection()
if col.count() == 0 and any(DATA.rglob("*.*")):  # fresh deploy: storage/ is not in git
    with st.spinner("First start: building the index (about a minute)… 🧠"):
        rebuild_index(STORE, load_all(DATA))
    st.cache_resource.clear()
    col = collection()
indexed = col.count()
st.session_state.setdefault("messages", [])
per_course = Counter(m["course"] for m in col.get(include=["metadatas"])["metadatas"]) if indexed else Counter()
courses = sorted(per_course)

with st.sidebar:
    st.markdown("<div class='brand'>🎓 Ask the course</div>", unsafe_allow_html=True)
    if courses:
        st.markdown("<div class='shelf-title'>📚 Your shelf</div>", unsafe_allow_html=True)
        st.markdown(
            "".join(
                f"<span class='chip' style='background:{CHIP_COLORS[i % 5]}'>{course_emoji(c)} {html.escape(c)} · {per_course[c]}</span>"
                for i, c in enumerate(courses)
            ),
            unsafe_allow_html=True,
        )
    chosen = st.multiselect("🔎 Search in", courses, default=courses, placeholder="All courses")
    top_k = st.slider("📄 Excerpts per question", 2, 8, 4)
    asked = sum(m["role"] == "user" for m in st.session_state.messages)
    st.markdown(f"<div class='status'>🔥 {asked} questions this session</div>", unsafe_allow_html=True)
    if st.button("🔄 Rebuild index", use_container_width=True):
        with st.spinner("Reading files and embedding… 🧠"):
            rebuild_index(STORE, load_all(DATA))
        st.cache_resource.clear()
        st.rerun()
    if st.session_state.messages and st.button("🧹 Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

if not indexed:
    st.markdown(
        "<div class='hero'><h1>📭 No index yet</h1><p>Add files under data/courses/&lt;course name&gt;/ "
        "and press Rebuild index in the sidebar.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()

q = st.chat_input("Ask anything about your courses… 💭") or st.session_state.pop("pending", None)

if not st.session_state.messages and not q:
    st.markdown(
        "<div class='hero'><div class='stickers'><span>🧠</span><span>📚</span><span>✨</span></div>"
        "<h1>What are we learning today? 🎓</h1>"
        "<p>Ask anything about your course files. I answer from them only, and show you the exact page it came from. 📖</p></div>",
        unsafe_allow_html=True,
    )
    for c, (emoji, s) in zip(st.columns(len(SUGGESTIONS)), SUGGESTIONS):
        c.button(f"{emoji}  {s}", on_click=lambda s=s: st.session_state.update(pending=s), use_container_width=True)


def with_chips(text):
    return re.sub(r"(?<![\w)\]])\[(\d+)\]", r"<span class='cite'>\1</span>", text)


def show_sources(hits, text):
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    for i, h in enumerate(hits, 1):
        if cited and i not in cited:
            continue
        with st.expander(f"{FILE_EMOJI.get(h.meta['type'], '📄')} {i} · {label(h)}"):
            pct = int(max(0, min(1, 1 - h.distance)) * 100)
            st.markdown(
                f"<div class='meta'><span>{course_emoji(h.meta['course'])} {html.escape(h.meta['course'])}</span>"
                f"<div class='meter'><i style='width:{pct}%'></i></div><span>🎯 {pct}% match</span></div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"<div class='note'>{html.escape(h.text).replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)


for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="😎" if m["role"] == "user" else "🤓"):
        st.markdown(with_chips(m["content"]), unsafe_allow_html=True)
        if m.get("hits"):
            show_sources(m["hits"], m["content"])

if q:
    st.session_state.messages.append({"role": "user", "content": q})
    with st.chat_message("user", avatar="😎"):
        st.markdown(q)
    with st.chat_message("assistant", avatar="🤓"):
        try:
            with st.spinner("Flipping through your notes… 📖"):
                hits = search(col, q, top_k, chosen or None)
                text = answer(q, hits)
        except Exception as e:  # missing key, network, etc.
            hits, text = [], f"😵 Something went wrong: `{e}`. Check ANTHROPIC_API_KEY in your .env file."
        st.markdown(with_chips(text), unsafe_allow_html=True)
        show_sources(hits, text)
    st.session_state.messages.append({"role": "assistant", "content": text, "hits": hits})
    found = bool(hits) and text != NOT_FOUND and not text.startswith("😵")
    st.toast("Found it in your notes!" if found else "Nothing in the notes for that one", icon="🎉" if found else "🤔")
