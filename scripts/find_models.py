#!/usr/bin/env python3
"""find_models.py - before modeling anything, look for a model that already exists.

Why this exists
    The best model is often already made, printed and reviewed by others. Searching first saves hours of modeling and
    starts from something people have actually printed. Only when nothing fits does the assistant model from scratch.

What it does
    Searches Printables (public GraphQL endpoint) and Thingiverse (official API, needs your own free app token) and prints
    one numbered shortlist with the signals that matter: likes, how many people posted a finished print ("makes"), date,
    licence and link. "Makes" is the best hint that a model is printable, so the list can be sorted by it.

What it does NOT do
    It does not download files (you do that from the page, so the licence and the author's notes are seen). It does not
    cover MakerWorld, Thangs or Cults3D: they have no open search API, so the assistant reads their search pages in a
    browser instead. The Printables endpoint is unofficial and can change or block requests at any time. Thingiverse
    hides its download counts from search results, so that column is empty for it.

Thingiverse token (optional)
    Create a free app at https://www.thingiverse.com/apps/create and copy its "App Token" (not the Client ID or Secret)
    into a file only you can read, without pasting it anywhere else:
        mkdir -p ~/.config/print-workflow && (umask 077; pbpaste > ~/.config/print-workflow/thingiverse-token)
    The token is sent in an Authorization header, never in the URL. Without it, Thingiverse is skipped with a note.

Usage
    python3 scripts/find_models.py "controller wall mount"
    python3 scripts/find_models.py "horse keychain" --limit 10 --sort makes
    python3 scripts/find_models.py "horse keychain" --site printables --json
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

PRINTABLES = "https://api.printables.com/graphql/"
THINGIVERSE = "https://api.thingiverse.com/search/"
TOKEN_FILE = os.path.expanduser("~/.config/print-workflow/thingiverse-token")
USER_AGENT = "3d-print-workflow/0.1 (personal assistant script; read-only search)"
QUERY = """query($q: String!, $n: Int!) {
  result: searchPrints2(query: $q, limit: $n) {
    items { id name slug likesCount downloadCount makesCount datePublished
            license { name } user { publicUsername } }
  }
}"""
TEXT_MAX = 120                                   # chars kept from any name, author or licence from a site
# ANSI CSI sequences, then any C0/C1 control, then the Unicode bidi and zero-width marks that reorder or hide text
CONTROL = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
THINGIVERSE_HOSTS = ("www.thingiverse.com", "thingiverse.com")


def clean(value, limit=TEXT_MAX):
    """Text from a site goes to a terminal and to the assistant: no control characters or escape
    sequences, whitespace collapsed, length capped. None stays None."""
    if value is None:
        return None
    text = " ".join(CONTROL.sub(" ", str(value)).split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


def thingiverse_url(item):
    """public_url only when it really is https on thingiverse.com; otherwise built from the id."""
    url = item.get("public_url")
    try:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme == "https" and parts.hostname in THINGIVERSE_HOSTS and not parts.username and not parts.password \
                and parts.port is None and not CONTROL.search(url):
            return url
    except (TypeError, AttributeError, ValueError):  # not a string, or a port that is not a number
        pass
    return f"https://www.thingiverse.com/thing:{urllib.parse.quote(str(item['id']), safe='')}"


def load_token(path=TOKEN_FILE):
    """The Thingiverse token from THINGIVERSE_TOKEN or the token file; None when there is none."""
    token = os.environ.get("THINGIVERSE_TOKEN")
    if not token and os.path.isfile(path):
        with open(path) as handle:
            token = handle.read()
    return (token or "").strip() or None


def search_printables(term, limit=8, opener=urllib.request.urlopen):
    """Raw items from Printables. `opener` is injectable so tests never touch the network."""
    body = json.dumps({"query": QUERY, "variables": {"q": term, "n": limit}}).encode()
    request = urllib.request.Request(PRINTABLES, body, {"Content-Type": "application/json", "User-Agent": USER_AGENT})
    payload = json.load(opener(request, timeout=20))
    if payload.get("errors"):
        raise RuntimeError(clean(payload["errors"][0].get("message", "search failed")))
    return ((payload.get("data") or {}).get("result") or {}).get("items") or []


def search_thingiverse(term, limit, token, opener=urllib.request.urlopen):
    """Raw hits from Thingiverse. The token travels in a header, never in the URL."""
    url = THINGIVERSE + urllib.parse.quote(term) + "?" + urllib.parse.urlencode({"type": "things", "per_page": limit, "sort": "popular"})
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT})
    return json.load(opener(request, timeout=20)).get("hits") or []


def shape_printables(item):
    return {
        "site": "Printables", "id": clean(item["id"]), "name": clean(item.get("name")),
        "author": clean((item.get("user") or {}).get("publicUsername")),
        "likes": item.get("likesCount") or 0, "downloads": item.get("downloadCount") or 0,
        "makes": item.get("makesCount") or 0, "published": clean((item.get("datePublished") or "")[:10]),
        "license": clean((item.get("license") or {}).get("name")),
        "url": "https://www.printables.com/model/" + urllib.parse.quote(f"{item['id']}-{item.get('slug') or ''}", safe="-_."),
    }


def shape_thingiverse(item):
    derivatives = item.get("allows_derivatives")
    return {
        "site": "Thingiverse", "id": clean(item["id"]), "name": clean(item.get("name")),
        "author": clean((item.get("creator") or {}).get("name")),
        "likes": item.get("like_count") or 0, "downloads": None, "makes": item.get("make_count") or 0,
        "published": clean((item.get("created_at") or "")[:10]),
        "license": None if derivatives is None else ("derivatives allowed" if derivatives else "NO derivatives"),
        "url": thingiverse_url(item),
        "ai_generated": bool(item.get("is_ai")),
    }


def keep_thingiverse(item):
    """Drop what should never reach a shortlist: adult, private, banned and unpublished things."""
    return not (item.get("is_nsfw") or item.get("is_private") or item.get("is_banned") or item.get("is_published") is False)


def matches_terms(item, term, minimum=0.5):
    """Thingiverse's search is loose (popular things that touch one word). Keep a hit only when at least
    `minimum` of the words you typed appear in its name or tags."""
    words = [w for w in term.lower().split() if len(w) > 2]
    if not words:
        return True
    tags = " ".join(str(t.get("name") or t.get("tag") or "") if isinstance(t, dict) else str(t) for t in item.get("tags") or [])
    haystack = f"{item.get('name') or ''} {tags}".lower()
    return sum(w in haystack for w in words) / len(words) >= minimum


def rank(items, sort):
    if sort == "relevance":
        return items
    return sorted(items, key=lambda i: (i[sort] or 0, i["likes"]), reverse=True)


def render(items):
    if not items:
        return "Nothing found. Try fewer or different words, or model it from scratch."
    lines = []
    for n, i in enumerate(items, 1):
        lines.append(f"{n}. [{i['site']}] {i['name']}  ({i['author']}, {i['published']})" + ("  [AI-generated]" if i.get("ai_generated") else ""))
        downloads = "n/a" if i["downloads"] is None else i["downloads"]
        lines.append(f"   likes {i['likes']} | downloads {downloads} | printed by others {i['makes']} | {i['license'] or 'licence not shown'}")
        lines.append(f"   {i['url']}")
    return "\n".join(lines)


def collect(term, limit, site, opener, token):
    """(items, notes): every site asked for, a note for each one that could not answer."""
    items, notes = [], []
    if site in ("printables", "all"):
        try:
            items += [shape_printables(i) for i in search_printables(term, limit, opener)]
        except (urllib.error.URLError, RuntimeError, ValueError, OSError) as error:
            notes.append(f"Printables failed ({type(error).__name__}: {error})")
    if site in ("thingiverse", "all"):
        if not token:
            notes.append("Thingiverse skipped: no token (see the docstring of this script).")
        else:
            try:
                items += [shape_thingiverse(i) for i in search_thingiverse(term, limit * 3, token, opener)
                          if keep_thingiverse(i) and matches_terms(i, term)][:limit]
            except urllib.error.HTTPError as error:
                notes.append(f"Thingiverse answered {error.code}" + (" (token wrong, or the app is not approved yet)" if error.code == 401 else ""))
            except (urllib.error.URLError, ValueError, OSError) as error:
                notes.append(f"Thingiverse failed ({type(error).__name__})")
    return items, notes


def main(argv=None, opener=urllib.request.urlopen, token=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("term", help="what you are looking for, in English works best")
    parser.add_argument("--limit", type=int, default=8, help="per site")
    parser.add_argument("--sort", choices=["relevance", "likes", "downloads", "makes"], default="relevance")
    parser.add_argument("--site", choices=["printables", "thingiverse", "all"], default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    items, notes = collect(args.term, args.limit, args.site, opener, token if token is not None else load_token())
    for note in notes:
        print(note, file=sys.stderr)
    if not items and notes:
        return 1
    items = rank(items, args.sort)
    print(json.dumps(items, indent=2) if args.json else render(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
