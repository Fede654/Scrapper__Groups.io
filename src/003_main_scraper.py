import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# --- Configuration ---
AUTH_FILE = Path("auth_state.json")
# Input file from Checkpoint 2
URLS_FILE = Path("thread_urls.json") 
# The final structured data output
DATA_FILE = Path("scraped_data.json") 
HEADLESS_MODE = False # Set to False to watch the browser work
# Save progress after every N threads to prevent data loss on long runs
SAVE_EVERY = 10 

# --- Helper function for Checkpoint 3 ---

async def scrape_thread_page(page, url):
    """
    Visits a single thread URL and extracts the title and all messages.
    Returns a dictionary with the scraped data.
    """
    print(f"-> Visiting: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Wait for the main message container to be present. This is a good sign the page is ready.
        await page.wait_for_selector("div.vcard", timeout=30000) 
    except TimeoutError:
        print("   -> ⚠️ Timed out waiting for page to load. Skipping.")
        return None
    except Exception as e:
        print(f"   -> ❌ Error navigating to page: {e}. Skipping.")
        return None

    # --- Scrape Thread Title ---
    try:
        title = await page.locator("h1#topic-title").text_content()
    except Exception:
        title = "Title not found"
        print("   -> ⚠️ Could not find thread title.")
        
    # --- Scrape all messages ---
    messages = []
    # Each message is contained within a 'div.vcard.row'
    message_elements = await page.locator("div.vcard.row").all()
    print(f"   -> Found {len(message_elements)} messages in thread.")

    for msg_element in message_elements:
        author, timestamp, body = "N/A", "N/A", "N/A"
        try:
            # The author's name is in a span with class 'fn'
            author = await msg_element.locator("span.fn").text_content()
        except Exception:
            print("      -> Warning: Could not find author for a message.")

        try:
            # The timestamp is in a 'time' element with a datetime attribute
            timestamp_el = msg_element.locator("time")
            timestamp = await timestamp_el.get_attribute("datetime")
        except Exception:
            print("      -> Warning: Could not find timestamp for a message.")

        try:
            # The message body is in 'div.msg-body'
            body = await msg_element.locator("div.msg-body").inner_text()
            # Clean up the body text a bit
            body = "\n".join(line.strip() for line in body.splitlines() if line.strip())
        except Exception:
            print("      -> Warning: Could not find body for a message.")
        
        messages.append({
            "author": author.strip() if author else "N/A",
            "timestamp": timestamp.strip() if timestamp else "N/A",
            "body": body
        })

    return {
        "url": url,
        "title": title.strip() if title else "N/A",
        "messages": messages
    }


# --- Main execution logic ---

async def main():
    # --- Input and Authentication Checks ---
    if not AUTH_FILE.exists():
        print(f"❌ Authentication file '{AUTH_FILE}' not found.")
        print("Please run '01_create_auth_state.py' first to log in.")
        return
        
    if not URLS_FILE.exists():
        print(f"❌ Thread URLs file '{URLS_FILE}' not found.")
        print("Please run the Checkpoint 2 script first to generate it.")
        return

    # --- Load URLs and set up for resume ---
    with open(URLS_FILE, 'r') as f:
        urls_to_scrape = json.load(f)

    scraped_data = {}
    if DATA_FILE.exists():
        print(f"✅ Found existing data file '{DATA_FILE}'. Resuming scrape.")
        with open(DATA_FILE, 'r') as f:
            scraped_data = json.load(f)
    
    # Filter out URLs that have already been scraped
    already_scraped_urls = set(scraped_data.keys())
    urls_to_process = [url for url in urls_to_scrape if url not in already_scraped_urls]
    
    if not urls_to_process:
        print("✅ All URLs have already been scraped. Nothing to do.")
        return
        
    print(f"Found {len(urls_to_scrape)} total URLs. {len(already_scraped_urls)} already scraped.")
    print(f"Starting to scrape {len(urls_to_process)} remaining threads...")
    
    # --- Main Scraping Loop ---
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS_MODE)
        context = await browser.new_context(storage_state=AUTH_FILE)
        page = await context.new_page()

        try:
            total_urls = len(urls_to_process)
            for i, url in enumerate(urls_to_process):
                print(f"\nScraping thread {i+1}/{total_urls}...")
                
                thread_data = await scrape_thread_page(page, url)
                if thread_data:
                    # Use the URL as the key for easy lookup and resuming
                    scraped_data[url] = thread_data
                
                # Save progress periodically
                if (i + 1) % SAVE_EVERY == 0:
                    print(f"\n--- Saving progress ({i+1}/{total_urls} done) ---")
                    with open(DATA_FILE, "w") as f:
                        json.dump(scraped_data, f, indent=2)

        except Exception as e:
            print(f"An unexpected error occurred in the main loop: {e}")
        finally:
            print("\n--- Scrape finished or interrupted. Saving final data... ---")
            with open(DATA_FILE, "w") as f:
                json.dump(scraped_data, f, indent=2)
            print(f"✅ All data saved to '{DATA_FILE}'.")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())