#!/usr/bin/env python3
"""find_models.py - before modeling anything, look for a model that already exists.

Why this exists
    The best model is often already made, printed and reviewed by others. Searching first saves hours of modeling and
    starts from something people have actually printed. Only when nothing fits does the assistant model from scratch.

What it does
    Searches Printables (public GraphQL endpoint, read-only, one request) and prints a numbered shortlist with the
    signals that matter: likes, downloads, how many people posted a finished print ("makes"), date, licence and link.
    "Makes" is the best hint that a model is printable, so the list can be sorted by it.

What it does NOT do
    It does not download files (you do that from the page, so the licence and the author's notes are seen), and it
    does not cover MakerWorld, Thingiverse or Thangs: those have no open search API, so the assistant searches them
    through the web instead. The Printables endpoint is unofficial and can change or block requests at any time.

Usage
    python3 scripts/find_models.py "controller wall mount"
    python3 scripts/find_models.py "horse keychain" --limit 10 --sort makes
    python3 scripts/find_models.py "horse keychain" --json
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.printables.com/graphql/"
USER_AGENT = "3d-print-workflow/0.1 (personal assistant script; read-only search)"
QUERY = """query($q: String!, $n: Int!) {
  result: searchPrints2(query: $q, limit: $n) {
    items { id name slug likesCount downloadCount makesCount datePublished
            license { name } user { publicUsername } }
  }
}"""


def search(term, limit=8, opener=urllib.request.urlopen):
    """Raw items from Printables. `opener` is injectable so tests never touch the network."""
    body = json.dumps({"query": QUERY, "variables": {"q": term, "n": limit}}).encode()
    request = urllib.request.Request(ENDPOINT, body, {"Content-Type": "application/json", "User-Agent": USER_AGENT})
    payload = json.load(opener(request, timeout=20))
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "search failed"))
    return ((payload.get("data") or {}).get("result") or {}).get("items") or []


def shape(item):
    return {
        "id": item["id"], "name": item.get("name"), "author": (item.get("user") or {}).get("publicUsername"),
        "likes": item.get("likesCount") or 0, "downloads": item.get("downloadCount") or 0,
        "makes": item.get("makesCount") or 0, "published": (item.get("datePublished") or "")[:10],
        "license": (item.get("license") or {}).get("name"),
        "url": f"https://www.printables.com/model/{item['id']}-{item.get('slug', '')}",
    }


def rank(items, sort):
    if sort == "relevance":
        return items
    return sorted(items, key=lambda i: (i[sort], i["likes"]), reverse=True)


def render(items):
    if not items:
        return "Nothing found. Try fewer or different words, or model it from scratch."
    lines = []
    for n, i in enumerate(items, 1):
        lines.append(f"{n}. {i['name']}  ({i['author']}, {i['published']})")
        lines.append(f"   likes {i['likes']} | downloads {i['downloads']} | printed by others {i['makes']} | {i['license'] or 'licence not shown'}")
        lines.append(f"   {i['url']}")
    return "\n".join(lines)


def main(argv=None, opener=urllib.request.urlopen):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("term", help="what you are looking for, in English works best")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--sort", choices=["relevance", "likes", "downloads", "makes"], default="relevance")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        items = rank([shape(i) for i in search(args.term, args.limit, opener)], args.sort)
    except (urllib.error.URLError, RuntimeError, ValueError, OSError) as error:
        print(f"Search failed ({type(error).__name__}: {error}). Search the site by hand, or use the web.", file=sys.stderr)
        return 1
    print(json.dumps(items, indent=2) if args.json else render(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
