import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# --- Configuration ---
AUTH_FILE = Path("auth_state.json")
GROUP_URL = "https://ardc.groups.io/g/44net/topics"
DATA_FILE = Path("scraped_data.json")
HEADLESS_MODE = False # Set to False to watch the browser work
PAGE_LOAD_DELAY = 2

async def find_and_click_next_page(page) -> bool:
    """
    Tries multiple common selectors to find and click the 'next' page link.
    Returns True if it successfully clicks, False otherwise.
    """
    # A list of potential locators for the 'next' button, from most to least likely.
    locators_to_try = [
        # 1. Accessibility-first: The best and most stable selector.
        page.locator('a[aria-label="Next page"]'),
        # 2. Role-based: The standards-compliant way.
        page.get_by_role("link", name="next", exact=True),
        # 3. Text-based with an arrow symbol, which is very common.
        page.locator('a:has-text("next ›")'),
        # 4. A link with a 'title' attribute.
        page.locator('a[title*="Next"]'),
        # 5. A link that contains a child element with the class 'fa-angle-right' (Font Awesome icon)
        page.locator('a:has(i.fa-angle-right)')
    ]

    for i, locator in enumerate(locators_to_try):
        try:
            # Check if the locator finds at least one element and if it's visible
            if await locator.is_visible(timeout=100): # Use a short timeout
                print(f"Found 'next' button with strategy #{i+1}. Clicking...")
                await locator.click()
                return True
        except TimeoutError:
            # This is expected if the locator doesn't find anything, so we just continue
            continue
            
    # If we get through the whole list without finding a button
    return False


async def get_all_thread_urls(page):
    """Navigates to the topics page and clicks 'next' until all thread URLs are collected."""
    print(f"Navigating to group topics list: {GROUP_URL}")
    await page.goto(GROUP_URL, wait_until="domcontentloaded")
    
    thread_link_selector = 'a[href*="/g/44net/topic/"]'
    await page.wait_for_selector(thread_link_selector, timeout=30000)
    print("Initial page loaded. Starting to collect URLs via pagination.")

    seen_urls = set()
    page_count = 1
    
    while True:
        print(f"--- Scraping Page {page_count} ---")
        
        # Give the page a moment to settle, especially if content loads dynamically
        await page.wait_for_timeout(1000)
        
        links = await page.locator(thread_link_selector).all()
        
        current_page_urls = set()
        for link in links:
            href = await link.get_attribute('href')
            if href:
                full_url = f"https://groups.io{href}"
                current_page_urls.add(full_url)
        
        new_urls_found = len(current_page_urls - seen_urls)
        if new_urls_found == 0 and page_count > 1:
            print("WARNING: No new URLs found on this page. This might indicate the end.")
        
        print(f"Found {new_urls_found} new thread URLs on this page.")
        seen_urls.update(current_page_urls)
        print(f"Total unique URLs so far: {len(seen_urls)}")

        # Use our new smart function to find and click the next button
        if await find_and_click_next_page(page):
            await page.wait_for_load_state("domcontentloaded")
            time.sleep(PAGE_LOAD_DELAY) 
            page_count += 1
        else:
            print("\nCould not find a 'next' button using any known strategy. Assuming last page.")
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
            
            print(f"\nSaving {len(thread_urls)} URLs to 'thread_urls.json'...")
            with open("thread_urls.json", "w") as f:
                json.dump(sorted(thread_urls), f, indent=2)

            print("✅ Checkpoint 2 complete! All thread URLs have been collected.")
            
        except TimeoutError:
            print("\n❌ A timeout occurred. This could be due to a slow network or a change in the website's structure.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            print("Closing browser.")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())