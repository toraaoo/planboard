"""Capture the web app in light and dark for the README.

    uv run --with playwright python docs/demo/screenshots.py <url> <out-dir>

<url> is a running `planboard serve` on the demo workspace. Set CHROMIUM to use an
installed Chromium instead of the one `playwright install chromium` downloads.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PLAN = "/#/plan/api/rate-limiting"

# name, route, viewport height, element scrolled to just below the sticky header
SHOTS = [
    ("board", f"{PLAN}?view=board", 850, None),
    ("document", PLAN, 820, "#section-design"),
    ("graph", f"{PLAN}?view=graph", 820, "[aria-label='Plan views']"),
]


def main(url: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM"))
        for scheme in ("light", "dark"):
            for name, route, height, selector in SHOTS:
                context = browser.new_context(
                    viewport={"width": 1280, "height": height},
                    device_scale_factor=2,
                    color_scheme=scheme,
                )
                page = context.new_page()
                page.goto(url + route, wait_until="networkidle")
                page.wait_for_timeout(1500)
                if selector:
                    page.locator(selector).first.evaluate(
                        "el => window.scrollTo(0,"
                        " el.getBoundingClientRect().top + window.scrollY - 90)"
                    )
                    page.wait_for_timeout(800)
                page.screenshot(path=out / f"{name}-{scheme}.png")
                context.close()
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/"), Path(sys.argv[2]))
