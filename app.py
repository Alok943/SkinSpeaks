import streamlit as st
import requests

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="SkinSpeaks | Semantic Search",
    page_icon="🧴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────
# CUSTOM CSS — Clean, premium dark skin-care aesthetic
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300&family=DM+Sans:wght@300;400;500&display=swap');

/* ── Reset & Base ── */
* { box-sizing: border-box; }

.stApp {
    background: #0d0d0d;
    color: #f0ece4;
    font-family: 'DM Sans', sans-serif;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 4rem 4rem 4rem; max-width: 1200px; margin: 0 auto; }

/* ── Hero Header ── */
.hero {
    text-align: center;
    padding: 3.5rem 0 2rem 0;
    border-bottom: 1px solid #2a2a2a;
    margin-bottom: 2.5rem;
}
.hero-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #c9a96e;
    margin-bottom: 1rem;
}
.hero-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 3.8rem;
    font-weight: 300;
    line-height: 1.1;
    color: #f0ece4;
    margin: 0 0 0.75rem 0;
    letter-spacing: -0.02em;
}
.hero-title em {
    font-style: italic;
    color: #c9a96e;
}
.hero-sub {
    font-size: 0.9rem;
    color: #666;
    font-weight: 300;
    letter-spacing: 0.05em;
}

/* ── Search Bar ── */
.stTextInput > div > div > input {
    background: #151515 !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 2px !important;
    color: #f0ece4 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 1rem !important;
    padding: 1rem 1.25rem !important;
    transition: border-color 0.2s ease;
}
.stTextInput > div > div > input:focus {
    border-color: #c9a96e !important;
    box-shadow: none !important;
}
.stTextInput > div > div > input::placeholder {
    color: #444 !important;
}
.stTextInput label { display: none !important; }

/* ── Filters ── */
.stSelectbox > div > div {
    background: #151515 !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 2px !important;
    color: #f0ece4 !important;
}
.stSelectbox label {
    color: #888 !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    font-weight: 500 !important;
}
.stNumberInput > div > div > input {
    background: #151515 !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 2px !important;
    color: #f0ece4 !important;
}
.stNumberInput label {
    color: #888 !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    font-weight: 500 !important;
}

/* ── Results Header ── */
.results-meta {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #1e1e1e;
}
.results-count {
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.8rem;
    font-weight: 300;
    color: #c9a96e;
}
.results-label {
    font-size: 0.75rem;
    color: #555;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.latency-badge {
    margin-left: auto;
    font-size: 0.7rem;
    color: #444;
    letter-spacing: 0.1em;
    font-family: 'DM Mono', monospace;
}

/* ── Product Card ── */
.product-card {
    background: #111;
    border: 1px solid #1e1e1e;
    border-radius: 3px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s ease, transform 0.2s ease;
    display: flex;
    gap: 1.5rem;
    align-items: flex-start;
}
.product-card:hover {
    border-color: #2e2e2e;
    transform: translateY(-1px);
}
.product-image {
    width: 90px;
    height: 90px;
    object-fit: cover;
    border-radius: 2px;
    flex-shrink: 0;
    background: #1a1a1a;
}
.product-image-placeholder {
    width: 90px;
    height: 90px;
    background: #1a1a1a;
    border-radius: 2px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
}
.product-info { flex: 1; min-width: 0; }
.product-brand {
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #c9a96e;
    margin-bottom: 0.3rem;
    font-weight: 500;
}
.product-name {
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.15rem;
    font-weight: 400;
    color: #f0ece4;
    line-height: 1.3;
    margin-bottom: 0.5rem;
}
.product-meta {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.6rem;
}
.product-price {
    font-size: 0.95rem;
    font-weight: 500;
    color: #f0ece4;
}
.product-score {
    font-size: 0.7rem;
    color: #444;
    letter-spacing: 0.05em;
}
.score-bar-bg {
    display: inline-block;
    width: 60px;
    height: 3px;
    background: #222;
    border-radius: 2px;
    vertical-align: middle;
    margin-left: 0.3rem;
}
.score-bar-fill {
    height: 100%;
    border-radius: 2px;
    background: linear-gradient(90deg, #c9a96e, #e8d5b0);
}
.product-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.5rem;
}
.tag {
    font-size: 0.65rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #555;
    border: 1px solid #222;
    padding: 0.2rem 0.5rem;
    border-radius: 1px;
}
.product-link {
    font-size: 0.7rem;
    color: #444;
    text-decoration: none;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-top: 0.75rem;
    display: inline-block;
    transition: color 0.2s;
}
.product-link:hover { color: #c9a96e; }

/* ── Empty / Error States ── */
.empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: #333;
}
.empty-state-icon {
    font-size: 2.5rem;
    margin-bottom: 1rem;
    opacity: 0.4;
}
.empty-state-text {
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.3rem;
    font-weight: 300;
    color: #444;
}
.empty-state-hint {
    font-size: 0.75rem;
    color: #333;
    margin-top: 0.5rem;
    letter-spacing: 0.05em;
}

/* ── Suggested Queries ── */
.suggestions-label {
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #444;
    margin-bottom: 0.75rem;
}
.stButton > button {
    background: transparent !important;
    border: 1px solid #222 !important;
    border-radius: 2px !important;
    color: #666 !important;
    font-size: 0.75rem !important;
    font-family: 'DM Sans', sans-serif !important;
    padding: 0.4rem 0.85rem !important;
    letter-spacing: 0.05em !important;
    transition: all 0.2s ease !important;
    white-space: nowrap !important;
}
.stButton > button:hover {
    border-color: #c9a96e !important;
    color: #c9a96e !important;
    background: transparent !important;
}

/* ── Divider ── */
hr { border-color: #1a1a1a !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0d0d0d; }
::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────
if "query" not in st.session_state:
    st.session_state.query = ""

# ──────────────────────────────────────────────
# HERO
# ──────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-label">Semantic Search Engine</div>
    <h1 class="hero-title">Skin<em>Speaks</em></h1>
    <p class="hero-sub">Search in English, Hindi, or Hinglish — we understand intent, not just keywords.</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SEARCH INPUT
# ──────────────────────────────────────────────
query = st.text_input(
    label="search",
    placeholder="e.g.  moisturizer for dry skin  ·  oily skin ke liye face wash  ·  gentle cleanser under 500",
    value=st.session_state.query,
    key="search_input",
)

# ──────────────────────────────────────────────
# FILTERS (collapsed by default — clean look)
# ──────────────────────────────────────────────
with st.expander("Filters", expanded=False):
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        brand_filter = st.selectbox(
            "Brand",
            options=["All", "Minimalist", "The Derma Co"],
        )
    with fcol2:
        category_filter = st.selectbox(
            "Category",
            options=["All", "Skin Care", "Kit", "Body Care", "Hair Care"],
        )
    with fcol3:
        price_filter = st.number_input(
            "Max Price (₹)",
            min_value=0,
            max_value=5000,
            value=0,
            step=100,
        )

top_k = 6  # Sweet spot for demo — enough to impress, not overwhelming

# ──────────────────────────────────────────────
# SUGGESTED QUERIES
# ──────────────────────────────────────────────
if not query:
    st.markdown('<div class="suggestions-label">Try these</div>', unsafe_allow_html=True)
    suggestions = [
        "moisturizer for dry skin",
        "oily skin face wash",
        "gentle cleanser under ₹500",
        "anti-aging serum",
        "sunscreen for sensitive skin",
        "vitamin C serum",
    ]
    cols = st.columns(len(suggestions))
    for i, suggestion in enumerate(suggestions):
        with cols[i]:
            if st.button(suggestion, key=f"sug_{i}"):
                st.session_state.query = suggestion
                st.rerun()

# ──────────────────────────────────────────────
# SEARCH EXECUTION
# ──────────────────────────────────────────────
if query:
    payload = {"query": query, "top_k": top_k}

    if brand_filter != "All":
        payload["brand"] = brand_filter
    if category_filter != "All":
        payload["category"] = category_filter
    if price_filter > 0:
        payload["max_price"] = float(price_filter)

    try:
        with st.spinner(""):
            res = requests.post("http://localhost:8000/search", json=payload, timeout=30)
            data = res.json()

        results = data.get("results", [])
        count = data.get("results_count", 0)
        latency = data.get("latency_ms", 0)

        # ── Results Header ──
        st.markdown(f"""
        <div class="results-meta">
            <span class="results-count">{count}</span>
            <span class="results-label">{'product found' if count == 1 else 'products found'}</span>
            <span class="latency-badge">{latency}ms</span>
        </div>
        """, unsafe_allow_html=True)

        if count == 0:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">◯</div>
                <div class="empty-state-text">No products matched your search.</div>
                <div class="empty-state-hint">Try broader terms or remove filters.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for prod in results:
                # Parse tags
                tags = []
                if prod.get("tags"):
                    tags = [t.strip() for t in prod["tags"].split(",") if t.strip()][:4]

                # Score bar (normalize 0.5–1.0 range for display)
                score = prod.get("score", 0)
                score_pct = min(100, max(0, int((score - 0.5) / 0.5 * 100)))
                score_display = f"{score:.2f}" if score else ""

                # Tags HTML
                tags_html = "".join([f'<span class="tag">{t}</span>' for t in tags])

                # Product link
                url = prod.get("product_url", "")
                link_html = f'<a href="{url}" target="_blank" class="product-link">View Product →</a>' if url else ""

                # Image
                img_url = prod.get("image_url", "")
                if img_url:
                    image_html = f'<img src="{img_url}" class="product-image" onerror="this.style.display=\'none\';this.nextSibling.style.display=\'flex\';"/><div class="product-image-placeholder" style="display:none">🧴</div>'
                else:
                    image_html = '<div class="product-image-placeholder">🧴</div>'

                st.markdown(f"""
                <div class="product-card">
                    {image_html}
                    <div class="product-info">
                        <div class="product-brand">{prod.get('brand', '')}</div>
                        <div class="product-name">{prod.get('product_name', '')}</div>
                        <div class="product-meta">
                            <span class="product-price">₹{prod.get('price', '')}</span>
                            <span class="product-score">
                                {score_display}
                                <span class="score-bar-bg"><span class="score-bar-fill" style="width:{score_pct}%"></span></span>
                            </span>
                        </div>
                        <div class="product-tags">{tags_html}</div>
                        {link_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    except requests.exceptions.ConnectionError:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">⊘</div>
            <div class="empty-state-text">Cannot reach the search API.</div>
            <div class="empty-state-hint">Make sure FastAPI is running on port 8000 — <code>uvicorn search_api:app --reload</code></div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Unexpected error: {e}")

# ──────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center; color:#222; font-size:0.65rem; letter-spacing:0.15em; text-transform:uppercase; border-top:1px solid #1a1a1a; padding-top:1.5rem;">
    SkinSpeaks · Semantic Search · Powered by paraphrase-multilingual-mpnet-base-v2 + Qdrant
</div>
""", unsafe_allow_html=True)