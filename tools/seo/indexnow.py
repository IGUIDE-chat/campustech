"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver and others; not Google)
that the site's pages changed, so they recrawl now instead of eventually.

    python tools/seo/indexnow.py            # every URL in sitemap.xml
    python tools/seo/indexnow.py /cases /faq

Run it after a deploy is live. The key file (the hex-named .txt at the repo root)
proves we own the site; IndexNow fetches it from the live domain.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://campustech.iguide.chat"


def key():
    keys = [p for p in ROOT.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}\.txt", p.name)]
    if len(keys) != 1:
        sys.exit(f"expected one IndexNow key file at the repo root, found {len(keys)}")
    return keys[0].stem


def urls():
    if len(sys.argv) > 1:
        return [SITE + (u if u.startswith("/") else "/" + u) for u in sys.argv[1:]]
    return re.findall(r"<loc>(.*?)</loc>", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))


def main():
    k = key()
    body = {"host": SITE.split("//")[1], "key": k, "keyLocation": f"{SITE}/{k}.txt", "urlList": urls()}
    request = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(f"IndexNow: HTTP {response.status} for {len(body['urlList'])} URLs")


if __name__ == "__main__":
    main()
