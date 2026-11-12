"""Download images from a website with Python: find the image URLs, stream them to disk in parallel.

Downloads the book covers from https://books.toscrape.com (a scraping sandbox):
safe file names, skips files you already have, checks the content type, retries,
and an optional residential proxy.

    pip install -r requirements.txt
    python download_images.py --pages 2
"""
import argparse
import hashlib
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

START = "https://books.toscrape.com/catalogue/page-{}.html"
OUT = Path("images")
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/avif": ".avif"}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    user, password = os.environ.get("FUSION_USER"), os.environ.get("FUSION_PASS")
    if user and password:  # rotating residential IPs: downloads spread over many IPs
        p = f"http://{user}-country-{os.environ.get('FUSION_COUNTRY', 'us')}:{password}@resi.fusionproxy.net:12286"
        s.proxies.update({"http": p, "https": p})
    return s


def image_urls(session: requests.Session, page_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(session.get(page_url, timeout=30).text, "html.parser")
    out = []
    for img in soup.select("article.product_pod img"):
        src = img.get("data-src") or img.get("src")  # lazy-loaded images keep the real URL in data-src
        if src:
            out.append((urljoin(page_url, src), img.get("alt", "")))
    return out


def safe_name(url: str, alt: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", alt).strip("-")[:60] or Path(urlparse(url).path).stem
    return f"{base}-{hashlib.sha1(url.encode()).hexdigest()[:8]}"  # short hash keeps names unique


def download(session: requests.Session, url: str, alt: str) -> str:
    stem = safe_name(url, alt)
    existing = list(OUT.glob(stem + ".*"))
    if existing:
        return "skipped"
    with session.get(url, stream=True, timeout=30) as r:  # stream: never hold a big file in memory
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "").split(";")[0]
        if not ctype.startswith("image/"):
            return f"not an image ({ctype})"
        path = OUT / (stem + EXT.get(ctype, Path(urlparse(url).path).suffix or ".img"))
        tmp = path.with_suffix(path.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(64 * 1024):
                f.write(chunk)
        tmp.replace(path)  # only complete files get the final name
    return "saved"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    session = make_session()

    jobs = []
    for n in range(1, a.pages + 1):
        jobs += image_urls(session, START.format(n))
        time.sleep(0.5)
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        results = list(pool.map(lambda j: download(session, *j), jobs))
    counts = {k: results.count(k) for k in set(results)}
    size = sum(p.stat().st_size for p in OUT.iterdir()) / 1024
    print(f"{len(jobs)} images: {counts} in {time.perf_counter() - start:.1f} s, folder {size:.0f} KB")


if __name__ == "__main__":
    main()
