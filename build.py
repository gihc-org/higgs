#!/usr/bin/env python3
"""higgs: feed-registry → k8s/feed.xml + k8s/feeds/<key>/feed.xml + nginx-conf.

Kilden til sandhed er FEEDS nedenfor: én post pr. feed med URL-sti, titel og
hvor indholdet kommer fra. Genererede feeds bygges fra markdown under
content/; vedhæftede feeds (fx rettede LibriVox-RSS-filer) ligger som XML i
feeds/ og kopieres uændret ind i k8s/, hvor kustomize kan se dem.

Neutralitets-ankre (se README): SITE_BASE er det eneste sted, domænet lever;
hver feed-URL står kun i registry'et her.
"""

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

import markdown

# ---------------------------------------------------------------------------
# Neutralitets-ankre: det eneste sted URL'er og identitet bor.
# SITE_BASE er domænet; hver feed har sin sti i FEEDS nedenfor.
# ---------------------------------------------------------------------------
SITE_BASE = "https://higgs.gihc.online"
# Fase 2: IPFS som ekstra distributionssti — gatewayen lever også her.
# Feedet virker uden IPFS; hvis ipfs mangler, springes IPFS-enclosures over.
FEED_IPFS_GATEWAY = "https://ipfs.higgs.gihc.online"

ATOM = "application/atom+xml"
RSS = "application/rss+xml"

K8S_DIR = Path("k8s")
NGINX_CONF = K8S_DIR / "nginx" / "default.conf"

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


@dataclass(frozen=True)
class Feed:
    """Ét feed: hvor det bor, hvad det hedder, og hvor indholdet kommer fra."""

    key: str  # unik nøgle; styrer artefakt-stien under k8s/
    path: str  # URL-sti på SITE_BASE, fx /tao/lieh-tzu/feed.xml
    title: str
    author: str
    kind: str  # "generated" (fra markdown) | "attached" (færdig XML)
    output: str  # artefakt-sti (kustomize kan kun se filer i k8s/)
    content_type: str = ATOM
    content_dir: str | None = None  # generated: mappe med markdown-poster
    source: str | None = None  # attached: XML-fil i repoet
    logo: str = "/logo.png"  # absolut URL eller sti på SITE_BASE
    subtitle: str = ""  # Atom <subtitle> — feedets beskrivelse

    @property
    def url(self) -> str:
        return SITE_BASE + self.path

    @property
    def anchor(self) -> str:
        """Basis-URL for entry-id'er og medie-enclosures (mappen feedet bor i)."""
        return SITE_BASE + self.path.rsplit("/", 1)[0] + "/"

    @property
    def logo_url(self) -> str:
        return self.logo if "://" in self.logo else SITE_BASE + self.logo


# ---------------------------------------------------------------------------
# Registry: tilføj et feed her — resten (artefakt, ConfigMap i k8s/,
# nginx-Content-Type, deploy-verifikation) følger med.
# ---------------------------------------------------------------------------
FEEDS: tuple[Feed, ...] = (
    Feed(
        key="higgs",
        path="/feed.xml",
        title="Higgs",
        author="Kristian Nygaard Jensen",
        kind="generated",
        output="k8s/feed.xml",
        content_dir="content/higgs",
    ),
    # >>> importerede feeds (FEEDS) — vedligeholdes af scripts/import-librivox.py >>>
    # kilde: https://librivox.org/rss/1263 (LibriVox, public domain)
    Feed(
        key="tao/lieh-tzu",
        path="/tao/lieh-tzu/feed.xml",
        title="Book of Lieh-Tzu, The by Liezi ( - ca. 400 BC)",
        author="LibriVox",
        kind="generated",
        output="k8s/feeds/tao/lieh-tzu/feed.xml",
        content_dir="content/tao/lieh-tzu",
        # Coveret ligger på PVC'en (media/ er gitignoreret) og serveres af nginx.
        logo="/media/tao/lieh-tzu/cover.jpg",
        subtitle=(
            "Lionel Giles' engelske oversættelse af The Book of Lieh-Tzu, indlæst "
            "af LibriVox (public domain). "
            "Although Lieh Tzu's work has evidently passed through the hands of "
            "many editors and gathered numerous accretions, there remains a "
            "considerable nucleus which in all probability was committed to "
            "writing by Lieh Tzu's immediate disciples, and is therefore older "
            "than the genuine parts of Chuang Tzu. There are some obvious "
            "analogies between the two authors, and indeed a certain amount of "
            "matter common to both; but on the whole Lieh Tzu's book bears an "
            "unmistakable impress of its own. The geniality of its tone contrasts "
            "with the somewhat hard brilliancy of Chuang Tzu, and a certain kindly "
            "sympathy with the aged, the poor and the humble of this life, not "
            "excluding the brute creation, makes itself felt throughout. "
            "— From Lionel Giles' introduction"
        ),
    ),
    # kilde: https://librivox.org/rss/12948
    Feed(
        key="tao/sayings-of-lao-tzu",
        path="/tao/sayings-of-lao-tzu/feed.xml",
        title="Sayings of Lao Tzu, The by Lao Tzu ( - c. 550 BCE)",
        author="LibriVox",
        kind="generated",
        output="k8s/feeds/tao/sayings-of-lao-tzu/feed.xml",
        content_dir="content/tao/sayings-of-lao-tzu",
        logo="/media/tao/sayings-of-lao-tzu/cover.jpg",
        subtitle=(
            "Lao-Tzu, also known as Laozi was a Chinese philosopher believed to have "
            "lived in the 6th century BCE and is credited with writing the "
            "Tao-Te-Ching which centers around the idea that the way of virtue lies "
            "in simplicity and a recognition of a natural, universal force known as "
            "the Tao. He is traditionally regarded as the founder of Taoism. This "
            "book is a compilation of his most profound writings translated directly "
            "from ancient Chinese texts. - Summary by Nemo"
        ),
    ),
    # kilde: https://librivox.org/rss/11547
    Feed(
        key="tao/musings-of-a-chinese-mystic",
        path="/tao/musings-of-a-chinese-mystic/feed.xml",
        title="Musings of a Chinese Mystic: Selections from the Philosophy of Chuang Tzu",
        author="LibriVox",
        kind="generated",
        output="k8s/feeds/tao/musings-of-a-chinese-mystic/feed.xml",
        content_dir="content/tao/musings-of-a-chinese-mystic",
        logo="/media/tao/musings-of-a-chinese-mystic/cover.jpg",
        subtitle=(
            "If Lao Tzu then had revolted against the growing artificiality of life "
            "in his day, a return to nature must have seemed doubly imperative to his "
            "disciple Chuang Tzu, who flourished more than a couple of centuries "
            "later, when the bugbear of civilisation had steadily advanced. With "
            "chagrin he saw that Lao Tzu's teaching had never obtained any firm hold "
            "on the masses, still less on the rulers of China, whereas the star of "
            "Confucius was unmistakably in the ascendant. Within his own recollection "
            "the propagation of Confucian ethics had received a powerful impetus from "
            "Mencius, the second of China's orthodox sages. Now Chuang Tzu was imbued "
            "to the core with the principles of pure Taoism, as handed down by Lao "
            "Tzu. He might more fitly be dubbed \"the Tao-saturated man\" than Spinoza "
            "\"the God-intoxicated.\" Tao in its various phases pervaded his inmost "
            "being and was reflected in all his thought. He was therefore eminently "
            "qualified to revive his Master's ringing protest against the "
            "materialistic tendencies of the time. - Summary by Lionel Giles"
        ),
    ),
    # <<< importerede feeds (FEEDS) <<<
)


@dataclass
class Post:
    slug: str
    title: str
    published: dt.datetime
    summary: str
    external_url: str | None
    content_html: str
    enclosures: list[dict] = field(default_factory=list)


def entry_id(feed: Feed, slug: str) -> str:
    """Stabil pr. slug: gamle poster bliver ikke genmarkeret som ulæste."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, feed.anchor + slug))


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


def post_datetime(meta: dict, slug: str) -> dt.datetime:
    if meta.get("date"):
        try:
            published = dt.datetime.fromisoformat(meta["date"])
        except ValueError:
            raise ValueError(f"{slug}: ugyldig dato i front matter: {meta['date']!r}")
        if published.tzinfo is None:
            published = published.replace(tzinfo=dt.timezone.utc)
        return published
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-", slug)
    if m:
        d = dt.date.fromisoformat(m.group(1))
        return dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
    raise ValueError(
        f"{slug}: ingen dato — filnavnet skal starte med YYYY-MM-DD "
        "eller have 'date' (evt. med tidspunkt) i front matter"
    )


def build_enclosures(meta: dict) -> list[dict]:
    """Enclosure-URL'er ud fra `src:` i front matter.

    `src:` er altid relativ til domæneroden (fx `media/tao/lieh-tzu/fil.mp3`),
    fordi nginx serverer `/media/…` fra PVC'en — ikke fra feedets mappe.
    """
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
                "href": f"{SITE_BASE}/{src}",
            }
        )
        cid = ipfs_wrap_dir_cid(p)
        if cid:
            out.append(
                {
                    "type": mime,
                    "length": p.stat().st_size,
                    "href": f"{FEED_IPFS_GATEWAY}/ipfs/{cid}/{p.name}",
                }
            )
    return out


def ipfs_wrap_dir_cid(path: Path) -> str | None:
    """Stabil CID for <fil> i en wrap-mappe (samme uanset maskine).

    `ipfs add -w` pakker filen i en mappe opkaldt efter filnavnet; den mappe-CID
    bruges i enclosure-URL'en, så gatewayen kan servere filen med korrekt
    Content-Type via `/ipfs/<dirCID>/<filnavn>`. Beregnes med --only-hash, så
    intet skrives til det lokale repo.
    """
    if shutil.which("ipfs") is None:
        print("advarsel: ipfs ikke fundet — IPFS-enclosures springes over", file=sys.stderr)
        return None
    try:
        proc = subprocess.run(
            ["ipfs", "add", "-Q", "--only-hash", "--wrap-with-directory", "--cid-version", "1", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"advarsel: ipfs fejlede for {path.name} ({e}) — IPFS-enclosure springes over", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(
            f"advarsel: ipfs kunne ikke beregne CID for {path.name} "
            f"({proc.stderr.strip() or proc.returncode}) — IPFS-enclosure springes over",
            file=sys.stderr,
        )
        return None
    return proc.stdout.strip().splitlines()[-1]


def load_posts(feed: Feed) -> list[Post]:
    posts = []
    for path in sorted(Path(feed.content_dir).glob("*.md")):
        slug = path.stem
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        posts.append(
            Post(
                slug=slug,
                title=meta.get("title") or slug,
                published=post_datetime(meta, slug),
                summary=meta.get("summary", ""),
                external_url=meta.get("external_url") or None,
                content_html=markdown.markdown(body) if body else "",
                enclosures=build_enclosures(meta),
            )
        )
    posts.sort(key=lambda p: (p.published, p.slug), reverse=True)
    return posts


def rfc3339(d: dt.datetime) -> str:
    s = d.isoformat()
    return s.replace("+00:00", "Z") if d.utcoffset() == dt.timedelta(0) else s


def build_feed(feed: Feed, posts: list[Post]) -> str:
    updated = max((p.published for p in posts), default=dt.datetime.now(dt.timezone.utc))
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"  <title>{escape(feed.title)}</title>",
    ]
    if feed.subtitle:
        lines.append(f"  <subtitle>{escape(feed.subtitle)}</subtitle>")
    lines += [
        f"  <id>{escape(feed.anchor)}</id>",
        f"  <updated>{rfc3339(updated)}</updated>",
        f'  <link rel="self" href={quoteattr(feed.url)}/>',
        f"  <logo>{escape(feed.logo_url)}</logo>",
        f"  <icon>{escape(feed.logo_url)}</icon>",
        f"  <author><name>{escape(feed.author)}</name></author>",
    ]
    for p in posts:
        lines.append("  <entry>")
        lines.append(f"    <title>{escape(p.title)}</title>")
        lines.append(f"    <id>urn:uuid:{entry_id(feed, p.slug)}</id>")
        lines.append(f"    <updated>{rfc3339(p.published)}</updated>")
        lines.append(f"    <published>{rfc3339(p.published)}</published>")
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


def check_attached(feed: Feed, text: str) -> None:
    """Vedhæftede feeds skal være gyldig XML med korrekt self-link."""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as e:
        raise ValueError(f"{feed.key}: {feed.source} er ikke gyldig XML ({e})")
    link = root.find("./channel/{http://www.w3.org/2005/Atom}link[@rel='self']")
    href = link.get("href") if link is not None else None
    if href != feed.url:
        raise ValueError(
            f'{feed.key}: <atom:link rel="self"> peger på {href!r}, forventet '
            f"{feed.url!r} — ret det i {feed.source}"
        )


def build_nginx_conf(feeds: tuple[Feed, ...]) -> str:
    """nginx sender text/xml for .xml — Content-Type sættes pr. feed her."""
    lines = [
        "# GENERERET af build.py ud fra FEEDS — redigér registry'et i stedet.",
        "server {",
        "    listen 80;",
        "    server_name _;",
        "    root /usr/share/nginx/html;",
        "    index index.html;",
        "    include /etc/nginx/mime.types;",
        "",
    ]
    for feed in feeds:
        lines += [
            f"    location = {feed.path} {{",
            f"        types {{ {feed.content_type} xml; }}",
            f"        default_type {feed.content_type};",
            "    }",
        ]
    lines += [
        "",
        "    location ~* \\.m4a$ {",
        "        types { audio/mp4 m4a; }",
        "        default_type audio/mp4;",
        "    }",
        "",
        "    location / {",
        "        try_files $uri =404;",
        "    }",
        "}",
    ]
    return "\n".join(lines) + "\n"


def build_feed_file(feed: Feed) -> int:
    """Skriver feedets artefakt i k8s/ og returnerer antal poster (0 for attached)."""
    out = Path(feed.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if feed.kind == "generated":
        posts = load_posts(feed)
        out.write_text(build_feed(feed, posts), encoding="utf-8")
        return len(posts)
    if feed.kind == "attached":
        text = Path(feed.source).read_text(encoding="utf-8")
        check_attached(feed, text)
        out.write_text(text, encoding="utf-8")
        return 0
    raise ValueError(f"{feed.key}: ukendt kind {feed.kind!r} (brug 'generated' eller 'attached')")


def expected_media(feeds: tuple[Feed, ...] = FEEDS) -> list[str]:
    """Alle mediefiler i genererede feeds: `src:`-stier og lokalt artwork.

    Artwork tælles med, fordi feedets `<logo>` kan pege på en fil under media/
    (fx `/media/tao/lieh-tzu/cover.jpg`) — den skal også med til en ny maskine.
    """
    srcs: list[str] = []
    for feed in feeds:
        if feed.kind != "generated" or not feed.content_dir:
            continue
        if feed.logo.startswith(("media/", "/media/")):
            src = feed.logo.lstrip("/")
            if src not in srcs:
                srcs.append(src)
        for path in sorted(Path(feed.content_dir).glob("*.md")):
            meta, _body = parse_front_matter(path.read_text(encoding="utf-8"))
            for item in meta.get("media", []):
                src = item.get("src")
                if src and src not in srcs:
                    srcs.append(src)
    return srcs


def missing_media(feeds: tuple[Feed, ...]) -> list[str]:
    """Mediefiler som `src:` peger på, men som ikke findes lokalt.

    Media er ikke i git, så et friskt checkout kan ikke bygge et komplet feed.
    deploy.sh kører derfor med --strict-media og afbryder, hvis listen ikke er
    tom — et deploy må aldrig fjerne enclosure-links i stilhed.
    """
    return [src for src in expected_media(feeds) if not Path(src).is_file()]


def validate_registry(feeds: tuple[Feed, ...]) -> None:
    for attr in ("key", "path", "output"):
        seen = [getattr(f, attr) for f in feeds]
        if len(seen) != len(set(seen)):
            raise ValueError(f"FEEDS: {attr} skal være unik pr. feed")
    for feed in feeds:
        if feed.kind == "generated" and not feed.content_dir:
            raise ValueError(f"{feed.key}: generated feed mangler content_dir")
        if feed.kind == "attached" and not feed.source:
            raise ValueError(f"{feed.key}: attached feed mangler source")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="higgs: byg alle feeds i FEEDS")
    parser.add_argument(
        "--list",
        action="store_true",
        help="skriv feeds som TSV (key, url, content_type, title) og afslut",
    )
    parser.add_argument(
        "--strict-media",
        action="store_true",
        help="fejl hvis en mediefil mangler (bruges af deploy.sh)",
    )
    args = parser.parse_args(argv)
    validate_registry(FEEDS)

    if args.list:
        for feed in FEEDS:
            print("\t".join([feed.key, feed.url, feed.content_type, feed.title]))
        return 0

    missing = missing_media(FEEDS)
    if missing and args.strict_media:
        print(f"FEJL: {len(missing)} mediefil(er) mangler lokalt:", file=sys.stderr)
        for src in missing:
            print(f"  - {src}", file=sys.stderr)
        print(
            "Stop: feedet ville blive udgivet uden enclosures. Hent medierne "
            "(media/ er ikke i git), eller byg bevidst uden med --strict-media.",
            file=sys.stderr,
        )
        return 2

    for feed in FEEDS:
        n = build_feed_file(feed)
        detail = f"{n} post(s)" if feed.kind == "generated" else f"vedhæftet {feed.source}"
        print(f"ok: {feed.key} → {feed.output} ({detail})")

    # Alle artefakter skal kunne parses, før de ryger i en ConfigMap.
    for feed in FEEDS:
        ElementTree.parse(feed.output)

    # Mappen kan mangle i et friskt checkout: default.conf er et genereret
    # artefakt og ligger derfor ikke i git (git gemmer ikke tomme mapper).
    NGINX_CONF.parent.mkdir(parents=True, exist_ok=True)
    NGINX_CONF.write_text(build_nginx_conf(FEEDS), encoding="utf-8")
    print(f"ok: nginx-Content-Type for {len(FEEDS)} feed(s) → {NGINX_CONF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
