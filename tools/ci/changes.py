"""Which CI tests a change needs.

Necessary (every push): the static checks, a few seconds.
Conditional: the browser tests (3 parallel jobs) run only when a changed file can
change what the browser loads. Anything not listed in SKIP runs them, so a new
kind of file is tested by default.

    python tools/ci/changes.py HEAD~1            # this repo, against a commit
    git diff --name-only A B | python tools/ci/changes.py -

Prints browser=true|false (the GitHub Actions output line) and why.
"""

import re
import subprocess
import sys

# Files the browser tests never load. Generators under tools/ write their output
# into site files (pages, assets, vendor/), and those changes trigger the tests.
SKIP = [
    r".*\.md",  # docs
    r"\.gitignore",
    r"CNAME",
    r"_headers",  # read by Cloudflare only, not by the local test server
    r"robots\.txt",
    r"sitemap\.xml",
    r"llms(-full)?\.txt",
    r"articles/feed\.xml",
    r"[0-9a-f]{32}\.txt",  # IndexNow key
    r"tools/(?!ci/).*",  # generators, not the tests
]
SKIP_RE = re.compile("|".join(f"(?:{p})" for p in SKIP))


def needs_browser(paths):
    """(bool, the first path that needs the browser tests or None)."""
    for p in paths:
        if p and not SKIP_RE.fullmatch(p):
            return True, p
    return False, None


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "-"
    if arg == "-":
        paths = sys.stdin.read().split()
    else:
        paths = subprocess.run(["git", "diff", "--name-only", arg], capture_output=True, text=True, check=True).stdout.split()
    run, why = needs_browser(paths)
    print(f"browser={'true' if run else 'false'}")
    print(f"{len(paths)} changed; " + (f"{why} needs the browser tests" if run else "none needs the browser tests"), file=sys.stderr)


if __name__ == "__main__":
    main()
