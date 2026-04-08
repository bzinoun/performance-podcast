#!/usr/bin/env python3
"""
linkedin-data.py
Extracts public profile data from a LinkedIn profile URL.
Uses LinkedIn's public data (no authentication required for basic info).

Usage:
    python3 linkedin-data.py "https://www.linkedin.com/in/username"
    python3 linkedin-data.py --interactive
"""

import sys
import json
import re
import argparse
from pathlib import Path

# Try to import requests; fall back to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.parse
    import urllib.error
    HAS_REQUESTS = False

# ── Config ───────────────────────────────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
LINKEDIN_PUBLIC_URL = "https://www.linkedin.com/in/"

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def log(msg, color=""):
    print(f"{color}[linkedin-data]{RESET} {msg}")

def extract_profile_data(url: str) -> dict:
    """
    Fetch and extract public profile data from LinkedIn.
    Note: LinkedIn heavily restricts scraping. This uses public-facing
    data only and respects LinkedIn's ToS. For full data, use LinkedIn API.
    """

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }

    log(f"Fetching profile: {url}", CYAN)

    try:
        if HAS_REQUESTS:
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        else:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                response = r

        status = response.status_code if HAS_REQUESTS else response.getcode()
        content = response.text if HAS_REQUESTS else response.read().decode("utf-8")

        log(f"HTTP {status}", YELLOW if status == 200 else RED)

        if status != 200:
            return {"error": f"HTTP {status}", "url": url}

        # Extract data using regex patterns
        data = {
            "url": url,
            "status": "ok",
            "name": extract_field(content, r'"firstName"\s*:\s*"([^"]+)"'),
            "lastName": extract_field(content, r'"lastName"\s*:\s*"([^"]+)"'),
            "headline": extract_field(content, r'"headline"\s*:\s*"([^"]+)"'),
            "occupation": extract_field(content, r'"occupation"\s*:\s*"([^"]+)"'),
            "profile_id": extract_field(content, r'"memberId"\s*:\s*"([^"]+)"'),
        }

        # Also try Open Graph tags
        data["og_title"] = extract_meta(content, "og:title")
        data["og_description"] = extract_meta(content, "og:description")
        data["og_image"] = extract_meta(content, "og:image")

        # Skills section (partial)
        skills = re.findall(r'"skillName"\s*:\s*"([^"]+)"', content)
        if skills:
            data["skills"] = skills[:15]  # Limit to 15

        # Clean None values
        data = {k: v for k, v in data.items() if v and v != "null"}

        # Format full name
        if data.get("name") or data.get("lastName"):
            data["full_name"] = f"{data.get('name', '')} {data.get('lastName', '')}".strip()

        return data

    except Exception as e:
        return {"error": str(e), "url": url}


def extract_field(html: str, pattern: str) -> str:
    """Extract first regex match group, or empty string."""
    try:
        match = re.search(pattern, html)
        return match.group(1).strip() if match else ""
    except:
        return ""


def extract_meta(html: str, property: str) -> str:
    """Extract Open Graph meta tag content."""
    pattern = f'<meta property="{property}" content="([^"]+)"'
    match = re.search(pattern, html)
    if match:
        return match.group(1).strip()
    # Try alternate
    pattern2 = f'<meta name="{property}" content="([^"]+)"'
    match2 = re.search(pattern2, html)
    return match2.group(1).strip() if match2 else ""


def format_for_notion(data: dict) -> dict:
    """Format extracted data as Notion page properties."""
    return {
        "LinkedIn": {"url": data.get("url", "")},
        "Occupation": {"rich_text": [{"text": {"content": data.get("occupation", data.get("headline", ""))}}]},
        "Notes": {"rich_text": [
            {"text": {"content": f"LinkedIn: {data.get('url','')}"}},
            {"text": {"content": f"Headline: {data.get('headline','')}"}},
            {"text": {"content": f"Skills: {', '.join(data.get('skills', []))}"}},
        ]}
    }


def interactive_mode():
    """Prompt for LinkedIn URL and extract."""
    print(f"\n{BOLD}LinkedIn Profile Extractor{RESET}")
    print(f"{'─'*40}")
    print("Enter a LinkedIn profile URL (or 'q' to quit):\n")

    while True:
        try:
            url = input("URL> ").strip()
            if url.lower() in ["q", "quit", "exit"]:
                break
            if not url:
                continue
            if "linkedin.com/in/" not in url:
                url = LINKEDIN_PUBLIC_URL + url if url else ""
                if "linkedin.com/in/" not in url:
                    print(f"{RED}Invalid URL. Must contain 'linkedin.com/in/'.{RESET}")
                    continue

            data = extract_profile_data(url)

            if "error" in data and data.get("status") != "ok":
                print(f"{RED}Error: {data['error']}{RESET}")
                continue

            print(f"\n{GREEN}✓ Profile extracted:{RESET}")
            print(f"  Name:       {BOLD}{data.get('full_name', '?')}{RESET}")
            print(f"  Headline:   {data.get('headline', '?')}")
            print(f"  Occupation: {data.get('occupation', '?')}")
            if data.get("skills"):
                print(f"  Skills:     {', '.join(data.get('skills', [])[:8])}")
            print()

            # Option to export as JSON
            save = input("Save as JSON? [y/N] ").strip().lower()
            if save == "y":
                outfile = f"/tmp/linkedin-{data.get('full_name','profile').replace(' ','-')}.json"
                Path(outfile).write_text(json.dumps(data, indent=2))
                print(f"{GREEN}Saved: {outfile}{RESET}\n")

        except (KeyboardInterrupt, EOFError):
            break

    print("\nDone.")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract LinkedIn public profile data")
    parser.add_argument("url", nargs="?", help="LinkedIn profile URL")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--format", choices=["text", "json", "notion"], default="text",
                        help="Output format")
    parser.add_argument("--output", "-o", help="Output file")
    args = parser.parse_args()

    if args.interactive or not args.url:
        interactive_mode()
        return 0

    url = args.url
    if "linkedin.com/in/" not in url:
        url = LINKEDIN_PUBLIC_URL + url

    data = extract_profile_data(url)

    if args.format == "json":
        output = json.dumps(data, indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"Saved to {args.output}")
        else:
            print(output)
    elif args.format == "notion":
        formatted = format_for_notion(data)
        print(json.dumps(formatted, indent=2))
    else:
        # Text format
        print(f"\n{BOLD}{'─'*50}{RESET}")
        print(f"{BOLD}LinkedIn Profile{RESET}")
        print(f"{'─'*50}")
        for key, val in data.items():
            if key == "skills" and val:
                val = ", ".join(val[:10])
            print(f"  {key.capitalize():15} {val}")
        print(f"{'─'*50}\n")

    return 0 if "error" not in data else 1


if __name__ == "__main__":
    sys.exit(main())
