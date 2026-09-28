# HANDOVER — higgs (2026-09-28)

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

Fase 3 (flere feeds) er bygget og **deployet** på branch `feat/flere-feeds`
(afventer kun genindlæsning i AntennaPod og push):
`build.py` har nu registry'et `FEEDS`, og Lieh-Tzu ligger på
`https://higgs.gihc.online/tao/lieh-tzu/feed.xml`. Feedet er undervejs
konverteret fra vedhæftet RSS til **genereret Atom med selv-hostede medier**
(`content/tao/lieh-tzu/` + `media/tao/lieh-tzu/`). Rod-feedets entry-id'er er
verificeret byte-identiske efter omlægningen, så eksisterende lyttere er
upåvirkede.

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
- Fase 3 (flere feeds) ligger på branch `feat/flere-feeds` oven på `trunk` —
  ikke pushet og ikke deployet.
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

## Fase 3 — flere feeds (tao m.fl.)

Design: ét repo, mange feeds. `FEEDS` i `build.py` er registry'et — hver post
har URL-sti (`/tao/lieh-tzu/feed.xml`), titel, indholdskilde og Content-Type.
`SITE_BASE` er fortsat det eneste sted, domænet lever.

- **URL-skema (besluttet):** nye feeds er stier under `higgs.gihc.online`, ikke
  subdomæner pr. bog. En ny bog kræver dermed hverken DNS-record eller cert;
  `tao` er temaet, `lieh-tzu` bogen. Stien er abonnements-kontrakten og kan
  ikke laves om bagefter uden at læserne skal tilmelde sig igen.
- **To slags feeds:** `generated` (markdown i `content/<key>/` → Atom) og
  `attached` (færdig XML i `feeds/<key>/`, fx rettede LibriVox-RSS-filer med
  eksterne archive.org-enclosures). Vedhæftede feeds kopieres uændret til
  `k8s/feeds/<key>/feed.xml`; build fejler, hvis `<atom:link rel="self">` ikke
  matcher registry'et.
- **Lieh-Tzu (endelig form):** genereret Atom fra `content/tao/lieh-tzu/` (otte
  kapitler) med medierne på PVC'en i `media/tao/lieh-tzu/` (8 × 64 kbps mp3 +
  cover.jpg). Enclosure-URL'erne peger derfor på vores eget domæne.
  **Baggrund:** feedet var først vedhæftet RSS med LibriVox' egne
  `www.archive.org/download/…`-URL'er; de begyndte at svare HTTP 500
  (`dn…`-downloadnoden fejlede, og browseren fik Cloudflare-fejl). Originalen
  bruger samme URL'er, så fejlen kom ikke af omskrivningen. LibriVox'
  indspilninger er i public domain.
- **Rækkefølge:** LibriVox' `pubDate` fandtes ikke i originalen (de var opfundet
  af en AI-assistent). Tiderne er nu vendt om, så kapitel 1 er nyest og listen
  står i bogens rækkefølge i en klient, der viser nyeste øverst.
- **`src:` i front matter er relativ til domæneroden** (`media/<sti>`), ikke til
  feedets URL-sti — det matcher nginx' `/media`-mount mod PVC'en.
- **k8s:** én ConfigMap pr. feed (`higgs-feed`, `higgs-feed-tao-lieh-tzu`),
  monteret på feedets sti i nginx-pod'en. `k8s/nginx/default.conf` genereres nu
  af `build.py` (Content-Type pr. feed) og er gitignoreret som artefakt.
- **Verifikation:** `make verify` parser alle feeds; `scripts/deploy.sh`
  verificerer HTTP 200 + Content-Type + titel for alle feeds via
  `python3 build.py --list`.
- **Import af nye bøger:** `scripts/import-librivox.py --theme <tema> --rss
  <librivox-rss>` (eller `--item <archive.org-id>`) gør hele kæden: metadata,
  download fra item'ets egen host med md5-verifikation, medier i
  `media/<tema>/<bog>/`, poster i `content/<tema>/<bog>/` og indsættelse i
  registry'et + k8s-manifesterne. **Redigér ikke de markerede
  `importerede feeds`-blokke i hånden** — de vedligeholdes af scriptet
  (`build.py`: FEEDS; `k8s/kustomization.yaml`: configMapGenerator;
  `k8s/deployment.yaml`: volumeMounts + volumes). Kapitel 1 får nyeste dato,
  så lister står i læserækkefølge; `--oldest-first`, `--variant`, `--date`,
  `--dry-run` er flag.
- **Deployet:** `/tao/lieh-tzu/feed.xml` er live (HTTP 200,
  `application/rss+xml`) og byte-identisk med repoets fil; rod-feedet er
  uændret inkl. IPFS-enclosure.
- **Lærdom (vigtig):** `curl … | grep -q` under `set -o pipefail` giver falske
  fejl efter et vellykket deploy — `grep -q` lukker røret, når den har matchet,
  hvorefter curl afbrydes med exit 23 midt i svaret (målt 2/10 kørsler mod det
  live feed). `scripts/deploy.sh` henter derfor hele svaret i én request og
  matcher uden pipe. Samme fælde gælder alle `… | grep -q` i scripts med
  `pipefail`.
- **Deployet:** `scripts/deploy.sh --sync-media` + `--sync-media --sync-ipfs`
  er kørt. Feedet svarer HTTP 200 + `application/atom+xml`, medierne ligger på
  PVC'en, og alle ni filer er pinnet i IPFS. Verificeret udefra: enclosure
  `206 audio/mpeg`, cover `200 image/jpeg`.
- **IPFS-enclosures er døde indtil videre:** `ipfs.higgs.gihc.online` mangler
  stadig offentlig DNS (fase 2-blokeringen), så de otte IPFS-links i feedet
  svarer ikke. De står efter nginx-linket pr. afsnit, og afspilning virker.
- **Afventer:** fjern + genindlæs `tao/lieh-tzu` i AntennaPod (RSS → Atom giver
  nye entry-id'er) og push branchen `feat/flere-feeds`.

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
- kubeconfig: `~/.kube/gihc.yml` (uden for alle repos, skrevet af infra's
  ansible-playbook) peger på `127.0.0.1:6443` — kræver åben SSH-tunnel:
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
- Stabile URL'er er kontrakten; `SITE_BASE` + registry'et `FEEDS` i `build.py`
  er eneste sted, domæne og feed-stier lever.
- Flere feeds som stier under `higgs.gihc.online` (`/tao/lieh-tzu/feed.xml`),
  ikke subdomæne pr. bog — ny bog koster ingen DNS-record og intet cert.
- Vedhæftede feeds (færdig XML i `feeds/<key>/`) hvor kilden er en rettet
  LibriVox-RSS; genererede feeds hvor indholdet er eget markdown.
- Subdomæne frem for apex (apex `gihc.online` holdes fri).
- Medier på PVC (ConfigMap har 1 MiB-grænse); stabile stier er exit-strategien.
- IPFS i fase 2 som ekstra sti, ikke erstatning; gateway in-cluster med
  `NoFetch` (kun pinned indhold), CID-stabilitet via wrap-mappe.
- Kustomize (configMapGenerator + content-hash) frem for image-build.
- Tidspunkt i `date` (RFC 3339) styrer rækkefølgen i feed-læsere — ellers
  sorterer de selv ved lige datoer.

## Naturlige næste skridt

1. **Deploy fase 3** (`scripts/deploy.sh` på branch `feat/flere-feeds`) og
   verificér `/tao/lieh-tzu/feed.xml` i AntennaPod; push branchen.
2. **Løs DNS-blokeringen** for `ipfs.higgs.gihc.online` (afsnittet ovenfor) —
   kræver brugerens Simply-adgang.
3. Når gatewayen er offentlig: verificér curl + cert; gen-deploy kun hvis cert
   ikke kom.
4. Flere bøger under `tao` (samme vedhæftede flow) og næste tema.
5. ipfs-cluster (CRDT-consensus) på VPS + Pi + laptop — redundant
   pinning/backup af medierne.
6. Flere poster/episoder i samme flow (`scripts/deploy.sh --sync-media
   --sync-ipfs`).
7. README-noter om WebTorrent/Handshake som research (ikke bygget).
8. Overblik-projektet ligger uden for dette repo:
   `/home/kristian/projects/overblik/README.md` (ikke git-initialiseret
   endnu). Kan verificeres live med `kubectl get ingress -A`.

## Verifikation efter deploy (altid)

```bash
curl -sS https://higgs.gihc.online/feed.xml | head
# forvent: HTTP 200, Content-Type: application/atom+xml, gyldigt LE-cert
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' \
  https://higgs.gihc.online/tao/lieh-tzu/feed.xml
# forvent: HTTP 200 application/rss+xml (vedhæftet Lieh-Tzu-feed)
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' \
  https://ipfs.higgs.gihc.online/ipfs/bafybeig4lawleiugo5hsagvt6ubgrj7qqdkajjvthmmpr7xr4jqapvgdyu/episode.m4a
# forvent (når DNS er løst): HTTP 200 audio/mp4
```

`scripts/deploy.sh` dækker de to første automatisk (den læser feed-listen fra
`python3 build.py --list`).
