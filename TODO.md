# TODO — higgs

> Plan fra dialog 2026-08-31. Fase 1 = simpelt statisk Atom-feed; fase 2 = IPFS som ekstra
> distributionssti. Baggrund i [STRATEGI.md](STRATEGI.md); IPFS-dialogen i
> [87a8a829-433b-41f9-90d8-c5a659e4204e.md](87a8a829-433b-41f9-90d8-c5a659e4204e.md).

## Beslutninger (foreløbige)

- [x] Domæne: `higgs.gihc.online` (subdomæne; apex holdes fri)
- [x] Variant A: kun feed, ingen HTML-sider endnu
- [x] Media: PVC i starten; IPFS tilføjes senere som anden sti
- [x] Stabil URL-kontrakt: `media/<slug>/<fil>` ændres aldrig
- [x] GitHub-remote findes allerede: `git@github.com:gihc-org/higgs.git`
- [ ] Medier nu eller tekst-only? (antaget: tekst-only i første omgang)

## Fase 1 — minimalt feed (nu)

- [x] `.gitignore` med `media/`
- [ ] Push til GitHub (brugeren pusher selv)
- [x] Scaffold `k8s/`:
  - [x] `namespace.yaml` (namespace: higgs)
  - [x] `kustomization.yaml` med `configMapGenerator` for feed.xml (content-hash)
  - [x] `deployment.yaml` — nginx:alpine, mount af ConfigMap + nginx-override for Content-Type
  - [x] `service.yaml` — port 80 → 80
  - [x] `ingress.yaml` — host `higgs.gihc.online`, `letsencrypt-prod`
  - [ ] `pvc.yaml` — `higgs-media` (udskudt, da vi starter tekst-only)
- [x] `build.py`:
  - [x] Front matter: `title` (påkrævet), `date` (default fra filnavn), `summary`, `external_url`, `media`
  - [x] Stabile entry-id'er: `uuid5` af slug (filnavn)
  - [x] `updated` = max af post-datoer (RFC 3339)
  - [x] Sortering: nyeste først
  - [x] Enclosure-støtte med automatisk `length` fra lokale filer
  - [x] Én konstant for feed-base-URL (neutralitets-anker)
- [x] `Makefile`: `build`, `verify`, `deploy`, `sync-media`
- [x] `content/` med første post (kladde)
- [x] DNS-script: `scripts/create-dns-record.sh` (klar til kørsel)
- [x] DNS: A-record for `higgs.gihc.online` oprettet
- [x] kubectl installeret lokalt (v1.37.0 i `~/.local/bin`, kustomize v5.8.1)
- [x] Deploy: SSH-tunnel → `make build` → `kubectl apply -k k8s/`
- [ ] Verificér:
- [x] `curl https://higgs.gihc.online/feed.xml` → HTTP 200 + gyldigt LE-cert
- [x] Content-Type `application/atom+xml` (nginx-override virker)
- [x] Validering i feed-læser — testet i AntennaPod (virker)

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
