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
> push overlades til brugeren. Kontekst: higgs fase 1 er i drift — statisk
> Atom-feed på https://higgs.gihc.online/feed.xml med to poster inkl. første
> medie-episode (m4a på PVC). Seneste commit (tidsstempler i front matter +
> feed-titel "Higgs") afventer brugerens push + deploy. Mål i denne session:
> <indsæt mål>."

## Session 2026-08-31 (aften)

- [x] Feed-titel ændret til "Higgs" (`FEED_TITLE` i build.py) — lokalt bygget
      og verificeret; **afventer deploy** (kræver tunnel + godkendelse)
- [x] Årsag fundet: "Hej verden" øverst i AntennaPod skyldes, at begge poster
      har samme tidsstempel (`2026-08-31T00:00:00Z`); AntennaPod sorterer selv
      på pubDate og falder tilbage til appens interne DB-rækkefølge ved lige
      datoer — feed-XML'en har selv korrekt rækkefølge (monero først)
- [x] Rækkefølge styres nu eksplicit: build.py understøtter tidspunkt i
      `date` (RFC 3339), og begge poster har fået reelle tider
      (Hej verden 17:46, monero 18:05, +02:00) — **afventer deploy**
- [x] Deploy-script: `scripts/deploy.sh` (tunnel + byg + apply + rollout +
      verificér; `--sync-media` for medier) — `make deploy` kalder scriptet

## Beslutninger (foreløbige)

- [x] Domæne: `higgs.gihc.online` (subdomæne; apex holdes fri)
- [x] Variant A: kun feed, ingen HTML-sider endnu
- [x] Media: PVC i starten; IPFS tilføjes senere som anden sti
- [x] Stabil URL-kontrakt: `media/<slug>/<fil>` ændres aldrig
- [x] GitHub-remote findes allerede: `git@github.com:gihc-org/higgs.git`
- [x] Medier: første episode live (TL;DR — Mastering Monero, m4a på PVC)
- [x] VPS-IP er ikke statisk: DNS-scriptet hardcoder ikke IP — den angives
      eksplicit eller udledes fra zonens A-records; recorden opdateres ved ændring

## Fase 1 — minimalt feed (nu)

- [x] `.gitignore` med `media/`
- [ ] Push til GitHub (brugeren pusher selv)
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

- [ ] Kubo-gateway-pod i k3s, eksponeret via ingress
- [ ] `build.py`: beregn CID (`ipfs add`), udsend anden enclosure mod egen gateway
- [ ] ipfs-cluster (CRDT-consensus) på VPS + Pi + laptop — redundant pinning
- [ ] README-noter om WebTorrent/Handshake som research (ikke bygget)

## Ikke-mål lige nu

- Ingen CI (manuelt `kubectl apply` indtil Woodpecker er klar)
- Ingen image-build, ingen secrets, ingen ændringer i infra-repoet
- Ingen HTML-sider (variant B senere, hvis ønsket)
- Ingen IPFS før fase 2
