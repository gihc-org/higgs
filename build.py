#!/usr/bin/env python3
"""higgs: content/ → k8s/feed.xml (Atom-feed)."""

import datetime as dt
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import markdown

# ---------------------------------------------------------------------------
# Neutralitets-ankre: det eneste sted URL'er og identitet bor.
# Skift domæne/host her, og feedet følger med — intet andet.
# ---------------------------------------------------------------------------
FEED_BASE = "https://higgs.gihc.online"
FEED_PATH = "/feed.xml"
FEED_TITLE = "higgs"
FEED_AUTHOR = "Kristian Nygaard Jensen"

CONTENT_DIR = Path("content")
OUTPUT = Path("k8s/feed.xml")  # i k8s/, fordi kustomize kun kan se filer i sin mappe

MIME_BY_EXT = {
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".ogg": "audio/ogg",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


@dataclass
class Post:
    slug: str
    title: str
    date: dt.date
    summary: str
    external_url: str | None
    content_html: str
    enclosures: list[dict] = field(default_factory=list)

    @property
    def entry_id(self) -> str:
        # Stabil pr. slug: gamle poster bliver ikke genmarkeret som ulæste.
        return str(uuid.uuid5(uuid.NAMESPACE_URL, FEED_BASE + "/" + self.slug))


def parse_front_matter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) != 3:
        return {}, raw
    return _parse_meta(parts[1]), parts[2].strip()


def _parse_meta(fm: str) -> dict:
    meta: dict = {}
    media: list[dict] = []
    in_media = False
    item: dict | None = None
    for line in fm.splitlines():
        s = line.strip()
        if s == "media:":
            in_media = True
            continue
        m_item = re.match(r"^-\s+([A-Za-z_]+):\s*(.*)$", s)
        if in_media and m_item:
            item = {m_item.group(1): m_item.group(2).strip()}
            media.append(item)
            continue
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", s)
        if not m:
            in_media = False
            continue
        key, val = m.group(1), m.group(2).strip()
        if in_media and item is not None:
            item[key] = val
        else:
            meta[key] = val
            in_media = False
    if media:
        meta["media"] = media
    return meta


def post_date(meta: dict, slug: str) -> dt.date:
    if meta.get("date"):
        try:
            return dt.date.fromisoformat(meta["date"])
        except ValueError:
            raise ValueError(f"{slug}: ugyldig dato i front matter: {meta['date']!r}")
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-", slug)
    if m:
        return dt.date.fromisoformat(m.group(1))
    raise ValueError(
        f"{slug}: ingen dato — filnavnet skal starte med YYYY-MM-DD "
        "eller have 'date' i front matter"
    )


def build_enclosures(meta: dict, slug: str) -> list[dict]:
    out = []
    for item in meta.get("media", []):
        src = item.get("src")
        if not src:
            continue
        p = Path(src)
        if not p.is_file():
            print(f"advarsel: medie mangler ({src}) — springes over", file=sys.stderr)
            continue
        mime = item.get("type") or MIME_BY_EXT.get(p.suffix.lower(), "application/octet-stream")
        out.append(
            {
                "type": mime,
                "length": p.stat().st_size,
                "href": f"{FEED_BASE}/{src}",
            }
        )
    return out


def load_posts() -> list[Post]:
    posts = []
    for path in sorted(CONTENT_DIR.glob("*.md")):
        slug = path.stem
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        posts.append(
            Post(
                slug=slug,
                title=meta.get("title") or slug,
                date=post_date(meta, slug),
                summary=meta.get("summary", ""),
                external_url=meta.get("external_url") or None,
                content_html=markdown.markdown(body) if body else "",
                enclosures=build_enclosures(meta, slug),
            )
        )
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)
    return posts


def rfc3339(d: dt.date) -> str:
    return d.isoformat() + "T00:00:00Z"


def build_feed(posts: list[Post]) -> str:
    updated = max((p.date for p in posts), default=dt.date.today())
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"  <title>{escape(FEED_TITLE)}</title>",
        f"  <id>{escape(FEED_BASE + '/')}</id>",
        f"  <updated>{rfc3339(updated)}</updated>",
        f'  <link rel="self" href={quoteattr(FEED_BASE + FEED_PATH)}/>',
        f"  <author><name>{escape(FEED_AUTHOR)}</name></author>",
    ]
    for p in posts:
        lines.append("  <entry>")
        lines.append(f"    <title>{escape(p.title)}</title>")
        lines.append(f"    <id>urn:uuid:{p.entry_id}</id>")
        lines.append(f"    <updated>{rfc3339(p.date)}</updated>")
        lines.append(f"    <published>{rfc3339(p.date)}</published>")
        if p.summary:
            lines.append(f'    <summary type="html">{escape(markdown.markdown(p.summary))}</summary>')
        if p.external_url:
            lines.append(f'    <link rel="alternate" href={quoteattr(p.external_url)}/>')
        if p.content_html:
            lines.append(f'    <content type="html">{escape(p.content_html)}</content>')
        for enc in p.enclosures:
            lines.append(
                f'    <link rel="enclosure" type={quoteattr(enc["type"])} '
                f'length="{enc["length"]}" href={quoteattr(enc["href"])}/>'
            )
        lines.append("  </entry>")
    lines.append("</feed>")
    return "\n".join(lines) + "\n"


def main() -> int:
    posts = load_posts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_feed(posts), encoding="utf-8")
    print(f"ok: {len(posts)} post(s) → {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
