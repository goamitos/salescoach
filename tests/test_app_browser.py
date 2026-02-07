"""Browser test for the Streamlit app using Playwright.

Verifies: app loads, all 48 expert avatars render, scrollable selector works,
clicking an expert shows their profile card.

Note: Chat input requires API keys (Airtable/Anthropic) which are not available
in local testing without secrets. The test validates the UI shell.
"""
from playwright.sync_api import sync_playwright
import json
import sys

REGISTRY_PATH = "data/influencers.json"
APP_URL = "http://localhost:8501"


def load_active_slugs():
    with open(REGISTRY_PATH) as f:
        data = json.load(f)
    return [i["slug"] for i in data["influencers"] if i["status"] == "active"]


def run_tests():
    active_slugs = load_active_slugs()
    print(f"Expected {len(active_slugs)} active experts")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # 1. Load the app
        print("\n[1] Loading app...")
        page.goto(APP_URL, wait_until="networkidle", timeout=30000)

        # Wait for Streamlit to render
        try:
            page.wait_for_selector("[data-testid='stApp']", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(8000)

        page.screenshot(path="/tmp/salescoach_initial.png", full_page=True)
        print("    Screenshot: /tmp/salescoach_initial.png")

        content = page.content()

        # 2. Check title
        has_title = "Sales Coach" in content
        print(f"\n[2] App title found: {has_title}")

        # 3. Check avatars
        avatar_images = page.locator("img.avatar-img").all()
        if not avatar_images:
            avatar_images = page.locator(".experts-grid img").all()
        avatar_count = len(avatar_images)
        print(f"\n[3] Avatar images found: {avatar_count}")

        # 4. Check slugs in page
        found_slugs = [s for s in active_slugs if s in content]
        print(f"\n[4] Expert slugs in page: {len(found_slugs)}/{len(active_slugs)}")

        # 5. Check scrollable grid
        experts_grid = page.locator(".experts-grid")
        grid_exists = experts_grid.count() > 0
        print(f"\n[5] Experts grid exists: {grid_exists}")
        if grid_exists:
            box = experts_grid.bounding_box()
            if box:
                print(f"    Dimensions: {box['width']:.0f}x{box['height']:.0f}px")

        # 6. Click an expert and verify profile card appears
        print("\n[6] Testing expert click...")
        st_buttons = page.locator("[data-testid='stButton'] button").all()
        print(f"    Buttons found: {len(st_buttons)}")
        click_success = False
        if len(st_buttons) > 1:
            st_buttons[1].click()  # Click first expert (skip "All")
            page.wait_for_timeout(3000)
            # Check for profile card (should show name, specialty, followers)
            post_click_content = page.content()
            click_success = "Selected" in post_click_content or "followers" in post_click_content
            page.screenshot(path="/tmp/salescoach_clicked.png", full_page=True)
            print(f"    Profile card appeared: {click_success}")
            print("    Screenshot: /tmp/salescoach_clicked.png")

        # Summary
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)
        results = []

        def check(name, condition):
            status = "PASS" if condition else "FAIL"
            results.append(condition)
            print(f"  [{status}] {name}")

        check("App loads with title", has_title)
        check(f"All 48 expert avatars render ({avatar_count})", avatar_count == 48)
        check(f"All 48 expert slugs in page ({len(found_slugs)})", len(found_slugs) == 48)
        check("Scrollable experts grid exists", grid_exists)
        check(f"Expert buttons present ({len(st_buttons)})", len(st_buttons) >= 49)
        check("Click shows expert profile card", click_success)

        passed = sum(results)
        total = len(results)
        print(f"\n  Result: {passed}/{total} tests passed")

        browser.close()
        return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
