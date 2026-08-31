#!/usr/bin/env bash
set -euo pipefail

# Sikrer en A-record for <navn>.gihc.online hos Simply.com mod VPS'ens
# nuværende IP. IP'en er IKKE hardcoded:
#   1) angives eksplicit som andet argument, eller
#   2) udledes fra zonens A-records — er de alle enige om én IP, bruges den
#      (alle subdomæner peger i praksis på samme VPS).
# Er records i uenighed, fejler scriptet og beder om IP'en — den gætter aldrig.
# Idempotent: opretter hvis recorden mangler, opdaterer hvis IP'en er ændret,
# springer over hvis den allerede er korrekt.
#
# Credentials hentes fra `pass`:
#   pass insert simply/account
#   pass insert simply/api-key
#
# Brug: scripts/create-dns-record.sh [record-navn] [ip]
#   record-navn: default "higgs"
#   ip: optional — ellers udledt fra zonens A-records (krav: alle enige)

DOMAIN="gihc.online"
RECORD_NAME="${1:-higgs}"
TARGET_IP="${2:-}"
TTL=3600

SIMPLY_ACCOUNT="$(pass simply/account)"
SIMPLY_API_KEY="$(pass simply/api-key)"

API_URL="https://api.simply.com/2/my/products/${DOMAIN}/dns/records/"

echo "==> Henter DNS records for ${DOMAIN}..."
RECORDS=$(curl -sf -u "${SIMPLY_ACCOUNT}:${SIMPLY_API_KEY}" "${API_URL}")

if [ -z "$TARGET_IP" ]; then
    TARGET_IP=$(python3 -c '
import json, sys
records = json.load(sys.stdin).get("records", [])
ips = {r.get("data") for r in records if r.get("type") == "A" and r.get("data")}
if len(ips) == 1:
    print(next(iter(ips)))
' <<<"$RECORDS")
fi

if [ -z "$TARGET_IP" ]; then
    echo "Fejl: kunne ikke udlede VPS-IP'en fra zonens A-records (uenige eller manglende). Angiv den eksplicit: $0 ${RECORD_NAME} <ip>" >&2
    exit 1
fi

EXISTING=$(RECORD_NAME="$RECORD_NAME" python3 -c '
import json, os, sys
records = json.load(sys.stdin).get("records", [])
name = os.environ["RECORD_NAME"]
for r in records:
    if r.get("type") == "A" and r.get("name") == name:
        print(str(r.get("record_id", "")) + "\t" + r.get("data", ""))
        break
' <<<"$RECORDS")

EXISTING_ID="${EXISTING%%$'\t'*}"
EXISTING_IP="${EXISTING#*$'\t'}"

if [ -n "$EXISTING_ID" ] && [ "$EXISTING_IP" = "$TARGET_IP" ]; then
    echo "==> A-record for ${RECORD_NAME}.${DOMAIN} peger allerede på ${TARGET_IP}, springer over."
    exit 0
fi

BODY="{\"type\":\"A\",\"name\":\"${RECORD_NAME}\",\"data\":\"${TARGET_IP}\",\"ttl\":${TTL}}"

if [ -z "$EXISTING_ID" ]; then
    echo "==> Opretter A-record ${RECORD_NAME}.${DOMAIN} -> ${TARGET_IP}..."
    curl -sf -u "${SIMPLY_ACCOUNT}:${SIMPLY_API_KEY}" \
        -X POST "${API_URL}" \
        -H "Content-Type: application/json" \
        -d "$BODY" -o /dev/null
else
    echo "==> Opdaterer A-record ${RECORD_NAME}.${DOMAIN} -> ${TARGET_IP} (var ${EXISTING_IP})..."
    curl -sf -u "${SIMPLY_ACCOUNT}:${SIMPLY_API_KEY}" \
        -X PUT "${API_URL}${EXISTING_ID}" \
        -H "Content-Type: application/json" \
        -d "$BODY" -o /dev/null
fi

echo "==> Klar."
