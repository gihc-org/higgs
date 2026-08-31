# higgs

Et helt simpelt statisk Atom-feed, live på
[https://higgs.gihc.online/feed.xml](https://higgs.gihc.online/feed.xml).

Status: **fase 1 i drift.** Feedet er deployet på k3s, udgiver to poster —
inkl. den første medie-episode (m4a på PVC) — og feed, medier og logo er
testet i en rigtig feed-læser (AntennaPod).

## Hvorfor findes higgs?

Projektet voksede ud af to ønsker, der hænger sammen:

1. **Et minimalt feed.** Ingen database, ingen backend, ingen CI, ingen
   secrets. Indholdet er markdown-filer, og produktet er én XML-fil.
2. **Vendor-neutralitet.** Feedet skal ikke være én udbyders beslutning fra at
   forsvinde. Hverken et CDN, en feed-hostingtjeneste eller en protokol-udbyder
   skal være en nødvendig del af løsningen.

Kerneholdningen: **feedet er produktet — hosting er udskiftelig.** Hvis
serveren forsvinder i morgen, kan hele feedet genskabes fra dette repo og
deployes et andet sted uden, at læsere opdager noget.

## Sådan hænger det sammen

```
content/*.md  →  build.py  →  k8s/feed.xml  →  ConfigMap (kustomize)
                                                          ↓
                          https://higgs.gihc.online/feed.xml  ←  Ingress  ←  nginx
```

1. **Markdown-poster** i `content/` er kilden. Filnavnet bærer datoen og er
   samtidig slug'en og stabilitetsnøglen for postens id.
2. **build.py** genererer `feed.xml`:
   - stabile entry-id'er via `uuid5` af slug'en — gamle poster bliver aldrig
     genmarkeret som ulæste, så længe filnavnet ikke ændres;
   - `updated` = max af post-datoerne (RFC 3339) — intet manuelt bump;
   - sortering nyeste først;
   - markdown → HTML med `python3-markdown` (eksekverer ikke kode);
   - enclosure-støtte med automatisk `length` fra de lokale medie-filer.
3. **Kustomize** lægger `feed.xml` + logo-filerne i en ConfigMap via
   `configMapGenerator`. Hver gang en fil ændrer sig, får ConfigMap'en et nyt
   content-hash i navnet → deployment'et ændrer sig → atomisk rolling update.
   Ingen image-build, ingen push til registry.
4. **nginx** serverer filen statisk. En lille conf-override i ConfigMap'en
   sikrer `Content-Type: application/atom+xml` (nginx sender ellers
   `text/xml`). ETag/Last-Modified og HTTP Range kommer automatisk.
5. **Ingress + cert-manager** (letsencrypt-prod) klarer HTTPS, og ingress-nginx
   leverer globale security headers (HSTS, nosniff, frame-options m.fl.).

Platformen er k3s på en Hetzner-VPS med infra i `../infra/`-repoet. higgs
ejer sine egne k8s-manifester og kræver ingen ændringer i infra-repoet.

## Neutralitets-ankrene

Tre principper blev lagt ind fra dag ét, fordi de er billige nu og svære at
lægge ind senere:

1. **Stabile URL'er er kontrakten.** Enclosure-URL'er er det eneste, læsere
   husker. Stien `media/<slug>/<fil>` ændres aldrig — uanset om det, der står
   bag, er en PVC, en IPFS-gateway eller en anden server.
2. **Én konstant for feed-URL'en.** `FEED_BASE` i [build.py](build.py) er det
   eneste sted, domænet lever. Et domæne-/host-skift er én linje + en
   ingress-ændring.
3. **Git er sandheden, serveren er en kopi.** `feed.xml` kan altid genskabes
   med `make build`. Serveren er et udstillingsvindue, ikke en database.

Sammen betyder de, at vi kan skifte hosting, domæne eller distributionsform
senere uden at bryde noget for læsere.

## Repostruktur

```
higgs/
├── content/                  # markdown-poster — kilden til feedet
│   └── 2026-08-31-foerste-post.md
├── logo/                     # logo-arbejde: logo-symmetrisk.svg er kilden
├── scripts/
│   └── create-dns-record.sh  # A-record hos Simply.com (idempotent)
├── build.py                  # generatoren: content/ → k8s/feed.xml
├── Makefile                  # build / verify / deploy / sync-media
├── k8s/                      # manifests + genererede artefakter
│   ├── kustomization.yaml    # configMapGenerator: feed + logo + nginx-override
│   ├── deployment.yaml       # nginx:alpine, mount af ConfigMap (feed + logo)
│   ├── service.yaml
│   ├── ingress.yaml          # higgs.gihc.online, letsencrypt-prod
│   ├── pvc.yaml              # higgs-media (5Gi, local-path) — medier
│   ├── logo.svg              # genereret kopi af logo-symmetrisk.svg
│   ├── logo.png              # genereret 1024×1024 PNG (feed-artwork)
│   └── nginx/default.conf    # Content-Type-override for feed.xml
├── AGENTS.md                 # arbejdsregler for AI-agenter
├── STRATEGI.md               # den oprindelige strategi
├── TODO.md                   # status og tjekliste
└── README.md
```

`media/`, `k8s/feed.xml`, `k8s/logo.svg` og `k8s/logo.png` er gitignoreret —
det første fordi binære medier ikke hører i git, de øvrige fordi de er
genererede artefakter (genskabes af `make build`).

Feedets `<logo>`/`<icon>` peger på `https://higgs.gihc.online/logo.png` — en
1024×1024 PNG (hvid baggrund) af den symmetriske tre-lags-udgave af den
håndtegnede trekivist. PNG bruges, fordi podcast-klienter (fx AntennaPod)
ikke kan afkode SVG som artwork; selve SVG'en serveres også som
`https://higgs.gihc.online/logo.svg` til browsere. Begge er små nok til at bo
i ConfigMap'en sammen med feed.xml.

## Daglig brug

### Krav

- Python 3 + `python3-markdown` (generatoren)
- ImageMagick (`convert` — genererer `k8s/logo.png` fra SVG'en)
- `kubectl` + en SSH-tunnel til k3s (kun til deploy)

### Tilføj en post

Opret `content/YYYY-MM-DD-slug.md`:

```markdown
---
title: Min nye post
summary: En kort beskrivelse
---

Brødteksten. **Markdown** bliver til HTML i feedet.
```

Med medier tilføjes en `media:`-liste:

```markdown
---
title: Post med lyd
media:
  - src: media/2026-09-01-min-post/episode.mp3
    type: audio/mpeg
---
```

Generatoren beregner filstørrelsen og udsender
`<link rel="enclosure" …>` med korrekt type, length og stabil href.

### Byg og verificér

```bash
make build    # content/ → k8s/feed.xml + logo.svg + logo.png
make verify   # tjekker feed.xml (XML) og logo.png (PNG)
```

### Deploy

Kræver en SSH-tunnel til k3s og `kubectl`:

```bash
ssh -N -f -L 6443:localhost:6443 -o ServerAliveInterval=30 hetzner-k3s
make deploy   # kører kubectl --kubeconfig ../infra/kubeconfig.yml apply -k k8s/
```

Verificér bagefter:

```bash
curl -sS https://higgs.gihc.online/feed.xml | head
```

### DNS (kun ved nye subdomæner)

```bash
scripts/create-dns-record.sh [navn]   # default: higgs
```

Kræver `pass simply/account` og `pass simply/api-key`. Scriptet er idempotent
og springer over, hvis recorden allerede findes.

## Beslutninger og begrundelser

- **Subdomæne frem for apex.** `higgs.gihc.online` holder apex `gihc.online`
  frit, og et evt. host-skift er én A-record. (Ved apex kan man ikke bruge
  CNAME og ville binde hele domæneroden til projektet.)
- **Variant A — kun feed, ingen HTML-sider.** Det mindste der virker. Hvis der
  senere er brug for browsbare sider, er det en lille udvidelse af generatoren.
- **Medier på PVC (i drift).** ConfigMap har en 1 MiB-grænse, så binære medier
  kan aldrig bo der. `higgs-media`-PVC'en er monteret i nginx-poden på
  `/usr/share/nginx/html/media`, og `make sync-media` uploader fra lokalt
  `media/`. Deployment'et bruger `Recreate`, fordi PVC'en er ReadWriteOnce.
  Stabile stier er exit-strategien.
- **Logo: SVG som kilde, PNG til feedet.** `logo/logo-symmetrisk.svg` er
  kilden; `make build` genererer både SVG- og PNG-kopier til ConfigMap'en.
  Feedet bruger PNG, fordi podcast-klienter ikke afkoder SVG.
- **IPFS i fase 2 — som ekstra sti, ikke erstatning.** Hovedkanalen forbliver
  plain HTTPS fra nginx; IPFS bliver en anden enclosure mod egen gateway, så
  intet afhænger af, at IPFS virker. Se dialog-notatet
  [87a8a829-433b-41f9-90d8-c5a659e4204e.md](87a8a829-433b-41f9-90d8-c5a659e4204e.md).

## Næste skridt

- Første medie-episode er live; tilføj flere poster/episoder i samme flow
  (fil i `media/` → front matter med `media:` → `make build` + deploy +
  `make sync-media`).
- Medie-backup-strategi: lige nu findes hver fil kun lokalt og på serverens
  PVC.
- Fase 2: Kubo-gateway-pod, CID-beregning i build.py, ipfs-cluster (CRDT) på
  VPS + Pi + laptop. WebTorrent/Handshake forbliver research indtil videre.
- Følg med i [TODO.md](TODO.md).

## Licens

[AGPL-3.0](LICENSE)
