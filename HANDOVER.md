# HANDOVER — higgs (2026-08-31, aften)

> Læs dette før alt andet i en ny session, sammen med README.md, TODO.md,
> AGENTS.md og STRATEGI.md. Dette dokument beskriver tilstanden og de
> vigtigste aftaler, så en ny session kan fortsætte uden samtalehistorikken.

## Status

Fase 1 er i drift: statisk Atom-feed på
[https://higgs.gihc.online/feed.xml](https://higgs.gihc.online/feed.xml) med
to poster (titel "Higgs", tidsstemplede `date`-felter), verificeret i
AntennaPod. Fase 2 (IPFS som ekstra distributionssti) er bygget og deployet
**internt**: Kubo-gateway-pod kører i k3s, medierne er pinned, og det
deployede feed indeholder IPFS-enclosure'en.

**Åben blokering:** `ipfs.higgs.gihc.online` er ikke offentligt nåelig endnu —
recorden findes i Simplys API, men serveres ikke af de autoritative
nameservere (se DNS-afsnittet nedenfor).

## Sådan arbejder vi (kort version — fulde regler i AGENTS.md)

- Sprog: dansk i samtale, dokumentation og commits.
- Commits lokalt med tag `[codex:deepseek-v4-flash]` — model-id hentes fra
  `~/.codex/config.toml`, aldrig antaget. **Brugeren pusher selv.**
- Rør aldrig `../infra/` (platform-repoet). higgs ejer egne manifester i `k8s/`.
- Eksterne skridt med credentials (pass, SSH, DNS-ændringer) kræver
  brugerens godkendelse.
- Opdatér TODO.md samme time noget ændres.

## Git-tilstand

- Fase 1-commits (`4d15a33`, `2bf61d9`) er pushet. Siden da ligger
  `cff57ca` → `154c44a` (fase 2 + alle rettelser) lokalt og afventer
  brugerens push.
- `TODO.pdf` er untracked og med vilje ikke committet (forældes hurtigt).
- Media ligger aldrig i git (`.gitignore`); kun lokalt + på PVC.

## Fase 2 — IPFS (nuværende arbejde)

Design: IPFS er en **ekstra** distributionssti, aldrig erstatning — hovedkanalen
forbliver nginx over HTTPS. Se dialog-notatet
[87a8a829-433b-41f9-90d8-c5a659e4204e.md](87a8a829-433b-41f9-90d8-c5a659e4204e.md).

- `build.py`: `FEED_IPFS_GATEWAY = "https://ipfs.higgs.gihc.online"` — eneste
  sted gateway-host lever. For hvert medie udsendes en anden enclosure med en
  stabil wrap-mappe-CID (`ipfs add -Q --only-hash -w --cid-version 1 <fil>`).
  Fejler/mangler `ipfs`, springes IPFS-enclosure over — feedet afhænger ikke af
  IPFS.
- `k8s/ipfs.yaml`: Kubo v0.42.0 (deployment + service + PVC `higgs-ipfs`),
  gateway på `0.0.0.0:8080`, `NoFetch true`, TCP probes, `Recreate`.
  **Vigtig viden:** i Kubo 0.42 hedder config-nøglen `Addresses.Gateway` —
  `Gateway.Addresses` er forældet og ignoreres (kostede flere iterationer).
- `k8s/ingress.yaml`: regel + TLS-secret `higgs-ipfs-tls` for
  `ipfs.higgs.gihc.online` (letsencrypt-prod). Cert afventer DNS.
- `scripts/sync-ipfs.sh`: venter på rollout, bekræfter Ready-pod, kopierer
  `media/` ind, pinner hver fil med `ipfs add -w` (samme CIDs som build.py),
  rydder op. **Brug altid `-n higgs` + pod-navn uden præfiks** — `kubectl
  exec` accepterer ikke `namespace/pod`.
- Verificeret: `episode.m4a` pinned recursive; dir-CID
  `bafybeig4lawleiugo5hsagvt6ubgrj7qqdkajjvthmmpr7xr4jqapvgdyu` matcher
  build.py; live feed indeholder enclosure-URL'en.

## DNS — åben blokering (løses først i næste session)

- `scripts/create-dns-record.sh ipfs` melder "peger allerede på
  65.109.233.92" (recorden findes i API'et og springes over), **men**
  `dig @ns1.simply.com +short ipfs.higgs.gihc.online A` er tom, mens
  `higgs` giver `65.109.233.92`. Recorden er altså ikke udgivet i zonen —
  sandsynligvis kladde/deaktiveret i UI'et eller i en anden DNS-konfiguration.
- Næste skridt: kig i Simplys web-UI for `gihc.online` → aktivér recorden,
  eller slet den og kør `scripts/create-dns-record.sh ipfs` igen (POST udgiver
  normalt med det samme). Derefter bekræft:
  `dig @ns1.simply.com +short ipfs.higgs.gihc.online A` → `65.109.233.92`.
- Når DNS svarer, fuldfører cert-manager letsencrypt-challenget af sig selv
  (tjek evt. `kubectl -n higgs get certificate`). Verificér så:
  `curl https://ipfs.higgs.gihc.online/ipfs/bafybeig4lawleiugo5hsagvt6ubgrj7qqdkajjvthmmpr7xr4jqapvgdyu/episode.m4a`
  (forvent HTTP 200, `audio/mp4`, ~4,1 MB).

## Deploy-opsætning

- Cluster: k3s, én node på Hetzner VPS. Offentlig IP `65.109.233.92` —
  **IP er ikke statisk**; maskinen kan slettes/genskabes (derfor er IP'en
  ikke hardcoded nogen steder).
- kubeconfig: `../infra/kubeconfig.yml` peger på `127.0.0.1:6443` — kræver
  åben SSH-tunnel:
  `ssh -N -f -L 6443:localhost:6443 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 hetzner-k3s`
  (tunnelen kan hænge — genstart ved fejl).
- Alt-i-ét: `scripts/deploy.sh [--sync-media] [--sync-ipfs]` (tunnel + byg +
  apply + rollout på BÅDE `higgs` og `ipfs-gateway` + verificér med retries —
  kortvarig 503 lige efter Recreate er normalt). `make deploy` kalder scriptet.
- Deployment bruger `Recreate` (RWO PVC). ConfigMap får content-hash via
  kustomize; `k8s/logo.png` genereres med `-strip`, så hash'en er deterministisk
  (ingen pod-genstart ved uændret indhold).

## Logo

- Kilde: `logo/logo-symmetrisk.svg`. `make build` genererer `k8s/logo.svg` +
  `k8s/logo.png` (1024×1024, hvid baggrund, `-strip`).
- Feedets `<logo>`/`<icon>` peger på `/logo.png` — podcast-klienter
  (AntennaPod) afkoder ikke SVG.

## Nylige beslutninger (begrundelser står i README.md)

- Vendor-neutralitet: feedet er produktet, hosting udskiftelig.
- Stabile URL'er er kontrakten; `FEED_BASE` i `build.py` er eneste sted,
  domænet lever.
- Subdomæne frem for apex (apex `gihc.online` holdes fri).
- Medier på PVC (ConfigMap har 1 MiB-grænse); stabile stier er exit-strategien.
- IPFS i fase 2 som ekstra sti, ikke erstatning; gateway in-cluster med
  `NoFetch` (kun pinned indhold), CID-stabilitet via wrap-mappe.
- Kustomize (configMapGenerator + content-hash) frem for image-build.
- Tidspunkt i `date` (RFC 3339) styrer rækkefølgen i feed-læsere — ellers
  sorterer de selv ved lige datoer.

## Naturlige næste skridt

1. **Løs DNS-blokeringen** for `ipfs.higgs.gihc.online` (afsnittet ovenfor) —
   kræver brugerens Simply-adgang.
2. Når gatewayen er offentlig: verificér curl + cert; gen-deploy kun hvis cert
   ikke kom.
3. ipfs-cluster (CRDT-consensus) på VPS + Pi + laptop — redundant
   pinning/backup af medierne.
4. Flere poster/episoder i samme flow (`scripts/deploy.sh --sync-media
   --sync-ipfs`).
5. README-noter om WebTorrent/Handshake som research (ikke bygget).
6. Overblik-projektet ligger uden for dette repo:
   `/home/kristian/projects/overblik/README.md` (ikke git-initialiseret
   endnu). Kan verificeres live med `kubectl get ingress -A`.

## Verifikation efter deploy (altid)

```bash
curl -sS https://higgs.gihc.online/feed.xml | head
# forvent: HTTP 200, Content-Type: application/atom+xml, gyldigt LE-cert
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' \
  https://ipfs.higgs.gihc.online/ipfs/bafybeig4lawleiugo5hsagvt6ubgrj7qqdkajjvthmmpr7xr4jqapvgdyu/episode.m4a
# forvent (når DNS er løst): HTTP 200 audio/mp4
```
