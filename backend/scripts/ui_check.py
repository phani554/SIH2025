"""Click through the real UI in headless Chrome and check every interaction.

Needs: backend on :8000 with a FRESH database, frontend on :5173, and
    pip install playwright && python -m playwright install chromium
Run:
    python -m scripts.ui_check --admin-key mm_... --viewer-key mm_...   (from backend/)
Screenshots go to ui_shots/.
"""
import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--admin-key", required=True)
ap.add_argument("--viewer-key", required=True)
args = ap.parse_args()
ADMIN, VIEWER = args.admin_key, args.viewer_key
CH = os.getenv("CHROME_PATH")          # optional: a specific Chrome binary
DOCS = Path(__file__).resolve().parents[1] / "sample_docs"
OUT = Path("ui_shots"); OUT.mkdir(exist_ok=True)
results, errors = [], []

def check(name, ok, info=""):
    results.append((name, ok, info)); print("PASS" if ok else "FAIL", name, info, flush=True)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CH, args=["--no-proxy-server"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://localhost:5173"); pg.wait_for_selector("header")
    pg.fill("input.key", ADMIN); pg.locator("input.key").blur(); pg.wait_for_timeout(500)
    check("header shows provider", "offline" in pg.inner_text("header"), pg.inner_text("header .badge"))
    pg.screenshot(path=OUT / "01_upload_tab.png")

    def upload(path):
        n = pg.locator(".upload-results li").count()
        pg.set_input_files(".dropzone input[type=file]", str(path))
        pg.wait_for_function(f"document.querySelectorAll('.upload-results li').length > {n}", timeout=60000)
        return pg.locator(".upload-results li").first.inner_text()

    t = upload(DOCS / "invoice_INV-2025-0917_alstom.txt"); check("upload invoice", "ANALYZED" in t, t)
    t = upload(DOCS / "safety_circular_SC-14_platform_screen_doors.txt"); check("upload circular", "ANALYZED" in t, t)
    t = upload(DOCS / "unclean_vendor_letter_injection_pii.txt"); check("upload unclean", "NEEDS_REVIEW" in t, t)
    t = upload(DOCS / "invoice_INV-2025-0917_alstom.txt"); check("re-upload duplicate", "duplicate" in t, t)
    bad = OUT / "layout.dwg"; bad.write_bytes(b"AC1015")
    t = upload(bad); check("unsupported rejected", "rejected" in t, t)
    check("rejected upload still has Show me how", pg.locator(".upload-results li").first.locator("text=Show me how").count() == 1)
    pg.screenshot(path=OUT / "02_uploads.png")

    # Show me how on the unclean document (3rd from top: unclean is below dup + rejected)
    pg.locator(".upload-results li", has_text="unclean_vendor").locator("text=Show me how").click()
    pg.wait_for_selector(".drawer .step-box")
    d = pg.inner_text(".drawer")
    check("drawer: preliminary analysis", "Preliminary analysis" in d and "Finance" in d)
    check("drawer: run plan", "max steps" in d and "18" in d)
    check("drawer: 6 lanes", pg.locator(".lane-title").count() == 6)
    check("drawer: 16 step boxes", pg.locator(".step-box").count() == 16, str(pg.locator(".step-box").count()))
    pg.screenshot(path=OUT / "03_drawer_unclean.png")
    pg.locator(".step-box", has_text="pii_redaction").click(); pg.wait_for_selector(".step-detail")
    sd = pg.inner_text(".step-detail")
    check("drill-down pii_redaction", "AADHAAR" in sd and "masked" in sd)
    pg.locator(".step-box", has_text="injection_scan").click(); pg.wait_for_timeout(200)
    sd = pg.inner_text(".step-detail")
    check("drill-down injection_scan shows quarantined line", "Ignore all previous instructions" in sd)
    pg.locator(".step-detail").scroll_into_view_if_needed(); pg.screenshot(path=OUT / "04_injection_detail.png")
    pg.locator(".step-box", has_text="level1_classification").click(); pg.wait_for_timeout(200)
    sd = pg.inner_text(".step-detail")
    check("drill-down level1 shows prompt + validation", "LEVEL 1" in sd and "passed" in sd and "9847012345" not in sd)
    pg.locator(".step-detail").scroll_into_view_if_needed(); pg.screenshot(path=OUT / "05_level1_detail.png")
    pg.locator(".step-box", has_text="review_gate").click(); pg.wait_for_timeout(200)
    check("drill-down review_gate", "prompt injection" in pg.inner_text(".step-detail"))
    pg.click(".drawer button:has-text('Close')"); pg.wait_for_timeout(200)
    check("drawer closes", pg.locator(".drawer").count() == 0)

    # Documents tab
    pg.click("nav button:has-text('Documents')"); pg.wait_for_selector("tbody tr")
    check("documents listed", pg.locator("tbody tr").count() == 3, str(pg.locator("tbody tr").count()))
    pg.locator("tbody tr", has_text="invoice").click(); pg.wait_for_selector(".detail h2")
    det = pg.inner_text(".detail")
    check("document detail L1 + L2", "Level 1" in det and "Rs. 21,71,200" in det, "")
    pg.screenshot(path=OUT / "06_document_detail.png")
    pg.click(".detail button:has-text('Show me how')"); pg.wait_for_selector(".drawer .step-box")
    check("document Show me how opens", "level2_extraction" in pg.inner_text(".drawer"))
    pg.screenshot(path=OUT / "07_drawer_invoice.png")
    pg.click(".drawer button:has-text('Close')")

    # Ask tab
    pg.click("nav button:has-text('Ask')")
    pg.fill("form input", "What is the total payable amount on the Alstom invoice?")
    pg.click("form button"); pg.wait_for_selector(".answer", timeout=60000)
    ans = pg.inner_text(".answer")
    check("answer with verified citation", "21,71,200" in ans and "verified" in ans, ans.split("\n")[0])
    pg.screenshot(path=OUT / "08_ask.png")
    pg.click(".answer button:has-text('Show me how')"); pg.wait_for_selector(".drawer .step-box")
    check("ask drawer lanes", pg.locator(".step-box").count() == 12, str(pg.locator(".step-box").count()))
    pg.locator(".step-box", has_text="keyword_search_bm25").click(); pg.wait_for_timeout(200)
    sd = pg.inner_text(".step-detail")
    check("bm25 drill-down: MATCH + scores table", "MATCH" in sd and "bm25" in sd)
    pg.locator(".step-box", has_text="rrf_fusion").click(); pg.wait_for_timeout(200)
    check("rrf drill-down", "rrf_score" in pg.inner_text(".step-detail"))
    pg.locator(".step-detail").scroll_into_view_if_needed(); pg.screenshot(path=OUT / "09_ask_drawer_rrf.png")
    pg.click(".drawer button:has-text('Close')")
    pg.fill("form input", "What is on the canteen menu today?"); pg.click("form button")
    pg.wait_for_function("document.querySelector('.answer') && document.querySelector('.answer').innerText.includes('Not found')", timeout=60000)
    check("refusal shown", True)

    # Review & Audit
    pg.click("nav button:has-text('Review')"); pg.wait_for_timeout(800)
    rv = pg.inner_text("main")
    check("review queue has unclean doc", "unclean_vendor" in rv)
    check("recent runs listed", pg.locator("text=Show me how").count() >= 5)
    pg.screenshot(path=OUT / "10_review.png", full_page=True)
    pg.locator(".review-item", has_text="unclean").locator("button:has-text('Approve')").click(); pg.wait_for_timeout(800)
    check("approve removes from queue", "unclean_vendor" not in pg.inner_text(".split section:first-child"))

    # Evals
    pg.click("nav button:has-text('Evals')"); pg.wait_for_selector("text=Eval report")
    ev = pg.inner_text("main")
    check("evals tab shows report + offline warning", "L1 accuracy" in ev and "Offline rules" in ev)
    pg.screenshot(path=OUT / "11_evals.png", full_page=True)

    # Finance viewer
    pg.fill("input.key", VIEWER); pg.locator("input.key").blur(); pg.wait_for_timeout(300)
    pg.click("nav button:has-text('Documents')"); pg.wait_for_timeout(800)
    rows = pg.inner_text("tbody") if pg.locator("tbody tr").count() else ""
    check("viewer sees only Finance docs", "safety" not in rows and "invoice" in rows)
    pg.click("nav button:has-text('Ask')")
    pg.fill("form input", "door sensors"); pg.select_option("form select", "Safety"); pg.click("form button")
    pg.wait_for_selector(".badge.red", timeout=8000)
    check("viewer blocked from Safety", "own department" in pg.inner_text(".badge.red"))
    pg.screenshot(path=OUT / "12_viewer_blocked.png")
    b.close()

# 400 (rejected .dwg) and 403 (viewer blocked) are expected; anything else is a bug.
unexpected = [e for e in errors if "400" not in e and "403" not in e]
check("no unexpected browser console errors", not unexpected, "; ".join(unexpected[:3]))
print(f"\n{sum(ok for _, ok, _ in results)} / {len(results)} UI checks passed")
