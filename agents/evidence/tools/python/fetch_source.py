"""Fetch a public URL and return only verbatim passages relevant to given keywords, so the Evidence agent can quote
what a source actually says. The full page text is cached under cache/pages/ so a citation's quote can be re-checked."""
import hashlib, html, json, os, re, urllib.request
from omnigent_client import tool

ROOT = os.environ.get("TRIAGE_LAB_ROOT", os.path.expanduser("~/hack-nation/triage-lab"))


@tool
def fetch_source(url: str, keywords: str = "detect,monitor,false positive,alert") -> str:
    """
    Fetch a public web page and return passages that contain any of the given keywords.

    :param url: The https URL to fetch.
    :param keywords: Comma-separated keywords; passages (sentences) containing any are returned.
    :returns: JSON string ``{"url", "status": "FETCHED"|"UNVERIFIED", "title", "passages": [verbatim sentences],
        "error"}``. Only quote text that appears in ``passages``. A page that fails to fetch is UNVERIFIED and
        cannot support a claim.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "triage-lab-research/1.0"})
        raw = urllib.request.urlopen(req, timeout=20).read(3_000_000).decode("utf-8", "ignore")
        title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", raw, flags=re.S)
        text = re.sub(r"\s+", " ", html.unescape(text)).strip()
        os.makedirs(os.path.join(ROOT, "cache", "pages"), exist_ok=True)
        open(os.path.join(ROOT, "cache", "pages", hashlib.sha1(url.encode()).hexdigest() + ".txt"), "w").write(text)
        kws = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        sents = re.split(r"(?<=[.!?])\s+", text)
        hits = [s for s in sents if 40 < len(s) < 420 and any(k in s.lower() for k in kws)]
        return json.dumps({"url": url, "status": "FETCHED", "title": html.unescape(title.group(1).strip()) if title else "",
                           "n_matching_passages": len(hits), "passages": hits[:8]})
    except Exception as e:
        return json.dumps({"url": url, "status": "UNVERIFIED", "title": "", "passages": [],
                           "error": f"{type(e).__name__}: {e}"})
