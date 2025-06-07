import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# --- Configuration ---
AUTH_FILE = Path("auth_state.json")
# The base URL for the list of all threads (topics)
GROUP_URL = "https://ardc.groups.io/g/44net/topics"
DATA_FILE = Path("scraped_data.json")
HEADLESS_MODE = True # Set to False to watch the browser work
# Polite delay between clicking "next" page
PAGE_LOAD_DELAY = 2

async def get_all_thread_urls(page):
    """Navigates to the topics page and clicks 'next' until all thread URLs are collected."""
    print(f"Navigating to group topics list: {GROUP_URL}")
    await page.goto(GROUP_URL, wait_until="domcontentloaded")
    
    # Wait for the first page of topics to ensure it's loaded.
    # Note: Individual thread links contain '/topic/' (singular). This is correct.
    thread_link_selector = 'a[href*="/g/44net/topic/"]'
    await page.wait_for_selector(thread_link_selector, timeout=30000)
    print("Initial page loaded. Starting to collect URLs via pagination.")

    seen_urls = set()
    page_count = 1
    
    # The main loop for pagination
    while True:
        print(f"--- Scraping Page {page_count} ---")
        
        # Find all thread links on the CURRENT page
        links = await page.locator(thread_link_selector).all()
        
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

        # --- MODIFIED: Use lowercase 'next' for the button name ---
        # Find the 'next' button to see if we can continue.
        # This locator is specific and robust.
        next_button = page.get_by_role("link", name="next", exact=True)

        # Check if the 'next' button exists and is visible on the page
        if await next_button.count() > 0 and await next_button.is_visible():
            print("Found 'next' button. Clicking to load next page...")
            await next_button.click()
            # Wait for the next page to load fully.
            await page.wait_for_load_state("domcontentloaded")
            time.sleep(PAGE_LOAD_DELAY) 
            page_count += 1
        else:
            # If no 'next' button is found, we are on the last page
            print("\nNo 'next' button found. Assuming we've reached the last page.")
            break # Exit the loop

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
            
            # Save the list of URLs. We will use this file in the next checkpoint.
            print(f"\nSaving {len(thread_urls)} URLs to a file for the next step...")
            with open("thread_urls.json", "w") as f:
                json.dump(thread_urls, f, indent=2)

            print("✅ Checkpoint 2 complete! All thread URLs have been collected in 'thread_urls.json'.")
            
        except TimeoutError:
            print("\n❌ A timeout occurred. This could be due to a slow network connection,")
            print("   or a change in the website's structure. Try running again or")
            print("   increasing the timeout in the `wait_for_selector` call.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            print("Closing browser.")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())