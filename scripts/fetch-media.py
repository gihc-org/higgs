#!/usr/bin/env python3
"""Hent medierne til en ny maskine (media/ er ikke i git).

Medierne findes kun tre steder: på den maskine de blev lagt ind fra, på PVC'en
bag nginx og som pin i IPFS-gatewayen. Efter et friskt `git clone` er `media/`
tomt, og `./scripts/deploy.sh` afbryder derfor med vilje. Dette script henter
den manglende halvdel over HTTPS fra det udgivne site — ingen kubeconfig, ingen
SSH og ingen credentials.

Filen listen kommer fra repoet selv (front matter i `content/`), og hver fil
verificeres mod serverens Content-Length, så en afbrudt hentning ikke gemmes.
Eksisterende filer med rigtig størrelse springes over, så scriptet kan køres
igen efter en afbrydelse.

Brug:
    scripts/fetch-media.py                 # hent alt der mangler
    scripts/fetch-media.py --only liehtzu  # kun filer hvis sti matcher
    scripts/fetch-media.py --dry-run       # vis hvad der ville blive hentet

Bagefter: `make verify BUILD_FLAGS=--strict-media` (skal være grøn) og derefter
et normalt `scripts/deploy.sh`.

Alternativ med klynge-adgang (samme kopi som nginx serverer):
    kubectl -n higgs cp "$(kubectl -n higgs get pod -l app=higgs -o jsonpath='{.items[0].metadata.name}')":/usr/share/nginx/html/media/ media/
"""

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build  # noqa: E402  (kræver stien ovenfor)

USER_AGENT = "higgs-fetch-media/1.0 (+https://higgs.gihc.online)"


def content_length(url: str) -> int | None:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            value = resp.headers.get("Content-Length")
            return int(value) if value else None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def download(url: str, dest: Path, expected: int | None) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with urllib.request.urlopen(req, timeout=600) as resp, tmp.open("wb") as fh:
        while chunk := resp.read(1 << 16):
            fh.write(chunk)
            written += len(chunk)
    if expected is not None and written != expected:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"{dest}: fik {written} bytes, serveren oplyste {expected} — prøv igen")
    tmp.replace(dest)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hent medierne over HTTPS fra det udgivne site")
    parser.add_argument("--base", default=build.SITE_BASE, help=f"site-base (default: {build.SITE_BASE})")
    parser.add_argument("--only", help="hent kun stier der indeholder denne tekst")
    parser.add_argument("--dry-run", action="store_true", help="vis kun planen")
    args = parser.parse_args(argv)

    wanted = build.expected_media()
    if args.only:
        wanted = [src for src in wanted if args.only in src]
    if not wanted:
        print("ingen mediefiler i content/ (eller intet matcher --only)")
        return 0

    print(f"== {len(wanted)} mediefil(er) fra {args.base} ==")
    fetched = skipped = failed = 0
    for src in wanted:
        dest = ROOT / src
        url = f"{args.base.rstrip('/')}/{src}"
        if args.dry_run:
            state = "findes" if dest.is_file() else "mangler"
            print(f"  [{state}] {src}")
            continue
        if dest.is_file():
            remote = content_length(url)
            if remote is None or dest.stat().st_size == remote:
                print(f"  {src}: findes allerede ({dest.stat().st_size} bytes)")
                skipped += 1
                continue
            print(f"  {src}: lokal fil afviger fra serveren — henter igen")
        remote = content_length(url)
        if remote is None:
            print(f"  FEJL: kunne ikke få størrelse for {url}", file=sys.stderr)
            failed += 1
            continue
        try:
            written = download(url, dest, remote)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"  FEJL: {src}: {e}", file=sys.stderr)
            failed += 1
            continue
        print(f"  {src}: hentet ({written / 1e6:.1f} MB)")
        fetched += 1

    if args.dry_run:
        return 0
    print(f"\n== færdig: {fetched} hentet, {skipped} fandtes, {failed} fejlede ==")
    if failed:
        return 1
    print("Næste skridt: make verify BUILD_FLAGS=--strict-media  (skal være grøn)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
