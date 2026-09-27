#!/usr/bin/env bash
# Smoke test against a running stack (docker compose up).
#
# Unit tests prove each piece works; this proves the assembled system does:
# the image builds, migrations run, web reaches Postgres, and a job travels
# web -> Redis -> worker -> Postgres. It walks one happy path end to end.
#
# Usage: scripts/smoke_test.sh [base_url]   (default http://localhost:8000)
set -euo pipefail

BASE="${1:-http://localhost:8000}/api"
RUN_ID="$(date +%s)"  # unique usernames so the script can be re-run
PASSWORD="Smoke-test-pass-1"

json() { python3 -c "import sys, json; print(json.load(sys.stdin)$1)"; }

call() {  # call METHOD PATH TOKEN [JSON_BODY] -> prints body, fails on 4xx/5xx
  local method=$1 path=$2 token=$3 body=${4:-}
  curl -sS --fail-with-body -X "$method" "$BASE$path" \
    -H "Content-Type: application/json" \
    ${token:+-H "Authorization: Bearer $token"} \
    ${body:+-d "$body"}
}

step() { echo "==> $*"; }

step "health"
call GET /health/ "" | grep -q '"db": "ok"'

step "register provider + customer, log in"
for role in provider customer; do
  call POST /auth/register/ "" \
    "{\"username\":\"smoke_${role}_$RUN_ID\",\"email\":\"${role}_$RUN_ID@smoke.test\",\"password\":\"$PASSWORD\",\"role\":\"$role\"}" >/dev/null
done
login() { call POST /auth/token/ "" "{\"username\":\"smoke_$1_$RUN_ID\",\"password\":\"$PASSWORD\"}" | json "['access']"; }
PROVIDER=$(login provider)
CUSTOMER=$(login customer)
PROVIDER_ID=$(call GET /auth/me/ "$PROVIDER" | json "['id']")

step "provider creates a slot"
START=$(date -u -d "+$((RUN_ID % 1000 + 1)) days" +%Y-%m-%dT10:00:00Z)
END=$(date -u -d "+$((RUN_ID % 1000 + 1)) days" +%Y-%m-%dT11:00:00Z)
SLOT=$(call POST /slots/ "$PROVIDER" "{\"start_time\":\"$START\",\"end_time\":\"$END\"}" | json "['id']")

step "customer books it; provider confirms and completes"
BOOKING=$(call POST /bookings/ "$CUSTOMER" "{\"slot\":$SLOT}" | json "['id']")
call PATCH "/bookings/$BOOKING/" "$PROVIDER" '{"status":"confirmed"}' >/dev/null
call PATCH "/bookings/$BOOKING/" "$PROVIDER" '{"status":"completed"}' >/dev/null

step "customer reviews"
call POST "/bookings/$BOOKING/review/" "$CUSTOMER" '{"rating":5,"comment":"smoke test"}' >/dev/null

step "RBAC: customer can't create slots (expect 403)"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/slots/" -H "Authorization: Bearer $CUSTOMER")
[ "$code" = "403" ] || { echo "expected 403, got $code"; exit 1; }

step "summarise: web -> Redis queue -> worker -> Postgres"
SUMMARY=$(call POST "/providers/$PROVIDER_ID/summarise/" "$PROVIDER" | json "['id']")
for _ in $(seq 1 30); do
  STATUS=$(call GET "/summaries/$SUMMARY/" "$PROVIDER" | json "['status']")
  [ "$STATUS" = "done" ] && break
  [ "$STATUS" = "failed" ] && { echo "summary job failed"; exit 1; }
  sleep 1
done
[ "$STATUS" = "done" ] || { echo "summary still '$STATUS' after 30s: is the worker running?"; exit 1; }
call GET "/summaries/$SUMMARY/" "$PROVIDER" | json "['summary']"

echo "SMOKE TEST PASSED"
