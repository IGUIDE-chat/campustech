"""Build the static sub pages (past, privacy, terms, articles) from one template.

    python tools/pages/build_pages.py

The site has no build step; this only writes plain HTML files so that every
page shares the same head (SEO tags, structured data), nav, pull cord,
backgrounds and scripts. Edit the content below, then run it again.
index.html is hand-written and not touched.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://campustech.iguide.chat/"
ORG_NAME = "Campus Tech @ University of Illinois Urbana-Champaign"
EMAIL = "techadmin.campustech@gmail.com"
APPLY = "https://docs.google.com/forms/d/e/1FAIpQLSeMlEGqn8lX7ka1y2-GVmQar_kuUYhIb8R-hxnGsNKfClFnXA/viewform"
PITCH = "https://docs.google.com/forms/d/e/1FAIpQLSeGh0xz6b-Ff0ADiqt3NYOjejxRsqgJLmz76ZMfjiONmeDLEw/viewform"
UPDATED = "2026-11-17"


def pretty(path):
    """Public URL path as Cloudflare Pages serves it: no ".html", no "index"."""
    if path.endswith("index.html"):
        return path[: -len("index.html")]
    return path[:-5] if path.endswith(".html") else path

PUBLISHER = {"@type": "Organization", "@id": SITE + "#org", "name": ORG_NAME, "url": SITE}


def page(path, title, description, body, active="", schema=None, og_type="website", noindex=False, absolute=False):
    depth = path.count("/")
    up = "/" if absolute else "../" * depth
    url = SITE + pretty(path)
    robots = "noindex, follow" if noindex else "index, follow, max-image-preview:large"
    ld = ""
    for block in schema or []:
        ld += f'  <script type="application/ld+json">{json.dumps(block, ensure_ascii=False)}</script>\n'

    def nav_link(href, label, key):
        current = ' class="active" aria-current="page"' if key == active else ""
        return f'      <a href="{href}"{current}>{label}</a>\n'

    nav = (
        nav_link(f"{up}./", "Home", "home")
        + nav_link(f"{up}./#products", "Products", "")
        + nav_link(f"{up}./#join", "Join", "")
        + nav_link(f"{up}./#team", "Team", "")
        + nav_link(f"{up}past.html", "Past", "past")
        + nav_link(f"{up}articles/", "Articles", "articles")
        + nav_link(f"{up}./#contact", "Contact", "")
    )
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{url}">
  <meta name="robots" content="{robots}">
  <meta property="og:type" content="{og_type}">
  <meta property="og:site_name" content="Campus Tech">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{SITE}assets/og.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{SITE}assets/og.png">
  <meta name="theme-color" content="#0d0d12">
  <link rel="icon" href="{up}assets/favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="{up}assets/apple-touch-icon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{up}vendor/pullcord.css">
  <link rel="stylesheet" href="{up}src/style.css">
  <script>
    try {{ if (localStorage.getItem("campustech-theme") === "light") document.documentElement.dataset.theme = "light" }} catch (e) {{}}
  </script>
{ld}  <!-- Loading screen: only appears if the page takes longer than ~0.35s, so fast
       loads never see it; hidden on window load (8s safety cut-off). Inline so it
       works before the stylesheet arrives. -->
  <style>
    #loader{{position:fixed;inset:0;z-index:100;display:grid;place-items:center;background:#0d0d12;opacity:0;visibility:hidden;animation:loader-in .25s ease .35s forwards}}
    :root[data-theme="light"] #loader{{background:#fff}}
    #loader div{{display:flex;gap:12px}}
    #loader i{{width:10px;height:10px;border-radius:50%;animation:loader-dot 1s ease-in-out infinite}}
    #loader i:nth-child(1){{background:#f967fb}}
    #loader i:nth-child(2){{background:#6958d5;animation-delay:.15s}}
    #loader i:nth-child(3){{background:#53bc28;animation-delay:.3s}}
    html.loaded #loader{{display:none}}
    @keyframes loader-in{{to{{opacity:1;visibility:visible}}}}
    @keyframes loader-dot{{0%,80%,100%{{transform:scale(.55);opacity:.35}}40%{{transform:scale(1);opacity:1}}}}
    @media (prefers-reduced-motion:reduce){{#loader i{{animation:none;opacity:.8}}}}
  </style>
  <script>
    (function () {{
      var done = function () {{ document.documentElement.classList.add("loaded") }}
      if (document.readyState === "complete") done()
      else window.addEventListener("load", done)
      setTimeout(done, 8000)
    }})()
  </script>
</head>
<body class="subpage">
  <div id="loader" aria-hidden="true"><div><i></i><i></i><i></i></div></div>
  <!-- Generated by tools/pages/build_pages.py: edit there, then rebuild. -->
  <!-- Background: Tubes Cursor by Kevin Levron (soju22), CC BY-NC-SA 4.0. -->
  <nav class="nav" aria-label="Sections">
    <div class="nav-links">
{nav}    </div>
  </nav>

  <div id="cord"></div>

  <div class="bg"><canvas id="canvas"></canvas></div>
  <canvas id="trail" class="trail" aria-hidden="true"></canvas>

  <div id="smooth-wrapper">
  <div id="smooth-content">
  <main class="sections">
{body}
  </main>
  <footer class="site-footer">
    <p>© 2026 Campus Tech @ UIUC · <a href="{up}articles/">Articles</a> · <a href="{up}faq.html">FAQ</a> · <a href="{up}privacy.html">Privacy</a> · <a href="{up}terms.html">Terms</a></p>
    <p>A registered student organization at the University of Illinois Urbana-Champaign; not an official University website. Background by <a href="https://codepen.io/soju22/pen/qEbdVjK" target="_blank" rel="noopener">Kevin Levron</a>, CC BY-NC-SA 4.0.</p>
  </footer>
  </div>
  </div>

  <script src="{up}vendor/gsap.min.js"></script>
  <script src="{up}vendor/ScrollTrigger.min.js"></script>
  <script src="{up}vendor/ScrollSmoother.min.js"></script>
  <script src="{up}vendor/pullcord.js"></script>
  <script type="module" src="{up}src/main.js"></script>
</body>
</html>
"""


def breadcrumbs(*items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE + pretty(href)}
            for i, (name, href) in enumerate(items)
        ],
    }


def article_schema(path, headline, description):
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "description": description,
        "datePublished": UPDATED,
        "dateModified": UPDATED,
        "mainEntityOfPage": SITE + pretty(path),
        "image": SITE + "assets/og.png",
        "author": PUBLISHER,
        "publisher": {**PUBLISHER, "logo": {"@type": "ImageObject", "url": SITE + "assets/apple-touch-icon.png"}},
    }


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

PAGES = {}

PAGES["past.html"] = page(
    "past.html",
    "Past · Campus Tech",
    "Past products and presidents of Campus Tech @ UIUC.",
    """    <section id="past">
      <h2>Past</h2>
      <!-- TODO(campustech): retired or earlier products; add each president as terms end -->
      <p class="label">Products</p>
      <ul>
        <li><b class="ph">[Product]</b><span class="ph">[Year] · [One line]</span></li>
        <li><b class="ph">[Product]</b><span class="ph">[Year] · [One line]</span></li>
      </ul>
      <p class="label">Presidents</p>
      <ul>
        <li><b>Michael Li</b><span>2026–27 · Founding president</span></li>
      </ul>
    </section>""",
    active="past",
    schema=[breadcrumbs(("Home", ""), ("Past", "past.html"))],
)

PAGES["privacy.html"] = page(
    "privacy.html",
    "Privacy Policy · Campus Tech",
    "How the Campus Tech @ UIUC website handles information: no accounts, no cookies, no analytics.",
    f"""    <section class="prose">
      <h1>Privacy Policy</h1>
      <p class="meta">Last updated: November 17, 2026</p>
      <p>This policy explains what information the Campus Tech website (campustech.iguide.chat) handles. Campus Tech @ University of Illinois Urbana-Champaign ("Campus Tech", "we") is a registered student organization at the University of Illinois Urbana-Champaign.</p>

      <h2>What this website collects</h2>
      <p>This is a static website. It has no accounts, no sign-up, no cookies and no analytics or advertising trackers. We do not sell or share personal information.</p>
      <ul>
        <li><b>Theme preference.</b> If you switch between dark and light mode, your choice is stored in your browser's local storage on your own device so the site remembers it. It is never sent to us. You can clear it at any time in your browser settings.</li>
        <li><b>Server logs.</b> Like any website, the hosting provider that serves these pages may keep standard technical logs (for example IP address, browser type and the page requested) for security and reliability. We do not use these logs to identify visitors.</li>
      </ul>

      <h2>Third-party services</h2>
      <ul>
        <li><b>Google Fonts.</b> The page font is loaded from Google, which receives your IP address when the font is requested. See <a href="https://policies.google.com/privacy" target="_blank" rel="noopener">Google's privacy policy</a>.</li>
        <li><b>Google Forms.</b> Our membership application and idea submission forms are hosted on Google Forms. What you enter there is collected by Google and shared with Campus Tech officers. We use it only to review applications and ideas and to contact you, and we do not sell it.</li>
        <li><b>Links to other sites.</b> Links such as iguide.chat and GitHub lead to sites with their own privacy policies.</li>
      </ul>

      <h2>Form submissions</h2>
      <p>Application and idea submissions are accessible only to current Campus Tech officers who need them. We keep them for as long as they are useful for recruiting or following up on an idea, and you can ask us to delete your submission at any time.</p>

      <h2>Children</h2>
      <p>This website is meant for university students and is not directed at children under 13.</p>

      <h2>Your choices</h2>
      <p>To ask what we hold about you, or to have a form submission corrected or deleted, email <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>

      <h2>Changes</h2>
      <p>If this policy changes, we will update the date at the top of this page.</p>
    </section>""",
    schema=[breadcrumbs(("Home", ""), ("Privacy Policy", "privacy.html"))],
)

PAGES["terms.html"] = page(
    "terms.html",
    "Terms of Use · Campus Tech",
    "Terms of use for the Campus Tech @ UIUC website, including the university disclaimer and third-party credits.",
    f"""    <section class="prose">
      <h1>Terms of Use</h1>
      <p class="meta">Last updated: November 17, 2026</p>
      <p>By using this website (campustech.iguide.chat) you agree to these terms.</p>

      <h2>About Campus Tech</h2>
      <p>Campus Tech @ University of Illinois Urbana-Champaign is a registered student organization. This is not an official website of the University of Illinois, and the University is not responsible for its content.</p>

      <h2>Use of this website</h2>
      <p>You may browse and share this website for personal, non-commercial purposes. Please do not misuse it, for example by attempting to disrupt it or by misrepresenting yourself as Campus Tech.</p>

      <h2>Content and credits</h2>
      <p>Text and images on this site belong to Campus Tech unless noted otherwise. Parts of the site use third-party work under their own licenses:</p>
      <ul>
        <li>The dark-mode background is based on Tubes Cursor by Kevin Levron, licensed <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener">CC BY-NC-SA 4.0</a>.</li>
        <li>The light switch uses pullcord by Sarthak Navalekar (MIT license).</li>
        <li>Smooth scrolling uses GSAP under the <a href="https://gsap.com/standard-license" target="_blank" rel="noopener">GreenSock standard license</a>.</li>
        <li>The light-mode cursor trail is our own implementation, inspired by DitherCursor by Eniyan Raja.</li>
      </ul>

      <h2>Links to other websites</h2>
      <p>This site links to other websites, such as iguide.chat, Google Forms and GitHub. We are not responsible for their content or practices.</p>

      <h2>No warranty</h2>
      <p>The website is provided "as is". We try to keep information accurate and current, but we make no guarantees, and dates such as application deadlines may change. To the extent permitted by law, Campus Tech is not liable for any loss arising from use of this website.</p>

      <h2>Changes</h2>
      <p>We may update these terms; the date at the top shows the latest version.</p>

      <h2>Contact</h2>
      <p>Questions: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
    </section>""",
    schema=[breadcrumbs(("Home", ""), ("Terms of Use", "terms.html"))],
)

# ---- Articles -------------------------------------------------------------- #

ARTICLES = [
    {
        "slug": "introducing-campus-tech",
        "title": "Introducing Campus Tech @ UIUC",
        "desc": "Campus Tech is a student organization at the University of Illinois Urbana-Champaign that builds products for campus life, starting with an AI campus assistant and a dorm guide.",
        "body": f"""      <p>Campus Tech @ University of Illinois Urbana-Champaign is a student organization that builds products for campus life. It was registered as a Registered Student Organization (RSO) at UIUC in November 2026.</p>

      <h2>What we build</h2>
      <p>We focus on tools students actually use day to day:</p>
      <ul>
        <li><b>AI Chat</b> on <a href="https://iguide.chat/chat" target="_blank" rel="noopener">iguide.chat</a>: ask questions about UIUC and campus life.</li>
        <li><b>Dorms</b> on <a href="https://iguide.chat/dorms" target="_blank" rel="noopener">iguide.chat/dorms</a>: compare UIUC residence halls to help choose housing.</li>
        <li><b>3D Room Scan</b>: walk through rooms in 3D.</li>
        <li><b>Apartments</b>: compare places to live off campus.</li>
        <li><b>RSO websites</b>: we build a website for any registered student organization.</li>
        <li><b>Local</b>: tools for nearby businesses.</li>
      </ul>

      <h2>Who we are</h2>
      <p>The organization is run by student officers: Michael Li (President), George Wang (Tech Lead), Lai Wei (Business Director), Nancy Zhang (Membership Director) and Chris Lopez (Treasurer), with Skylar Chu as advisor. Members come from different majors and years, and both domestic and international students are welcome.</p>

      <h2>Get involved</h2>
      <p>Fall 2026 Round 1 recruiting is open for programming, design, marketing, business and administration roles. Read <a href="fall-2026-recruiting.html">how to apply</a>, or <a href="pitch-your-idea.html">pitch a product idea</a>. You can also email us at <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>""",
    },
    {
        "slug": "fall-2026-recruiting",
        "title": "Campus Tech Fall 2026 Round 1 Recruiting: Roles and How to Apply",
        "desc": "Campus Tech @ UIUC is recruiting for Fall 2026 Round 1: programming, design, marketing, business and administration roles. Applications close November 29, 2026 at 11:59 PM CT.",
        "body": f"""      <p>Campus Tech @ UIUC is recruiting new members for Fall 2026 Round 1. Students of any major and year can apply, and both domestic and international students are welcome.</p>

      <h2>Open roles</h2>
      <ul>
        <li><b>Programming</b>: build our products, from websites to AI features.</li>
        <li><b>Design</b>: design product interfaces and visuals.</li>
        <li><b>Marketing</b>: content and social media, including Xiaohongshu.</li>
        <li><b>Business</b>: partnerships and sponsorship.</li>
        <li><b>Administration</b>: operations that keep the organization running.</li>
      </ul>

      <h2>How to apply</h2>
      <ol>
        <li>Fill in the <a href="{APPLY}" target="_blank" rel="noopener">membership application</a>. It takes about 5 minutes.</li>
        <li>We will reach out by email to schedule a short interview.</li>
      </ol>

      <h2>Deadline</h2>
      <p>Round 1 applications close at <b>11:59 PM Central Time on Sunday, November 29, 2026</b>, the last day of Fall Break. Recruiting happens in several rounds, so if you miss this one, watch for the next.</p>

      <h2>Frequently asked questions</h2>
      <dl>
        <dt>Who can join Campus Tech?</dt>
        <dd>Any student at the University of Illinois Urbana-Champaign, of any major and year. Domestic and international students are both welcome.</dd>
        <dt>Do I need coding experience?</dt>
        <dd>No. Only programming roles involve code; design, marketing, business and administration roles do not.</dd>
        <dt>How does joining work?</dt>
        <dd>Every member joins through the application and a short interview.</dd>
        <dt>When is the Fall 2026 Round 1 deadline?</dt>
        <dd>11:59 PM Central Time on Sunday, November 29, 2026.</dd>
        <dt>Can I join as an advisor?</dt>
        <dd>Yes. Faculty and staff interested in advising can get in touch through the same application form or by emailing {EMAIL}.</dd>
      </dl>""",
        "faq": [
            ("Who can join Campus Tech?", "Any student at the University of Illinois Urbana-Champaign, of any major and year. Domestic and international students are both welcome."),
            ("Do I need coding experience?", "No. Only programming roles involve code; design, marketing, business and administration roles do not."),
            ("How does joining work?", "Every member joins through the application and a short interview."),
            ("When is the Fall 2026 Round 1 deadline?", "11:59 PM Central Time on Sunday, November 29, 2026."),
            ("Can I join as an advisor?", f"Yes. Faculty and staff interested in advising can get in touch through the same application form or by emailing {EMAIL}."),
        ],
    },
    {
        "slug": "pitch-your-idea",
        "title": "Have an Idea for a Campus Product? Pitch It to Campus Tech",
        "desc": "Campus Tech @ UIUC takes product ideas from any student. Tell us who would use it, what problem it solves and what skills it needs. No full plan or coding required.",
        "body": f"""      <p>Have an idea for a product that would make campus life better? You can pitch it to Campus Tech @ UIUC, even if you are not a member.</p>

      <h2>What to tell us</h2>
      <ul>
        <li><b>Who would use it</b>: which students or groups on campus.</li>
        <li><b>What problem it solves</b>: what is hard, slow or missing today.</li>
        <li><b>What skills it needs</b>: what you would need from other people to build it.</li>
      </ul>
      <p>You do not need a full plan, and you do not need to know how to code.</p>

      <h2>How to pitch</h2>
      <p>Use the <a href="{PITCH}" target="_blank" rel="noopener">Pitch Your Idea form</a>. Our team reads every idea, and we will reach out by email if we want to talk.</p>

      <h2>What happens next</h2>
      <p>Promising ideas can become Campus Tech projects, built by members across programming, design, marketing and business. If you would like to help build it yourself, also <a href="fall-2026-recruiting.html">apply to join</a>.</p>""",
    },
]

cards = ""
for a in ARTICLES:
    cards += f"""        <article>
          <h2><a href="{a['slug']}.html">{a['title']}</a></h2>
          <p>{a['desc']}</p>
        </article>
"""
PAGES["articles/index.html"] = page(
    "articles/index.html",
    "Articles · Campus Tech",
    "News and guides from Campus Tech @ UIUC: who we are, how to join, and how to pitch a campus product idea.",
    f"""    <section class="prose">
      <h1>Articles</h1>
      <p>News and guides from Campus Tech @ UIUC.</p>
      <div class="cards">
{cards}      </div>
    </section>""",
    active="articles",
    schema=[
        breadcrumbs(("Home", ""), ("Articles", "articles/")),
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Campus Tech Articles",
            "url": SITE + "articles/",
            "publisher": PUBLISHER,
        },
    ],
)

for a in ARTICLES:
    path = f"articles/{a['slug']}.html"
    schema = [
        breadcrumbs(("Home", ""), ("Articles", "articles/"), (a["title"], path)),
        article_schema(path, a["title"], a["desc"]),
    ]
    if a.get("faq"):
        schema.append(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": ans}}
                    for q, ans in a["faq"]
                ],
            }
        )
    PAGES[path] = page(
        path,
        f"{a['title']} · Campus Tech",
        a["desc"],
        f"""    <section class="prose">
      <p class="crumbs"><a href="./">Articles</a></p>
      <h1>{a['title']}</h1>
      <p class="meta">Published November 17, 2026 · Campus Tech @ UIUC</p>
{a['body']}
    </section>""",
        active="articles",
        schema=schema,
        og_type="article",
    )


# ---- FAQ (also the main GEO page: short, factual answers) ------------------- #

FAQ = [
    ("What is Campus Tech?", "Campus Tech @ University of Illinois Urbana-Champaign is a student organization that builds products for campus life. It was registered as a Registered Student Organization (RSO) at UIUC in November 2026."),
    ("What does Campus Tech build?", "AI Chat (iguide.chat/chat) for questions about UIUC, Dorms (iguide.chat/dorms) for comparing UIUC residence halls, a 3D room scan, apartment comparison, websites for registered student organizations, and tools for local businesses."),
    ("Who leads Campus Tech?", "Michael Li (President), George Wang (Tech Lead), Lai Wei (Business Director), Nancy Zhang (Membership Director) and Chris Lopez (Treasurer), with Skylar Chu as advisor."),
    ("How do I join Campus Tech?", "Submit the membership application and complete a short interview. Fall 2026 Round 1 applications close at 11:59 PM Central Time on Sunday, November 29, 2026."),
    ("Which roles are open?", "Programming, design, marketing, business and administration."),
    ("Do I need coding experience to join?", "No. Only programming roles involve code."),
    ("Who can join?", "Any UIUC student, of any major and year. Domestic and international students are both welcome."),
    ("Can I suggest a product idea?", "Yes. Anyone can pitch an idea through the Pitch Your Idea form; no full plan or coding is needed."),
    ("How do I contact Campus Tech?", f"Email {EMAIL}."),
    ("Is this an official University of Illinois website?", "No. Campus Tech is a registered student organization, and this is not an official University website."),
]

faq_html = "".join(f"        <dt>{q}</dt>\n        <dd>{a}</dd>\n" for q, a in FAQ)
PAGES["faq.html"] = page(
    "faq.html",
    "FAQ · Campus Tech @ UIUC",
    "Answers about Campus Tech @ UIUC: what it is, what it builds, who leads it, and how to join or pitch an idea.",
    f"""    <section class="prose">
      <h1>Frequently asked questions</h1>
      <p class="meta">Last updated: November 17, 2026</p>
      <dl>
{faq_html}      </dl>
      <p>Ready to apply? Read <a href="articles/fall-2026-recruiting.html">how to join</a>, or <a href="{PITCH}" target="_blank" rel="noopener">pitch an idea</a>.</p>
    </section>""",
    schema=[
        breadcrumbs(("Home", ""), ("FAQ", "faq.html")),
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ
            ],
        },
    ],
)

# ---- 404 and Coming soon (not indexed, not in the sitemap) ------------------ #

PAGES["404.html"] = page(
    "404.html",
    "Page not found · Campus Tech",
    "This page does not exist.",
    """    <section>
      <h2>404</h2>
      <p>This page doesn't exist.</p>
      <p><a href="/">Back to Campus Tech</a> · <a href="/articles/">Articles</a></p>
    </section>""",
    noindex=True,
    absolute=True,
)

PAGES["coming-soon.html"] = page(
    "coming-soon.html",
    "Coming soon · Campus Tech",
    "This part of Campus Tech is coming soon.",
    f"""    <section>
      <h2>Coming soon</h2>
      <p>We're still building this one.</p>
      <p class="note">Want to help build it? <a href="{APPLY}" target="_blank" rel="noopener">Apply</a> · or go <a href="./">back home</a></p>
    </section>""",
    noindex=True,
)

NOT_INDEXED = {"404.html", "coming-soon.html"}

# ---- Sitemap and llms.txt follow the pages above ---------------------------- #

def sitemap():
    urls = [""] + [pretty(p) for p in PAGES if p not in NOT_INDEXED]
    rows = "".join(
        f"  <url><loc>{SITE}{u}</loc><lastmod>{UPDATED}</lastmod></url>\n" for u in urls
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n'


def llms_txt():
    lines = [
        "# Campus Tech @ University of Illinois Urbana-Champaign",
        "",
        "> Campus Tech is a registered student organization at the University of Illinois Urbana-Champaign (UIUC) that builds products for campus life. Registered as an RSO in November 2026.",
        "",
        "Key facts:",
        "- Products: AI Chat (https://iguide.chat/chat) for questions about UIUC; Dorms (https://iguide.chat/dorms), a guide for comparing UIUC residence halls; 3D Room Scan; apartment comparison; websites for registered student organizations; tools for local businesses.",
        "- Officers: Michael Li (President), George Wang (Tech Lead), Lai Wei (Business Director), Nancy Zhang (Membership Director), Chris Lopez (Treasurer). Advisor: Skylar Chu.",
        f"- Recruiting: Fall 2026 Round 1, roles in programming, design, marketing, business and administration. Application plus short interview. Deadline 11:59 PM CT, Sunday November 29, 2026. Apply: {APPLY}",
        f"- Product ideas from any student: {PITCH}",
        f"- Contact: {EMAIL}",
        "",
        "## Pages",
        f"- [Home]({SITE}): products, recruiting, team and contact",
        f"- [Past]({SITE}past): past products and presidents",
        f"- [Articles]({SITE}articles/): news and guides",
    ]
    for a in ARTICLES:
        lines.append(f"- [{a['title']}]({SITE}articles/{a['slug']}): {a['desc']}")
    lines += [
        f"- [FAQ]({SITE}faq): short answers about the organization",
        f"- [Privacy Policy]({SITE}privacy)",
        f"- [Terms of Use]({SITE}terms)",
        "",
    ]
    return "\n".join(lines)


def text_of(html):
    """Readable text of a page's <main>, for llms-full.txt."""
    import html as htmllib
    import re

    main = re.search(r"<main[^>]*>(.*)</main>", html, re.S)
    body = main.group(1) if main else html
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"</(b|a)>\s*<span>", r"</> — <span>", body)  # "Name — description"
    body = re.sub(r"<(h1|h2)[^>]*>", "\n## ", body)
    body = re.sub(r"<dt[^>]*>", "\nQ: ", body)
    body = re.sub(r"<dd[^>]*>", "\nA: ", body)
    body = re.sub(r"<li[^>]*>", "\n- ", body)
    body = re.sub(r"</(p|ul|ol|dl|section|h1|h2|dd)>", "\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = htmllib.unescape(body)
    out, blank = [], False
    for line in (l.strip() for l in body.splitlines()):
        if not line:
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(line)
            blank = False
    return "\n".join(out).strip()


def llms_full():
    """Full text of every indexed page (home page included) in one file."""
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    parts = [llms_txt(), "", "---", "", f"# Home ({SITE})", "", text_of(home)]
    for path, html in PAGES.items():
        if path in NOT_INDEXED or path == "past.html":
            continue
        parts += ["", "---", "", f"# {SITE}{pretty(path)}", "", text_of(html)]
    return "\n".join(parts) + "\n"


def main():
    for path, html in PAGES.items():
        out = ROOT / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print("wrote", path)
    (ROOT / "sitemap.xml").write_text(sitemap(), encoding="utf-8")
    (ROOT / "llms.txt").write_text(llms_txt(), encoding="utf-8")
    (ROOT / "llms-full.txt").write_text(llms_full(), encoding="utf-8")
    print("wrote sitemap.xml, llms.txt, llms-full.txt")


if __name__ == "__main__":
    main()
