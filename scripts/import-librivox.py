#!/usr/bin/env python3
"""Importér en LibriVox-bog som higgs-feed.

Henter metadata og lydfiler fra archive.org, lægger medierne i
`media/<tema>/<bog>/`, skriver markdown-poster i `content/<tema>/<bog>/` og
indsætter feedet i registry'et (build.py: FEEDS) samt i k8s-manifesterne —
altid i de markerede "importerede feeds"-blokke, så indsættelsen er idempotent
og let at revidere.

Brug:
    scripts/import-librivox.py --theme tao --rss https://librivox.org/rss/1263
    scripts/import-librivox.py --theme tao --book zhuangzi --item zhuangzi_cm_librivox

Vigtigt om kilden: LibriVox' egne enclosure-URL'er peger på
`www.archive.org/download/…`, som redirecter til en downloadnode (`dn…`) der
uregelmæssigt svarer HTTP 500. Scriptet henter derfor altid fra item'ets egen
host (`ia…us.archive.org`) via archive.orgs metadata-API, med md5-verifikation
af hver fil.

Rækkefølge: LibriVox publicerer ingen brugbare datoer, så scriptet giver hvert
kapitel en deterministisk dato (23:00 og bagud, ét minut pr. kapitel) med
**kapitel 1 som det nyeste**, så podcast-klienter der viser nyeste øverst
lister bogen i læserækkefølge. Brug --oldest-first for det modsatte.

Bagefter: `scripts/deploy.sh --sync-media` (og evt. --sync-ipfs).
"""

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import textwrap
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "higgs-import/1.0 (+https://higgs.gihc.online)"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"

# Lydvarianter på archive.org: navnesuffix -> (format, mime)
VARIANTS = {
    "64kb": ("_64kb.mp3", "64Kbps MP3", "audio/mpeg"),
    "vbr": (".mp3", "VBR MP3", "audio/mpeg"),
    "ogg": (".ogg", "Ogg Vorbis", "audio/ogg"),
}

MARKERS = {
    "build": (
        ROOT / "build.py",
        "    # >>> importerede feeds (FEEDS)",
        "    # <<< importerede feeds (FEEDS) <<<",
    ),
    "kustomization": (
        ROOT / "k8s/kustomization.yaml",
        "  # >>> importerede feeds (configMapGenerator)",
        "  # <<< importerede feeds (configMapGenerator) <<<",
    ),
    "mounts": (
        ROOT / "k8s/deployment.yaml",
        "            # >>> importerede feeds (volumeMounts)",
        "            # <<< importerede feeds (volumeMounts) <<<",
    ),
    "volumes": (
        ROOT / "k8s/deployment.yaml",
        "        # >>> importerede feeds (volumes)",
        "        # <<< importerede feeds (volumes) <<<",
    ),
}


@dataclass
class Track:
    n: int
    title: str
    duration: str
    base: str  # fælles navnestamme på tværs af varianterne
    files: dict = field(default_factory=dict)  # variant -> {"name","size","md5","length"}


@dataclass
class Book:
    item: str
    title: str
    description: str
    link: str
    cover_url: str
    server: str  # fx ia801602.us.archive.org
    directory: str  # fx /33/items/lieh_tzu_cm_librivox
    publicdate: dt.date | None
    tracks: list[Track]


def fetch(url: str, retries: int = 3, timeout: int = 60) -> bytes:
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            print(f"  advarsel: {url} fejlede ({e}) — forsøg {attempt}/{retries}", file=sys.stderr)
    raise SystemExit(f"kunne ikke hente {url}: {last}")


def fetch_json(url: str) -> dict:
    return json.loads(fetch(url).decode("utf-8"))


def download(url: str, dest: Path, size: int, md5: str, retries: int = 4) -> None:
    """Hent url til dest og verificér størrelse + md5. Springer over hvis ok."""
    if dest.is_file() and dest.stat().st_size == size:
        got = hashlib.md5(dest.read_bytes()).hexdigest()
        if got == md5:
            print(f"  {dest.name}: findes allerede (md5 ok)")
            return
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=600) as resp, tmp.open("wb") as fh:
                while chunk := resp.read(1 << 16):
                    fh.write(chunk)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"  advarsel: {dest.name} fejlede ({e}) — forsøg {attempt}/{retries}", file=sys.stderr)
            continue
        if tmp.stat().st_size != size or hashlib.md5(tmp.read_bytes()).hexdigest() != md5:
            print(f"  advarsel: {dest.name} afveg fra arkivets md5 — forsøg {attempt}/{retries}", file=sys.stderr)
            tmp.unlink(missing_ok=True)
            continue
        tmp.replace(dest)
        print(f"  {dest.name}: hentet ({size / 1e6:.1f} MB, md5 ok)")
        return
    raise SystemExit(f"kunne ikke hente {dest.name} i hel stand efter {retries} forsøg")


def slugify(text: str) -> str:
    text = text.replace("'", "").replace("\u2019", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or "kapitel"


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def pretty_duration(value: str) -> str:
    """LibriVox skriver 00:14:41 — vi viser 14:41 når timetallet er nul."""
    m = re.fullmatch(r"(\d+):(\d{2}):(\d{2})", value or "")
    if m and int(m.group(1)) == 0:
        return f"{int(m.group(2))}:{m.group(3)}"
    return value


def variant_of(filename: str) -> str | None:
    for name, (suffix, _fmt, _mime) in VARIANTS.items():
        if filename.endswith(suffix):
            return name
    return None


def base_of(filename: str) -> str:
    name = variant_of(filename)
    return filename[: -len(VARIANTS[name][0])] if name else filename.rsplit(".", 1)[0]


def parse_rss(data: bytes, item_hint: str | None) -> Book:
    root = ET.fromstring(data)
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("RSS-filen har ingen <channel>")
    title = collapse(channel.findtext("title") or "")
    description = collapse(channel.findtext("description") or channel.findtext(f"{ITUNES}summary") or "")
    link = collapse(channel.findtext("link") or "")
    image = channel.find(f"{ITUNES}image")
    cover_url = (image.get("href") if image is not None else "") or ""

    tracks: list[Track] = []
    item = item_hint or ""
    for n, node in enumerate(channel.findall("item"), start=1):
        enc = node.find("enclosure")
        url = enc.get("url") if enc is not None else ""
        if not url:
            continue
        filename = url.rsplit("/", 1)[-1]
        if not item:
            m = re.search(r"/download/([^/]+)/", url)
            item = m.group(1) if m else ""
        if not cover_url:
            img = node.find(f"{ITUNES}image")
            cover_url = (img.get("href") if img is not None else "") or ""
        tracks.append(
            Track(
                n=n,
                title=collapse(node.findtext("title") or f"Kapitel {n}"),
                duration=pretty_duration(collapse(node.findtext(f"{ITUNES}duration") or "")),
                base=base_of(filename),
            )
        )
    if not item:
        raise SystemExit("kunne ikke udlede archive.org-item fra RSS'en — angiv --item")
    return Book(item, title, description, link, cover_url, "", "", None, tracks)


def parse_item(item: str) -> Book:
    meta = fetch_json(f"https://archive.org/metadata/{item}")
    md = meta.get("metadata", {})
    title = collapse(md.get("title") or item)
    description = collapse(md.get("description") or "")
    link = f"https://archive.org/details/{item}"
    published = (md.get("publicdate") or md.get("date") or "")[:10]
    return Book(
        item=item,
        title=title,
        description=description,
        link=link,
        cover_url="",
        server=meta.get("server", ""),
        directory=meta.get("dir", ""),
        publicdate=dt.date.fromisoformat(published) if _is_date(published) else None,
        tracks=[],
    )


def _is_date(value: str) -> bool:
    try:
        dt.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def fill_from_metadata(book: Book, variant: str) -> None:
    """Berig bogen med server/dir, filstørrelser, md5 og (hvis nødvendigt) spor."""
    meta = fetch_json(f"https://archive.org/metadata/{book.item}")
    md = meta.get("metadata", {})
    book.server = meta.get("server", "") or book.server
    book.directory = meta.get("dir", "") or book.directory
    if not book.description:
        book.description = collapse(md.get("description") or "")
    if book.publicdate is None:
        published = (md.get("publicdate") or md.get("date") or "")[:10]
        if _is_date(published):
            book.publicdate = dt.date.fromisoformat(published)
    if not book.cover_url:
        # Fallback uden RSS: brug item'ets eget JPEG (fx Book_*.jpg).
        jpegs = [f["name"] for f in meta.get("files", []) if (f.get("name") or "").lower().endswith(".jpg")]
        if jpegs:
            book.cover_url = f"{source_base(book)}/{sorted(jpegs)[0]}"

    by_name = {f["name"]: f for f in meta.get("files", []) if f.get("name")}
    if not book.tracks:  # ingen RSS: udled sporene fra filerne
        wanted_format = VARIANTS[variant][1]
        seen: dict[str, Track] = {}
        for f in meta.get("files", []):
            if f.get("format") != wanted_format:
                continue
            base = base_of(f["name"])
            seen[base] = Track(n=0, title=collapse(f.get("title") or base), duration="", base=base)
        ordered = sorted(seen.values(), key=lambda t: t.base)
        for n, track in enumerate(ordered, start=1):
            track.n = n
            seconds = _seconds_of(by_name.get(track.base + VARIANTS[variant][0], {}).get("length"))
            track.duration = _mmss(seconds) if seconds else ""
        book.tracks = ordered
    for track in book.tracks:
        for variant_name, (suffix, fmt, _mime) in VARIANTS.items():
            info = by_name.get(track.base + suffix)
            if not info or info.get("format") != fmt:
                continue
            track.files[variant_name] = {
                "name": info["name"],
                "size": int(info.get("size", 0)),
                "md5": info.get("md5", ""),
            }
        if not track.duration:
            info = track.files.get(variant)
            if info:
                track.duration = _mmss(_seconds_of(by_name[info["name"]].get("length")))


def _seconds_of(value: str | None) -> float:
    try:
        return float(value) if value else 0.0
    except (TypeError, ValueError):
        return 0.0


def _mmss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def source_base(book: Book) -> str:
    """Item'ets egen host — den sti vi ved svarer (i modsætning til dn…-noden)."""
    if book.server and book.directory:
        return f"https://{book.server}{book.directory}"
    return f"https://archive.org/download/{book.item}"


def python_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def kwarg(name: str, value: str, indent: str = "        ", width: int = 72) -> list[str]:
    """`name="…"` — eller som implicit konkatenering, hvis værdien er lang."""
    if len(value) + len(name) + len(indent) + 4 <= 100:
        return [f"{indent}{name}={python_literal(value)},"]
    chunks = textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False)
    chunks = [c + " " for c in chunks[:-1]] + chunks[-1:]
    return [f"{indent}{name}=(", *[f"{indent}    {python_literal(c)}" for c in chunks], f"{indent}),"]


def registry_block(key: str, path: str, title: str, author: str, output: str, content_dir: str, logo: str, subtitle: str, source: str) -> str:
    lines = [f"    # kilde: {source}", "    Feed("]
    for name, value in (
        ("key", key),
        ("path", path),
        ("title", title),
        ("author", author),
        ("output", output),
        ("content_dir", content_dir),
        ("logo", logo),
    ):
        lines += kwarg(name, value)
        if name == "author":
            lines.append('        kind="generated",')
    if subtitle:
        lines += kwarg("subtitle", subtitle)
    lines += ["    ),", ""]
    return "\n".join(lines)


def insert_block(path: Path, end_marker: str, block: str) -> None:
    """Indsæt block lige før end_marker — matchet som en hel linje.

    Hele linjer (ikke delstrenge) er afgørende: en 8-space-markør er ellers en
    delstreng af en 12-space-markør, og så ryger blokken i den forkerte liste.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if line.rstrip("\n") == end_marker]
    if len(hits) != 1:
        raise SystemExit(
            f"{path}: forventede præcis én linje '{end_marker.strip()}' (fandt {len(hits)}) — er filen redigeret i hånden?"
        )
    lines.insert(hits[0], block if block.endswith("\n") else block + "\n")
    path.write_text("".join(lines), encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}: blok indsat")


def assert_new(key: str, dashes: str) -> None:
    for path, _start, _end in MARKERS.values():
        text = path.read_text(encoding="utf-8")
        if f'key="{key}"' in text or f"feeds/{key}/feed.xml" in text or f"feed-{dashes}" in text:
            raise SystemExit(f"{path.relative_to(ROOT)}: feedet '{key}' findes allerede — vælg en anden --book/--theme")


def self_check() -> None:
    print("== egenkontrol ==")
    for cmd in ([sys.executable, "build.py"], ["kubectl", "kustomize", "k8s/"]):
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        except FileNotFoundError:
            print(f"  {cmd[0]}: ikke installeret — springer over")
            continue
        if proc.returncode != 0:
            print(proc.stdout[-2000:])
            print(proc.stderr[-2000:], file=sys.stderr)
            raise SystemExit(f"{' '.join(cmd)} fejlede — intet er committet, men filerne er skrevet")
        note = "ok" if cmd[0] != "kubectl" else "ok (manifesterne kan rendres)"
        print(f"  {' '.join(cmd[:2])}: {note}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Importér en LibriVox-bog som higgs-feed")
    parser.add_argument("--theme", required=True, help="tema, fx tao")
    parser.add_argument("--book", help="bognavn i stien, fx lieh-tzu (default: fra titlen)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--rss", help="LibriVox RSS-URL (giver titler, varigheder og rækkefølge)")
    src.add_argument("--item", help="archive.org-item-id")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="64kb", help="lydvariant (default: 64kb)")
    parser.add_argument("--date", help="basisdato YYYY-MM-DD (default: archive.orgs publicdate)")
    parser.add_argument("--oldest-first", action="store_true", help="gør kapitel 1 ældst i stedet for nyest")
    parser.add_argument("--dry-run", action="store_true", help="vis kun planen — hent og skriv intet")
    args = parser.parse_args(argv)
    for name, value in (("theme", args.theme), ("book", args.book)):
        if value and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
            raise SystemExit(f"--{name} må kun indeholde a-z, 0-9 og bindestreg: {value!r}")

    print(f"== læser kilde ({args.rss or args.item}) ==")
    book = parse_rss(fetch(args.rss), args.item) if args.rss else parse_item(args.item)
    fill_from_metadata(book, args.variant)
    if not book.tracks:
        raise SystemExit("fandt ingen spor i kilden")

    book_slug = args.book or slugify(book.title)[:60]
    key = f"{args.theme}/{book_slug}"
    dashes = key.replace("/", "-")
    media_dir = ROOT / "media" / key
    content_dir = ROOT / "content" / key
    base_day = dt.date.fromisoformat(args.date) if args.date else (book.publicdate or dt.date.today())
    newest = dt.datetime.combine(base_day, dt.time(23, 0), tzinfo=dt.timezone.utc)
    url_base = source_base(book)
    suffix, _fmt, mime = VARIANTS[args.variant]

    print(f"== bog: {book.title}")
    print(f"   item: {book.item}  |  {len(book.tracks)} spor  |  variant: {args.variant}  |  basisdato: {base_day}")
    missing = [t for t in book.tracks if args.variant not in t.files]
    if missing:
        print(f"   advarsel: {len(missing)} spor mangler varianten '{args.variant}' — de springes over", file=sys.stderr)
    tracks = [t for t in book.tracks if args.variant in t.files]
    if not tracks:
        raise SystemExit(f"ingen spor har varianten '{args.variant}'")
    for track in tracks:
        info = track.files[args.variant]
        print(f"   {track.n:02d}. {track.title} ({track.duration or '?'}) → {info['name']} ({info['size'] / 1e6:.1f} MB)")

    if args.dry_run:
        print("\n== plan (dry-run) ==")
        print(f"   medier:   {media_dir.relative_to(ROOT)}/")
        print(f"   poster:   {content_dir.relative_to(ROOT)}/ (én pr. spor)")
        print(f"   feed:     /{key}/feed.xml  →  k8s/feeds/{key}/feed.xml")
        print("   blokke:   build.py FEEDS + k8s/kustomization.yaml + k8s/deployment.yaml (markerede blokke)")
        return 0

    assert_new(key, dashes)
    if content_dir.exists() and any(content_dir.glob("*.md")):
        raise SystemExit(f"{content_dir.relative_to(ROOT)} har allerede poster — slet dem eller vælg en anden --book")

    print("== henter medier ==")
    media_dir.mkdir(parents=True, exist_ok=True)
    for track in tracks:
        info = track.files[args.variant]
        download(f"{url_base}/{info['name']}", media_dir / info["name"], info["size"], info["md5"])

    if book.cover_url:
        cover = media_dir / "cover.jpg"
        if not cover.is_file():
            data = fetch(book.cover_url)
            if not data.startswith(b"\xff\xd8"):
                raise SystemExit(f"coveret fra {book.cover_url} er ikke et JPEG")
            cover.write_bytes(data)
            print(f"  cover.jpg: hentet ({len(data) / 1e3:.0f} kB)")
        else:
            print("  cover.jpg: findes allerede")

    print("== skriver poster ==")
    content_dir.mkdir(parents=True, exist_ok=True)
    total = len(book.tracks)
    for track in tracks:
        info = track.files[args.variant]
        offset = (total - track.n) if args.oldest_first else (track.n - 1)
        published = newest - dt.timedelta(minutes=offset)
        slug = f"{base_day.isoformat()}-{track.n:02d}-{slugify(track.title)[:60]}"
        path = content_dir / f"{slug}.md"
        summary = (
            f"Kapitel {track.n} af {total}: {track.title}"
            + (f" ({track.duration})" if track.duration else "")
            + ". Indlæst af LibriVox — indspilningen er i public domain."
        )
        body = f"Kapitel {track.n} af {total} fra {book.title} (LibriVox, public domain)."
        if track.duration:
            body += f"\n\n- Varighed: {track.duration}"
        path.write_text(
            "\n".join(
                [
                    "---",
                    f"title: {track.title}",
                    f"date: {published.isoformat().replace('+00:00', 'Z')}",
                    f"summary: {summary}",
                    f"source: {args.rss or book.link}",
                    "media:",
                    f"  - src: media/{key}/{info['name']}",
                    f"    type: {mime}",
                    "---",
                    "",
                    body,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(f"  {path.relative_to(ROOT)}")

    print("== indsætter i registry og manifester ==")
    source_note = args.rss or f"https://archive.org/details/{book.item}"
    insert_block(
        MARKERS["build"][0],
        MARKERS["build"][2],
        registry_block(
            key=key,
            path=f"/{key}/feed.xml",
            title=book.title,
            author="LibriVox",
            output=f"k8s/feeds/{key}/feed.xml",
            content_dir=f"content/{key}",
            logo=f"/media/{key}/cover.jpg",
            subtitle=book.description,
            source=source_note,
        ),
    )
    insert_block(
        MARKERS["kustomization"][0],
        MARKERS["kustomization"][2],
        "\n".join(
            [
                f"  - name: higgs-feed-{dashes}",
                "    files:",
                f"      - feeds/{key}/feed.xml",
                "",
            ]
        ),
    )
    insert_block(
        MARKERS["mounts"][0],
        MARKERS["mounts"][2],
        "\n".join(
            [
                f"            - name: feed-{dashes}",
                f"              mountPath: /usr/share/nginx/html/{key}/feed.xml",
                "              subPath: feed.xml",
                "              readOnly: true",
                "",
            ]
        ),
    )
    insert_block(
        MARKERS["volumes"][0],
        MARKERS["volumes"][2],
        "\n".join(
            [
                f"        - name: feed-{dashes}",
                "          configMap:",
                f"            name: higgs-feed-{dashes}",
                "",
            ]
        ),
    )

    self_check()
    print("\n== næste skridt ==")
    print(f"   scripts/deploy.sh --sync-media          # læg medierne på PVC'en")
    print(f"   scripts/deploy.sh --sync-media --sync-ipfs")
    print(f"   tilmeld https://higgs.gihc.online/{key}/feed.xml i din feed-læser")
    return 0


if __name__ == "__main__":
    sys.exit(main())
