import hashlib
import re
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    work_html = repo_root / "work.html"
    out_dir = repo_root / "assets" / "images" / "work"

    if not work_html.exists():
        print(f"ERROR: not found: {work_html}")
        return 2
    if not out_dir.exists():
        print(f"ERROR: not found: {out_dir}")
        return 2

    content = work_html.read_text(encoding="utf-8")
    cover_urls = re.findall(r'coverImage:\s*"([^"]*)"', content)

    files = list(out_dir.iterdir())
    by_hash: dict[str, str] = {}
    for f in files:
        m = re.search(r'_([0-9a-f]{10})\.', f.name)
        if m:
            by_hash[m.group(1)] = f"assets/images/work/{f.name}"

    replacements: dict[str, str] = {}
    missing: list[str] = []

    for url in cover_urls:
        if not url.startswith("http"):
            continue
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
        local = by_hash.get(h)
        if not local:
            missing.append(url)
            continue
        replacements[url] = local

    if not replacements:
        print("No URLs replaced.")
        if missing:
            print(f"Missing matches: {len(missing)}")
        return 0

    new_content = content
    for old in sorted(replacements.keys(), key=len, reverse=True):
        new_content = new_content.replace(old, replacements[old])

    if new_content != content:
        work_html.write_text(new_content, encoding="utf-8")

    print(f"Replaced URLs: {len(replacements)}")
    if missing:
        print(f"Missing matches: {len(missing)}")
        for u in missing:
            print(f"- {u}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
