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

# Kubeconfig ligger uden for alle repos (skrives af infra's ansible-playbook).
KUBECONFIG="${KUBECONFIG:-$HOME/.kube/gihc.yml}"
export KUBECONFIG
KUBECTL=(kubectl)
TUNNEL_CMD=(ssh -N -f -L 6443:localhost:6443 -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 hetzner-k3s)

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
[ -f "$KUBECONFIG" ] || { echo "FEJL: mangler $KUBECONFIG — kør infra/ansible/infra.yml" >&2; exit 1; }

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
make verify

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
# Feedene kommer fra registry'et (build.py: FEEDS), så nye feeds verificeres
# automatisk. TSV: key, url, content_type, title.
while IFS=$'\t' read -r KEY URL CONTENT_TYPE TITLE; do
    attempt=0
    while [ "$attempt" -lt 10 ]; do
        HTTP_CT="$(curl -sS -o /dev/null -w '%{http_code} %{content_type}' "$URL" || true)"
        [ "${HTTP_CT%% *}" = "200" ] && break
        attempt=$((attempt + 1))
        echo "verificér: $KEY — HTTP ${HTTP_CT%% *} — prøver igen om 3 s ($attempt/10)"
        sleep 3
    done
    CODE="${HTTP_CT%% *}"
    CT="${HTTP_CT#* }"
    [ "$CODE" = "200" ] || { echo "FEJL: HTTP ${CODE:-ingen respons} på $URL efter 10 forsøg" >&2; exit 1; }
    case "$CT" in
        "$CONTENT_TYPE"*) ;;
        *) echo "FEJL: $KEY — Content-Type er '$CT' (forventet $CONTENT_TYPE)" >&2; exit 1 ;;
    esac
    curl -sS "$URL" | grep -qF "<title>${TITLE}</title>" \
        || { echo "FEJL: $KEY — titlen er ikke '${TITLE}'" >&2; exit 1; }
    echo "OK: $KEY — HTTP 200, $CT, titel '${TITLE}'"
done < <(python3 build.py --list)
