"""Exercise retained reports and comparison controls at a project subpath in Chromium."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import json
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    data = json.loads((ROOT / "dist/data/ledger.json").read_text())
    cfg = json.loads((ROOT / "dist/config.json").read_text())
    default = next(a for a in data["airports"] if a["icao"] == cfg["defaultAirport"])
    alternative = next((a for a in data["airports"] if a["icao"] != default["icao"]), default)
    screenshots = ROOT / "browser-checks"
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        shutil.copytree(ROOT / "dist", Path(temporary) / "example-tool")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=temporary))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/example-tool/")
                expect(page.locator("#airport-name")).to_have_text(default["label"])
                coverage = page.get_by_text("Airport coverage and capture time", exact=True)
                coverage.click()
                assert int(page.locator("#airport-count").inner_text()) == len(data["airports"])
                coverage.click()
                assert page.locator("#airport-name").inner_text() == default["label"]
                page.get_by_text("Read latest raw observation", exact=True).click()
                expect(page.locator("#raw-observation")).to_be_visible()
                expect(page.locator("#raw-observation")).to_contain_text(default["icao"])
                assert "saved" in page.locator("#comparison-note").inner_text()
                page.locator("#mode").select_option("reconstructed")
                assert "Reconstructed" in page.locator("#comparison-note").inner_text()
                assert page.locator("#comparison-rows tr").count() >= 1
                assert page.locator("#chart svg").count() == 1
                page.locator("#airport-search").fill(alternative["icao"])
                assert page.locator(".airport-button").count() == 1
                page.locator(".airport-button").click()
                assert page.locator("#airport-name").inner_text() == alternative["label"]
                expect(page.locator("#raw-observation")).to_be_visible()
                expect(page.locator("#raw-observation")).to_contain_text(alternative["icao"])
                page.locator("#airport-search").fill("<img src=x onerror=alert(1)>")
                assert "No airports match" in page.locator("#airports").inner_text()
                assert page.locator("img").count() == 0
                page.locator("#airport-search").fill("")
                page.get_by_text("Add another airport", exact=True).click()
                page.locator("#new-icao").fill("CYYZ")
                page.locator("#new-label").fill("Toronto")
                page.locator("#make-config").click()
                assert '"icao": "CYYZ"' in page.locator("#config-entry").inner_text()
                page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                tool_url = page.url
                page.goto("about:blank")
                page.goto(tool_url)
                expect(page.locator("#airport-name")).to_have_text(default["label"])
                first_airport = page.locator(".airport-button").first.bounding_box()
                assert first_airport["y"] >= 0 and first_airport["y"] + first_airport["height"] < 844
                expect(page.locator(".notice")).to_contain_text("official aviation briefings")
                page.locator(".airport-button").filter(has_text=alternative["icao"]).click()
                expect(page.locator("#airport-name")).to_have_text(alternative["label"])
                expect(page.locator("#airport-name")).to_be_focused()
                page.wait_for_function("""() => {
                    const top = document.querySelector('#airport-name').getBoundingClientRect().top;
                    return top >= 0 && top < 120;
                }""")
                page.get_by_role("link", name="Choose another airport").click()
                page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
            print("Browser checks passed: airport selection, captured/reconstructed modes, configurable expansion, safe text, mobile layout")
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
