# TODO — higgs

> Plan fra dialog 2026-08-31. Fase 1 = simpelt statisk Atom-feed; fase 2 = IPFS som ekstra
> distributionssti. Baggrund i [STRATEGI.md](STRATEGI.md); IPFS-dialogen i
> [87a8a829-433b-41f9-90d8-c5a659e4204e.md](87a8a829-433b-41f9-90d8-c5a659e4204e.md).

## Næste session — start her

> Kopiér denne prompt til næste session:
>
> "Læs README.md, TODO.md, AGENTS.md, STRATEGI.md og HANDOVER.md i dette
> repo, og fortsæt derfra. Følg AGENTS.md: dansk, commit lokalt med
> [codex:…]-tag hentet fra ~/.codex/config.toml (antag aldrig model-id), og
> push overlades til brugeren. Kontekst: higgs er i drift med flere feeds —
> rod-feedet på https://higgs.gihc.online/feed.xml og bøger under temaer, fx
> https://higgs.gihc.online/tao/lieh-tzu/feed.xml (genereret Atom med
> selv-hostede medier på PVC'en). Nye bøger importeres med
> scripts/import-librivox.py, der skriver i de markerede
> "importerede feeds"-blokke i build.py og k8s/ — redigér dem ikke i hånden.
> Fase 3 (flere feeds) er færdig og i drift; se HANDOVER → Git-tilstand for
> branch- og merge-status. Fase 2 (IPFS) er deployet internt: gateway i k3s,
> medier pinnet, men ipfs.higgs.gihc.online mangler stadig offentlig DNS, så
> IPFS-enclosure-linkene i feedet er døde (nginx-linket står først, så
> afspilning virker). Mål i denne session:
> <indsæt mål>."

## Session 2026-09-28 — flere feeds (tao m.fl.)

- [x] **Beslutning (URL-skema):** nye feeds ligger som stier under
      `higgs.gihc.online` (`/tao/lieh-tzu/feed.xml`) i stedet for et subdomæne
      pr. bog. Ny bog = ingen DNS-record og intet nyt cert. Begrundelse og
      alternativer (A/B/C) står i README → "Flere feeds".
- [x] **Beslutning (format, oprindeligt):** Lieh-Tzu blev først vedhæftet som
      færdig RSS-fil — se nedenfor, hvor den blev konverteret til genereret Atom
- [x] Feature-branch `feat/flere-feeds` oprettet (arbejdet ligger her; push
      overlades til brugeren)
- [x] `build.py`: registry `FEEDS` (genererede + vedhæftede feeds).
      `SITE_BASE` + `FEEDS` er nu det eneste sted, domæne og feed-URL'er
      lever; `--list` udskriver feeds som TSV til deploy-verifikation
- [x] `build.py` genererer også `k8s/nginx/default.conf` med korrekt
      Content-Type pr. feed (atom for genererede, rss for vedhæftede) —
      filen er nu gitignoreret artefakt
- [x] `content/` → `content/higgs/` for rod-feedet; **entry-id'er verificeret
      byte-identiske** med før omlægningen (ingen genlæsning for læsere)
- [x] Lieh-Tzu flyttet fra repo-roden til `feeds/tao/lieh-tzu/feed.xml`, og
      `<atom:link rel="self">` rettet til den rigtige URL. Build fejler, hvis
      self-link og registry ikke matcher (den gamle "HUSK" er nu håndhævet)
- [x] k8s: én ConfigMap pr. feed (`higgs-feed`, `higgs-feed-tao-lieh-tzu`) +
      mount på `/usr/share/nginx/html/tao/lieh-tzu/feed.xml`;
      `kubectl kustomize k8s/` verificeret lokalt (ConfigMaps, keys, mounts)
- [x] `scripts/deploy.sh`: verificerer alle feeds fra `python3 build.py
      --list` (HTTP 200 + Content-Type + titel) i stedet for én hardcoded URL
- [x] `make verify` parser alle feeds; `.gitignore` opdateret
      (`k8s/feeds/`, `k8s/nginx/default.conf`)
- [x] Docs opdateret: README ("Flere feeds", repostruktur, neutralitets-ankre,
      beslutninger), AGENTS.md (neutralitets-anker 2) og HANDOVER.md
- [x] **Deployet** (brugeren kørte `scripts/deploy.sh`): `/tao/lieh-tzu/feed.xml`
      svarer HTTP 200 + `application/rss+xml` og er byte-identisk med
      `feeds/tao/lieh-tzu/feed.xml`; rod-feedet er uændret (inkl. IPFS-enclosure)
- [x] Fejl fundet og rettet efter deploy: `curl … | grep -q` sammen med
      `set -o pipefail` gav falsk "titlen er ikke …" — grep lukker røret, så
      curl afbrydes med exit 23 midt i svaret (målt 2/10 kørsler mod live).
      Verifikationen henter nu hele svaret i én request uden pipe.
      **Vigtig viden til næste session.**
- [x] **Afspilning fejlede i AntennaPod (HTTP 500).** Årsag fundet: archive.orgs
      `www.archive.org/download/…`-URL'er (som LibriVox selv bruger i dag)
      redirecter til en `dn…`-downloadnode, der svarer 500 (og Cloudflare-fejl i
      browseren). Item'ets egen host svarede 206 på alle otte filer, så filerne
      var i behold. Fejlen kom ikke af feed-omskrivningen — originalen bruger
      samme URL'er.
- [x] **Beslutning (re-hosting):** de otte kapitler hentes ned (64 kbps, ~85 MB)
      og hostes selv på PVC'en under `media/tao/lieh-tzu/`; LibriVox' indspilninger
      er i public domain. Coveret (`cover.jpg`) følger med.
- [x] **Beslutning (Atom):** tao-feedet konverteres fra vedhæftet RSS til
      **genereret Atom** fra `content/tao/lieh-tzu/` — nu muligt, fordi vi selv
      hoster medierne, og `length` beregnes af generatoren. Apple Podcasts
      kræver fortsat RSS 2.0, hvis det bliver et krav (se README-beslutning).
- [x] **Beslutning (rækkefølge):** de kunstige LibriVox-`pubDate`-tider vendes om,
      så kapitel 1 (Editorial & Intro) er nyest. Podcast-klienter viser normalt
      nyeste øverst, og så står kapitlerne i bogens rækkefølge uden at læseren
      skal ændre sortering.
- [x] `build.py`: `src:` i front matter er nu relativ til domæneroden (matcher
      nginx' `/media`-mount), og feeds kan have `<subtitle>` (LibriVox-beskrivelsen)
- [x] `feeds/tao/lieh-tzu/feed.xml` fjernet (erstattet af de otte markdown-poster);
      `attached`-mekanikken i build.py findes fortsat til tredjeparts-XML
- [x] **Deployet** (`scripts/deploy.sh --sync-media` og derefter
      `--sync-media --sync-ipfs`): tao-feedet svarer HTTP 200 +
      `application/atom+xml`, medierne ligger på PVC'en, og alle ni filer
      (8 kapitler + cover) er pinnet i IPFS med wrap-mappe-CID'er.
      Verificeret udefra: enclosure `206 audio/mpeg`, cover
      `200 image/jpeg`
- [ ] **Afventer bruger:** fjern + genindlæs `tao/lieh-tzu` i AntennaPod (RSS →
      Atom betyder nye entry-id'er, så de gamle afsnit skal væk), og push
      branchen `feat/flere-feeds`
- [ ] **Åbent (fase 2):** IPFS-enclosure-URL'erne i feedet er døde, indtil
      DNS-blokeringen for `ipfs.higgs.gihc.online` er løst. De ligger efter
      nginx-enclosure'en pr. afsnit, så afspilning er upåvirket. Alternativ:
      gør IPFS-enclosures tilvalg (fx flag), så feedet ikke annoncerer en sti,
      der ikke svarer
- [x] **`scripts/import-librivox.py`** — formaliseret import af LibriVox-bøger:
      læser RSS eller archive.org-item, henter metadata via metadata-API'et,
      downloader fra item'ets egen host (ikke `www.archive.org/download/…`) med
      md5-verifikation, lægger medier i `media/<tema>/<bog>/`, skriver
      `content/<tema>/<bog>/<dato>-NN-<kapitel>.md` og indsætter feedet i
      registry'et + `kustomization.yaml` + `deployment.yaml`. Egenkontrol til
      sidst (`build.py` + `kubectl kustomize`). Testet end-to-end i en kopi af
      repoet: medier genbrugt via md5, cover hentet, 8 poster skrevet,
      indsættelser korrekte, egenkontrol grøn. `--dry-run`, `--variant`,
      `--date` og `--oldest-first` findes.
- [x] Markerede **`importerede feeds`-blokke** i `build.py`,
      `k8s/kustomization.yaml` og `k8s/deployment.yaml` (mounts + volumes).
      Egenkontrollen fangede undervejs at 8-space-slutmarkøren var en delstreng
      af 12-space-markøren, så blokken røg i den forkerte liste — markørerne er
      nu sektionsnavngivne og matches som hele linjer.
- [x] Lieh-Tzu-summaries: overflødige citationstegn fjernet + `source:`-linje
      tilføjet (samme form som importøren skriver). Entry-id'er og rækkefølge
      uændrede — kræver blot et nyt deploy for at slå igennem live.
- [x] **Fejl efter merge:** `make build` fejlede i et friskt checkout, fordi
      `k8s/nginx/` forsvandt, da `default.conf` blev et genereret (untracked)
      artefakt — git gemmer ikke tomme mapper. `build.py` opretter nu mappen
      selv, som den allerede gør for feed-artefakterne.
      **Lærdom: verificér i en frisk clone, ikke kun i arbejdstræet.**
- [x] **Spærring mod manglende medier:** `build.py --strict-media` fejler
      (exit 2) med listen af manglende filer, og `deploy.sh` bruger altid den
      variant — så et deploy ikke kan fjerne enclosure-links i stilhed.
      Undtagelsen er `--allow-missing-media`. `make build` uden flag er fortsat
      tilladende, så et checkout kan inspiceres; `Makefile` sender `BUILD_FLAGS`
      videre.
- [x] **`scripts/fetch-media.py` + `make fetch-media`:** henter `media/` over
      HTTPS fra det udgivne site til en ny maskine. Fil-listen kommer fra
      front matter plus feed-artwork (`logo:`), størrelsen verificeres mod
      serverens `Content-Length`, og filer der allerede passer springes over.
      Testet i et friskt clone: cover og ét kapitel hentet, md5 identisk med
      originalen, og gentagne kørsler springer over. (Fandt undervejs samme
      mappe-skal-oprettes-fejl som i build.py — rettet.)
- [ ] **Afventer beslutning:** hvilke bøger der kommer under `tao` som de
      næste, og hvilke temaer der kommer efter `tao`

## Session 2026-08-31 (aften)

- [x] Feed-titel ændret til "Higgs" (`FEED_TITLE` i build.py) — **deployet
      og verificeret live** (HTTP 200, `application/atom+xml`, titel "Higgs")
- [x] Årsag fundet: "Hej verden" øverst i AntennaPod skyldes, at begge poster
      har samme tidsstempel (`2026-08-31T00:00:00Z`); AntennaPod sorterer selv
      på pubDate og falder tilbage til appens interne DB-rækkefølge ved lige
      datoer — feed-XML'en har selv korrekt rækkefølge (monero først)
- [x] Rækkefølge styres nu eksplicit: build.py understøtter tidspunkt i
      `date` (RFC 3339), og begge poster har fået reelle tider
      (Hej verden 17:46, monero 18:05, +02:00) — **deployet og verificeret i
      AntennaPod**: "Hej verden" står nu nederst, monero øverst
- [x] Deploy-script: `scripts/deploy.sh` (tunnel + byg + apply + rollout +
      verificér med retries efter Recreate-503; `--sync-media` for medier) —
      `make deploy` kalder scriptet
- [x] Fase 2 påbegyndt (IPFS som ekstra distributionssti + backup):
  - [x] `build.py`: anden enclosure mod egen gateway — stabil wrap-mappe-CID
        via `ipfs add -Q --only-hash -w --cid-version 1` (`FEED_IPFS_GATEWAY`)
  - [x] `k8s/ipfs.yaml`: Kubo-gateway (deployment + service + PVC), ingress-rule
        for `ipfs.higgs.gihc.online` (gateway på 0.0.0.0:8080, `NoFetch`)
  - [x] `scripts/sync-ipfs.sh`: pin media/ i gateway-pod'en (samme CIDs)
  - [x] **Deployet**: gateway kører, medier pinned (CID matcher build.py),
        live feed indeholder IPFS-enclosure
  - [ ] **Blokeret (DNS)**: `ipfs.higgs.gihc.online` findes i Simplys API,
        men serveres ikke af de autoritative nameservere — aktivér i Simplys
        UI eller slet+genopret via script; derefter cert-manager + offentlig
        curl af gateway-URL'en
  - [ ] ipfs-cluster (CRDT) på VPS + Pi + laptop — redundant pinning/backup
- [x] DNS-script: rettet quoting-bug i existing-record-snippet (record_id) —
      `scripts/create-dns-record.sh ipfs` kører nu
- [x] HANDOVER + TODO-start-prompt opdateret til næste session (2026-08-31
      aften)

## Beslutninger (foreløbige)

- [x] Domæne: `higgs.gihc.online` (subdomæne; apex holdes fri)
- [x] Variant A: kun feed, ingen HTML-sider endnu
- [x] Media: PVC i starten; IPFS tilføjes senere som anden sti
- [x] Stabil URL-kontrakt: `media/<slug>/<fil>` ændres aldrig
- [x] GitHub-remote findes allerede: `git@github.com:gihc-org/higgs.git`
- [x] Medier: første episode live (TL;DR — Mastering Monero, m4a på PVC)
- [x] VPS-IP er ikke statisk: DNS-scriptet hardcoder ikke IP — den angives
      eksplicit eller udledes fra zonens A-records; recorden opdateres ved ændring
- [x] Flere feeds: sti pr. bog under `higgs.gihc.online` (fx
      `/tao/lieh-tzu/feed.xml`) — ikke ét subdomæne pr. bog
- [x] Vedhæftede feeds: færdig XML committes i `feeds/<tema>/<bog>/feed.xml` og
      kopieres til `k8s/` af build.py (genererede feeds bliver i `content/<feed>/`)

## Fase 1 — minimalt feed (nu)

- [x] `.gitignore` med `media/`
- [x] Push til GitHub (brugeren pusher selv)
- [x] Scaffold `k8s/`:
  - [x] `namespace.yaml` (namespace: higgs)
  - [x] `kustomization.yaml` med `configMapGenerator` for feed.xml (content-hash)
  - [x] `deployment.yaml` — nginx:alpine, mount af ConfigMap + nginx-override for Content-Type
  - [x] `service.yaml` — port 80 → 80
  - [x] `ingress.yaml` — host `higgs.gihc.online`, `letsencrypt-prod`
  - [x] `pvc.yaml` — `higgs-media` (5Gi, local-path) + mount + `Recreate`
- [x] `build.py`:
  - [x] Front matter: `title` (påkrævet), `date` (default fra filnavn), `summary`, `external_url`, `media`
  - [x] Stabile entry-id'er: `uuid5` af slug (filnavn)
  - [x] `updated` = max af post-datoer (RFC 3339)
  - [x] Sortering: nyeste først
  - [x] Enclosure-støtte med automatisk `length` fra lokale filer
  - [x] Én konstant for feed-base-URL (neutralitets-anker)
- [x] `Makefile`: `build`, `verify`, `deploy`, `sync-media`
- [x] `content/` med første post (kladde)
- [x] DNS-script: `scripts/create-dns-record.sh` (ingen hardcoded IP; opret/opdater/skip)
- [x] DNS: A-record for `higgs.gihc.online` oprettet
- [x] kubectl installeret lokalt (v1.37.0 i `~/.local/bin`, kustomize v5.8.1)
- [x] Deploy: SSH-tunnel → `make build` → `kubectl apply -k k8s/`
- [x] `curl https://higgs.gihc.online/feed.xml` → HTTP 200 + gyldigt LE-cert
- [x] Content-Type `application/atom+xml` (nginx-override virker)
- [x] Validering i feed-læser — testet i AntennaPod (virker)
- [x] Første medie-post: enclosure + `audio/mp4` + Range (206) verificeret
- [x] Feed-logo (PNG af logo-symmetrisk) verificeret i AntennaPod

## Fase 2 — IPFS som ekstra sti (senere)

- [x] Kubo-gateway-pod i k3s, eksponeret via ingress — **i drift**
- [x] `build.py`: beregn CID (`ipfs add`), udsend anden enclosure mod egen gateway
- [x] `scripts/sync-ipfs.sh`: pin medier i gateway-pod'en
- [ ] ipfs-cluster (CRDT-consensus) på VPS + Pi + laptop — redundant pinning
- [ ] README-noter om WebTorrent/Handshake som research (ikke bygget)

## Fase 3 — flere feeds (temaer/bøger) — i gang

- [x] Registry `FEEDS` i build.py: per-feed URL-sti, type og indholdskilde
- [x] Én ConfigMap pr. feed + mount på feedets URL-sti
- [x] Vedhæftet Lieh-Tzu-RSS på `/tao/lieh-tzu/feed.xml` — afventer deploy
- [ ] Flere bøger under `tao` (samme vedhæftede flow)
- [ ] Næste tema efter `tao`
- [ ] Evt. browsbar forside med listen af feeds (variant B — ikke besluttet)

## Ikke-mål lige nu

- Ingen CI (manuelt `kubectl apply` indtil Woodpecker er klar)
- Ingen image-build, ingen secrets, ingen ændringer i infra-repoet
- Ingen HTML-sider (variant B senere, hvis ønsket)
- Ingen IPFS før fase 2
