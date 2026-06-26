#!/usr/bin/env python3
"""
HelpDocs -> Mintlify migration for docs.getthread.com.

Two modes:
  Live  (default):  fetches categories + articles from the HelpDocs read API
                    (set HELPDOCS_API_KEY), downloads images into images/,
                    and writes the full Mintlify docs tree + docs.json.
  Cache (--from-cache PATH): builds everything from a previously pulled
                    articles_full.json. No network, no image download
                    (image links still rewritten to local /images paths,
                    and an image manifest is written for a later fetch).

Usage:
  HELPDOCS_API_KEY=xxxx python3 scripts/migrate.py            # full live run
  python3 scripts/migrate.py --from-cache work/articles_full.json --cats work/categories.json

The API key is read only from the environment. It is never written to disk.
"""
import os, sys, json, re, argparse, html, hashlib, urllib.parse, urllib.request, time
from datetime import datetime, timezone, timedelta

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    sys.exit("Missing dependency: pip install beautifulsoup4")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.helpdocs.io/v1"
SCOPE_CUTOFF = "2026-04-27"   # private articles created/updated on/after this are in scope

# ---------------------------------------------------------------------------
# Information architecture: top-level sections -> ordered category ids.
# Articles whose category isn't listed fall back to "get-started". Specific
# uncategorised articles are routed by id in UNCAT_ROUTING.
# ---------------------------------------------------------------------------
SECTIONS = [
    ("Get Started",        "get-started",     ["d6ve4kr53p"]),
    ("Thread Inbox",       "inbox",           ["vm5pbco129","5amvg6ovpu","zd45019dlu","saxwkkma57",
                                               "sss8ktql0m","c3m895mu3p","cuecb6u01s","5a5xck4gzv",
                                               "kuosqbjuyu","aoytyur1zs"]),
    ("Assistive AI",       "assistive-ai",    ["wpdony1msw","oa1a3vbd8z","2jpu8l0svb","b9psnnfude",
                                               "ad14ulcf04","zz4xcertkh"]),
    ("AI Agents",          "ai-agents",       ["rqyxo5rltr","754xabotpc","20wdvddtgg","l3a8pb2m3a","nnf9ux2xj5"]),
    ("Super Magic",        "super-magic",     ["498jpafm5g","gvyg1xustr"]),
    ("Magic Analytics",    "analytics",       ["ozxfq1rfry"]),
    ("Automagically",      "automagically",   ["7f7hykugsc"]),
    ("Messenger",          "messenger",       ["91jqgkjqmd","e2bpm2l5ox","3lw05p3npx","aydibnsdr6",
                                               "7xriind6w9","39z5b7r3kb","k4vf1jx7gk"]),
    ("Companion Apps",     "companion-apps",  ["5fgs2fexk5","k3oln3kl2w","8wdfq4nuvo"]),
    ("Integrations",       "integrations",    ["y99zb51li5","vds0g5cor4","5wml6pt11v","n1eav2c3uu",
                                               "v9pg12su0x","zbgl5u38nd"]),
    ("Notifications",      "notifications",   ["gpnkr34s8r","naj94va2f6","ykk3fqvhlm"]),
    ("Security & Billing", "security-billing",["wvu7ay5ey7"]),
    ("Adoption",           "adoption",        ["d3cpp3d7pk"]),
]
# uncategorised (or off-tree) article_id -> section folder
UNCAT_ROUTING = {
    "9cynnfpyng": "integrations",   # Microsoft Bookings + Power Automate
    "qr9jy2gsfe": "integrations",   # Pia Integration
    "29vncfaox8": "ai-agents",      # From Triage to Resolution
    "pmxb0c0f3n": "assistive-ai",   # Working with Variables
    "bfjtgpt0bb": "assistive-ai",   # Best Practices for Writing Prompts
    "ttc32szrp1": "inbox",          # Setting Up Thread Inbox by team structure
}
SECTION_FOLDER = {s[1]: s[0] for s in SECTIONS}
CAT_TO_SECTION = {}
for title, folder, cats in SECTIONS:
    for c in cats:
        CAT_TO_SECTION[c] = folder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(text, fallback="page"):
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback

def esc_mdx(text):
    text = text.replace("\\", "\\\\")
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("{", "\\{").replace("}", "\\}")
    return text

def esc_inline_table(text):
    return esc_mdx(text).replace("|", "\\|").replace("\n", " ")

# ---------------------------------------------------------------------------
# HTML -> MDX
# ---------------------------------------------------------------------------
class Converter:
    def __init__(self, link_map, cat_link_map, image_cb):
        self.link_map = link_map
        self.cat_link_map = cat_link_map
        self.image_cb = image_cb

    def rewrite_href(self, href):
        if not href:
            return href
        m = re.search(r"/article/([a-z0-9]{10})", href)
        if m and m.group(1) in self.link_map:
            frag = "#" + href.split("#", 1)[1] if "#" in href else ""
            return self.link_map[m.group(1)] + frag
        m = re.search(r"/category/([a-z0-9]{10})", href)
        if m and m.group(1) in self.cat_link_map:
            return self.cat_link_map[m.group(1)]
        # out-of-scope article/category links: point at the live site, not a relative 404
        if href.startswith("/article/") or href.startswith("/category/"):
            return "https://docs.getthread.com" + href
        return href

    def inline(self, node):
        if isinstance(node, NavigableString):
            return esc_mdx(str(node))
        if not isinstance(node, Tag):
            return ""
        name = node.name
        if name in ("strong", "b"):
            inner = "".join(self.inline(c) for c in node.children).strip()
            return f"**{inner}**" if inner else ""
        if name in ("em", "i"):
            inner = "".join(self.inline(c) for c in node.children).strip()
            return f"*{inner}*" if inner else ""
        if name == "code":
            return f"`{node.get_text()}`"
        if name == "br":
            return "\n"
        if name == "a":
            href = self.rewrite_href(node.get("href", ""))
            txt = "".join(self.inline(c) for c in node.children).strip() or href
            if node.get("data-hd-link-type") == "button":
                txt = node.get_text().strip() or txt
            return f"[{txt}]({href})" if href else txt
        if name == "img":
            return self.img(node)
        if name in ("span", "u"):
            return "".join(self.inline(c) for c in node.children)
        return "".join(self.inline(c) for c in node.children)

    def img(self, node):
        src = node.get("src", "")
        if not src:
            return ""
        local = self.image_cb(src)
        alt = node.get("alt", "").replace("]", "").replace("[", "")
        return f"![{alt}]({local})"

    def list_items(self, node, ordered, depth):
        lines = []
        i = 1
        for li in node.find_all("li", recursive=False):
            marker = f"{i}." if ordered else "-"
            sub = []
            inline_parts = []
            for c in li.children:
                if isinstance(c, Tag) and c.name in ("ul", "ol"):
                    sub.append(c)
                elif isinstance(c, Tag) and c.name in ("p", "div", "figure", "pre", "table", "blockquote"):
                    if c.name == "figure" or c.name == "pre" or (isinstance(c, Tag) and c.find("img")):
                        sub.append(("block", c))
                    else:
                        inline_parts.append("".join(self.inline(x) for x in c.children))
                else:
                    inline_parts.append(self.inline(c))
            text = re.sub(r"[ \t]*\n[ \t]*", " ", "".join(inline_parts)).strip()
            indent = "  " * depth
            lines.append(f"{indent}{marker} {text}".rstrip())
            for s in sub:
                if isinstance(s, Tag):
                    lines.append(self.list_items(s, s.name == "ol", depth + 1))
                else:
                    rendered = self.block(s[1]).strip()
                    for ln in rendered.splitlines():
                        lines.append(f"{indent}  {ln}")
            i += 1
        return "\n".join(lines)

    def table(self, node):
        rows = []
        for tr in node.find_all("tr"):
            cells = [" ".join(esc_inline_table(td.get_text(" ", strip=True)).split())
                     for td in tr.find_all(["td", "th"])]
            rows.append(cells)
        rows = [r for r in rows if any(c.strip() for c in r)]
        if not rows:
            return ""
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        out = ["| " + " | ".join(rows[0]) + " |",
               "| " + " | ".join(["---"] * width) + " |"]
        for r in rows[1:]:
            out.append("| " + " | ".join(r) + " |")
        return "\n".join(out)

    def callout(self, node, comp):
        inner = self.children_blocks(node).strip()
        inner = re.sub(r"^\*\*(Note|Tip|Pro Tip|Warning)\*\*[:\s]*", "", inner)
        body = "\n".join("  " + l for l in inner.splitlines())
        return f"<{comp}>\n{body}\n</{comp}>"

    def embed(self, node):
        iframe = node.find("iframe")
        if not iframe or not iframe.get("src"):
            return ""
        return f'<Frame>\n  <iframe src="{iframe["src"]}" width="100%" height="400" allowfullscreen></iframe>\n</Frame>'

    def block(self, node):
        if isinstance(node, NavigableString):
            return esc_mdx(str(node)).strip()
        if not isinstance(node, Tag):
            return ""
        name = node.name
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = {"h1": 2, "h2": 2, "h3": 2, "h4": 3, "h5": 4, "h6": 4}[name]
            txt = re.sub(r"\s+", " ", "".join(self.inline(c) for c in node.children).strip())
            return ("#" * level + " " + txt) if txt else ""
        if name == "p":
            txt = re.sub(r"[ \t]+", " ", "".join(self.inline(c) for c in node.children).strip())
            return txt
        if name in ("ul", "ol"):
            return self.list_items(node, name == "ol", 0)
        if name == "figure":
            img = node.find("img")
            if img:
                return self.img(img)
            if node.find("iframe"):
                return self.embed(node)
            return ""
        if name == "img":
            return self.img(node)
        if name == "table":
            return self.table(node)
        if name == "blockquote":
            inner = self.children_blocks(node).strip()
            return "\n".join("> " + l if l else ">" for l in inner.splitlines())
        if name == "pre":
            for br in node.find_all("br"):
                br.replace_with("\n")
            code = html.unescape(node.get_text()).strip("\n")
            return "```\n" + code + "\n```"
        if name == "div":
            cls = " ".join(node.get("class", []))
            if "tip-callout" in cls:
                return self.callout(node, "Tip")
            if "note-callout" in cls:
                return self.callout(node, "Note")
            if "warning-callout" in cls:
                return self.callout(node, "Warning")
            if "hd--embed" in cls or node.find("iframe"):
                return self.embed(node)
            return self.children_blocks(node)
        if name == "iframe":
            return self.embed(node)
        if name == "br":
            return ""
        return self.children_blocks(node)

    def children_blocks(self, node):
        out = []
        for c in node.children:
            r = self.block(c)
            if r and r.strip():
                out.append(r.strip())
        return "\n\n".join(out)

    def convert(self, body_html):
        soup = BeautifulSoup(body_html or "", "html.parser")
        for b in soup.find_all("button"):
            b.replace_with(b.get_text())
        return self.children_blocks(soup).strip()

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def http_get(url):
    import urllib.request
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())

def fetch_all_live(key):
    cats = http_get(f"{API}/category?key={key}")["categories"]
    cat_rows = [[c["category_id"], c.get("parent_category_id", ""), c["title"], c.get("slug", ""),
                 c.get("is_featured", False)] for c in cats]
    arts = {}
    skip = 0
    while True:
        page = http_get(f"{API}/article?key={key}&include_body=true&limit=25&skip={skip}&sort=updated_at")
        items = page.get("articles", [])
        if not items:
            break
        for a in items:
            arts[a["article_id"]] = a
        skip += 25
        time.sleep(0.2)
    return cat_rows, arts

def load_cache(path, cats_path):
    return json.load(open(cats_path)), json.load(open(path))

def in_scope(a):
    if not a.get("is_published"):
        return False
    if not a.get("is_private"):
        return True
    return (a.get("updated_at", "")[:10] >= SCOPE_CUTOFF) or (a.get("created_at", "")[:10] >= SCOPE_CUTOFF)

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-cache")
    ap.add_argument("--cats", default=os.path.join(REPO, "work", "categories.json"))
    ap.add_argument("--out", default=REPO)
    args = ap.parse_args()

    download_images = False
    if args.from_cache:
        cat_rows, arts = load_cache(args.from_cache, args.cats)
    else:
        key = os.environ.get("HELPDOCS_API_KEY")
        if not key:
            sys.exit("Set HELPDOCS_API_KEY in your environment for a live run.")
        cat_rows, arts = fetch_all_live(key)
        download_images = True

    cats = {c[0]: {"parent": c[1], "title": c[2], "slug": c[3]} for c in cat_rows}
    scope = {aid: a for aid, a in arts.items() if in_scope(a)}

    def section_of(a):
        aid = a["article_id"]
        if aid in UNCAT_ROUTING:
            return UNCAT_ROUTING[aid]
        return CAT_TO_SECTION.get(a.get("category_id") or "", "get-started")

    page_path = {}
    used = set()
    for aid, a in scope.items():
        folder = section_of(a)
        s = slugify(a.get("slug") or a.get("title"), aid)
        p = f"{folder}/{s}"
        if p in used:
            p = f"{folder}/{s}-{aid[:4]}"
        used.add(p)
        page_path[aid] = p
    link_map = {aid: "/" + p for aid, p in page_path.items()}
    cat_link_map = {}
    for cid in cats:
        for aid, a in scope.items():
            if a.get("category_id") == cid:
                cat_link_map[cid] = link_map[aid]
                break

    images_dir = os.path.join(args.out, "images")
    manifest = {}
    def image_cb(url):
        url = html.unescape(url)
        if url in manifest:
            return manifest[url]
        path = urllib.parse.urlparse(url).path
        base = os.path.basename(path) or "image"
        name = f"{hashlib.sha1(url.encode()).hexdigest()[:8]}-{base}"
        local = f"/images/{name}"
        manifest[url] = local
        if download_images:
            try:
                os.makedirs(images_dir, exist_ok=True)
                dest = os.path.join(images_dir, name)
                if not os.path.exists(dest):
                    urllib.request.urlretrieve(url, dest)
            except Exception as e:
                print(f"  ! image failed {url}: {e}", file=sys.stderr)
        return local

    conv = Converter(link_map, cat_link_map, image_cb)

    written = stubs = 0
    for aid, a in scope.items():
        dest = os.path.join(args.out, page_path[aid] + ".mdx")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        title = (a.get("title") or "Untitled").strip()
        desc = re.sub(r"\s+", " ", (a.get("description") or "")).strip().replace('"', "'")
        if len(desc) > 250:
            desc = desc[:247] + "..."
        body_html = a.get("body") or ""
        if body_html.strip():
            mdx = conv.convert(body_html)
            written += 1
        else:
            mdx = "<Note>Content for this article is being migrated.</Note>"
            stubs += 1
        fm = ["---", f'title: "{title.replace(chr(34), chr(39))}"']
        if desc:
            fm.append(f'description: "{desc}"')
        fm.append("---")
        open(dest, "w").write("\n".join(fm) + "\n\n" + mdx + "\n")

    def cat_articles(cid):
        items = [(aid, a) for aid, a in scope.items() if a.get("category_id") == cid]
        items.sort(key=lambda x: x[1].get("title", ""))
        return [page_path[aid] for aid, _ in items]

    groups = []
    for title, folder, catids in SECTIONS:
        pages = []
        for idx, cid in enumerate(catids):
            arts_in = cat_articles(cid)
            if not arts_in:
                continue
            if idx == 0:
                pages.extend(arts_in)
            else:
                pages.append({"group": cats.get(cid, {}).get("title", cid), "pages": arts_in})
        pages.extend([page_path[aid] for aid, sec in UNCAT_ROUTING.items()
                      if sec == folder and aid in page_path])
        if pages:
            groups.append({"group": title, "pages": pages})

    docs = {
        "$schema": "https://mintlify.com/docs.json",
        "theme": "mint",
        "name": "Thread",
        "colors": {"primary": "#6C5CE7", "light": "#A29BFE", "dark": "#4B3FB0"},
        "favicon": "/favicon.svg",
        "navigation": {"groups": groups},
        "navbar": {"links": [{"label": "Support", "href": "https://help.getthread.com"}],
                   "primary": {"type": "button", "label": "Thread Inbox", "href": "https://inbox.getthread.com"}},
        "footer": {"socials": {"website": "https://www.getthread.com"}},
    }
    open(os.path.join(args.out, "docs.json"), "w").write(json.dumps(docs, indent=2))

    os.makedirs(os.path.join(args.out, "scripts"), exist_ok=True)
    json.dump(manifest, open(os.path.join(args.out, "scripts", "image-manifest.json"), "w"), indent=2)

    print(f"pages written: {written}, stubs: {stubs}, images referenced: {len(manifest)}")
    print(f"nav groups: {len(groups)}")

if __name__ == "__main__":
    main()
