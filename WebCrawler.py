#!/usr/bin/env python3
from jinja2 import Environment, FileSystemLoader
import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio
from datetime import datetime
import argparse
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import logging

logging.basicConfig(
    filename='crawler.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def extract_links(url, attempts=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': url,
        'Accept': 'text/html,application/xhtml+xml',
    }

    for attempt in range(attempts):
        try:
            response = httpx.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            links = set()
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    absolute_url = urljoin(url, href)
                    links.add(absolute_url)
            logging.info(f"Extracted {len(links)} links from {url}")
            return links, None
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt == attempts - 1:
                return set(), str(e)

async def check_link_async(client, link, retries=2):
    for attempt in range(retries + 1):
        try:
            response = await client.head(link, follow_redirects=True, timeout=10)
            return (link, response.status_code, "")
        except httpx.ConnectTimeout:
            error_msg = "ConnectTimeout"
        except httpx.RequestError as e:
            error_msg = f"RequestError: {e.__class__.__name__}"
        except Exception as e:
            error_msg = f"UnhandledError: {str(e)}"

        logging.warning(f"Attempt {attempt + 1} failed for {link}: {error_msg}")
        if attempt == retries:
            return (link, "ERROR", error_msg)
        await asyncio.sleep(1)

async def check_all_links_async(links):
    results = []
    async with httpx.AsyncClient(http2=True, timeout=10) as client:
        tasks = [check_link_async(client, link) for link in links]
        for coro in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc="Checking links"):
            result = await coro
            results.append(result)
    return results


def get_status_notes(status_code):
    status_notes = {
        200: "OK: The request was successful.",
        400: "Bad Request: Invalid syntax.",
        403: "Forbidden: Access denied.",
        404: "Not Found: The resource could not be found.",
        408: "Request Timeout: The server timed out waiting for the request.",
        429: "Too Many Requests: The user has sent too many requests in a given amount of time.",
        500: "Internal Server Error: The server encountered an unexpected condition.",
        502: "Bad Gateway: The server received an invalid response from the upstream server.",
        503: "Service Unavailable: The server cannot handle the request at the moment.",
        504: "Gateway Timeout: The upstream server failed to send a request in time.",
        999: "Custom Error: Often used by some servers for unhandled errors.",
        "ERROR": "An error occurred while checking the link."
    }
    return status_notes.get(status_code, "Unexpected status code.")


async def crawl_and_check_links(start_url, follow_internal_links=False):
    checked_links = []
    seen_links = set()

    def filter_new_links(links):
        return [link for link in links if link not in seen_links]

    links_to_check, error_message = extract_links(start_url)
    if error_message:
        logging.error(f"Error extracting links from {start_url}: {error_message}")
        print(f"Error extracting links: {error_message}")
        return checked_links

    links_to_check = filter_new_links(links_to_check)
    seen_links.update(links_to_check)

    print(f"\nFound {len(links_to_check)} links on {start_url}")
    print("-" * 50)

    results = await check_all_links_async(links_to_check)

    for link, status_code, error in results:
        note = get_status_notes(status_code)
        checked_links.append((link, status_code, note, 'start_url'))
        logging.info(f"Checked {link} - {status_code} - {note}")

        if follow_internal_links and status_code == 200:
            internal_links, _ = extract_links(link)
            internal_links = filter_new_links(internal_links)
            seen_links.update(internal_links)

            if internal_links:
                internal_results = await check_all_links_async(internal_links)
                for int_link, int_status_code, int_error in internal_results:
                    int_note = get_status_notes(int_status_code)
                    checked_links.append((int_link, int_status_code, int_note, 'internal'))
                    logging.info(f"Checked internal {int_link} - {int_status_code} - {int_note}")

    return checked_links

def save_html_report(checked_links, filename=None):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_file = filename or f"test-results/link_report_{now}.html"

    # Count stats
    successful = sum(1 for _, code, _, _ in checked_links if code == 200)
    errors = sum(1 for _, code, _, _ in checked_links if code == "ERROR")
    broken = sum(1 for _, code, _, _ in checked_links if code != 200 and code != "ERROR")

    # Prepare CSV content
    csv_content = "URL,Status,Note,Source\n"

    # Prepare structured data for rendering
    render_links = []
    for url, status, note, source in checked_links:
        safe_note = note.replace(",", " ").replace("\n", " ")
        csv_content += f'"{url}",{status},"{safe_note}",{source}\n'

        domain = urlparse(url).netloc
        source_domain = urlparse(source).netloc
        if ".gov" in domain or ".edu" in domain:
            source_class = "trusted"
        elif domain == source_domain:
            source_class = "internal"
        else:
            source_class = ""

        render_links.append({
            "url": url,
            "status": status,
            "note": note,
            "source": source,
            "class": source_class
        })

    # Set up Jinja2
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('report.html')

    # Render HTML template
    rendered_html = template.render(
        total=len(checked_links),
        successful=successful,
        broken=broken,
        errors=errors,
        links=render_links,
        csv_content=csv_content,
        timestamp=now
    )

    # Save to file
    os.makedirs("test-results", exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    full_path = os.path.abspath(report_file)
    print(f"\n✅ Detailed report saved to: file://{full_path}")

def main():
    parser = argparse.ArgumentParser(description="Link checker")
    parser.add_argument('--url', type=str, help='Starting URL (must include http/https)')
    parser.add_argument('--follow', action='store_true', help='Follow internal links')
    parser.add_argument('--fail-on-broken', action='store_true', help='Exit with error if any broken or error links found')

    args = parser.parse_args()

    if args.url:
        start_url = args.url
        follow_internal = args.follow
        fail_on_broken = args.fail_on_broken
    else:
        start_url = input("Enter the starting URL (must include http/https): ").strip()
        follow_internal = input("Would you like to follow internal links? (yes/no): ").strip().lower() in ["yes", "y"]
        fail_on_broken = input("Fail if broken links are found? (yes/no): ").strip().lower() in ["yes", "y"]

    result = asyncio.run(crawl_and_check_links(start_url, follow_internal_links=follow_internal))

    if result:
        save_html_report(result)

        if fail_on_broken:
            broken_count = sum(1 for _, code, _, _ in result if code != 200 and code != "ERROR")
            if broken_count > 0:
                print(f"\n❌ {broken_count} broken/error links found. Exiting with error code 1.")
                sys.exit(1)
    else:
        print("No links found or an error occurred.")


if __name__ == "__main__":
    main()