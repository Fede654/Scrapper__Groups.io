import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

# --- Configuration ---
AUTH_FILE = Path("auth_state.json")
START_URL = "https://groups.io/login"
# ---

async def main():
    """
    This script launches a browser, allowing you to log in to Groups.io manually.
    Once you have successfully logged in, close the browser window.
    The script will then save your authentication state (cookies, etc.) to a file.
    """
    async with async_playwright() as p:
        # We launch the browser in non-headless mode so you can see the UI.
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(">>> A browser window has opened.")
        print(f">>> Please log in to Groups.io at: {START_URL}")
        await page.goto(START_URL)

        # The script will pause here, waiting for the page to be closed.
        await page.wait_for_event("close")

        # Once you close the page, the authentication state is saved.
        await context.storage_state(path=AUTH_FILE)
        await browser.close()
        
        print(f"\n✅ Authentication state saved successfully to '{AUTH_FILE}'!")
        print("You can now run the main scraper script.")

if __name__ == "__main__":
    if AUTH_FILE.exists():
        print(f"⚠️ Auth file '{AUTH_FILE}' already exists.")
        overwrite = input("Do you want to overwrite it? (y/n): ").lower()
        if overwrite != 'y':
            print("Aborted. Using existing auth file.")
        else:
            asyncio.run(main())
    else:
        asyncio.run(main())
        