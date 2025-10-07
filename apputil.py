# ---------------------------------------------------------
# apputil.py
# ---------------------------------------------------------
# Loads environment variables and implements a custom
# Genius class for Exercises 1–3 with smarter artist matching.
# ---------------------------------------------------------

import os
import re
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv, find_dotenv


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------
dotenv_path = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parent / ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
if not ACCESS_TOKEN:
    print(
        "⚠️  ACCESS_TOKEN not found.\n"
        "Make sure your .env file exists and contains:\n"
        "ACCESS_TOKEN=your_real_genius_token_here\n"
        f"Checked: {dotenv_path}"
    )
else:
    print("✅ Environment variables loaded successfully.")


# ---------------------------------------------------------
# Exercises 1 – 3:  Custom Genius class
# ---------------------------------------------------------
class Genius:
    """
    A simplified Genius class that stores the API access token (Ex 1),
    retrieves artist information (Ex 2), and aggregates multiple artists
    into a DataFrame (Ex 3) using the Genius API.
    """

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.genius.com"
        self._headers = {"Authorization": f"Bearer {self.access_token}"}

    def __repr__(self):
        return f"Genius(access_token='{self.access_token[:6]}...')"

    # ---------- internal helpers ----------
    @staticmethod
    def _norm(s: str) -> str:
        """Normalize names for fuzzy comparison."""
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    def _pick_best_artist(self, search_term: str, hits: list):
        """Choose the most plausible primary_artist from /search hits."""
        if not hits:
            return None

        q = self._norm(search_term)

        def score(hit):
            name = hit["result"]["primary_artist"]["name"]
            n = self._norm(name)
            # exact match best, then prefix, then substring
            if n == q:
                return (3, -len(name))
            if n.startswith(q) or q in n.split():
                return (2, -len(name))
            if q in n:
                return (1, -len(name))
            return (0, -len(name))

        best = max(hits, key=score)
        return best["result"]["primary_artist"]

    # ---------- Exercise 2 ----------
    def get_artist(self, search_term: str):
        """
        Search Genius for an artist and return detailed artist info dict.
        """
        params = {"q": search_term}
        r = requests.get(f"{self.base_url}/search", headers=self._headers, params=params, timeout=15)
        r.raise_for_status()
        hits = r.json().get("response", {}).get("hits", [])

        primary = self._pick_best_artist(search_term, hits)
        if not primary:
            return None

        artist_id = primary["id"]
        r2 = requests.get(f"{self.base_url}/artists/{artist_id}", headers=self._headers, timeout=15)
        r2.raise_for_status()
        return r2.json().get("response", {}).get("artist", {})

    # ---------- Exercise 3 ----------
    def get_artists(self, search_terms):
        """
        For a list of artist names, return a DataFrame with:
          search_term | artist_name | artist_id | followers_count
        """
        rows = []
        for term in search_terms:
            try:
                artist = self.get_artist(term)
                rows.append({
                    "search_term": term,
                    "artist_name": artist.get("name") if artist else None,
                    "artist_id": artist.get("id") if artist else None,
                    "followers_count": artist.get("followers_count") if artist else None,
                })
            except Exception:
                rows.append({
                    "search_term": term,
                    "artist_name": None,
                    "artist_id": None,
                    "followers_count": None,
                })

        return pd.DataFrame(rows, columns=["search_term", "artist_name", "artist_id", "followers_count"])


# ---------------------------------------------------------
# Optional: instantiate default Genius object from .env
# ---------------------------------------------------------
genius = Genius(ACCESS_TOKEN) if ACCESS_TOKEN else None


# ---------------------------------------------------------# Example usage (uncomment to run)
# ---------------------------------------------------------
from apputil import genius

# Exercise 2 – single artist
artist_info = genius.get_artist("Radiohead")
print(artist_info["name"], artist_info["id"], artist_info.get("followers_count"))

# Exercise 3 – multiple artists
df = genius.get_artists(["Rihanna", "Tycho", "Seal", "U2"])
print(df)
