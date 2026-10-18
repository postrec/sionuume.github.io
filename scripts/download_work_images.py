import argparse
import hashlib
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9\-_.]+", "", text)
    text = re.sub(r"-+", "-", text)
    return text[:60] or "item"


def guess_ext(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    _, ext = os.path.splitext(path)
    ext = ext.lower()

    # Common image extensions
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if ext == ".jpeg" else ext

    # Some endpoints (e.g., viewimage.php) have no extension
    return ".jpg"


def download(url: str, dest: Path, timeout: int = 15) -> bool:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status and resp.status >= 400:
                return False
            dest.write_bytes(resp.read())
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download coverImage URLs referenced in work.html into assets/images/work and rewrite work.html to local paths.",
    )
    parser.add_argument("--timeout", type=int, default=15, help="Per-request timeout seconds (default: 15)")
    parser.add_argument("--max", type=int, default=0, help="Max number of URLs to process this run (0 = no limit)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    work_html = repo_root / "work.html"
    out_dir = repo_root / "assets" / "images" / "work"

    if not work_html.exists():
        print(f"ERROR: not found: {work_html}")
        return 2

    content = work_html.read_text(encoding="utf-8")

    # Extract titles in order (best-effort) and coverImage URLs.
    # We'll name files based on URL + optional nearby title (using index fallback).
    cover_matches = list(re.finditer(r'coverImage:\s*"([^"]*)"', content))
    if not cover_matches:
        print("No coverImage entries found.")
        return 0

    # Precompute title positions to find nearest previous title for each coverImage
    title_matches = list(re.finditer(r'title:\s*"([^"]*)"', content))

    def nearest_title(pos: int) -> str:
        # find last title before pos
        last = ""
        for m in title_matches:
            if m.start() < pos:
                last = m.group(1)
            else:
                break
        return last

    out_dir.mkdir(parents=True, exist_ok=True)

    replacements: dict[str, str] = {}
    failed: list[str] = []
    downloaded_count = 0

    processed = 0

    try:
        for idx, m in enumerate(cover_matches, start=1):
            url = m.group(1)
            if not url or not url.startswith("http"):
                continue

            if args.max and processed >= args.max:
                break

        # Avoid downloading YouTube thumbnails if user later wants to keep them remote.
        # If you want *all* external images, remove this guard.
        # We still allow ytimg/img.youtube.com if present.

            if url in replacements:
                continue

            title = nearest_title(m.start())
            ext = guess_ext(url)
            url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
            name = f"{idx:03d}_{slugify(title)}_{url_hash}{ext}"
            dest = out_dir / name

            processed += 1
            print(f"[{processed}] {title or '(no title)'}")
            print(f"  url : {url}")
            print(f"  file: {dest.relative_to(repo_root)}")

            # If file already exists, reuse and just replace.
            if not dest.exists():
                ok = download(url, dest, timeout=args.timeout)
                if not ok:
                    failed.append(url)
                    print("  -> FAILED\n")
                    continue
                downloaded_count += 1
                print("  -> downloaded\n")
            else:
                print("  -> exists\n")

            rel_path = f"assets/images/work/{name}"
            replacements[url] = rel_path

    except KeyboardInterrupt:
        print("\nInterrupted. Keeping downloaded files; not rewriting work.html this run.")
        return 130

    if not replacements:
        print("No images downloaded (nothing to replace).")
        if failed:
            print("Failed URLs:")
            for u in failed:
                print(f"- {u}")
        return 0

    # Apply replacements in file content.
    new_content = content
    # Replace longer URLs first (more specific)
    for old in sorted(replacements.keys(), key=len, reverse=True):
        new_content = new_content.replace(old, replacements[old])

    if new_content != content:
        work_html.write_text(new_content, encoding="utf-8")

    print(f"Downloaded: {downloaded_count} files")
    print(f"Replaced URLs: {len(replacements)}")
    if failed:
        print(f"Failed: {len(failed)}")
        for u in failed:
            print(f"- {u}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
