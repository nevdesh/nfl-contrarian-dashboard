import os
import json
import base64
import gzip
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

DATA_URL = os.getenv("DATA_URL", "https://data.vsin.com/betting-splits/?source=DK&sport=NFL")
STATE_B64 = os.getenv("PLAYWRIGHT_STORAGE_STATE_B64", "")
LOGIN_MARKERS = [x.strip().lower() for x in os.getenv("LOGIN_URL_MARKERS", "login,signin,sign-in").split(",") if x.strip()]
OUT = Path("captures")
OUT.mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

if not STATE_B64:
    raise RuntimeError("Missing PLAYWRIGHT_STORAGE_STATE_B64 GitHub secret")

state_path = Path("/tmp/vsin-storage-state.json")
decoded_state = base64.b64decode(STATE_B64, validate=True)
if decoded_state.startswith(b"\x1f\x8b"):
    decoded_state = gzip.decompress(decoded_state)
# Validate the decoded state before handing it to Playwright.
state_data = json.loads(decoded_state.decode("utf-8"))
if not isinstance(state_data, dict) or "cookies" not in state_data:
    raise RuntimeError("Decoded session is not a valid Playwright storage state")
state_path.write_bytes(decoded_state)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(state_path))
    page = context.new_page()
    try:
        response = page.goto(DATA_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        text = page.locator("body").inner_text(timeout=20000)
        url = page.url
        parsed = urlparse(url.lower())
        lower = text.lower()

        login_redirect = (
            any(marker in parsed.path for marker in LOGIN_MARKERS)
            or ("input" in lower and "password" in lower and ("sign in" in lower or "log in" in lower))
        )
        if login_redirect:
            raise RuntimeError("Authentication appears expired or redirected to login. Refresh the saved session.")
        if response and response.status >= 400:
            raise RuntimeError(f"Page returned HTTP {response.status}")
        if "handle" not in lower or "nfl" not in lower:
            raise RuntimeError("Expected NFL/Handle content not found; page may be blocked, logged out, or changed.")

        page.screenshot(path=str(OUT / f"vsin-{stamp}.png"), full_page=True)
        (OUT / f"vsin-{stamp}.txt").write_text(text, encoding="utf-8")

        tables_out = []
        tables = page.locator("table")
        for i in range(min(tables.count(), 80)):
            rows = tables.nth(i).locator("tr")
            row_data = []
            for j in range(min(rows.count(), 500)):
                cells = rows.nth(j).locator("th,td")
                values = [cells.nth(k).inner_text().strip() for k in range(cells.count())]
                if values:
                    row_data.append(values)
            if row_data:
                tables_out.append({"table_index": i, "rows": row_data})
        (OUT / f"vsin-{stamp}-tables.json").write_text(
            json.dumps(tables_out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        status = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "status": "captured_needs_parser_validation",
            "url": url,
            "http_status": response.status if response else None,
            "html_tables_found": len(tables_out),
            "visible_text_characters": len(text),
            "note": "Capture only. Inspect artifact before enabling automated pick generation."
        }
        (OUT / f"vsin-{stamp}-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        print(json.dumps(status, indent=2))
    except Exception as exc:
        try:
            page.screenshot(path=str(OUT / f"vsin-{stamp}-failure.png"), full_page=True)
            (OUT / f"vsin-{stamp}-failure.txt").write_text(page.locator("body").inner_text(timeout=5000), encoding="utf-8")
        except Exception:
            pass
        print(f"SCRAPE_FAILED: {exc}")
        raise
    finally:
        context.close()
        browser.close()
