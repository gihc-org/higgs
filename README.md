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
     Medier får to `<link rel="enclosure">`: én fra nginx og — hvis `ipfs` er
     installeret — én mod egen IPFS-gateway (`FEED_IPFS_GATEWAY`).
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

### Hvad er Kustomize?

Kustomize er Kubernetes' indbyggede værktøj til at samle og tilpasse
YAML-manifests — uden skabeloner eller et separat sprog. Man skriver
almindelig YAML, og `kustomization.yaml` beskriver, hvordan filerne skal
sættes sammen. `kubectl apply -k k8s/` (flaget `-k`) kører kustomize
automatisk.

I higgs bruger vi to af dets egenskaber:

- `namespace: higgs` sættes ét sted og tilføjes til alle ressourcer.
- `configMapGenerator` bygger ConfigMap'en af `feed.xml`, `logo.svg`,
  `logo.png` og `nginx/default.conf` og giver den et content-hash i navnet
  (fx `higgs-feed-mtg2mkfg6b`). Ændrer en fil sig, får ConfigMap'en nyt navn →
  deployment'et peger på det nye navn → pod'en genstarter atomisk. Det er
  derfor, en ny post kun kræver `make build` + `kubectl apply -k k8s/`.

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
│   ├── deploy.sh             # tunnel + byg + apply + verificér (--sync-media/--sync-ipfs)
│   ├── sync-ipfs.sh          # pin media/ i gateway-pod'en (wrap-mappe-CIDs)
│   └── create-dns-record.sh  # A-record hos Simply.com — IP som arg eller udledt fra zonen
├── build.py                  # generatoren: content/ → k8s/feed.xml
├── Makefile                  # build / verify / deploy / sync-media
├── k8s/                      # manifests + genererede artefakter
│   ├── kustomization.yaml    # configMapGenerator: feed + logo + nginx-override
│   ├── deployment.yaml       # nginx:alpine, mount af ConfigMap (feed + logo)
│   ├── service.yaml
│   ├── ingress.yaml          # higgs.gihc.online, letsencrypt-prod
│   ├── pvc.yaml              # higgs-media (5Gi, local-path) — medier
│   ├── ipfs.yaml             # fase 2: Kubo-gateway (deployment + service + PVC)
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

`date` er valgfri og kan indeholde et tidspunkt (RFC 3339, fx
`2026-08-31T18:05:00+02:00`). Uden `date` bruges filnavnets dato kl. 00:00Z.
Tidspunktet styrer `published`/`updated` og sorteringen (nyeste først) — så
flere poster samme dag får en entydig rækkefølge i feed-læsere.

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

`scripts/deploy.sh` (eller `make deploy`) klarer hele flowet i ét kald: åbner
SSH-tunnelen hvis den ikke kører, bygger, deployer, venter på rollout og
verificerer HTTP 200 + `application/atom+xml` + titlen "Higgs".
Verifikationen genprøver automatisk i op til ~30 sekunder: lige efter en
`Recreate`-rollout kan ingressen kortvarigt svare 503, indtil den nye pod er
registreret som endpoint.

```bash
scripts/deploy.sh
scripts/deploy.sh --sync-media   # uploader også lokalt media/ til PVC
scripts/deploy.sh --sync-ipfs    # pinner også medierne i IPFS-gatewayen
```

Har du ændret medier, skal du bruge `--sync-media` (eller køre
`make sync-media` bagefter); skal IPFS-enclosure-URL'erne virke, kør
`--sync-ipfs` (eller `scripts/sync-ipfs.sh` bagefter). Manuelt svarer flowet til:

```bash
ssh -N -f -L 6443:localhost:6443 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 hetzner-k3s
kubectl --kubeconfig ../infra/kubeconfig.yml apply -k k8s/
```

### DNS (kun ved nye subdomæner)

```bash
scripts/create-dns-record.sh [navn]   # default: higgs
```

Kræver `pass simply/account` og `pass simply/api-key`. Scriptet er idempotent
og springer over, hvis recorden allerede har den rigtige IP.

IP'en er **ikke hardcoded**. Angiv den eksplicit som andet argument
(`scripts/create-dns-record.sh higgs 1.2.3.4`) — eller lad scriptet udlede
den fra zonens A-records. Udledning bruges kun, hvis alle A-records er enige
om én IP; ellers fejler scriptet med en besked i stedet for at gætte. Da alle
subdomæner peger på samme VPS, følger `higgs` med, når IP'en er opdateret
andre steder i zonen. Er IP'en ændret, opdateres recorden (PUT i stedet for
at springe over).

## Beslutninger og begrundelser

- **Subdomæne frem for apex.** `higgs.gihc.online` holder apex `gihc.online`
  frit, og et evt. host-skift er én A-record. (Ved apex kan man ikke bruge
  CNAME og ville binde hele domæneroden til projektet.) DNS-scriptet
  hardcoder ikke IP'en: efter et maskin-skift på VPS'en angiver man den nye
  IP eksplicit, eller scriptet udleder den fra zonens A-records.
- **Variant A — kun feed, ingen HTML-sider.** Det mindste der virker. Hvis der
  senere er brug for browsbare sider, er det en lille udvidelse af generatoren.
- **Tidspunkt i `date` styrer rækkefølgen i læserne.** Feed-læsere (fx
  AntennaPod) sorterer selv på `published`/`updated` og garanterer ikke at
  følge XML-rækkefølgen. Uden tidspunkt får flere poster samme dag samme
  tidsstempel (00:00Z), og læseren falder tilbage til sin egen interne
  rækkefølge — så en ældre post kan stå øverst. Derfor: angiv altid
  tidspunkt i `date`, når en dag kan få flere poster.
- **Medier på PVC (i drift).** ConfigMap har en 1 MiB-grænse, så binære medier
  kan aldrig bo der. `higgs-media`-PVC'en er monteret i nginx-poden på
  `/usr/share/nginx/html/media`, og `make sync-media` uploader fra lokalt
  `media/`. Deployment'et bruger `Recreate`, fordi PVC'en er ReadWriteOnce.
  Stabile stier er exit-strategien.
- **Logo: SVG som kilde, PNG til feedet.** `logo/logo-symmetrisk.svg` er
  kilden; `make build` genererer både SVG- og PNG-kopier til ConfigMap'en.
  Feedet bruger PNG, fordi podcast-klienter ikke afkoder SVG.
- **IPFS i fase 2 — som ekstra sti, ikke erstatning.** Hovedkanalen forbliver
  plain HTTPS fra nginx; IPFS bliver en anden enclosure mod egen gateway
  (`ipfs.higgs.gihc.online`), så intet afhænger af, at IPFS virker. I gang:
  Kubo-gateway-pod i k8s (k8s/ipfs.yaml), CID-beregning i build.py
  (`ipfs add -w` giver en stabil wrap-mappe-CID) og `scripts/sync-ipfs.sh`
  til pinning. Tilbage: DNS-record + deploy + ipfs-cluster (CRDT) på
  VPS + Pi + laptop som redundant backup. Se dialog-notatet
  [87a8a829-433b-41f9-90d8-c5a659e4204e.md](87a8a829-433b-41f9-90d8-c5a659e4204e.md).

## Næste skridt

- Første medie-episode er live; tilføj flere poster/episoder i samme flow
  (fil i `media/` → front matter med `media:` → `scripts/deploy.sh
  --sync-media`).
- Fase 2 (i gang): gateway-pod og CID'er er scaffoldet — mangler
  DNS-record for `ipfs.higgs.gihc.online`, deploy og pinning af medierne.
- Fase 2 (senere): ipfs-cluster (CRDT) på VPS + Pi + laptop som redundant
  backup af medierne. WebTorrent/Handshake forbliver research indtil videre.
- Følg med i [TODO.md](TODO.md).

## Licens

[AGPL-3.0](LICENSE)
