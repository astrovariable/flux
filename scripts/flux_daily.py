#!/usr/bin/env python3
"""
Flux daily job.

Runs once a day (GitHub Actions). It:
  1. reads today's new papers from the arXiv RSS feeds for the categories in config.json,
  2. marks papers that match your keywords or followed authors,
  3. optionally writes plain-language summaries in English and Hindi (needs ANTHROPIC_API_KEY),
  4. chooses a "pick of the day" from picks.json,
  5. writes JSON files into docs/data/ for the Flux web app,
  6. sends a phone notification through ntfy (needs NTFY_TOPIC).

Only the Python standard library is used, so nothing needs installing.

Usage:
  python scripts/flux_daily.py                 # normal run
  python scripts/flux_daily.py --no-notify     # do everything except the notification
  python scripts/flux_daily.py --fixtures tests/fixtures --no-notify --no-summaries   # offline test
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
ARCHIVE = DATA / "archive"

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
USER_AGENT = "Flux/1.0 (personal daily arXiv reader; github actions)"
ARXIV_PAUSE_S = 3  # arXiv asks for at least 3 seconds between requests

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}

CATEGORY_NAMES = {
    "astro-ph.GA": "Galaxies",
    "astro-ph.CO": "Cosmology",
    "astro-ph.EP": "Exoplanets",
    "astro-ph.HE": "High energy",
    "astro-ph.IM": "Instruments",
    "astro-ph.SR": "Solar & stellar",
    "gr-qc": "Gravity",
    "physics.space-ph": "Space physics",
    "physics.ed-ph": "Physics education",
}


# ---------------------------------------------------------------- helpers

def log(msg):
    print(f"[flux] {msg}", flush=True)


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def arxiv_id_from(text):
    """Pull an arXiv ID (new or old style) out of a link, guid or description; drop the version."""
    m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", text or "")
    if m:
        return m.group(1)
    m = re.search(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?", text or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- arXiv RSS (today's papers)

def fetch_rss(category, fixtures=None):
    if fixtures:
        p = Path(fixtures) / f"rss_{category}.xml"
        return p.read_bytes() if p.exists() else None
    url = f"https://rss.arxiv.org/rss/{category}"
    try:
        return http_get(url)
    except (urllib.error.URLError, TimeoutError) as e:
        log(f"could not fetch {url}: {e}")
        return None


def parse_rss(xml_bytes, category):
    """Return (announce_date or None, list of paper dicts) from one arXiv RSS feed."""
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        return None, []

    announce_date = None
    for tag in ("pubDate", "lastBuildDate"):
        el = channel.find(tag)
        if el is not None and el.text:
            try:
                announce_date = dt.datetime.strptime(el.text.strip()[:16], "%a, %d %b %Y").date().isoformat()
                break
            except ValueError:
                pass

    papers = []
    for item in channel.findall("item"):
        title = clean(item.findtext("title"))
        link = clean(item.findtext("link"))
        desc = item.findtext("description") or ""
        guid = item.findtext("guid") or ""
        pid = arxiv_id_from(link) or arxiv_id_from(guid) or arxiv_id_from(desc)
        if not pid:
            continue

        atype = clean(item.findtext("arxiv:announce_type", namespaces=NS))
        if not atype:
            m = re.search(r"Announce Type:\s*([\w-]+)", desc)
            atype = m.group(1) if m else "new"

        m = re.search(r"Abstract:\s*(.*)", desc, re.S)
        abstract = clean(m.group(1) if m else desc)

        authors_raw = clean(item.findtext("dc:creator", namespaces=NS))
        # arXiv sometimes adds affiliations in brackets, e.g. "Noam Soker (Technion, Israel)";
        # drop them so the comma inside does not split one author into two.
        while re.search(r"\([^()]*\)", authors_raw):
            authors_raw = re.sub(r"\s*\([^()]*\)", "", authors_raw)
        authors = [a.strip() for a in re.split(r",\s*|\s+and\s+", authors_raw) if a.strip()]

        cats = [clean(c.text) for c in item.findall("category") if c.text]
        if not announce_date:
            pd = item.findtext("pubDate")
            if pd:
                try:
                    announce_date = dt.datetime.strptime(pd.strip()[:16], "%a, %d %b %Y").date().isoformat()
                except ValueError:
                    pass

        papers.append({
            "id": pid,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "categories": cats or [category],
            "primary": (cats[0] if cats else category),
            "feed": category,
            "announce_type": atype,
            "link": f"https://arxiv.org/abs/{pid}",
            "pdf": f"https://arxiv.org/pdf/{pid}",
        })
    return announce_date, papers


def collect_today(cfg, fixtures=None):
    include_cross = cfg.get("include_cross_lists", True)
    wanted_types = {"new"} | ({"cross"} if include_cross else set())
    by_id, dates = {}, []
    for i, cat in enumerate(cfg["categories"]):
        if i and not fixtures:
            time.sleep(ARXIV_PAUSE_S)
        raw = fetch_rss(cat, fixtures)
        if not raw:
            continue
        try:
            date, papers = parse_rss(raw, cat)
        except ET.ParseError as e:
            log(f"bad RSS for {cat}: {e}")
            continue
        if date:
            dates.append(date)
        for p in papers:
            if p["announce_type"] not in wanted_types:
                continue  # skip replacements (updated old papers)
            if p["id"] in by_id:
                by_id[p["id"]]["feeds"].append(cat)
            else:
                p["feeds"] = [cat]
                by_id[p["id"]] = p
    announce = max(dates) if dates else None
    return announce, list(by_id.values())


# ---------------------------------------------------------------- matching

def mark_matches(papers, cfg):
    kws = [k for k in cfg.get("keywords", []) if k.strip()]
    auths = [a for a in cfg.get("authors", []) if a.strip()]
    for p in papers:
        text = (p["title"] + " " + p["abstract"]).lower()
        hits = [k for k in kws if k.lower() in text]
        who = [a for a in auths if any(a.lower() in name.lower() for name in p["authors"])]
        p["matched"] = {"keywords": hits, "authors": who}
        p["is_match"] = bool(hits or who)
    # matches first, then new before cross-lists, keep arXiv order otherwise
    papers.sort(key=lambda p: (not p["is_match"], p["announce_type"] != "new"))
    return papers


# ---------------------------------------------------------------- AI summaries (optional)

SUMMARY_PROMPT = """You write plain-language summaries of astronomy research papers for a reader with a master's degree in astrophysics who also does public outreach in English and Hindi.

Paper title: {title}
Abstract: {abstract}

Write:
1. "en": 2 to 3 short, plain English sentences saying what the authors did and what they found. No hype, no dramatic words. Do not add anything that is not in the abstract.
2. "hi": the same summary in simple Hindi (Devanagari script). Keep standard technical terms (for example "spectrograph", "exoplanet") in Devanagari transliteration when there is no common Hindi word.

Reply with only a JSON object: {{"en": "...", "hi": "..."}}"""


def summarise(paper, model, api_key):
    body = json.dumps({
        "model": model,
        "max_tokens": 700,
        "messages": [{"role": "user", "content": SUMMARY_PROMPT.format(title=paper["title"], abstract=paper["abstract"])}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        out = json.loads(r.read())
    text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0)) if m else {}
    return {"en": clean(data.get("en", "")), "hi": clean(data.get("hi", ""))}


def add_summaries(papers, cfg, previous):
    s = cfg.get("summaries", {})
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not s.get("enabled") or not key:
        log("summaries skipped (disabled or no ANTHROPIC_API_KEY)")
        return
    done = {p["id"]: p.get("summary") for p in previous.get("papers", []) if p.get("summary")}
    budget = int(s.get("max_papers", 15))
    for p in papers:
        if budget <= 0:
            break
        if p["id"] in done:
            p["summary"] = done[p["id"]]
            continue
        try:
            p["summary"] = summarise(p, s.get("model", "claude-haiku-4-5"), key)
            budget -= 1
            log(f"summarised {p['id']}")
        except Exception as e:  # never let one failed summary stop the run
            log(f"summary failed for {p['id']}: {e}")


# ---------------------------------------------------------------- pick of the day

def fetch_arxiv_meta(pid, fixtures=None):
    if fixtures:
        p = Path(fixtures) / "api_pick.xml"
        raw = p.read_bytes() if p.exists() else None
    else:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": pid})
        try:
            raw = http_get(url)
        except (urllib.error.URLError, TimeoutError) as e:
            log(f"could not fetch metadata for {pid}: {e}")
            raw = None
    if not raw:
        return None
    root = ET.fromstring(raw)
    entry = root.find("atom:entry", NS)
    if entry is None or entry.find("atom:title", NS) is None:
        return None
    prim = entry.find("arxiv:primary_category", NS)
    return {
        "title": clean(entry.findtext("atom:title", namespaces=NS)),
        "authors": [clean(a.findtext("atom:name", namespaces=NS)) for a in entry.findall("atom:author", NS)],
        "abstract": clean(entry.findtext("atom:summary", namespaces=NS)),
        "published": clean(entry.findtext("atom:published", namespaces=NS))[:10],
        "primary": prim.get("term") if prim is not None else "",
    }


def choose_pick(today, picks):
    mmdd = today.strftime("%m-%d")
    for p in picks:
        if p.get("on") == mmdd:
            return p, True
    return picks[today.timetuple().tm_yday % len(picks)], False


def build_pick(today, fixtures=None):
    picks = read_json(ROOT / "picks.json", {}).get("picks", [])
    if not picks:
        return None
    pick, on_this_day = choose_pick(today, picks)
    cache = read_json(DATA / "picks_cache.json", {})
    meta = cache.get(pick["id"])
    if not meta:
        meta = fetch_arxiv_meta(pick["id"], fixtures)
        if meta:
            cache[pick["id"]] = meta
            write_json(DATA / "picks_cache.json", cache)
    meta = meta or {"title": f"arXiv:{pick['id']}", "authors": [], "abstract": "", "published": "", "primary": ""}
    return {
        "date": today.isoformat(),
        "id": pick["id"],
        "on_this_day": on_this_day,
        "note": pick.get("note", ""),
        "year": meta["published"][:4],
        "link": f"https://arxiv.org/abs/{pick['id']}",
        "pdf": f"https://arxiv.org/pdf/{pick['id']}",
        **meta,
    }


# ---------------------------------------------------------------- notification

def notify(cfg, today, today_data, pick, new_mailing):
    n = cfg.get("notify", {})
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not n.get("enabled") or not topic:
        log("notification skipped (disabled or no NTFY_TOPIC)")
        return
    lines = []
    if new_mailing:
        papers = today_data["papers"]
        matches = [p for p in papers if p["is_match"]]
        lines.append(f"{len(papers)} new papers in your topics, {len(matches)} match your keywords.")
        if matches:
            lines.append(f"Top match: {matches[0]['title']}")
    if pick:
        lines.append(f"Pick of the day: {pick['title']}")
    if not lines:
        return
    url = n.get("server", "https://ntfy.sh").rstrip("/") + "/" + urllib.parse.quote(topic)
    date_label = today.strftime("%a %d %b")
    req = urllib.request.Request(
        url,
        data="\n".join(lines).encode("utf-8"),
        headers={
            "Title": f"Flux: {date_label}",  # keep headers plain ASCII
            "Click": cfg.get("app_url", ""),
            "Tags": "telescope",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=30).read()
        log("notification sent")
    except Exception as e:
        log(f"notification failed: {e}")


# ---------------------------------------------------------------- archive housekeeping

def update_index(keep_days):
    files = sorted(ARCHIVE.glob("*.json"), reverse=True)
    for old in files[keep_days:]:
        old.unlink()
    dates = [f.stem for f in sorted(ARCHIVE.glob("*.json"), reverse=True)]
    write_json(DATA / "index.json", {"dates": dates})


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Flux daily job")
    ap.add_argument("--fixtures", help="read arXiv data from this folder instead of the internet (testing)")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--no-summaries", action="store_true")
    ap.add_argument("--date", help="pretend today is YYYY-MM-DD (testing the pick of the day)")
    args = ap.parse_args()

    cfg = read_json(ROOT / "config.json", None)
    if not cfg:
        sys.exit("config.json missing or not valid JSON")
    if args.no_summaries:
        cfg.setdefault("summaries", {})["enabled"] = False
    if args.no_notify:
        cfg.setdefault("notify", {})["enabled"] = False

    today = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(IST).date()
    previous = read_json(DATA / "today.json", {})

    announce, papers = collect_today(cfg, args.fixtures)
    new_mailing = bool(papers) and announce != previous.get("date")
    log(f"feed date {announce}, {len(papers)} papers, new mailing: {new_mailing}")

    if new_mailing:
        mark_matches(papers, cfg)
        add_summaries(papers, cfg, previous)
        counts = {}
        for p in papers:
            for f in p["feeds"]:
                counts[f] = counts.get(f, 0) + 1
        today_data = {
            "date": announce,
            "generated_at": dt.datetime.now(IST).isoformat(timespec="minutes"),
            "user_name": cfg.get("user_name", ""),
            "categories": [{"id": c, "name": CATEGORY_NAMES.get(c, c), "count": counts.get(c, 0)} for c in cfg["categories"]],
            "keywords": cfg.get("keywords", []),
            "authors": cfg.get("authors", []),
            "match_count": sum(p["is_match"] for p in papers),
            "papers": papers,
        }
        write_json(DATA / "today.json", today_data)
        write_json(ARCHIVE / f"{announce}.json", today_data)
        update_index(int(cfg.get("archive_days", 30)))
    else:
        today_data = previous

    pick = build_pick(today, args.fixtures)
    if pick:
        write_json(DATA / "pick.json", pick)
        log(f"pick of the day: {pick['id']} {pick['title'][:60]}")

    notify(cfg, today, today_data, pick, new_mailing)


if __name__ == "__main__":
    main()
