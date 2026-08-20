# higgs — strategi: statisk Atom-feed på gihc-domænet

> Notat fra dialog 2026-08-20/21. Status: strategi under afklaring — intet implementeret endnu.
> Kontekst-repo for platformen: `../infra/` (k3s-migration, ADR'er, platform-lag).

## Baggrund

- VPS hos Hetzner (65.109.233.92, cpx22, hel1) — migreret fra caddy+docker compose til k3s.
- higgs er et nyt, separat projekt: et **helt simpelt statisk Atom-feed** på gihc-domænet.
- Lag-inddeling (infra ADR 0002): platform ejes af `infra`-repoet (OpenTofu + Ansible);
  apps ejer deres egne `k8s/`-manifester. **At tilføje en ny app kræver ingen ændring i infra-repoet.**

## Hvad platformen allerede giver

- ingress-nginx (ServiceLB på 80/443) + globale security headers via ConfigMap i `tofu/platform.tf`
- cert-manager med `ClusterIssuer`s: `letsencrypt-prod` og `letsencrypt-staging`
- k3s API kun via SSH-tunnel:
  `ssh -L 6443:localhost:6443 -N -f root@65.109.233.92` — `infra/kubeconfig.yml` peger på `127.0.0.1:6443`
- `local-path-provisioner` (dynamiske PVC'er) + daglige Hetzner-disk-backups
- DNS hos Simply.com — apex peger allerede på serveren; nye subdomæner via script
  (mønster fra capture: `scripts/create-dns-record.sh`, creds i `pass simply/…`)
- Ingen CI endnu (Woodpecker står på infra-TODO) — deploys er manuelle `kubectl apply`

## Overordnet strategi

**Statisk markdown → genereret `feed.xml` → ConfigMap (kustomize) → nginx → Ingress.**

Kerneegenskaber: ingen image-build, ingen CI, ingen secrets, ingen PVC til selve feedet,
ingen ændringer i infra-repoet. Feedet er en fil, der deployes med `kubectl apply`.

## Repostruktur (plan)

```
higgs/
├── content/
│   ├── 2026-08-20-foerste-post.md
│   └── 2026-07-02-hej-verden.md
├── media/                   # gitignoreret — binære medier lokalt inden upload
├── build.py                 # generator: content/ (+ media/) → feed.xml
├── Makefile                 # make build / make deploy / make sync-media
├── k8s/
│   ├── namespace.yaml       # namespace: higgs
│   ├── kustomization.yaml   # configMapGenerator: feed.xml (content-hash)
│   ├── deployment.yaml      # nginx:alpine, mount af ConfigMap + PVC (media)
│   ├── pvc.yaml             # higgs-media — kun hvis medier skal med
│   ├── service.yaml         # port 80 → 80
│   └── ingress.yaml         # cert-manager.io/cluster-issuer: letsencrypt-prod
└── STRATEGI.md
```

## Post-format

Filnavnet bærer datoen — det er slug'en og stabilitetsnøglen for entry-id'et.

```markdown
---
title: Første post
summary: Hvad det hele går ud på
---

Brødteksten. **Markdown** bliver til HTML i feedet.
```

Med medier (se afsnit om media nedenfor):

```markdown
---
title: Post med lyd og grafik
media:
  - src: media/2026-08-20-foerste-post/episode.mp3
    type: audio/mpeg
  - src: media/2026-08-20-foerste-post/diagram.svg
    type: image/svg+xml
---
```

## Generator (build.py)

- **Python 3 + `python3-markdown`** — ét bibliotek, ~80 linjer, kører overalt.
  (`python-markdown` eksekverer ikke kode.) Rust-alternativ med `pulldown-cmark` er muligt
  hvis det foretrækkes, men Python er det mindste værktøj til opgaven.
- **`updated` automatisk korrekt**: max af post-datoerne — intet manuelt bump.
- **Stabile entry-id'er**: `uuid5` af slug'en — gamle poster bliver ikke genmarkeret
  som ulæste hos læsere, så længe filnavnet ikke ændres.
- **Sortering**: nyeste først efter filnavns-datoen.
- Front matter: `title` (påkrævet), `date` (default = filnavnet), `summary` og
  `external_url` (valgfri), `media` (valgfri).
- Medier: generatoren beregner `length` automatisk ved build-tid (den står med de
  lokale filer) og udsender `<link rel="enclosure">`.

## Deploy-flow

```bash
make build   # content/ → feed.xml
kubectl --kubeconfig ../infra/kubeconfig.yml apply -k k8s/
make sync-media   # kun hvis medier: kubectl cp media/ → pod
```

**Kustomize-tricket**: `kubectl apply -k` (kustomize er indbygget i kubectl) med en
`configMapGenerator` giver ConfigMap'en et nyt content-hash-suffiks i navnet, hver gang
`feed.xml` ændrer sig → Deployment'et ændrer sig → atomisk rolling update. Alternativet
(rå ConfigMap + plain apply) virker, men opdateringen er ikke atomisk og tager ~1 min
(kubelet-sync af monteret ConfigMap).

Flowet kører lokalt med SSH-tunnel indtil Woodpecker er klar — generator + apply passer
direkte ind i en CI-pipeline senere.

## Atom-detaljer

- nginx sender `text/xml` for `.xml` som standard; feed-læsere vil helst have
  `application/atom+xml`. Løsning: lille nginx-conf-override i ConfigMap'en (~5 linjer)
  eller `.atom`-filnavn.
- ETag/Last-Modified på statiske filer kommer automatisk i nginx → feed-læsere kan lave
  conditional GET. Ingen caching-konfiguration nødvendig.
- `updated`-felt i feedet er RFC 3339 (automatisk via generatoren).
- Globale security headers kommer automatisk fra ingress-nginx; CSP per app kan tilføjes
  som ingress-annotation hvis ønsket.

## Media-håndtering (mp3/mp4/svg)

Reglen der styrer designet: **ConfigMap har en hård 1 MiB-grænse** — binære medier kan
aldrig bo der.

**Feed-siden**: `media:`-liste i front matter → generator udsender enclosure-elementer:

```xml
<link rel="enclosure" type="audio/mpeg" length="4829134"
      href="https://gihc.online/media/2026-08-20-foerste-post/episode.mp3"/>
```

nginx kan allerede det hele uden konfiguration: `audio/mpeg`, `video/mp4`,
`image/svg+xml` findes i stock `mime.types`, og statisk servering understøtter HTTP
**Range** nativt (nødvendigt for at lyttere/afspillere kan søge i en fil).

**Opbevaring — anbefalet: PVC** (`higgs-media`, fx 10Gi, monteret i nginx-pod'en på
`/usr/share/nginx/html/media`):

- local-path-provisioner kører allerede — PVC'en er bare diskplads, nul ny infrastruktur.
- Medierne er dækket af de daglige Hetzner-disk-backups.
- Samme domæne som feedet, Range/Content-Length nativt.
- `ReadWriteOnce` → brug `strategy: Recreate` i Deployment'et (samme grund som capture).

Upload (Makefile-helper, over SSH-tunnelen):

```make
sync-media:
	POD=$$(kubectl -n higgs get pod -l app=higgs -o jsonpath='{.items[0].metadata.name}'); \
	kubectl cp media/ higgs/$$POD:/usr/share/nginx/html/media/
```

Nødsituation for kæmpe filer: `scp` direkte til node-stien under
`/var/lib/rancher/k3s/storage/` — virker, men bryder abstraktionen.

**Alternativ: Hetzner Object Storage** (creds-mønster findes allerede — tofu-state-bucketen):

- Fordele: upload med rclone/aws-cli uden tunnel, uafhængig af diskstørrelse.
- Ulemper: fremmed bucket-hostname i URL'erne (Hetzner understøtter ikke custom
  domæne/HTTPS på buckets uden reverse proxy), betalt egress-trafik, medierne uden for
  disk-backuppen.
- Sikker exit-strategi: enclosure-URL'en er bare en href. Hold stierne stabile
  (`media/<slug>/fil.ext`, aldrig flyt/forkort), så kan basen skiftes senere uden at
  gamle poster dør.

**SVG-særregel**: SVG er tekst og fylder typisk < 100 KB — kan bo i ConfigMap'en og
dermed i git. Anbefaling: hold reglen simpel (alt media på PVC'en), indfør
ConfigMap-varianten senere hvis git-historik på grafikker savnes.

## Åbne beslutninger

1. **Domæne** (ikke besluttet):
   - Apex `gihc.online` — DNS peger allerede, nul DNS-arbejde; apex bliver optaget.
   - Subdomæne `higgs.gihc.online` — følger app-navnekonventionen; kræver ny A-record
     via Simply.com-scriptet; holder apex fri.
   - Subdomæne `feed.gihc.online` — samme som ovenstående, mere beskrivende navn.
   - Konsekvens for koden: én konstant i generatoren (feed-URL, indgår i id/rel="self")
     + én Ingress-host. Alt andet er uafhængigt.
2. **Hvad linker posterne til?**
   - Variant A — kun feed: feedet *er* produktet; poster linker til `external_url` eller
     selve feedet; indholdet ligger i feedets `content`-felt. **Anbefalet som start.**
   - Variant B — feed + minimale HTML-sider: generatoren udskriver også `index.html` +
     `posts/<slug>.html`, så poster kan læses i browser. ~30 linjer ekstra, naturlig
     udbygning af A senere.
3. **Medie-opbevaring**: PVC anbefalet (besluttet de facto), object storage som
   escape hatch hvis medier vokser eller upload-flowet irriterer.

## Næste skridt (når beslutningerne er truffet)

1. `git init` + push til GitHub (gihc-org), med `media/` i `.gitignore`.
2. Scaffold: `k8s/` (namespace, kustomization, deployment, service, ingress med
   `letsencrypt-prod`), `build.py`, `Makefile`, `content/` med første post.
3. DNS: intet hvis apex; ellers kopi af captures `create-dns-record.sh` tilpasset
   record-navnet.
4. Deploy: SSH-tunnel → `make build` → `kubectl apply -k k8s/`.
5. Verificér: `curl https://<domæne>/feed.xml` returnerer gyldigt LE-cert + korrekt
   Content-Type; feedet validerer i en feed-læser.
