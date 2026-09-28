# higgs

Et helt simpelt statisk Atom-feed, live på
[https://higgs.gihc.online/feed.xml](https://higgs.gihc.online/feed.xml).
Ved siden af det ligger flere feeds pr. bog/tema, fx
[https://higgs.gihc.online/tao/lieh-tzu/feed.xml](https://higgs.gihc.online/tao/lieh-tzu/feed.xml).

Status: **fase 1 og 3 i drift.** Rod-feedet udgiver to poster (inkl. den
første medie-episode på PVC'en), og under temaer ligger bøger som
`tao/lieh-tzu` med selv-hostede kapitler. Feed, medier og artwork er testet i
en rigtig feed-læser (AntennaPod). Fase 2 (IPFS) er deployet internt: gateway
i klyngen og medier pinnet — afventer fortsat offentlig DNS + cert for
`ipfs.higgs.gihc.online`. Indtil da er IPFS-enclosure-linkene i feedet døde;
nginx-linket står først, så afspilning virker.

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
content/<feed>/*.md  →  build.py (FEEDS)  →  k8s/feeds/<key>/feed.xml  →  ConfigMap pr. feed
feeds/<key>/feed.xml ↗                             ↓
                    https://higgs.gihc.online/<sti>/feed.xml  ←  Ingress  ←  nginx
```

1. **Markdown-poster** i `content/<feed>/` er kilden til genererede feeds.
   Filnavnet bærer datoen og er samtidig slug'en og stabilitetsnøglen for
   postens id. Vedhæftede feeds er i stedet færdige XML-filer i `feeds/<key>/`.
2. **build.py** genererer feedene ud fra registry'et `FEEDS`:
   - stabile entry-id'er via `uuid5` af slug'en — gamle poster bliver aldrig
     genmarkeret som ulæste, så længe filnavnet ikke ændres;
   - `updated` = max af post-datoerne (RFC 3339) — intet manuelt bump;
   - sortering nyeste først;
   - markdown → HTML med `python3-markdown` (eksekverer ikke kode);
   - enclosure-støtte med automatisk `length` fra de lokale medie-filer.
     Medier får to `<link rel="enclosure">`: én fra nginx og — hvis `ipfs` er
     installeret — én mod egen IPFS-gateway (`FEED_IPFS_GATEWAY`).
3. **Kustomize** lægger hvert feeds filer i sin egen ConfigMap via
   `configMapGenerator`. Hver gang en fil ændrer sig, får den ConfigMap et nyt
   content-hash i navnet → deployment'et ændrer sig → atomisk rolling update.
   Ingen image-build, ingen push til registry. Én ConfigMap pr. feed betyder
   også, at 1 MiB-grænsen kun gælder det enkelte feed.
4. **nginx** serverer filerne statisk. Conf'en genereres af `build.py` ud fra
   `FEEDS` og sikrer korrekt `Content-Type` pr. feed (nginx sender ellers
   `text/xml`) — `application/atom+xml` for genererede feeds,
   `application/rss+xml` for vedhæftede. ETag/Last-Modified og HTTP Range
   kommer automatisk.
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
- `configMapGenerator` bygger én ConfigMap pr. feed: rod-feedet har
  `feed.xml`, `logo.svg`, `logo.png` og `nginx/default.conf`, hvert vedhæftet
  feed har sin egen `feed.xml`. Hver ConfigMap får et content-hash i navnet
  (fx `higgs-feed-mtg2mkfg6b`). Ændrer en fil sig, får ConfigMap'en nyt navn →
  deployment'et peger på det nye navn → pod'en genstarter atomisk. Det er
  derfor, en ny post kun kræver `make build` + `kubectl apply -k k8s/`.

### Flere feeds (temaer og bøger)

Alle feeds står i registry'et `FEEDS` i [build.py](build.py). Et feed er
**genereret** (markdown i `content/<key>/` → Atom) eller **vedhæftet** (en
færdig XML-fil i `feeds/<key>/`, fx en rettet RSS-fil fra en anden udgiver).
Tilføjer man en post i registry'et, følger build, ConfigMap,
nginx-Content-Type og deploy-verifikation automatisk.

Bøger grupperes i temaer via URL-stien — `tao` er temaet, `lieh-tzu` er bogen:

| Feed | Type | URL |
| --- | --- | --- |
| Higgs (rod) | genereret Atom | `https://higgs.gihc.online/feed.xml` |
| Lieh-Tzu | genereret Atom | `https://higgs.gihc.online/tao/lieh-tzu/feed.xml` |

Lieh-Tzu er født som et vedhæftet RSS-feed (rettet LibriVox-fil), men er nu et
genereret Atom-feed med **selv-hostede medier**: de otte kapitler ligger på
PVC'en under `media/tao/lieh-tzu/` og serveres fra vores eget domæne. Baggrund:
LibriVox' `www.archive.org/download/…`-URL'er begyndte at svare HTTP 500 (deres
`dn…`-dowloadnode fejlede), og uden egne URL'er ville feedet være afhængigt af
en tredjeparts oppetid. Indspilningerne er i public domain. `src:` i front
matter skrives derfor altid relativt til **domæneroden** (`media/<sti>`), mens
entry-id'er fortsat bruger feedets egen sti som anker.

**Rækkefølge:** LibriVox' `pubDate` fandtes ikke i originalen og blev opfundet
(episode 0 = ældst). Her er tiderne vendt om, så `date` for kapitel 1 er den
nyeste: podcast-klienter viser normalt nyeste øverst, og dermed står kapitlerne
i bogens rækkefølge uden at læseren skal ændre sortering.

Hvert afsnit har desuden `external_url` til sit kapitel i den frie
[Wikisource-udgave](https://en.wikisource.org/wiki/Taoist_teachings_from_the_book_of_Lieh_Tz%C5%AD)
af Lionel Giles' 1912-oversættelse; generatoren gør det til
`<link rel="alternate">`. Bemærk ophavsretten: oversættelsen er public domain i
USA (derfor kan Wikisource og LibriVox bruge den), men beskyttet i DK/EU til og
med 2028 (Giles døde 1958) — derfor linker vi frem for at hoste teksten selv.
En scan med PDF, EPUB og OCR-tekst ligger på
[archive.org](https://archive.org/details/taoistteachings00liez).

Hvordan klienter læser det, er efterprøvet i AntennaPods kildekode:
`<link rel="alternate">` bliver episodens *hjemmeside* (episodemenuen "Besøg
hjemmeside"), mens **beskrivelsen** sættes til det længste af `<content>` og
`<summary>`. Vigtigere: AntennaPod koger Atom-tekst til **ren tekst**
(`AtomText.getProcessedContent()` kører `fromHtml(...).toString()` på
`type="html"`, og `type="xhtml"` mister tags i SAX-opsamlingen), så `href`
overlever ikke i beskrivelsen. Derfor står kapitellinket også som en **synlig
URL** i teksten: AntennaPods `PlainTextLinksConverter` gør bare URL'er
klikbare i beskrivelsen. Links der skal kunne trykkes på i Atom-feeds, skal
altså skrives som `<https://…>` — ikke som skjult `href` bag en pæn tekst.

Stien er abonnements-kontrakten og kan ikke laves om bagefter uden at læserne
skal tilmelde sig igen. Derfor ligger nye feeds under `higgs.gihc.online` i
stedet for på et subdomæne pr. bog: nye bøger kræver hverken DNS-record eller
cert. Vil man have et tema på eget subdomæne (`tao.higgs.gihc.online`), er det
én linje i `FEEDS` plus en DNS-record og en ingress-regel.

Sådan importerer du en LibriVox-bog (den normale vej):

```bash
scripts/import-librivox.py --theme tao --book zhuangzi \
  --rss https://librivox.org/rss/XXXX     # eller --item <archive.org-id>
scripts/deploy.sh --sync-media
```

[scripts/import-librivox.py](scripts/import-librivox.py) henter metadata og
filer fra archive.org — via item'ets egen host, ikke `www.archive.org/download/…`,
hvis downloadnode svarer 500 — og verificerer hver fil mod arkivets md5.
Den lægger medierne i `media/<tema>/<bog>/`, skriver
`content/<tema>/<bog>/<dato>-NN-<kapitel>.md` og indsætter feedet i registry'et
samt i `k8s/kustomization.yaml` og `k8s/deployment.yaml` — altid i de markerede
`importerede feeds`-blokke, så indsættelsen er idempotent og let at revidere.
Til sidst kører den `build.py` og `kubectl kustomize` som egenkontrol.

Kapitel 1 får den nyeste dato (23:00 og bagud, ét minut pr. kapitel), så listen
står i læserækkefølge i klienter der viser nyeste øverst — brug `--oldest-first`
for det modsatte. `--variant vbr|ogg` vælger en anden lydudgave, `--date`
overstyrer basisdatoen, og `--dry-run` viser planen uden at hente noget.

Sådan tilføjer du en genereret bog i hånden (kilder uden LibriVox-metadata):

1. Læg medierne i `media/<tema>/<bog>/` (gitignoreret — uploades med
   `scripts/deploy.sh --sync-media`).
2. Opret `content/<tema>/<bog>/YYYY-MM-DD-NN-titel.md` pr. kapitel med `title`,
   `date` og en `media:`-liste, hvor `src:` er stien fra domæneroden.
3. Tilføj feedet i `FEEDS` med `kind="generated"`, `content_dir` og `output`
   samt en ConfigMap i `k8s/kustomization.yaml` og et mount i
   `k8s/deployment.yaml` (Lieh-Tzu er skabelonen).
4. `make verify`, derefter `scripts/deploy.sh --sync-media` — verifikationen
   dækker alle feeds i registry'et.

Sådan tilføjer du en vedhæftet bog (kun hvis kilden er en færdig XML, og
medierne bliver liggende hos udgiveren):

1. Læg XML-filen i `feeds/<tema>/<bog>/feed.xml` (mappen findes ikke i dag —
   opret den, hvis kode-stien tages i brug), og ret
   `<atom:link rel="self">` til den URL, feedet udgives på — `build.py`
   fejler, hvis self-linket ikke matcher registry'et.
2. Tilføj feedet i `FEEDS` med `kind="attached"`, `content_type=RSS` og
   `output="k8s/feeds/<tema>/<bog>/feed.xml"`.
3. ConfigMap + mount som ovenfor. Feedet kan kun bruges, så længe udgiverens
   medie-URL'er svarer — det var netop den afhængighed, der ramte Lieh-Tzu.

## Neutralitets-ankrene

Tre principper blev lagt ind fra dag ét, fordi de er billige nu og svære at
lægge ind senere:

1. **Stabile URL'er er kontrakten.** Enclosure-URL'er er det eneste, læsere
   husker. Stien `media/<slug>/<fil>` ændres aldrig — uanset om det, der står
   bag, er en PVC, en IPFS-gateway eller en anden server.
2. **Ét sted for feed-URL'er.** `SITE_BASE` og registry'et `FEEDS` i
   [build.py](build.py) er det eneste sted, domænet og feed-stierne lever. Et
   domæne-/host-skift er én linje + en ingress-ændring.
3. **Git er sandheden, serveren er en kopi.** Alle feeds kan altid genskabes
   med `make build` (vedhæftede feeds kopieres fra `feeds/`). Serveren er et
   udstillingsvindue, ikke en database. Medierne er den ene undtagelse — de
   ligger ikke i git, men hentes tilbage med `make fetch-media` (eller fra
   IPFS), så også de kan genskabes.

Sammen betyder de, at vi kan skifte hosting, domæne eller distributionsform
senere uden at bryde noget for læsere.

## Repostruktur

```
higgs/
├── content/                  # markdown-poster pr. feed — kilden til genererede feeds
│   ├── higgs/                # rod-feedet (higgs.gihc.online/feed.xml)
│   │   └── 2026-08-31-foerste-post.md
│   └── tao/lieh-tzu/         # Lieh-Tzu: otte kapitler, selv-hostede medier
├── media/                    # medier (gitignoreret) — uploades til PVC med --sync-media
│   └── tao/lieh-tzu/         # Lieh-Tzu: 8 × mp3 + cover.jpg (public domain)
├── logo/                     # logo-arbejde: logo-symmetrisk.svg er kilden
├── scripts/
│   ├── deploy.sh             # tunnel + byg + apply + verificér (--sync-media/--sync-ipfs)
│   ├── fetch-media.py        # hent media/ over HTTPS til en ny maskine
│   ├── import-librivox.py    # importér en LibriVox-bog (medier + poster + registry)
│   ├── sync-ipfs.sh          # pin media/ i gateway-pod'en (wrap-mappe-CIDs)
│   └── create-dns-record.sh  # A-record hos Simply.com — IP som arg eller udledt fra zonen
├── build.py                  # registry (FEEDS) + generator: content/ + feeds/ → k8s/
├── Makefile                  # build / verify / deploy / sync-media / fetch-media
├── k8s/                      # manifests + genererede artefakter
│   ├── kustomization.yaml    # configMapGenerator: én ConfigMap pr. feed
│   ├── deployment.yaml       # nginx:alpine, mount af hvert feed på dets sti
│   ├── service.yaml
│   ├── ingress.yaml          # higgs.gihc.online, letsencrypt-prod
│   ├── pvc.yaml              # higgs-media (5Gi, local-path) — medier
│   ├── ipfs.yaml             # fase 2: Kubo-gateway (deployment + service + PVC)
│   ├── feed.xml              # genereret: rod-feedet
│   ├── feeds/                # genereret: vedhæftede feeds på deres URL-sti
│   ├── logo.svg              # genereret kopi af logo-symmetrisk.svg
│   ├── logo.png              # genereret 1024×1024 PNG (feed-artwork)
│   └── nginx/default.conf    # genereret: Content-Type pr. feed
├── AGENTS.md                 # arbejdsregler for AI-agenter
├── STRATEGI.md               # den oprindelige strategi
├── TODO.md                   # status og tjekliste
└── README.md
```

`media/`, `k8s/feed.xml`, `k8s/feeds/`, `k8s/nginx/default.conf`,
`k8s/logo.svg` og `k8s/logo.png` er gitignoreret — det første fordi binære
medier ikke hører i git, de øvrige fordi de er genererede artefakter
(genskabes af `make build`).

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

Opret `content/<feed>/YYYY-MM-DD-slug.md` (rod-feedet er `content/higgs/`):

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
`<link rel="enclosure" …>` med korrekt type, length og stabil href. Stien i
`src:` er relativ til **domæneroden** — rod-feedet bruger `media/<slug>/<fil>`,
et bog-feed bruger `media/<tema>/<bog>/<fil>`. Det matcher nginx-mountet
(`/media` → PVC'en), uanset hvilken URL-sti feedet selv har.

### Byg og verificér

```bash
make build    # feeds → k8s/ + nginx-conf + logo.svg + logo.png
make verify   # tjekker alle feeds (XML) og logo.png (PNG)
```

Medierne er ikke i git, så et friskt checkout bygger et feed **uden
enclosures** — bygget advarer, og `make build BUILD_FLAGS=--strict-media` gør
det til en fejl i stedet. `deploy.sh` bruger altid den strenge variant.

### Deploy

`scripts/deploy.sh` (eller `make deploy`) klarer hele flowet i ét kald: åbner
SSH-tunnelen hvis den ikke kører, bygger, deployer, venter på rollout og
verificerer HTTP 200 + Content-Type + titel for **alle** feeds i registry'et.
Verifikationen genprøver automatisk i op til ~30 sekunder pr. feed: lige efter
en `Recreate`-rollout kan ingressen kortvarigt svare 503, indtil den nye pod
er registreret som endpoint.

```bash
scripts/deploy.sh
scripts/deploy.sh --sync-media            # uploader også lokalt media/ til PVC
scripts/deploy.sh --sync-ipfs             # pinner også medierne i IPFS-gatewayen
scripts/deploy.sh --allow-missing-media   # bevidst undtagelse (frarådet)
```

Deployet bygger med `--strict-media`: mangler en fil som `media:` peger på,
afbrydes det **før** klyngen røres, så et deploy aldrig kan fjerne
enclosure-links i stilhed. `--allow-missing-media` er den bevidste undtagelse.

Har du ændret medier, skal du bruge `--sync-media` (eller køre
`make sync-media` bagefter); skal IPFS-enclosure-URL'erne virke, kør
`--sync-ipfs` (eller `scripts/sync-ipfs.sh` bagefter). Manuelt svarer flowet til:

### Hent medierne på en ny maskine

Media er ikke i git, så et friskt `git clone` har tom `media/` — og et deploy
afbryder derfor med vilje. Hent den manglende halvdel over HTTPS fra det
udgivne site (ingen kubeconfig, ingen SSH, ingen credentials):

```bash
make fetch-media                        # alt der mangler
scripts/fetch-media.py --only liehtzu   # kun stier der matcher
scripts/fetch-media.py --dry-run        # vis kun planen
```

Fil-listen kommer fra repoet selv (front matter plus feed-artwork), og hver fil
verificeres mod serverens `Content-Length`. Filer der allerede findes med
rigtig størrelse springes over, så kommandoen kan køres igen efter en
afbrydelse. De 85 MB tager sekunder fra vores egen server. Bagefter:
`make verify BUILD_FLAGS=--strict-media`.

Med klynge-adgang kan man i stedet hente nøjagtig den kopi nginx serverer:

```bash
POD=$(kubectl -n higgs get pod -l app=higgs -o jsonpath='{.items[0].metadata.name}')
kubectl cp "higgs/$POD:/usr/share/nginx/html/media/" media/
```

Når IPFS-DNS'en er løst, bliver gatewayen en tredje kilde — feedet annoncerer
allerede CID'erne for hver fil.

```bash
ssh -N -f -L 6443:localhost:6443 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 hetzner-k3s
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/gihc.yml}"   # skrives af infra's ansible-playbook
kubectl apply -k k8s/
```

Gatewayen verificeres separat (CID'et udskrives af `sync-ipfs.sh`):

```bash
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' \
  https://ipfs.higgs.gihc.online/ipfs/<CID>/<fil>
# forvent: HTTP 200 og fx audio/mp4
```

### DNS (kun ved nye subdomæner)

Nye feeds under `higgs.gihc.online` kræver ingen DNS-ændring — det gør kun et
nyt subdomæne.

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
- **Flere feeds: én sti pr. bog, ikke ét subdomæne pr. bog.** `FEEDS` i
  build.py er registry'et; `tao` er et tema i stien og `lieh-tzu` bogen, så en
  ny bog koster en registry-post (plus ConfigMap-mount) og hverken DNS-record
  eller cert.
- **Selv-hostede medier frem for tredjeparts-URL'er.** Lieh-Tzu startede som
  vedhæftet RSS med enclosures på `www.archive.org/download/…`. Da archive.orgs
  download-proxy begyndte at svare HTTP 500 (og Cloudflare-fejl i browseren),
  blev de otte filer hentet ned og lagt på PVC'en. Feedet er nu genereret Atom
  med vores egne, stabile URL'er — samme afhængighedsprincip som resten af
  higgs. LibriVox' indspilninger er i public domain, så det er uproblematisk.
- **Atom frem for RSS for vores egne feeds.** Generatoren udgiver Atom, og det
  virker i både rod-feedet og tao-feedet (testet i AntennaPod). RSS 2.0 med
  `itunes:`-tags er fortsat nødvendigt, hvis et feed skal godkendes i Apple
  Podcasts — bliver det et krav, skal generatoren kunne begge formater.
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
  Kubo-gateway-pod i k8s (k8s/ipfs.yaml), CID-beregning i build.py (`ipfs add
  -w` giver en stabil wrap-mappe-CID) og `scripts/sync-ipfs.sh` til pinning —
  **deployet og medier pinned**. Åbent: offentlig DNS for
  `ipfs.higgs.gihc.online` (recorden findes i Simplys API, men serveres ikke
  endnu) + cert; derefter ipfs-cluster (CRDT) på VPS + Pi + laptop som
  redundant backup. Se dialog-notatet
  [87a8a829-433b-41f9-90d8-c5a659e4204e.md](87a8a829-433b-41f9-90d8-c5a659e4204e.md).

## Næste skridt

- **Flere bøger:** `scripts/import-librivox.py --theme <tema> --rss
  <librivox-url>` efterfulgt af `scripts/deploy.sh --sync-media` — scriptet
  klarer metadata, download med md5-verifikation, poster, registry og
  manifester, og verificerer selv `build.py` + `kubectl kustomize`.
- **Fase 2 (i gang):** gateway og CID'er er deployet, medier pinnet — mangler
  offentlig DNS + cert for `ipfs.higgs.gihc.online` (recorden findes i Simplys
  API, men serveres ikke endnu) og offentlig verifikation. Overvej at gøre
  IPFS-enclosures tilvalg, indtil DNS svarer.
- **Fase 2 (senere):** ipfs-cluster (CRDT) på VPS + Pi + laptop som redundant
  backup af medierne. WebTorrent/Handshake forbliver research indtil videre.
- **Åbent:** større artwork til Lieh-Tzu (LibriVox' er 300×300); Apple
  Podcasts kræver RSS 2.0 med `itunes:`-tags, hvis bøgerne en dag skal derind.
- Følg med i [TODO.md](TODO.md).

## Licens

[AGPL-3.0](LICENSE)
