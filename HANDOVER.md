# HANDOVER — higgs (2026-08-31)

> Læs dette før alt andet i en ny session, sammen med README.md, TODO.md,
> AGENTS.md og STRATEGI.md. Dette dokument beskriver tilstanden og de
> vigtigste aftaler, så en ny session kan fortsætte uden samtalehistorikken.

## Status

Fase 1 er i drift. Et statisk Atom-feed serveres på
[https://higgs.gihc.online/feed.xml](https://higgs.gihc.online/feed.xml) fra
en enkelt nginx-pod i k3s (Hetzner VPS). Der er to poster, inkl. den første
medie-episode (m4a på PVC), og feed, medier og logo er testet i AntennaPod.

## Sådan arbejder vi (kort version — fulde regler i AGENTS.md)

- Sprog: dansk i samtale, dokumentation og commits.
- Commits lokalt med tag `[codex:deepseek-v4-flash]` — model-id hentes fra
  `~/.codex/config.toml`, aldrig antaget. **Brugeren pusher selv.**
- Rør aldrig `../infra/` (platform-repoet). higgs ejer egne manifester i `k8s/`.
- Eksterne skridt med credentials (pass, SSH, DNS-ændringer) kræver
  brugerens godkendelse.
- Opdatér TODO.md samme time noget ændres.

## Git-tilstand

- Lokal `trunk` ligger én commit foran `origin/trunk`: `fd94c60`
  ("DNS-script: ingen hardcoded IP …"). Den afventer brugerens push.
- `TODO.pdf` er untracked og med vilje ikke committet (forældes hurtigt).
- Media ligger aldrig i git (`.gitignore`); kun lokalt + på PVC.

## Deploy-opsætning

- Cluster: k3s, én node på Hetzner VPS. Offentlig IP `65.109.233.92` —
  **IP er ikke statisk**; maskinen kan slettes/genskabes (derfor er IP'en
  ikke hardcoded nogen steder).
- kubeconfig: `../infra/kubeconfig.yml` peger på `127.0.0.1:6443` — kræver
  åben SSH-tunnel:
  `ssh -N -f -L 6443:localhost:6443 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 hetzner-k3s`
  (tunnelen kan hænge — genstart ved fejl).
- Ny post/episode: fil i `media/` → front matter med `media:` →
  `make build` → `kubectl --kubeconfig ../infra/kubeconfig.yml apply -k k8s/`
  → `make sync-media` → verificér.
- Deployment bruger `Recreate` (RWO PVC). ConfigMap får content-hash via
  kustomize, så ændringer i feed.xml/logo genstarter pod'en automatisk.

## Logo

- Kilde: `logo/logo-symmetrisk.svg`. `make build` genererer `k8s/logo.svg` +
  `k8s/logo.png` (1024×1024, hvid baggrund).
- Feedets `<logo>`/`<icon>` peger på `/logo.png` — podcast-klienter
  (AntennaPod) afkoder ikke SVG.

## DNS (nylig ændring)

`scripts/create-dns-record.sh` hardcoder ikke længere IP'en:

- IP angives eksplicit som andet argument, eller udledes fra zonens A-records
  (kun hvis alle er enige om én IP — ellers fejler scriptet i stedet for at
  gætte).
- Idempotent: opretter hvis recorden mangler, opdaterer (PUT via `record_id`)
  hvis IP'en er ændret, springer over hvis den er korrekt.
- Verificeret read-only 2026-08-31: udledning giver `65.109.233.92`, record
  `higgs` har `record_id` 27138772 og ville blive sprunget over (uændret).

## Nylige beslutninger (begrundelser står i README.md)

- Vendor-neutralitet: feedet er produktet, hosting udskiftelig.
- Stabile URL'er er kontrakten; `FEED_BASE` i `build.py` er eneste sted,
  domænet lever.
- Subdomæne frem for apex (apex `gihc.online` holdes fri).
- Medier på PVC (ConfigMap har 1 MiB-grænse); stabile stier er
  exit-strategien.
- IPFS i fase 2 som ekstra distributionssti, ikke erstatning — se
  `87a8a829-433b-41f9-90d8-c5a659e4204e.md`.
- Kustomize (configMapGenerator + content-hash) frem for image-build.

## Naturlige næste skridt

- Brugeren skal pushe `fd94c60` (og evt. denne fil + TODO-opdatering).
- Flere poster/episoder i samme flow (se deploy-opsætning ovenfor).
- Fase 2: IPFS som ekstra sti (TODO.md har listen).
- Overblik-projektet ligger uden for dette repo:
  `/home/kristian/projects/overblik/README.md` (opslagsværk for hvor
  projekter kører; ikke git-initialiseret endnu). Kan verificeres live med
  `kubectl get ingress -A` når tunnel er åben.
- TODO.md har en tom `- [ ] Verificér:`-linje — fjern ved næste
  TODO-opdatering.

## Verifikation efter deploy (altid)

```bash
curl -sS https://higgs.gihc.online/feed.xml | head
# forvent: HTTP 200, Content-Type: application/atom+xml, gyldigt LE-cert
```
