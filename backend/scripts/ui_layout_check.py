"""Look for broken layout: text spilling out of its box, horizontal scrollbars, clipped content.

Run after ui_check (so there is data), from backend/:
    python -m scripts.ui_layout_check --admin-key mm_...
Checks every tab and every Show me how drawer at three laptop sizes and saves screenshots to ui_shots/layout/.
"""
import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--admin-key", required=True)
ap.add_argument("--url", default="http://localhost:5173")
args = ap.parse_args()
OUT = Path("ui_shots/layout"); OUT.mkdir(parents=True, exist_ok=True)

# Any visible element whose content is wider than its box (and the box doesn't scroll on purpose).
OVERFLOW_JS = """
() => {
  const bad = [];
  if (document.documentElement.scrollWidth > window.innerWidth + 1)
    bad.push('PAGE scrolls sideways: ' + document.documentElement.scrollWidth + 'px > ' + window.innerWidth + 'px');
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || !el.offsetParent && cs.position !== 'fixed') continue;
    if (['auto', 'scroll'].includes(cs.overflowX)) continue;          // scrolls on purpose
    if (['SVG', 'svg', 'INPUT', 'SELECT', 'TEXTAREA', 'OPTION'].includes(el.tagName)) continue;
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) {
      // only report if a child's text actually leaves the visible area
      const r = el.getBoundingClientRect();
      let spill = false;
      for (const c of el.children) { const cr = c.getBoundingClientRect(); if (cr.right > r.right + 2) spill = true; }
      if (!el.children.length) spill = true;
      if (spill) bad.push(el.tagName.toLowerCase() + '.' + (el.className || '') + ' : ' + (el.innerText || '').slice(0, 60).replace(/\\n/g, ' '));
    }
  }
  return [...new Set(bad)].slice(0, 15);
}
"""

problems = {}

def scan(pg, label):
    found = pg.evaluate(OVERFLOW_JS)
    pg.screenshot(path=OUT / f"{label}.png", full_page=True)
    print(("OK   " if not found else "FAIL ") + label)
    for f in found:
        print("       ", f)
    if found:
        problems[label] = found

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.getenv("CHROME_PATH"), args=["--no-proxy-server"])
    for w, h in [(1366, 768), (1280, 720), (1920, 1080)]:
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.goto(args.url); pg.wait_for_selector("header")
        pg.fill("input.key", args.admin_key); pg.locator("input.key").blur(); pg.wait_for_timeout(400)
        tag = f"{w}x{h}"
        for tab in ["Documents", "Ask", "Review", "Evals", "Upload"]:
            pg.click(f"nav button:has-text('{tab}')"); pg.wait_for_timeout(700)
            if tab == "Documents" and pg.locator(".doc-table tbody tr").count():
                for i in range(pg.locator(".doc-table tbody tr").count()):
                    pg.locator(".doc-table tbody tr").nth(i).click(); pg.wait_for_timeout(400)
                    scan(pg, f"{tag}_documents_{i}")
                    btn = pg.locator(".detail button:has-text('Show me how')")
                    if not btn.count():          # e.g. a document with no stored run
                        continue
                    btn.first.click(); pg.wait_for_selector(".drawer .step-box")
                    scan(pg, f"{tag}_documents_{i}_drawer")
                    for s in range(pg.locator(".step-box").count()):
                        pg.locator(".step-box").nth(s).click(); pg.wait_for_timeout(80)
                        found = pg.evaluate(OVERFLOW_JS)
                        if found:
                            problems[f"{tag}_doc{i}_step{s}"] = found
                            print(f"FAIL {tag} doc {i} step {s}", found[:3])
                    pg.click(".drawer button:has-text('Close')")
            elif tab == "Ask":
                pg.fill("form input", "What must station controllers do about the platform screen door sensors?")
                pg.click("form button"); pg.wait_for_selector(".answer", timeout=60000)
                scan(pg, f"{tag}_ask")
                pg.click(".answer button:has-text('Show me how')"); pg.wait_for_selector(".drawer .step-box")
                for s in range(pg.locator(".step-box").count()):
                    pg.locator(".step-box").nth(s).click(); pg.wait_for_timeout(80)
                    found = pg.evaluate(OVERFLOW_JS)
                    if found:
                        problems[f"{tag}_ask_step{s}"] = found
                        print(f"FAIL {tag} ask step {s}", found[:3])
                scan(pg, f"{tag}_ask_drawer")
                pg.click(".drawer button:has-text('Close')")
            else:
                scan(pg, f"{tag}_{tab.lower()}")
        pg.close()
    b.close()

print(f"\n{len(problems)} view(s) with overflowing text" if problems else "\nNo overflowing text found")
