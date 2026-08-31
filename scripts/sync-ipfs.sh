#!/usr/bin/env bash
# higgs — pin lokale medier i IPFS-gateway-pod'en (fase 2).
#
# Tilføjer hver fil i media/ med `ipfs add -w` (wrap-mappe) og pin, så de
# IPFS-enclosure-URL'er som build.py har beregnet faktisk svarer på
# https://ipfs.higgs.gihc.online/ipfs/<CID>/<fil>.
#
# IPFS er content-addressed: samme fil giver samme CID uanset maskine, så
# scriptet er idempotent — at køre det igen ændrer ikke noget.
#
# Brug:
#   scripts/sync-ipfs.sh   # kræver åben SSH-tunnel til k3s
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

KUBECTL=(kubectl --kubeconfig ../infra/kubeconfig.yml)

if ! find media -type f 2>/dev/null | grep -q .; then
    echo "intet i media/ — intet at pinne"
    exit 0
fi

POD="$("${KUBECTL[@]}" -n higgs get pod -l app=ipfs-gateway -o jsonpath='{.items[0].metadata.name}')"
[ -n "$POD" ] || { echo "FEJL: ingen ipfs-gateway-pod (er gatewayen deployet?)" >&2; exit 1; }

echo "== kopiér media/ til pod =="
"${KUBECTL[@]}" cp media/ "$POD:/tmp/"

echo "== pin hver fil (wrap-mappe-CID) =="
while IFS= read -r f; do
    rel="${f#media/}"
    cid="$("${KUBECTL[@]}" exec "$POD" -- ipfs add -Q -w --cid-version 1 "/tmp/media/$rel" | tr -d '\r')"
    echo "$rel → $cid"
done < <(find media -type f | sort)

"${KUBECTL[@]}" exec "$POD" -- rm -rf /tmp/media
echo "OK: medier pinned — verificér med curl -sS https://ipfs.higgs.gihc.online/ipfs/<CID>/<fil>"
