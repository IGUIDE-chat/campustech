"""Add a content hash to every local CSS/JS URL (?v=<hash>).

Cloudflare serves CSS and JS with a 4-hour browser cache while HTML is always
revalidated, so without this a returning visitor gets new HTML with old CSS/JS
for up to 4 hours after a deploy. A changed file gets a new URL, so it is
fetched fresh; unchanged files keep their URL and stay cached.

Run after editing anything in src/ or vendor/ (build_pages.py runs it too):

    python tools/stamp_assets.py
"""

import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()[:10]


def main():
    # ES module imports inside main.js first, since they change main.js's own hash.
    main_js = ROOT / "src" / "main.js"
    text = main_js.read_text(encoding="utf-8")
    stamped = re.sub(
        r'from "\./([\w.-]+\.js)(?:\?v=[0-9a-f]+)?"',
        lambda m: f'from "./{m.group(1)}?v={digest(ROOT / "src" / m.group(1))}"',
        text,
    )
    if stamped != text:
        main_js.write_text(stamped, encoding="utf-8")

    pattern = re.compile(r'((?:\./|/|(?:\.\./)+)?)((?:src|vendor)/[\w.-]+\.(?:js|css))(?:\?v=[0-9a-f]+)?"')
    hashes = {}

    def stamp(m):
        rel = m.group(2)
        if rel not in hashes:
            hashes[rel] = digest(ROOT / rel)
        return f'{m.group(1)}{rel}?v={hashes[rel]}"'

    pages = [p for p in ROOT.rglob("*.html") if "tools" not in p.parts and ".git" not in p.parts]
    for page in pages:
        html = page.read_text(encoding="utf-8")
        new = pattern.sub(stamp, html)
        if new != html:
            page.write_text(new, encoding="utf-8")
    print(f"stamped {len(hashes)} assets in {len(pages)} pages")


if __name__ == "__main__":
    main()
