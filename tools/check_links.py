#!/usr/bin/env python3
"""check_links.py - verify that every relative link and every #anchor in the Markdown files resolves.

Checks, for every *.md file:
  - [text](relative/path.md)         the file exists
  - [text](relative/path.md#anchor)  the file exists AND has a heading with that anchor
  - [text](#anchor)                  the heading exists in the same file
  - <img src="assets/x.svg">         the file exists
External links (http, https, mailto) are NOT fetched: this runs offline and never touches the network.

Usage:  python3 tools/check_links.py        exit code 0 = all good, 1 = broken links found
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKIP_DIRS = {".git", "__pycache__"}
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMG_MD = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
IMG_HTML = re.compile(r"""<img[^>]+src=["']([^"']+)["']""")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$", re.M)


def slugify(title):
    """GitHub-style anchor: lowercase, strip punctuation, spaces to hyphens."""
    title = re.sub(r"`", "", title.strip().lower())
    title = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    return re.sub(r"\s", "-", title)


def anchors_of(path):
    with open(path, encoding="utf-8") as handle:
        text = re.sub(r"```.*?```", "", handle.read(), flags=re.S)   # headings inside code fences do not count
    return {slugify(m.group(2)) for m in HEADING.finditer(text)}


def markdown_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(".md"):
                yield os.path.join(base, name)


def check(root):
    """Return a list of human-readable problems found under `root`."""
    problems = []
    for path in sorted(markdown_files(root)):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        text_no_code = re.sub(r"```.*?```", "", text, flags=re.S)
        links = MD_LINK.findall(text_no_code) + IMG_MD.findall(text_no_code) + IMG_HTML.findall(text_no_code)
        for target in links:
            if re.match(r"^(https?:|mailto:)", target) or target.startswith("<"):
                continue
            file_part, _, anchor = target.partition("#")
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), file_part)) if file_part else path
            rel = os.path.relpath(path, root)
            if file_part and not os.path.exists(resolved):
                problems.append(f"{rel}: missing file -> {target}")
            elif anchor and resolved.endswith(".md") and anchor not in anchors_of(resolved):
                problems.append(f"{rel}: missing anchor -> {target}")
    return problems


def main():
    problems = check(ROOT)
    for line in problems:
        print(line)
    print(f"{len(problems)} broken link(s)" if problems else "all relative links and anchors resolve")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
