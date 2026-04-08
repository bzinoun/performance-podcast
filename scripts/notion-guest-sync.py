#!/usr/bin/env python3
"""
notion-guest-sync.py
Syncs guest research data to Notion Guest Tracker database.
Reads from guests-research-2026-04-08.md and creates/updates Notion pages.

Usage: python3 notion-guest-sync.py [--dry-run] [--debug]
"""

import os
import re
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
# Load from environment (recommended)
# Set NOTION_API_KEY in your shell profile or .env file
NOTION_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_VERSION = "2025-09-03"
GUEST_DB_ID = "d722f66b-3030-45de-8297-1e0b994fa340"
GUESTS_FILE = Path(__file__).parent.parent / "memory" / "guests-research-2026-04-08.md"
BASE_URL = "https://api.notion.com/v1"

# ── Colors ──────────────────────────────────────────────────────────────────
ORANGE  = "\033[95m"   # pink-ish (closest available)
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
RESET   = "\033[0m"
BOLD    = "\033[1m"

def log(msg, color=""):
    print(f"{color}[{datetime.now().strftime('%H:%M:%S')}]{RESET} {msg}")

def section(msg):
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{msg}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

# ── Notion API helpers ───────────────────────────────────────────────────────

def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def notion_get(endpoint, params=None):
    import urllib.request, urllib.parse
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=notion_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()}

def notion_post(endpoint, data):
    import urllib.request
    url = f"{BASE_URL}/{endpoint}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=notion_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            body = json.loads(body)
        except:
            pass
        return None, {"code": e.code, "body": body}

def notion_patch(endpoint, data):
    import urllib.request
    url = f"{BASE_URL}/{endpoint}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.urlopen(
        urllib.request.Request(url, data=payload, headers=notion_headers(), method="PATCH"),
        timeout=15
    )
    return json.loads(req.read())

def create_guest_page(guest):
    """Create a Notion page for a guest."""
    name = guest.get("name", "Unknown")
    role = guest.get("role", "")
    company = guest.get("company", "")
    sport = guest.get("sport", [])
    level = guest.get("level", "Amateur")
    priority = guest.get("priority", "Warm")
    email = guest.get("email", "")
    linkedin = guest.get("linkedin", "")
    source = guest.get("source", "")
    notes = guest.get("notes", "")

    payload = {
        "parent": {"database_id": GUEST_DB_ID},
        "properties": {
            "Guest Name": {"title": [{"text": {"content": name}}]},
            "Role": {"rich_text": [{"text": {"content": role}}]},
            "Company": {"rich_text": [{"text": {"content": company}}]},
            "Level": {"select": {"name": level}},
            "Contact Status": {"select": {"name": "Identified"}},
            "Priority": {"select": {"name": priority}},
            "Source": {"rich_text": [{"text": {"content": source}}]},
            "Notes": {"rich_text": [{"text": {"content": notes}}]},
        }
    }

    if sport:
        payload["properties"]["Sport"] = {
            "multi_select": [{"name": s} for s in sport if s]
        }
    if email:
        payload["properties"]["Email"] = {"email": email}
    if linkedin:
        payload["properties"]["LinkedIn"] = {"url": linkedin}

    result, err = notion_post("pages", payload)
    if err:
        return None, f"HTTP {err['code']}"
    return result.get("id", "unknown"), None

# ── Parser ───────────────────────────────────────────────────────────────────

def parse_guests_file(filepath):
    """Parse the guests research markdown file into structured dicts."""
    if not filepath.exists():
        return [], f"File not found: {filepath}"

    content = filepath.read_text(encoding="utf-8")
    guests = []

    # Split by ## or ### headings (guest names)
    sections = re.split(r"\n(?=##?\s+)", content)

    current = {}
    for section_text in sections:
        lines = section_text.strip().split("\n")
        if not lines:
            continue

        # Detect if this is a guest entry (starts with # or contains known fields)
        is_guest = False
        for line in lines:
            line = line.strip()
            if re.match(r"^##?\s+\w", line) and len(line) < 100:
                if any(kw in line.lower() for kw in ["nom", "name", "guest", "invité", "athlète"]):
                    is_guest = True
                elif not line.startswith("#"):
                    # Plain text might be name
                    pass
            if any(line.startswith(f"{k}:") or line.startswith(f"**{k}**") for k in
                    ["Nom", "Name", "Email", "LinkedIn", "Sport", "Company", "Role", "Poste"]):
                is_guest = True

        if not is_guest:
            # Try to extract from lines that look like guest data
            pass

        # Parse fields from lines
        guest = {}
        for line in lines:
            line = line.strip().lstrip("*-• ").rstrip(",;")
            for prefix, key in [
                ("Nom:", "name"), ("Name:", "name"),
                ("Poste:", "role"), ("Role:", "role"), ("Title:", "role"),
                ("Entreprise:", "company"), ("Company:", "company"),
                ("Email:", "email"), ("Mail:", "email"),
                ("LinkedIn:", "linkedin"), ("Linkedin:", "linkedin"),
                ("Sport:", "sport_raw"), ("Sports:", "sport_raw"),
                ("Niveau:", "level"), ("Level:", "level"),
                ("Priorité:", "priority"), ("Priority:", "priority"),
                ("Source:", "source"),
                ("Notes:", "notes"),
            ]:
                if line.startswith(prefix) or line.startswith(f"**{prefix}"):
                    val = line[len(prefix):].strip().strip("**").strip()
                    if key == "sport_raw":
                        sports = [s.strip().capitalize() for s in re.split(r"[,;+&/]", val) if s.strip()]
                        guest["sport"] = sports
                    elif val and val != "—":
                        guest[key] = val

        if "name" in guest and guest.get("name"):
            # Clean level field
            if "level" not in guest:
                guest["level"] = "Amateur"
            # Default priority
            if "priority" not in guest:
                guest["priority"] = "Warm"
            guests.append(guest)

    return guests, None

# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync guests to Notion")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    parser.add_argument("--debug", action="store_true", help="Verbose output")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of guests to process (0=all)")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}═══ notion-guest-sync ═══{RESET}")
    print(f"File:   {YELLOW}{GUESTS_FILE}{RESET}")
    print(f"DB:     {YELLOW}{GUEST_DB_ID}{RESET}")
    print(f"Dry run: {YELLOW}{args.dry_run}{RESET}\n")

    # Parse guests
    guests, err = parse_guests_file(GUESTS_FILE)
    if err:
        log(f"{RED}Parse error: {err}{RESET}", RED)
        return 1

    log(f"Found {GREEN}{len(guests)}{RESET} guests in research file")

    if args.limit > 0:
        guests = guests[:args.limit]
        log(f"Limited to {YELLOW}{len(guests)}{RESET} guests")

    if args.dry_run:
        log(f"{YELLOW}DRY RUN — would create {len(guests)} pages:{RESET}")
        for i, g in enumerate(guests, 1):
            print(f"  {i}. {BOLD}{g.get('name','?')}{RESET} | {g.get('role','?')} @ {g.get('company','?')}")
            print(f"     Sport: {', '.join(g.get('sport', []))} | Level: {g.get('level','?')} | Priority: {g.get('priority','?')}")
            if g.get('email'): print(f"     Email: {g.get('email')}")
            if g.get('linkedin'): print(f"     LinkedIn: {g.get('linkedin')}")
            print()
        return 0

    section("Creating Notion pages")
    success = 0
    errors = []

    for i, guest in enumerate(guests, 1):
        name = guest.get("name", "?")
        log(f"[{i}/{len(guests)}] Creating: {BOLD}{name}{RESET}")

        page_id, err = create_guest_page(guest)
        if err:
            log(f"  {RED}✗ Error: {err}{RESET}", RED)
            errors.append({"guest": name, "error": err})
        else:
            short_id = page_id[:8] if page_id else "?"
            log(f"  {GREEN}✓ Created: ...{short_id}{RESET}", GREEN)
            success += 1

        time.sleep(0.6)  # Rate limit

    section("Results")
    log(f"{GREEN}Created: {success}/{len(guests)}{RESET}")
    if errors:
        log(f"{RED}Errors: {len(errors)}{RESET}")
        for e in errors:
            print(f"  - {e['guest']}: {e['error']}")
    else:
        log(f"{GREEN}All pages created successfully!{RESET}", GREEN)

    # Save sync log
    log_path = Path(__file__).parent.parent / "memory" / f"sync-log-{datetime.now().strftime('%Y-%m-%d')}.json"
    log_data = {
        "date": datetime.now().isoformat(),
        "total": len(guests),
        "created": success,
        "errors": errors
    }
    log_path.write_text(json.dumps(log_data, indent=2))
    log(f"Sync log: {YELLOW}{log_path}{RESET}")

    return 0 if not errors else 1

if __name__ == "__main__":
    exit(main())
