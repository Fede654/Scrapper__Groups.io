import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# --- Configuration ---
AUTH_FILE = Path("auth_state.json")
GROUP_URL = "https://ardc.groups.io/g/44net/topics"
DATA_FILE = Path("thread_urls.json") # Changed from scraped_data.json
HEADLESS_MODE = True # Set to False to watch the browser work
PAGE_LOAD_DELAY = 2

async def find_and_click_next_page(page) -> bool:
    """
    Tries multiple common selectors to find and click the 'next' page link.
    Returns True if it successfully clicks, False otherwise.
    """
    # A list of potential locators, with the most specific one first.
    locators_to_try = [
        # 1. THE DEFINITIVE SELECTOR (found in your HTML): A link with the `rel="next"` attribute.
        page.locator('a[rel="next"]'),

        # --- Fallback strategies (kept for robustness, but #1 should work) ---
        # 2. Accessibility-first: A link with an explicit aria-label.
        page.locator('a[aria-label="Next page"]'),
        # 3. Role-based: A link with the visible text "next".
        page.get_by_role("link", name="next", exact=True),
        # 4. Icon-based: A link that contains the right-arrow icon.
        page.locator('a:has(i.fa-chevron-right)')
    ]

    for i, locator in enumerate(locators_to_try):
        try:
            # Check if the locator finds at least one element and if it's visible
            if await locator.is_visible(timeout=500): # Use a short timeout
                print(f"✅ Found 'next' button with strategy #{i+1}. Clicking...")
                await locator.click()
                return True
        except (TimeoutError, Exception):
            # This is expected if the locator doesn't find anything, so we just continue
            continue
            
    # If we get through the whole list without finding a button
    return False


async def get_all_thread_urls(page):
    """Navigates to the topics page and clicks 'next' until all thread URLs are collected."""
    print(f"Navigating to group topics list: {GROUP_URL}")
    await page.goto(GROUP_URL, wait_until="domcontentloaded")
    
    thread_link_selector = 'a.subject[href*="/g/44net/topic/"]'
    await page.wait_for_selector(thread_link_selector, timeout=30000)
    print("Initial page loaded. Starting to collect URLs via pagination.")

    seen_urls = set()
    page_count = 1
    
    while True:
        print(f"--- Scraping Page {page_count} ---")
        await page.wait_for_timeout(1000) # Give the page a moment to settle
        
        links = await page.locator(thread_link_selector).all()
        
        if not links:
            print("Warning: No thread links found on this page.")
            
        current_page_urls = set()
        for link in links:
            href = await link.get_attribute('href')
            if href:
                full_url = f"https://groups.io{href}"
                current_page_urls.add(full_url)
        
        new_urls_found = len(current_page_urls - seen_urls)
        print(f"Found {new_urls_found} new thread URLs on this page.")
        seen_urls.update(current_page_urls)
        print(f"Total unique URLs so far: {len(seen_urls)}")

        # Use our new smart function to find and click the next button
        if await find_and_click_next_page(page):
            await page.wait_for_load_state("domcontentloaded")
            time.sleep(PAGE_LOAD_DELAY) 
            page_count += 1
        else:
            print("\nCould not find a 'next' button. Assuming this is the last page.")
            break

    print(f"\n✅ Finished paginating through all {page_count} pages.")
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
            thread_urls = await get_all_thread_urls(page)
            
            print(f"\nSaving {len(thread_urls)} URLs to '{DATA_FILE}'...")
            # Save as a sorted list for consistency
            with open(DATA_FILE, "w") as f:
                json.dump(sorted(thread_urls), f, indent=2)

            print(f"✅ Checkpoint 2 complete! All thread URLs have been collected in '{DATA_FILE}'.")
            
        except TimeoutError:
            print("\n❌ A timeout occurred. This could be due to a slow network or a change in the website's structure.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            print("Closing browser.")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())