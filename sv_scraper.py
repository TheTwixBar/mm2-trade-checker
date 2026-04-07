import os
import re
import time
import base64
import requests
from bs4 import BeautifulSoup

#github config.
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "YOUR_TOKEN_HERE")
GITHUB_REPO   = "TheTwixBar/mm2-trade-checker"
GITHUB_PATH   = "data_txt/mm2values.txt"
GITHUB_BRANCH = "main"


BASE_URL = "https://supremevalues.com/mm2/"

CATEGORIES = [
    "godlies",
    "chromas",
    "ancients",
    "uniques",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Local output folder
OUT_DIR = os.path.join(
    os.path.expanduser("~"), "Desktop", "MM2TradeChecker", "data_txt"
)


def fetch_page(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_items(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        cells = rows[0].find_all("td")
        if len(cells) < 2:
            continue

        img_cell = cells[0]
        stat_cell = cells[1]

        # scrape name
        img = img_cell.find("img")
        if not img:
            continue
        raw_name = img.get("alt", "").strip()
        if not raw_name:
            continue
        name = re.sub(r"\s*\(.*?\)\s*$", "", raw_name).strip()

        # Get clean text from the stat cell
        stat_text = stat_cell.get_text(separator=" ").replace("\xa0", " ")
        stat_text = re.sub(r"\s+", " ", stat_text).strip()

        # value
        m = re.search(r"Value\s*[-–]\s*\*?\*?([\d,]+)\*?\*?", stat_text)
        value = m.group(1).replace(",", "") if m else "N/A"

        # ranged value
        m = re.search(r"Ranged Value\s*[-–]\s*\[?\*?\*?([\d,]+\s*-\s*[\d,]+|N/A)\*?\*?\]?", stat_text)
        if m and m.group(1) != "N/A":
            ranged = re.sub(r"\s*-\s*", "-", m.group(1)).replace(",", "")
        else:
            ranged = "N/A"

        # stability
        m = re.search(r"Stability\s*[-–]\s*\*?\*?([A-Za-z ]+?)\*?\*?(?:\s+Item Stability|\s+Demand|$)", stat_text)
        stability = m.group(1).strip() if m else "N/A"

        # demand
        m = re.search(r"Demand\s*[-–]\s*\*?\*?(\d+)\*?\*?", stat_text)
        demand = m.group(1) if m else "N/A"

        # rarity
        m = re.search(r"Rarity\s*[-–]\s*\*?\*?(\d+)\*?\*?", stat_text)
        rarity = m.group(1) if m else "N/A"

        items.append({
            "name":      name,
            "value":     value,
            "range":     ranged,
            "demand":    demand,
            "rarity":    rarity,
            "stability": stability,
        })

    return items


def format_items(items):
    sep = "-" * 40
    lines = []
    for item in items:
        lines.append(f"Name: {item['name']}")
        lines.append(f"Value: {item['value']}")
        lines.append(f"Range: {item['range']}")
        lines.append(f"Demand: {item['demand']}")
        lines.append(f"Rarity: {item['rarity']}")
        lines.append(f"Stability: {item['stability']}")
        lines.append(sep)
    return "\n".join(lines) + "\n"


def push_to_github(content: str):
    """Push content to GitHub using the REST API. Creates or updates the file."""

    if GITHUB_TOKEN == "YOUR_TOKEN_HERE":
        print("\n  Skipping GitHub push — no token set in GITHUB_TOKEN.")
        return

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    gh_headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    # see if file exists
    sha = None
    check = requests.get(api_url, headers=gh_headers, params={"ref": GITHUB_BRANCH})
    if check.status_code == 200:
        sha = check.json().get("sha")

    # encode 64
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": "chore: update mm2values.txt via scraper",
        "content": encoded,
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha  # required when updating an existing file

    resp = requests.put(api_url, headers=gh_headers, json=payload)

    if resp.status_code in (200, 201):
        action = "updated" if sha else "created"
        print(f"  GitHub push successful — file {action}.")
    else:
        print(f"  GitHub push FAILED ({resp.status_code}): {resp.json().get('message', resp.text)}")


def main():
    all_items = []
    print(f"\nScraping {', '.join(CATEGORIES)} from supremevalues.com...\n")

    for cat in CATEGORIES:
        url = BASE_URL + cat
        print(f"  Fetching {cat}...", end=" ", flush=True)
        try:
            html = fetch_page(url)
            items = parse_items(html)
            # Uniques: only keep the first item (Corrupt)
            if cat == "uniques" and items:
                items = items[:1]
            all_items.extend(items)
            print(f"{len(items)} items found.")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.5)

    content = format_items(all_items)

    # Save locally
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "mm2values.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\nSaved locally: {out_path}")

    # Push to GitHub
    print("\nPushing to GitHub...", end=" ", flush=True)
    push_to_github(content)

    print(f"\nDone! {len(all_items)} total items.")


if __name__ == "__main__":
    main()
