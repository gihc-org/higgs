# higgs — statisk Atom-feed

## Formål

Et minimalt, statisk Atom-feed på
[https://higgs.gihc.online/feed.xml](https://higgs.gihc.online/feed.xml).
Indhold er markdown i `content/` (genererede feeds); `feeds/` kan bruges til
vedhæftede XML-feeds (fx tredjeparts-RSS). `build.py` har registry'et `FEEDS`
og genererer `k8s/feed.xml` + `k8s/feeds/`, som deployes som ConfigMaps
(kustomize) bag nginx + ingress — medierne ligger på PVC'en. Ingen backend,
ingen CI, ingen image-build, ingen secrets.

Vendor-neutralitet er designprincippet: **feedet er produktet, hosting er
udskiftelig.** Læs `README.md` (hvordan/hvorfor), `STRATEGI.md` (den
oprindelige strategi), `TODO.md` (status/tjekliste) og `HANDOVER.md`
(tilstand for næste session) før arbejde.

## Status

- **Fase 1 i drift** (aug 2026): feedet er live på k3s (Hetzner), cert-manager
  (letsencrypt-prod), DNS A-record oprettet, feedet testet i AntennaPod.
- Generator, k8s-manifester, Makefile og DNS-script er på plads; kubectl er
  installeret lokalt (`~/.local/bin`), SSH-tunnel via `hetzner-k3s`.
- Afventer: brugeren pusher selv; fase 2 = IPFS som ekstra distributionssti
  (ikke erstatning). Medie-håndtering er i drift (første m4a-episode på PVC).

## Agentens rolle

Du er udvikler/dokumentarist for higgs. Hold løsningen så enkel som muligt og
beskyt de tre neutralitets-ankre:

1. **Stabile URL'er er kontrakten.** `media/<slug>/<fil>` — og
   `media/<tema>/<bog>/<fil>` — ændres aldrig. Omdøb/flyt aldrig
   content-filer; filnavnet er slug'en og entry-id'et (`uuid5`), så ændringer
   markerer gamle poster som nye for læsere.
2. **Ét sted for feed-URL'er.** `SITE_BASE` + registry'et `FEEDS` i
   `build.py` er det eneste sted, domænet og feed-stierne lever.
   Domæne-/host-skift er én linje + ingress.
3. **Git er sandheden, serveren er en kopi.** `make build` skal altid kunne
   genskabe feedene fra `content/` + `feeds/` + `build.py`.

## Vigtige regler

- **Rør aldrig `../infra/`** — higgs ejer sine egne k8s-manifester i `k8s/`;
  app-laget kræver ingen ændringer i platformen.
- **Medier hører ikke i git.** `media/` er gitignoreret; upload via
  `make sync-media` (kubectl cp). ConfigMap har en 1 MiB-grænse — binære
  medier kan aldrig bo der.
- **Kustomize kan ikke se uden for `k8s/`** — derfor genereres `feed.xml` og
  `feeds/<key>/feed.xml` ind i `k8s/` og er gitignorerede som artefakter.
- **Deploy kræver tunnel + byg:** `make build`, derefter
  `kubectl apply -k k8s/` (kubeconfig ligger uden for repoet, i
  `~/.kube/gihc.yml` — se `scripts/deploy.sh`). Verificér altid efter deploy:
  HTTP 200, `Content-Type: application/atom+xml`, gyldigt
  letsencrypt-cert (`curl -sS https://higgs.gihc.online/feed.xml`).
- **Eksterne skridt med brugerens credentials** (pass, SSH-passphrase,
  GitHub-push, DNS-ændringer): udføres af brugeren eller med eksplicit
  godkendelse.
- **Sprog:** dokumentation og samtale på dansk.

## Dokumentation undervejs

- Hold `TODO.md` opdateret samme time noget ændres eller afklares — korte
  pointere, ikke dubletter af README.
- Skel mellem **aftalt / udført / afventer / foreslået**; afventende
  beslutninger stilles til brugeren og må ikke forsvinde i samtalen.
- Ved ændringer af arkitektur eller beslutninger: opdatér `README.md` samme
  time; opdatér `STRATEGI.md` kun hvis selve strategien ændres.
- Status-spørgsmål: giv ét kort statusafsnit + peg på README/TODO.
- Hold vigtige fakta i repo-filer, ikke kun i samtalehistorikken.

## Git-disciplin

- Commits på dansk, korte og beskrivende. Committer lokalt; push overlades til
  brugeren, medmindre andet er aftalt.
- Hvis du laver commits i en agent-session, følg geekbox-konventionen med et
  `[agent:model]`-tag (fx `[codex:…]`): hent model-id fra den aktuelle
  sessions egne oplysninger — antag den aldrig. Ret aldrig ældre commits eller
  tags uden brugerens godkendelse.

## Checkpoint- og tråd-disciplin

- Ved milepæle (deploy, beslutning, dokument opdateret): opdatér `TODO.md`
  samme time.
- Hvis du gentager dig selv, spørger om ting der allerede er fastslået, eller
  genkører kommandoer: sig det højt og foreslå at starte en ny tråd, der
  begynder med "Læs README.md + TODO.md og fortsæt derfra".
