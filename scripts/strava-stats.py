#!/usr/bin/env python3
"""
strava-stats.py
Fetches athlete stats from Strava using the Strava API.
Requires: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN
(Or can work with a read-only access token)

Usage:
    python3 strava-stats.py --summary
    python3 strava-stats.py --activities --limit 10
    python3 strava-stats.py --plan  # Plan training for upcoming race
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN", "")
ATHLETE_ID    = "148255713"  # Badr's Strava ID
ACCESS_TOKEN  = os.getenv("STRAVA_ACCESS_TOKEN", "")

BASE_URL      = "https://www.strava.com/api/v3"

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def log(msg, color=""):
    print(f"{color}[strava]{RESET} {msg}")

# ── Auth ─────────────────────────────────────────────────────────────────────

def get_access_token():
    """Refresh or return existing access token."""
    if ACCESS_TOKEN:
        return ACCESS_TOKEN

    if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
        return None

    import urllib.request, urllib.parse

    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }).encode()

    req = urllib.request.Request(
        "https://www.strava.com/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            token_data = json.loads(r.read())
            return token_data.get("access_token")
    except Exception as e:
        log(f"Token refresh failed: {e}", RED)
        return None

# ── API helpers ───────────────────────────────────────────────────────────────

def strava_get(endpoint, params=None):
    """Make authenticated GET request to Strava API."""
    token = get_access_token()
    if not token:
        return {"error": "No access token. Set STRAVA_ACCESS_TOKEN env var or configure OAuth."}

    import urllib.request, urllib.parse

    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()}"}


def get_athlete():
    """Get athlete profile."""
    return strava_get("athlete")


def get_activities(limit=10, after=None):
    """Get recent activities."""
    params = {"per_page": min(limit, 200)}
    if after:
        params["after"] = after
    return strava_get("athlete/activities", params)


def get_stats(athlete_id=ATHLETE_ID):
    """Get athlete stats (requires token with 'read' scope)."""
    return strava_get(f"athletes/{athlete_id}/stats")


# ── Formatters ────────────────────────────────────────────────────────────────

def format_distance(meters):
    """Convert meters to km."""
    return f"{meters/1000:.1f} km"


def format_duration(seconds):
    """Convert seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def format_pace(seconds_per_km):
    """Convert seconds/km to min:sec/km."""
    m = int(seconds_per_km // 60)
    s = int(seconds_per_km % 60)
    return f"{m}:{s:02d} /km"


SPORTS_EMOJI = {
    "Run": "🏃", "Ride": "🚴", "Swim": "🏊",
    "Trail Run": "🏔️", "Walk": "🚶", "Workout": "💪",
    "Triathlon": "🏊🚴🏃", "Virtual Ride": "🚴"
}

def activity_summary(act):
    """Format a single activity as a one-liner."""
    sport = act.get("type", "Activity")
    emoji = SPORTS_EMOJI.get(sport, "•")
    dist = format_distance(act.get("distance", 0))
    dur = format_duration(act.get("moving_time", 0))
    date = act.get("start_date_local", "")[:10]
    name = act.get("name", "Activity")
    # Pace for runs
    pace = ""
    if sport == "Run" and act.get("average_speed"):
        pace = f" | {format_pace(1/act['average_speed'])}"
    return f"  {emoji} {date} — {name[:40]}\n     {dist} | {dur}{pace}"


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_summary():
    """Show athlete summary."""
    log("Fetching athlete profile...")
    athlete = get_athlete()

    if "error" in athlete:
        log(f"Error: {athlete['error']}", RED)
        log("To fix: Set STRAVA_ACCESS_TOKEN, or configure OAuth (STRAVA_CLIENT_ID + CLIENT_SECRET + REFRESH_TOKEN)", YELLOW)
        return 1

    name = f"{athlete.get('firstname','')} {athlete.get('lastname','')}"
    print(f"\n{BOLD}{'═'*50}{RESET}")
    print(f"  🏃 {BOLD}{name}{RESET} | @{athlete.get('username','?')}")
    print(f"  📍 {athlete.get('city','?')}, {athlete.get('country','?')}")
    print(f"  ⭐ {athlete.get('follower_count',0)} followers | {athlete.get('following_count',0)} following")
    print(f"  🏆 {athlete.get('total_athlete_count',0)} athletes followed")
    print(f"{'═'*50}\n")

    return 0


def cmd_activities(limit=10):
    """Show recent activities."""
    log(f"Fetching last {limit} activities...")
    after = (datetime.now() - timedelta(days=90)).timestamp()
    acts = get_activities(limit=limit, after=int(after))

    if "error" in acts:
        log(f"Error: {acts['error']}", RED)
        return 1

    if not acts:
        log("No activities found.", YELLOW)
        return 0

    print(f"\n{BOLD}Recent Activities{RESET} (last {len(acts)})\n")
    for act in acts[:limit]:
        print(activity_summary(act))
    print()
    return 0


def cmd_stats():
    """Show yearly stats."""
    log("Fetching stats...")
    stats = get_stats()

    if "error" in stats:
        log(f"Error: {stats['error']}", RED)
        return 1

    print(f"\n{BOLD}All-Time & Recent Stats{RESET}\n")

    def stat_row(label, val):
        print(f"  {label:30} {BOLD}{val}{RESET}")

    y = stats.get("ytd_", {})
    a = stats.get("all_", {})

    print(f"  {CYAN}This Year (YTD){RESET}")
    stat_row("Distance", f"{format_distance(y.get('distance', 0))}")
    stat_row("Activities", f"{y.get('count', 0)}")
    stat_row("Moving time", f"{format_duration(y.get('moving_time', 0))}")

    print(f"\n  {CYAN}All Time{RESET}")
    stat_row("Distance", format_distance(a.get('distance', 0)))
    stat_row("Activities", f"{a.get('count', 0)}")
    stat_row("Moving time", format_duration(a.get('moving_time', 0)))

    # Recent runs
    recent_runs = y.get("recent_runs_totals", {})
    if recent_runs:
        print(f"\n  {CYAN}Recent Runs (last 4 weeks){RESET}")
        stat_row("Distance", format_distance(recent_runs.get('distance', 0)))
        stat_row("Count", f"{recent_runs.get('count', 0)}")

    # Recent rides
    recent_rides = y.get("recent_rides_totals", {})
    if recent_rides:
        print(f"\n  {CYAN}Recent Rides (last 4 weeks){RESET}")
        stat_row("Distance", format_distance(recent_rides.get('distance', 0)))
        stat_row("Count", f"{recent_rides.get('count', 0)}")

    print()
    return 0


def cmd_plan(race_date_str="2026-05-17", race_type="Triathlon M"):
    """Plan training leading up to a race."""
    from datetime import date

    race_date = date.fromisoformat(race_date_str)
    today = date.today()
    days_left = (race_date - today).days

    if days_left < 0:
        log(f"Race date {race_date} is in the past!", RED)
        return 1

    log(f"Race: {race_type} on {race_date} — {days_left} days away")

    print(f"""
{BOLD}╔══════════════════════════════════════════════════╗
║         TRAINING PLAN — {days_left} DAYS OUT              ║
╠══════════════════════════════════════════════════╣
║  Race: {race_type:<38} ║
║  Date: {str(race_date):<38} ║
╚══════════════════════════════════════════════════╝{RESET}

  Weeks: ~{days_left // 7} weeks + {days_left % 7} days

  Recommended structure:
  • Weeks 1-2 (Base):    Low volume, focus on swim technique
  • Weeks 3-5 (Build):   +20% volume/week, brick workouts
  • Weeks 6-8 (Peak):    Race-pace intervals, race simulation
  • Weeks 9+ (Taper):    Reduce volume 50%, maintain intensity

  Key sessions per week:
  🏊 Swim: 2-3x (technique drills + threshold)
  🚴 Bike: 2-3x (FTP intervals + long ride weekend)
  🏃 Run:  3-4x (tempo + long run + easy runs)
  💪 Strength: 1-2x (mobility + core)

  Race pace targets (to fill in after testing):
  • Swim 1.5km:    ___:___ /100m
  • Bike 40km:    ___:___ avg speed
  • Run 10km:     ___:___ /km

  Note: This is a template. Fill in your actual
  test results (CP, threshold pace, 100m pace)
  and I can generate a personalized plan.
""")
    return 0


def cmd_sync():
    """Sync activities to local JSON file."""
    log("Syncing recent activities...")
    after = (datetime.now() - timedelta(days=30)).timestamp()
    acts = get_activities(limit=50, after=int(after))

    if "error" in acts:
        log(f"Error: {acts['error']}", RED)
        return 1

    outfile = Path(__file__).parent.parent / "memory" / "strava-recent.json"
    outfile.parent.mkdir(exist_ok=True)

    # Save condensed version
    condensed = []
    for act in acts:
        condensed.append({
            "date": act.get("start_date_local", "")[:10],
            "type": act.get("type"),
            "name": act.get("name"),
            "distance_m": act.get("distance"),
            "moving_time_s": act.get("moving_time"),
            "avg_speed_ms": act.get("average_speed"),
            "elevation_m": act.get("total_elevation_gain"),
            "avg_hr": act.get("average_heartrate"),
            "max_hr": act.get("max_heartrate"),
            "kudos": act.get("kudos_count", 0),
            "url": act.get("url", ""),
        })

    outfile.write_text(json.dumps(condensed, indent=2))
    log(f"✓ Synced {len(condensed)} activities → {outfile}", GREEN)
    return 0


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Strava stats & training tool")
    parser.add_argument("--summary", action="store_true", help="Show athlete profile")
    parser.add_argument("--activities", action="store_true", help="Show recent activities")
    parser.add_argument("--stats", action="store_true", help="Show yearly stats")
    parser.add_argument("--sync", action="store_true", help="Sync to local JSON")
    parser.add_argument("--plan", action="store_true", help="Plan training")
    parser.add_argument("--race-date", default="2026-05-17", help="Race date (YYYY-MM-DD)")
    parser.add_argument("--race-type", default="Triathlon M", help="Race type")
    parser.add_argument("--limit", type=int, default=10, help="Number of activities")
    args = parser.parse_args()

    # If no args, show summary
    if len(sys.argv) == 1:
        args.summary = True

    if args.activities:
        return cmd_activities(limit=args.limit)
    elif args.stats:
        return cmd_stats()
    elif args.sync:
        return cmd_sync()
    elif args.plan:
        return cmd_plan(race_date_str=args.race_date, race_type=args.race_type)
    else:
        return cmd_summary()

if __name__ == "__main__":
    sys.exit(main())
