# app.py — Week 6 "Genius Explorer"
# Intricate Streamlit app: single-artist search, batch processing,
# parallel fetching, interactive charts, CSV export, and caching.

import os
from pathlib import Path
from typing import List, Dict, Optional
import time
import textwrap
import concurrent.futures as cf

import pandas as pd
import altair as alt
import streamlit as st

# Your utilities (Exercises 1–3)
from apputil import Genius, ACCESS_TOKEN, genius as default_genius


# =============== App Config & Helpers ===============

st.set_page_config(
    page_title="Genius Explorer — Week 6",
    page_icon="🎵",
    layout="wide"
)

THEME_NOTE = """
<style>
/* Subtle polish */
.reportview-container .markdown-text-container { font-size: 1.0rem; }
.block-container { padding-top: 1.8rem; }
div.stButton > button:first-child { border-radius: 12px; padding: 0.6rem 1rem; }
div[data-testid="stMetricValue"] { font-weight: 700; }
</style>
"""
st.write(THEME_NOTE, unsafe_allow_html=True)

# Cache the API client so we don’t re-create it every rerun
@st.cache_resource(show_spinner=False)
def get_client() -> Genius:
    if not ACCESS_TOKEN:
        st.stop()
    # Prefer the default instance if it exists and has a token
    if default_genius:
        return default_genius
    return Genius(ACCESS_TOKEN)

# Cache per-artist results for 10 minutes
@st.cache_data(show_spinner=False, ttl=600)
def cached_get_artist(name: str) -> Optional[Dict]:
    g = get_client()
    return g.get_artist(name)

# Batch fetch with threads (I/O bound -> threads > processes in Streamlit)
def fetch_batch(artists: List[str], max_workers: int = 6) -> pd.DataFrame:
    rows: List[Dict] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(cached_get_artist, a.strip()): a.strip()
                   for a in artists if a and a.strip()}
        progress = st.progress(0.0, text="Fetching artists…")
        total = len(futures)
        done = 0
        for fut in cf.as_completed(futures):
            name = futures[fut]
            try:
                artist = fut.result()
                rows.append({
                    "search_term": name,
                    "artist_name": (artist or {}).get("name"),
                    "artist_id": (artist or {}).get("id"),
                    "followers_count": (artist or {}).get("followers_count"),
                    "url": (artist or {}).get("url"),
                    "image_url": (artist or {}).get("image_url"),
                })
            except Exception:
                rows.append({
                    "search_term": name,
                    "artist_name": None, "artist_id": None,
                    "followers_count": None, "url": None, "image_url": None
                })
            done += 1
            progress.progress(done / total, text=f"Fetching artists… ({done}/{total})")

    df = pd.DataFrame(rows, columns=[
        "search_term", "artist_name", "artist_id",
        "followers_count", "url", "image_url"
    ])
    return df


def clean_artist_list(raw: str) -> List[str]:
    lines = [ln.strip() for ln in raw.splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def _metric_card(label: str, value, help_text: str = ""):
    c1, c2 = st.columns([1, 3])
    with c1:
        st.metric(label, value)
    with c2:
        if help_text:
            st.caption(help_text)


# =============== Sidebar ===============

with st.sidebar:
    st.header("⚙️ Settings")
    token_ok = bool(ACCESS_TOKEN)
    st.success("ACCESS_TOKEN loaded") if token_ok else st.error("Missing ACCESS_TOKEN in .env")

    max_workers = st.slider("Parallel workers", 1, 16, 6,
                            help="Threaded requests; safe for Streamlit & I/O-bound APIs.")
    show_images = st.toggle("Show artist images", value=True)
    st.caption("Tip: Results are cached for 10 minutes to keep things snappy.")

# =============== Header ===============

st.title("🎵 Genius Explorer — APIs & Multiprocessing (Week 6)")
st.markdown(
    "Search artists, batch-enrich from the Genius API, explore results, and export to CSV. "
    "Implements your exercises with caching and parallelism."
)

# =============== Tabs ===============

tab1, tab2, tab3 = st.tabs(["🔍 Single Artist", "📚 Batch (TXT / Paste / Upload)", "📈 Explore & Export"])

# ---------- TAB 1: Single Artist Search ----------
with tab1:
    st.subheader("Search a single artist")

    col1, col2 = st.columns([2, 1])
    with col1:
        query = st.text_input("Artist name", value="Radiohead")
    with col2:
        st.write("")
        run_single = st.button("Search", type="primary", use_container_width=True)

    if run_single and query:
        with st.spinner("Contacting Genius…"):
            t0 = time.time()
            info = cached_get_artist(query)
            dt = time.time() - t0

        if info:
            left, right = st.columns([1, 2])
            with left:
                if show_images and info.get("image_url"):
                    st.image(info["image_url"], caption=info["name"], use_container_width=True)
            with right:
                st.markdown(f"### {info['name']}")
                _metric_card("Artist ID", info.get("id"))
                _metric_card("Followers", info.get("followers_count", "N/A"))
                st.markdown(f"[Open on Genius]({info.get('url')})")
                st.caption(f"Fetched in {dt:.2f}s (cached: {'yes' if dt < 0.05 else 'no'})")
        else:
            st.warning("No results found. Try a different spelling.")

# ---------- TAB 2: Batch Mode ----------
with tab2:
    st.subheader("Batch lookup (100+ artists recommended)")
    st.caption("Provide artists via TXT file, or paste names (one per line).")

    colA, colB = st.columns(2)
    with colA:
        uploaded = st.file_uploader("Upload artists.txt", type=["txt"], accept_multiple_files=False)
        if uploaded:
            raw_text = uploaded.read().decode("utf-8", errors="ignore")
        else:
            # Fallback: try project-root artists.txt
            default_path = Path("artists.txt")
            raw_text = ""
            if default_path.exists():
                raw_text = default_path.read_text(encoding="utf-8", errors="ignore")
                st.caption(f"Loaded {default_path.resolve()}")

    with colB:
        pasted = st.text_area(
            "Or paste artist names here",
            value="Rihanna\nTycho\nSeal\nU2\nRadiohead\nBillie Eilish\nAdele",
            height=180
        )

    batch_text = pasted if pasted.strip() else raw_text
    artists_list = clean_artist_list(batch_text) if batch_text else []

    st.write(f"Detected **{len(artists_list)}** artist names.")
    run_batch = st.button("Process batch", type="primary")

    if run_batch and artists_list:
        df = fetch_batch(artists_list, max_workers=max_workers)
        st.session_state["batch_df"] = df
        st.success(f"Fetched {len(df)} rows.")
        st.dataframe(df, use_container_width=True, hide_index=True)

# ---------- TAB 3: Explore & Export ----------
with tab3:
    st.subheader("Explore results")

    df: Optional[pd.DataFrame] = st.session_state.get("batch_df")
    if df is None:
        st.info("No batch results yet. Use the Batch tab to fetch artists first.")
    else:
        # Filters
        col1, col2, col3 = st.columns([1.2, 1, 2])
        with col1:
            min_follow = st.number_input("Min followers", value=0, step=10)
        with col2:
            only_matched = st.toggle("Only matched", value=True,
                                     help="Hide rows where no artist was found.")
        with col3:
            name_filter = st.text_input("Filter by (partial) name", value="")

        filtered = df.copy()
        if only_matched:
            filtered = filtered[filtered["artist_name"].notna()]
        if name_filter.strip():
            m = filtered["artist_name"].fillna("").str.contains(name_filter.strip(), case=False, regex=False)
            filtered = filtered[m]
        if min_follow > 0:
            filtered = filtered[(filtered["followers_count"].fillna(0) >= min_follow)]

        st.dataframe(filtered, use_container_width=True, hide_index=True)

        # Top 15 by followers chart
        topN = st.slider("Top-N by followers", 5, 50, 15)
        chart_df = (
            filtered.dropna(subset=["artist_name", "followers_count"])
                    .sort_values("followers_count", ascending=False)
                    .head(topN)
        )

        if len(chart_df) > 0:
            chart = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X("followers_count:Q", title="Followers"),
                    y=alt.Y("artist_name:N", sort="-x", title="Artist"),
                    tooltip=["artist_name", "followers_count", "artist_id"]
                )
                .properties(height=400)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.warning("No rows available for chart after filters.")

        # Download
        st.markdown("### Export")
        colx, coly = st.columns(2)
        with colx:
            st.download_button(
                "⬇️ Download filtered CSV",
                data=filtered.to_csv(index=False).encode("utf-8"),
                file_name="genius_artists_filtered.csv",
                mime="text/csv"
            )
        with coly:
            st.download_button(
                "⬇️ Download full batch CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="genius_artists_full.csv",
                mime="text/csv"
            )

# =============== Footer ===============
st.markdown("---")
st.caption(
    "Built with Streamlit • Cached API calls • Threaded batch requests • Altair charts • "
    "Implements Exercises 1–3 + bonus.\n"
    "Tip: results cache for 10 minutes; change inputs to refresh."
)
# ---------------------------------------------------------
# apputil.py — Week 6 "Genius Explorer"
# Exercises 1–3: Genius API client with search, single artist,
# and batch fetching with pandas DataFrame output.