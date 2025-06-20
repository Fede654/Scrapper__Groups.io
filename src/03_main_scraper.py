import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# --- Configuration ---
AUTH_FILE = Path("auth_state.json")
URLS_FILE = Path("thread_urls.json") 
DATA_FILE = Path("scraped_data.json") 
HEADLESS_MODE = True
SAVE_EVERY = 10 

# --- UPDATED function for Checkpoint 3 ---

async def scrape_thread_page(page, url):
    """
    Visits a single thread URL and extracts the title and all messages
    using the CORRECTED selectors based on the provided HTML sample.
    """
    print(f"-> Visiting: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Wait for the main message container element to be present.
        await page.wait_for_selector("div.expanded-message", timeout=30000) 
    except TimeoutError:
        print("   -> ⚠️ Timed out waiting for page content. Skipping.")
        return None
    except Exception as e:
        print(f"   -> ❌ Error navigating to page: {e}. Skipping.")
        return None

    # --- Scrape Thread Title (Corrected) ---
    try:
        # The most reliable title is the page's <title> tag.
        full_title = await page.title()
        # Parse "44net@ardc.groups.io | 44. And aredn" to get "44. And aredn"
        title_parts = full_title.split('|')
        title = title_parts[-1].strip() if len(title_parts) > 1 else full_title
    except Exception:
        title = "Title not found"
        print("   -> ⚠️ Could not find thread title.")
        
    # --- Scrape all messages (Corrected) ---
    messages = []
    # Each message is in a 'div.expanded-message'
    message_elements = await page.locator("div.expanded-message").all()
    print(f"   -> Found {len(message_elements)} messages in thread.")

    for msg_element in message_elements:
        author, timestamp, body = "N/A", "N/A", "N/A"
        try:
            # Author is in a <u> tag
            author = await msg_element.locator("u").text_content()
        except Exception:
            print("      -> Warning: Could not find author for a message.")

        try:
            # Timestamp is in the `title` attribute of a <span>
            timestamp_el = msg_element.locator("span[title]")
            timestamp = await timestamp_el.get_attribute("title")
        except Exception:
            print("      -> Warning: Could not find timestamp for a message.")

        try:
            # Message body is in 'div.user-content'
            body = await msg_element.locator("div.user-content").inner_text()
            # Clean up the body text
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


# --- Main execution logic (Unchanged) ---

async def main():
    if not AUTH_FILE.exists():
        print(f"❌ Authentication file '{AUTH_FILE}' not found. Run login script first.")
        return
        
    if not URLS_FILE.exists():
        print(f"❌ Thread URLs file '{URLS_FILE}' not found. Run URL collection script first.")
        return

    with open(URLS_FILE, 'r') as f:
        urls_to_scrape = json.load(f)

    scraped_data = {}
    if DATA_FILE.exists():
        print(f"✅ Found existing data file '{DATA_FILE}'. Resuming scrape.")
        with open(DATA_FILE, 'r') as f:
            scraped_data = json.load(f)
    
    already_scraped_urls = set(scraped_data.keys())
    urls_to_process = [url for url in urls_to_scrape if url not in already_scraped_urls]
    
    if not urls_to_process:
        print("✅ All URLs have already been scraped. Nothing to do.")
        return
        
    print(f"Total URLs: {len(urls_to_scrape)}. Already scraped: {len(already_scraped_urls)}.")
    print(f"Starting to scrape {len(urls_to_process)} remaining threads...")
    
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
                    scraped_data[url] = thread_data
                
                if (i + 1) % SAVE_EVERY == 0 or i == total_urls - 1:
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