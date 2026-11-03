"""Record genuine footage of the running SENTINEL app (local dev servers) with Playwright.

Prerequisites: backend on http://127.0.0.1:8000 and frontend on http://localhost:5173, freshly reset
(scripts/reset-demo.ps1). Logs in with the seeded synthetic demo accounts on localhost only.
Writes footage/<scene>.webm and footage/timing.json (seconds to trim from each clip's start).
"""
import json
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "footage"
APP = "http://localhost:5173"
API = "http://127.0.0.1:8000"
PASSWORD = "SentinelDemo!2026"  # seeded synthetic demo password (see .env.example)
W, H = 1920, 1080

durations = {}
for f in (HERE / "audio").glob("*.json"):
    cues = json.loads(f.read_text(encoding="utf-8"))
    durations[f.stem] = cues[-1]["end"]


def token(email: str) -> str:
    r = httpx.post(f"{API}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def smooth_scroll(page, top: int, wait: float = 1.2) -> None:
    page.evaluate(f"window.scrollTo({{top: {top}, behavior: 'smooth'}})")
    page.wait_for_timeout(int(wait * 1000))


def glide(page, points, step_ms: int = 600) -> None:
    for x, y in points:
        page.mouse.move(x, y, steps=12)
        page.wait_for_timeout(step_ms)


class Recorder:
    def __init__(self, browser):
        self.browser = browser
        self.timing = {}
        self.ctx = {}

    def scene(self, name: str, tok: str, fn) -> None:
        target = durations[name] + 1.6
        ctx = self.browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(OUT / "_raw"),
                                       record_video_size={"width": W, "height": H}, device_scale_factor=1)
        ctx.add_init_script(f"try{{sessionStorage.setItem('sentinel_token', {json.dumps(tok)})}}catch(e){{}}")
        page = ctx.new_page()
        t0 = time.monotonic()
        ready = fn(page, t0)  # returns monotonic time when the first content is fully drawn
        elapsed = time.monotonic() - ready
        if elapsed < target:
            page.wait_for_timeout(int((target - elapsed) * 1000))
        video = page.video
        ctx.close()
        dest = OUT / f"{name}.webm"
        if dest.exists():
            dest.unlink()
        video.save_as(str(dest))
        self.timing[name] = {"trim_start": round(ready - t0, 2), "length": round(time.monotonic() - ready, 2)}
        print(name, self.timing[name])


def run():
    OUT.mkdir(exist_ok=True)
    staff, shopper = token("reviewer@sentinel.dev"), token("ben@shopper.sentinel.dev")
    state = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        rec = Recorder(browser)

        def s2(page, t0):
            page.goto(f"{APP}/console")
            page.wait_for_selector("text=Transaction volume")
            page.wait_for_timeout(2500)
            ready = time.monotonic()
            glide(page, [(300, 180), (700, 180), (1100, 180), (1500, 180)], 700)
            smooth_scroll(page, 520, 2.2)
            smooth_scroll(page, 0, 1.2)
            page.goto(f"{APP}/console/transactions")
            page.wait_for_selector(".ag-row")
            page.wait_for_timeout(1500)
            glide(page, [(600, 240), (600, 320), (600, 400)], 700)
            return ready

        def s3(page, t0):
            page.goto(f"{APP}/shop")
            page.wait_for_selector("text=Vector 14")
            page.wait_for_timeout(2200)
            ready = time.monotonic()
            smooth_scroll(page, 260, 2.0)
            page.click("a:has-text('Vector 14')")
            page.wait_for_selector("text=Add to cart")
            page.wait_for_timeout(2600)
            page.click("button:has-text('Add to cart')")
            page.wait_for_selector("text=Order summary")
            page.wait_for_timeout(2600)
            page.click("button:has-text('Checkout with PayPal')")
            page.wait_for_selector("text=PayPal Sandbox is not configured")
            page.wait_for_timeout(800)
            glide(page, [(1100, 300), (1250, 340)], 900)
            return ready

        def s4(page, t0):
            page.goto(f"{APP}/console")
            page.wait_for_selector("text=Demonstration scenarios")
            page.wait_for_timeout(2000)
            ready = time.monotonic()
            page.locator("button:has-text('Run risk pipeline')").nth(1).click()
            link = page.wait_for_selector("a:has-text('Open investigation workspace')")
            page.wait_for_timeout(2500)
            state["txn_b"] = link.get_attribute("href").rsplit("/", 1)[-1]
            link.click()
            page.wait_for_selector("text=ML risk")
            page.wait_for_timeout(3000)
            smooth_scroll(page, 330, 2.0)
            glide(page, [(300, 400), (320, 520), (300, 640)], 800)
            return ready

        def s5(page, t0):
            page.goto(f"{APP}/console")
            page.wait_for_selector("text=Demonstration scenarios")
            page.wait_for_timeout(1500)
            ready = time.monotonic()
            page.locator("button:has-text('Run risk pipeline')").nth(2).click()
            link = page.wait_for_selector("a:has-text('Open investigation workspace')")
            page.wait_for_timeout(1800)
            state["txn_c"] = link.get_attribute("href").rsplit("/", 1)[-1]
            link.click()
            page.wait_for_selector("text=Financial relationship graph")
            page.wait_for_timeout(3500)
            glide(page, [(800, 400), (900, 450), (1000, 500), (950, 600)], 700)
            page.goto(f"{APP}/console/network?entity=DEV_0147")
            page.wait_for_selector("text=Neighbourhood of DEV_0147")
            page.wait_for_timeout(3500)
            glide(page, [(600, 500), (700, 550), (800, 600)], 700)
            return ready

        def s6(page, t0):
            page.goto(f"{APP}/console/investigate/{state['txn_c']}")
            page.wait_for_selector("text=Recommendation only", timeout=60000)
            page.wait_for_timeout(1500)
            ready = time.monotonic()
            page.click("button:has-text('INVESTIGATE')")
            page.wait_for_timeout(3500)
            for top in (300, 650, 1000, 1350):
                smooth_scroll(page, top, 2.6)
            return ready

        def s7(page, t0):
            txn = state["txn_c"]
            page.goto(f"{APP}/console/investigate/{txn}")
            page.wait_for_selector("text=Recommendation only", timeout=60000)
            page.evaluate("document.evaluate(\"//*[text()='Decision & history']\", document, null, 9, null)"
                          ".singleNodeValue.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(1500)
            ready = time.monotonic()
            page.click("button:has-text('Reject')")
            page.wait_for_selector("text=Re-enter your password")
            page.wait_for_timeout(900)
            page.locator("textarea").type("Device shared with 3 ring accounts and a flagged mule wallet.", delay=35)
            page.locator("input[type=password]").type(PASSWORD, delay=45)
            page.locator("input.font-mono").last.type(txn, delay=60)
            page.wait_for_timeout(700)
            page.click("button:has-text('Confirm reject')")
            page.wait_for_selector("text=REJECTED", timeout=20000)
            page.wait_for_timeout(1200)
            return ready

        def s8(page, t0):
            page.goto(f"{APP}/console/audit")
            page.wait_for_selector("text=Audit log")
            page.wait_for_timeout(1500)
            ready = time.monotonic()
            page.click("button:has-text('Verify hash chain')")
            page.wait_for_selector("text=Chain intact")
            page.wait_for_timeout(1500)
            return ready

        for name, fn, tok in (("s2_solution", s2, staff), ("s3_paypal", s3, shopper), ("s4_ml", s4, staff),
                              ("s5_graph", s5, staff), ("s6_agent", s6, staff), ("s7_review", s7, staff),
                              ("s8_close", s8, staff)):
            rec.scene(name, tok, fn)
        browser.close()
    (OUT / "timing.json").write_text(json.dumps(rec.timing, indent=1), encoding="utf-8")
    print("done", state)


if __name__ == "__main__":
    run()
