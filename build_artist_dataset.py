# build_artist_dataset.py
import argparse
import os
from pathlib import Path
from multiprocessing import Pool, cpu_count
import pandas as pd
from tqdm import tqdm
from time import sleep
from apputil import Genius, ACCESS_TOKEN


def read_artists(path: str):
    p = Path(path)
    print(f"Reading artists from: {p.resolve()}")
    if not p.exists():
        raise FileNotFoundError(f"artists file not found: {p.resolve()}")

    lines = p.read_text(encoding="utf-8-sig").splitlines()
    artists = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]

    print(f"Found {len(lines)} lines, {len(artists)} usable artist names.")
    if len(artists) == 0:
        raise ValueError("No artist names parsed — check encoding or blank lines.")

    return artists


def _worker(term: str):
    g = Genius(ACCESS_TOKEN)
    try:
        info = g.get_artist(term)
        sleep(0.1)
        return {
            "search_term": term,
            "artist_name": info.get("name") if info else None,
            "artist_id": info.get("id") if info else None,
            "followers_count": info.get("followers_count") if info else None,
        }
    except Exception:
        return {"search_term": term, "artist_name": None,
                "artist_id": None, "followers_count": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artists", default="artists.txt")
    parser.add_argument("--out", default="data/genius_artists.csv")
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()

    if not ACCESS_TOKEN:
        raise RuntimeError("ACCESS_TOKEN not found in .env")

    artists = read_artists(args.artists)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.workers > 0:
        n = min(args.workers, cpu_count())
        print(f"Using multiprocessing with {n} workers...")
        with Pool(n) as pool:
            rows = list(tqdm(pool.imap_unordered(_worker, artists), total=len(artists)))
        df = pd.DataFrame(rows)
    else:
        print("Using single-process mode...")
        g = Genius(ACCESS_TOKEN)
        df = g.get_artists(artists)

    df.to_csv(out_path, index=False)
    print(f"✅ Saved {len(df)} rows to {out_path.resolve()}")


if __name__ == "__main__":
    main()
