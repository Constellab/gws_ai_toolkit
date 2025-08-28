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

        # Setup console log listener
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"{msg.type}: {msg.text}"))

        # Navigate to your Reflex app with the specified route
        url = f"http://localhost:8511{route}"
        print(f"Navigating to {url}")
        page.goto(url)

        # Wait for page to load fully
        page.wait_for_load_state("networkidle")

        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Save screenshot in the same directory as the script
        screenshot_path = os.path.join(current_dir, "app_screenshot.png")
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

        # Print collected console logs
        print("\nBrowser Console Logs:")
        for log in console_logs:
            print(log)

        # Optionally save console logs to a file
        log_path = os.path.join(current_dir, "console_logs.txt")
        with open(log_path, "w") as f:
            f.write("\n".join(console_logs))
        print(f"Console logs saved to {log_path}")

        # Close browser
        browser.close()


# use xvfb-run python take_screenshot.py --route [ROUTE] to run
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Take a screenshot of the Reflex app")
    parser.add_argument("--route", "-r", default="/", help="Route to navigate to (default: /)")

    args = parser.parse_args()
    test_reflex_app(args.route)
