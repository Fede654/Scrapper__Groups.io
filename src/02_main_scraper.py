import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# --- Configuration ---
AUTH_FILE = Path("auth_state.json")
# We define the base URL and let the loop add the page number
GROUP_URL_BASE = "https://ardc.groups.io/g/44net/topics?page="
# As requested, we will loop from page 1 to 9.
# The range(1, 10) in Python goes from 1 up to (but not including) 10.
PAGE_RANGE = range(1, 10) 
DATA_FILE = Path("thread_urls.json")
HEADLESS_MODE = True # Set to False to watch the browser work
PAGE_LOAD_DELAY = 1.5 # Seconds to wait between page loads

async def get_all_thread_urls_by_looping(page):
    """
    Scrapes all thread URLs by directly iterating through page numbers in the URL.
    """
    print("Starting URL collection by looping through page numbers.")
    
    seen_urls = set()
    
    # Selector for the links to individual threads
    thread_link_selector = 'a.subject[href*="/g/44net/topic/"]'
    
    for page_num in PAGE_RANGE:
        target_url = f"{GROUP_URL_BASE}{page_num}"
        print(f"--- Navigating to Page {page_num}: {target_url} ---")
        
        try:
            await page.goto(target_url, wait_until="domcontentloaded")
            # Wait for the list of topics to appear on the page
            await page.wait_for_selector(thread_link_selector, timeout=15000)
        except TimeoutError:
            print(f"⚠️  Timeout on page {page_num}. It might not exist. Ending collection.")
            break # Exit the loop if a page doesn't load/exist

        # Find all thread links on the current page
        links = await page.locator(thread_link_selector).all()
        
        if not links:
            print(f"⚠️  No topic links found on page {page_num}. Assuming end of topics.")
            break
            
        initial_count = len(seen_urls)
        for link in links:
            href = await link.get_attribute('href')
            if href:
                full_url = f"https://groups.io{href}"
                seen_urls.add(full_url)
        
        new_urls_found = len(seen_urls) - initial_count
        print(f"Found {new_urls_found} new URLs. Total unique URLs: {len(seen_urls)}")
        
        # Add a polite delay
        time.sleep(PAGE_LOAD_DELAY)

    print(f"\n✅ Finished scanning pages {PAGE_RANGE.start} through {page_num}.")
    print(f"Collected a total of {len(seen_urls)} unique thread URLs.")
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
            # Call our new loop-based function
            thread_urls = await get_all_thread_urls_by_looping(page)
            
            if not thread_urls:
                 print("\nNo URLs were collected. Please check the configuration and selectors.")
                 return
                 
            print(f"\nSaving {len(thread_urls)} URLs to '{DATA_FILE}'...")
            with open(DATA_FILE, "w") as f:
                json.dump(sorted(thread_urls), f, indent=2)

            print(f"✅ Checkpoint 2 complete! All thread URLs have been collected in '{DATA_FILE}'.")
            
        except TimeoutError:
            print("\n❌ A timeout occurred during initial page load.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            print("Closing browser.")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())