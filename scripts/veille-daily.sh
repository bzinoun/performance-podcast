#!/usr/bin/env bash
# veille-daily.sh
# Automated daily tech/AI/startup veille → Telegram
# Runs via cron: 0 8 * * *  (8:00 AM GMT+1)
# Usage: ./veille-daily.sh [--test] [--compact]

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN="8434849806:AAGU54XM4esPw6bOiaOlx_0BH27mHdaY5E8"
TELEGRAM_USER_ID="5643887720"
SEARXNG_URL="http://localhost:8888"
SEARXNG_API="${SEARXNG_URL}/search"

# Topics to search
TOPICS=(
  "tech AI breakthrough 2026"
  "startup funding Morocco 2026"
  "new AI model release"
  "fintech Africa 2026"
  "marocain startup innovate 2026"
  "GitHub trending project"
  "architecture enterprise banking insurance"
)

# Output file for debug
LOGFILE="/tmp/veille-$(date +%Y%m%d).txt"
TEST_MODE=false
COMPACT=false

# ── Colors ────────────────────────────────────────────────────────────────────
ORANGE='\033[95m'
GREEN='\033[92m'
RED='\033[91m'
YELLOW='\033[93m'
CYAN='\033[96m'
RESET='\033[0m'

# ── Args ──────────────────────────────────────────────────────────────────────
for arg in "$@"; do
  case $arg in
    --test)    TEST_MODE=true ;;
    --compact) COMPACT=true ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────────────────
log() { echo -e "[$(date +%H:%M:%S)] $*" }

search_searxng() {
  local query="$1"
  local format="${2:-json}"
  curl -s --max-time 15 \
    "${SEARXNG_API}?q=${query}&format=${format}&engines=google,bing,duckduckgo&language=fr" \
    2>/dev/null || echo "{}"
}

format_telegram_message() {
  local topic="$1"
  local results="$2"
  local msg=""

  if [[ "$COMPACT" == "true" ]]; then
    msg="📰 <b>${topic}</b>\n"
    echo "$results" | jq -r '.results[:3] // [] | .[] | "* \(.title // "?"): \(.url // "")"' 2>/dev/null | head -5 | while read -r line; do
      msg+="• ${line}\n"
    done
  else
    msg="━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg+="📰 <b>Veille — ${topic}</b>\n"
    msg+="━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    local count=0
    echo "$results" | jq -r '.results // [] | .[] | @text "\(.title // "")\n\(.url // "")"' 2>/dev/null | while read -r title && read -r url; do
      [[ -z "$title" || "$title" == "null" ]] && continue
      ((count++)) || true
      [[ $count -gt 5 ]] && return
      # Truncate long titles
      title="${title:0:80}"
      msg+="▸ <code>${title}</code>\n"
      [[ -n "$url" && "$url" != "null" ]] && msg+="  ${url}\n"
      msg+="\n"
    done

    [[ $count -eq 0 ]] && msg+="(Aucun résultat)\n"
  fi

  echo "$msg"
}

send_telegram() {
  local message="$1"
  local max_len=4096
  # Split if too long
  local chunks=()
  while [[ ${#message} -gt $max_len ]]; do
    chunks+=("${message:0:$max_len}")
    message="${message:$max_len}"
  done
  chunks+=("$message")

  for chunk in "${chunks[@]}"; do
    curl -s --max-time 30 \
      -d "chat_id=${TELEGRAM_USER_ID}" \
      -d "text=${chunk}" \
      -d "parse_mode=HTML" \
      "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      | jq -r '.ok // false' >/dev/null 2>&1 || true
  done
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  log "${CYAN}═══ Veille Daily — $(date '+%Y-%m-%d %H:%M') ═══${RESET}"

  # Test SearXNG connectivity
  if curl -s --max-time 5 "${SEARXNG_URL}/health" | grep -q "ok"; then
    log "${GREEN}✓ SearXNG connected${RESET}"
  else
    log "${YELLOW}⚠ SearXNG not responding at ${SEARXNG_URL} — using direct search fallback${RESET}"
  fi

  if [[ "$TEST_MODE" == "true" ]]; then
    log "${YELLOW}TEST MODE — results will print, not send${RESET}\n"
  fi

  echo "" > "$LOGFILE"
  total_results=0

  for topic in "${TOPICS[@]}"; do
    log "Searching: ${topic}"

    # Search via SearXNG
    result=$(search_searxng "$topic")
    sleep 1  # Rate limit

    # Parse results (SearXNG returns JSON)
    count=$(echo "$result" | jq '.results | length' 2>/dev/null || echo "0")
    log "  Found: ${count} results"

    if [[ "$TEST_MODE" == "true" ]]; then
      echo "━━━ $topic ━━━" >> "$LOGFILE"
      echo "$result" | jq -r '.results[:5][] | "\(.title)\n\(.url)\n"' >> "$LOGFILE" 2>/dev/null
      echo "" >> "$LOGFILE"
    fi

    ((total_results+=count)) || true
  done

  log "${GREEN}✓ Search complete — ${total_results} total results${RESET}"

  # Send to Telegram
  header="━━━━━━━━━━━━━━━━━━━━━━━
🏃 <b>Veille Atlas — $(date '+%d/%m/%Y')</b>
<i>Tech • AI • Startup • Fintech • GitHub • Maroc</i>
━━━━━━━━━━━━━━━━━━━━━━━
"

  if [[ "$TEST_MODE" == "true" ]]; then
    echo ""
    log "${YELLOW}Would send Telegram message, skipping (test mode)${RESET}"
    log "Full results in: ${LOGFILE}"
    return 0
  fi

  log "Sending to Telegram..."
  send_telegram "$header"
  sleep 1

  # Send each topic summary
  for topic in "${TOPICS[@]}"; do
    result=$(search_searxng "$topic")
    msg=$(format_telegram_message "$topic" "$result")
    send_telegram "$msg"
    sleep 2
  done

  footer="
━━━━━━━━━━━━━━━━━━━━━━━
🤖 Atlas — veille automatique
📅 Prochain: demain 8h"
  send_telegram "$footer"

  log "${GREEN}✓ Veille sent to Telegram${RESET}"
}

# ── Run ───────────────────────────────────────────────────────────────────────
main "$@"
