import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# --- Configuration ---
AUTH_FILE = Path("auth_state.json")
GROUP_URL = "https://ardc.groups.io/g/44net/topics"
DATA_FILE = Path("scraped_data.json")
HEADLESS_MODE = True # Set to False to watch the browser work
SCROLL_DELAY = 3 # Seconds to wait between scrolls
SCROLL_PATIENCE = 5 # How many times to retry scrolling when no new content is found

async def get_all_thread_urls(page):
    """Navigates to the topics page and scrolls until all threads are loaded."""
    print(f"Navigating to group topics: {GROUP_URL}")
    await page.goto(GROUP_URL, wait_until="domcontentloaded")
    await page.wait_for_selector('a[href*="/g/44net/topic/"]', timeout=30000)
    
    print("Starting to scroll to load all threads. This may take a while...")
    
    # Selector for the links to individual threads
    thread_link_selector = 'a[href*="/g/44net/topic/"]'
    
    seen_urls = set()
    patience_counter = 0
    
    while patience_counter < SCROLL_PATIENCE:
        initial_url_count = len(seen_urls)
        
        links = await page.locator(thread_link_selector).all()
        for link in links:
            href = await link.get_attribute('href')
            if href:
                full_url = f"https://groups.io{href}"
                seen_urls.add(full_url)

        if len(seen_urls) > initial_url_count:
            print(f"Found {len(seen_urls)} unique thread URLs...")
            patience_counter = 0 # Reset patience because we found new content
        else:
            patience_counter += 1
            print(f"No new threads found on this scroll. Patience: {patience_counter}/{SCROLL_PATIENCE}")

        # Scroll to the bottom of the page
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        
        # Wait for potential new content to load
        time.sleep(SCROLL_DELAY)

    print(f"\n✅ Finished scrolling. Found a total of {len(seen_urls)} thread URLs.")
    return list(seen_urls)


async def main():
    if not AUTH_FILE.exists():
        print(f"❌ Authentication file '{AUTH_FILE}' not found.")
        print("Please run '01_create_auth_state.py' first to log in.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS_MODE)
        context = await browser.new_context(storage_state=AUTH_FILE)
        page = await context.new_page()

        try:
            thread_urls = await get_all_thread_urls(page)
            
            # For now, we'll just save the list of URLs.
            # In the next step, we'll iterate through them to scrape content.
            print(f"\nSaving {len(thread_urls)} URLs to a temporary file...")
            with open("temp_thread_urls.json", "w") as f:
                json.dump(thread_urls, f, indent=2)

            print("Checkpoint 2 complete! All thread URLs have been collected.")
            
            # --- NEXT STEPS (to be implemented) ---
            # scraped_data = {}
            # for url in thread_urls:
            #     # scrape_single_thread(page, url) ...
            #     pass

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())