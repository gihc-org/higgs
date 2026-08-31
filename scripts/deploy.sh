#!/usr/bin/env bash
# higgs — byg, deploy og verificér feedet i ét kald.
#
# Brug:
#   scripts/deploy.sh               # byg + apply + vent på rollout + verificér
#   scripts/deploy.sh --sync-media  # ovenstående + upload lokalt media/ til PVC
#   scripts/deploy.sh --sync-ipfs   # ovenstående + pin medier i IPFS-gatewayen
#
# Kræver: SSH-alias 'hetzner-k3s', kubectl, make, curl.
# SSH-tunnelen (6443) åbnes automatisk, hvis porten ikke svarer lokalt.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

KUBECONFIG_PATH="../infra/kubeconfig.yml"
KUBECTL=(kubectl --kubeconfig "$KUBECONFIG_PATH")
TUNNEL_CMD=(ssh -N -f -L 6443:localhost:6443 -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 hetzner-k3s)
FEED_URL="https://higgs.gihc.online/feed.xml"

SYNC_MEDIA=0
SYNC_IPFS=0
for arg in "$@"; do
    case "$arg" in
        --sync-media) SYNC_MEDIA=1 ;;
        --sync-ipfs) SYNC_IPFS=1 ;;
        -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) echo "ukendt argument: $arg (se --help)" >&2; exit 2 ;;
    esac
done

for tool in kubectl curl make; do
    command -v "$tool" >/dev/null || { echo "FEJL: $tool mangler i PATH" >&2; exit 1; }
done
[ -f "$KUBECONFIG_PATH" ] || { echo "FEJL: mangler $KUBECONFIG_PATH (infra-repo)" >&2; exit 1; }

port_open() {
    timeout 3 bash -c 'exec 3<>/dev/tcp/127.0.0.1/6443' 2>/dev/null
}

ensure_tunnel() {
    if port_open; then
        echo "tunnel: port 6443 svarer allerede"
        return 0
    fi
    echo "tunnel: åbner SSH-tunnel til hetzner-k3s …"
    "${TUNNEL_CMD[@]}"
    for _ in 1 2 3 4 5; do
        sleep 1
        if port_open; then
            echo "tunnel: åben"
            return 0
        fi
    done
    echo "FEJL: tunnelen svarer ikke på 127.0.0.1:6443" >&2
    echo "Genstart den manuelt: ${TUNNEL_CMD[*]}" >&2
    return 1
}

echo "== byg =="
make build
python3 -c "import xml.etree.ElementTree as ET; ET.parse('k8s/feed.xml'); print('feed.xml: gyldig XML')"

ensure_tunnel

echo "== deploy =="
"${KUBECTL[@]}" apply -k k8s/
"${KUBECTL[@]}" -n higgs rollout status deployment/higgs --timeout=180s
"${KUBECTL[@]}" -n higgs rollout status deployment/ipfs-gateway --timeout=180s

if [ "$SYNC_MEDIA" = 1 ]; then
    if [ -d media ] && find media -type f | grep -q .; then
        echo "== sync-media =="
        POD="$("${KUBECTL[@]}" -n higgs get pod -l app=higgs -o jsonpath='{.items[0].metadata.name}')"
        "${KUBECTL[@]}" cp media/ "higgs/$POD:/usr/share/nginx/html/"
    else
        echo "sync-media: intet i media/ — springer over"
    fi
fi

if [ "$SYNC_IPFS" = 1 ]; then
    echo "== sync-ipfs =="
    bash scripts/sync-ipfs.sh
fi

echo "== verificér =="
# Lige efter en Recreate-rollout kan ingressen kortvarigt svare 503,
# indtil det nye pod er registreret som endpoint — prøv igen med pauser.
attempt=0
while [ "$attempt" -lt 10 ]; do
    HTTP_CT="$(curl -sS -o /dev/null -w '%{http_code} %{content_type}' "$FEED_URL" || true)"
    CODE="${HTTP_CT%% *}"
    [ "$CODE" = "200" ] && break
    attempt=$((attempt + 1))
    echo "verificér: HTTP ${CODE:-fejl} — prøver igen om 3 s ($attempt/10)"
    sleep 3
done
CODE="${HTTP_CT%% *}"
CT="${HTTP_CT#* }"
TITLE_OK="$(curl -sS "$FEED_URL" | grep -q '<title>Higgs</title>' && echo ja || echo nej)"

[ "$CODE" = "200" ] || { echo "FEJL: HTTP ${CODE:-ingen respons} på $FEED_URL efter 10 forsøg" >&2; exit 1; }
case "$CT" in
    application/atom+xml*) ;;
    *) echo "FEJL: Content-Type er '$CT' (forventet application/atom+xml)" >&2; exit 1 ;;
esac
[ "$TITLE_OK" = "ja" ] || { echo "FEJL: feed-titlen er ikke 'Higgs'" >&2; exit 1; }

echo "OK: HTTP 200, application/atom+xml, titel 'Higgs'"
