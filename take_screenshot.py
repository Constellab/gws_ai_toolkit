import argparse
import os

from playwright.sync_api import sync_playwright


def test_reflex_app(route="/"):
    with sync_playwright() as p:
        # Use the system installed browser
        browser = p.chromium.launch(
            headless=False,  # Still use headless mode in container
            # executable_path="/usr/bin/chromium-browser"  # Path to system chromium
            # For Chrome use: executable_path="/usr/bin/google-chrome"
        )

        # Create a new page
        page = browser.new_page()

        # Navigate to your Reflex app with the specified route
        url = f"http://localhost:8511{route}"
        page.goto(url)

        # Wait for page to load fully
        page.wait_for_load_state("networkidle")

        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Save screenshot in the same directory as the script
        screenshot_path = os.path.join(current_dir, "app_screenshot.png")
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

        # Close browser
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Take a screenshot of the Reflex app")
    parser.add_argument("--route", "-r", default="/", help="Route to navigate to (default: /)")
    
    args = parser.parse_args()
    test_reflex_app(args.route)
