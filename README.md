<p align="center">
  <a href="https://fusionproxy.net/?utm_source=github&utm_medium=python-download-images">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/FusionProxies/.github/main/assets/logo-on-dark.png">
      <img src="https://raw.githubusercontent.com/FusionProxies/.github/main/assets/logo-on-light.png" alt="Fusion Proxy" height="52">
    </picture>
  </a>
</p>

# How to download images from a website with Python

Find every image on a page, download them in parallel, and save them safely: [`download_images.py`](download_images.py) handles relative and lazy-loaded image URLs, streams files to disk, names them safely, skips what you already have, checks that the answer really is an image, retries failures and can spread downloads over rotating proxies.

The example downloads the book covers from [books.toscrape.com](https://books.toscrape.com), a scraping sandbox:

```bash
pip install -r requirements.txt
python download_images.py --pages 2
python download_images.py --pages 2      # second run: nothing to download
```

```
40 images: {'saved': 40} in 1.5 s, folder 372 KB
40 images: {'skipped': 40} in 0.0 s, folder 372 KB
```

## 1. Find the image URLs

```python
soup = BeautifulSoup(html, "html.parser")
for img in soup.select("article.product_pod img"):
    src = img.get("data-src") or img.get("src")   # lazy loading keeps the real URL in data-src
    url = urljoin(page_url, src)                   # "../media/cover.jpg" -> full URL
```

Also look at `srcset` (several sizes, take the largest), `<picture><source srcset>` and CSS `background-image` URLs if images are missing.

## 2. Stream each file to disk

```python
with session.get(url, stream=True, timeout=30) as r:
    r.raise_for_status()
    if not r.headers.get("Content-Type", "").startswith("image/"):
        return "not an image"                       # an error page saved as .jpg is a classic bug
    with open(tmp_path, "wb") as f:
        for chunk in r.iter_content(64 * 1024):     # never load a large file into memory
            f.write(chunk)
tmp_path.replace(final_path)                        # only complete files get the final name
```

Writing to a `.part` file first means a crash never leaves a half-written image that looks complete.

## 3. Safe, unique file names

URLs can contain characters that are illegal in file names, and two different images can share a name (`cover.jpg`). The script builds the name from the `alt` text plus a short hash of the URL:

```
A-Light-in-the-Attic-281d7495.jpg
```

The extension comes from the `Content-Type`, not from the URL, which often has none or lies.

## 4. Download in parallel, politely

```python
with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(lambda job: download(session, *job), jobs))
```

Downloads are network-bound, so threads work well. One shared `Session` reuses connections (`pool_maxsize` is raised to match the workers), and `Retry` repeats `429` and `5xx` answers with a pause. Keep the worker count modest: image servers rate-limit like any other.

## 5. Rotating proxies for large jobs

Thousands of downloads from one IP get throttled. With `FUSION_USER` and `FUSION_PASS` set, the script sends every connection through a rotating residential gateway, so the downloads spread over many IPs:

```python
proxy = f"http://{user}-country-us:{password}@resi.fusionproxy.net:12286"
session.proxies.update({"http": proxy, "https": proxy})
```

Images are large compared with HTML, so they are most of your proxy traffic. Download only the sizes you need, and skip files you already have (the script does both).

## Copyright

Images are usually copyrighted. Download only what you are allowed to use, and respect the site's terms and `robots.txt`.

## Related

- [python-web-scraping](https://github.com/FusionProxies/python-web-scraping): the scraping basics
- [python-async-scraping](https://github.com/FusionProxies/python-async-scraping): asyncio for many requests at once
- [rotating-proxies-python](https://github.com/FusionProxies/rotating-proxies-python): rotate a proxy list or use a gateway

[Fusion Proxy residential proxies](https://fusionproxy.net/proxies/residential?utm_source=github&utm_medium=python-download-images) from $2.95/GB, with a [free trial](https://fusionproxy.net/free-trial?utm_source=github&utm_medium=python-download-images).

## License

MIT, see [LICENSE](LICENSE).
