#!/usr/bin/env python3
"""
Download every image referenced by the migrated docs into images/.

Use this for the "images later" step when the MDX text is already in place and
you only need to pull the binaries. It reads scripts/image-manifest.json
(written by migrate.py), which maps each original HelpDocs/CDN URL to its local
/images/<name> path, and downloads anything not already present.

  python3 scripts/fetch_assets.py

No API key needed — these are public asset URLs.
"""
import os, sys, json, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
manifest_path = os.path.join(REPO, "scripts", "image-manifest.json")
if not os.path.exists(manifest_path):
    sys.exit("No image-manifest.json found. Run scripts/migrate.py first.")

manifest = json.load(open(manifest_path))
images_dir = os.path.join(REPO, "images")
os.makedirs(images_dir, exist_ok=True)

ok = skipped = failed = 0
for url, local in manifest.items():
    name = local.lstrip("/").split("/", 1)[1]   # images/<name> -> <name>
    dest = os.path.join(images_dir, name)
    if os.path.exists(dest):
        skipped += 1
        continue
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "thread-docs-migration"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            f.write(r.read())
        ok += 1
    except Exception as e:
        print(f"  ! failed {url}: {e}", file=sys.stderr)
        failed += 1

print(f"downloaded: {ok}, already present: {skipped}, failed: {failed}, total: {len(manifest)}")
