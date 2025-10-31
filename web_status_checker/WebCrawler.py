#!/usr/bin/env python3
from jinja2 import Environment, FileSystemLoader
import httpx
import asyncio
from bs4 import BeautifulSoup
import urllib.parse
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
from pathlib import Path
import aiohttp
import json
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import ssl

def create_secure_tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    return context

@dataclass_json
@dataclass
class LinkInfo:
    url: str
    status_code: int
    source_type: str
    source_url: str
    note: str
    final_url: str = ""
    redirect_count: int = 0
    redirect_chain: list[str] = None

log_path = Path("test-results/errors.log")

SSL_CONTEXT = create_secure_tls_context()

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/113.0.0.0 Safari/537.36"
}

class LinkChecker:
    def extract_links(self, url, attempts=3):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/115.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Referer": url
        }

        for attempt in range(attempts):
            try:
                response = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)

                if "html" not in response.headers["Content-Type"]:
                    logging.warning(f"Non-HTML content received from {url}. Skipping link extraction.")
                    return set(), "Non-HTML content"

                soup = BeautifulSoup(response.text, 'html.parser')
                links = set()
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if href:
                        absolute_url = urljoin(url, href)
                        links.add(absolute_url)

                logging.info(f"Extracted {len(links)} links from {url}")
                return links, None

            except httpx.RequestError as e:
                logging.warning(f"Request failed for {url}: {str(e)}")
                if attempt == attempts - 1:
                    return set(), str(e)
            except Exception as e:
                logging.warning(f"Error extracting links from {url}: {str(e)}")
                if attempt == attempts - 1:
                    return set(), str(e)

    async def fetch_with_redirects(self, client, url: str, retries=2):
        """
        Checks a URL, following redirects and returning final status and chain.
        Handles Cloudflare 520/522/524 and timeouts gracefully.
        """
        for attempt in range(retries + 1):
            try:
                # normal request first
                response = await client.get(url, headers=DEFAULT_HEADERS, follow_redirects=True, timeout=20)

                chain = [str(r.url) for r in response.history] + [str(response.url)]
                redirect_count = len(chain) - 1
                final_status = response.status_code
                final_url = str(response.url)

                # Handle Cloudflare-style 520/522/524 responses
                if final_status in {520, 522, 524}:
                    logging.warning(
                        f"Cloudflare-style error {final_status} on {url}. Retrying without HTTP/2..."
                    )
                    await asyncio.sleep(2)
                    # Retry once using a client without HTTP/2
                    transport = httpx.AsyncHTTPTransport(http2=False)
                    async with httpx.AsyncClient(transport=transport, timeout=20) as temp_client:
                        response = await temp_client.get(url, headers=DEFAULT_HEADERS, follow_redirects=True)
                        final_status = response.status_code
                        final_url = str(response.url)
                        chain = [str(r.url) for r in response.history] + [str(response.url)]
                        redirect_count = len(chain) - 1
                    if final_status in {520, 522, 524}:
                        return url, final_status, f"Cloudflare error {final_status}", url, 0, []

                note = self.get_status_notes(final_status)
                if redirect_count > 0:
                    note += f" (Redirected {redirect_count}x → {final_url})"

                return url, final_status, note, final_url, redirect_count, chain

            except httpx.ReadTimeout:
                error_msg = "ReadTimeout"
            except httpx.RequestError as e:
                error_msg = f"RequestError: {e.__class__.__name__}"
            except Exception as e:
                error_msg = f"UnhandledError: {str(e)}"

            logging.warning(f"Attempt {attempt + 1} failed for {url}: {error_msg}")
            if attempt == retries:
                return url, "ERROR", error_msg, url, 0, []
            await asyncio.sleep(2)

    async def check_link_async(self, client, link, retries=2):
        """
        Checks a link asynchronously, skipping binary files and delegating to fetch_with_redirects.
        """
        binary_extensions = [".pdf", ".zip", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg", ".gif"]
        is_binary_file = any(link.lower().endswith(ext) for ext in binary_extensions)

        if is_binary_file:
            # skip content fetch, just confirm reachable
            try:
                response = await client.head(link, headers=DEFAULT_HEADERS, timeout=10)
                note = self.get_status_notes(response.status_code) + " (binary file)"
                return link, response.status_code, note, link, 0, []
            except Exception as e:
                return link, "ERROR", f"BinaryCheckError: {e}", link, 0, []

        # Otherwise handle normally (with redirect following)
        return await self.fetch_with_redirects(client, link, retries)

    async def check_all_links_async(self, links):
        results = []
        async with httpx.AsyncClient(http2=True, timeout=10, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            tasks = [self.check_link_async(client, link) for link in links]
            for coro in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc="Checking links"):
                url, status, note, final_url, redirect_count, chain = await coro
                results.append((url, status, note, final_url, redirect_count, chain))
        return results

    def get_status_notes(self, status_code: int) -> str:
        status_notes: Dict[Union[int,str], str] = {
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

    async def crawl_recursive(self, url, current_depth, max_depth, seen_links, checked_links):
        if current_depth > max_depth:
            return

        internal_links, _ = self.extract_links(url)
        internal_links = [
            link for link in internal_links
            if link not in seen_links and link and not link.lower().startswith("javascript:")
        ]
        seen_links.update(internal_links)

        if internal_links:
            internal_results = await self.check_all_links_async(internal_links)
            for link, status_code, note, final_url, redirect_count, chain in internal_results:
                checked_links.append(LinkInfo(
                    url=link,
                    status_code=status_code,
                    note=note,
                    source_type='link',
                    source_url=url,
                    final_url=final_url,
                    redirect_count=redirect_count,
                    redirect_chain=chain
                ))
                logging.info(f"Checked internal {link} - {status_code} - {note}")

                # Recurse only if the final URL responded successfully
                if str(status_code).isdigit() and int(status_code) < 400:
                    await self.crawl_recursive(link, current_depth + 1, max_depth, seen_links, checked_links)

    async def crawl_and_check_links(self, start_url, follow_internal_links=False, max_depth=1):
        checked_links = []
        seen_links = set([start_url])

        def filter_new_links(links):
            return [
                link for link in links
                if link not in seen_links and link and not link.lower().startswith("javascript:")
            ]

        # Step 1: Extract visible <a> links
        links_to_check, error_message = self.extract_links(start_url)
        if error_message:
            logging.error(f"Error extracting links from {start_url}: {error_message}")
            print(f"Error extracting links: {error_message}")
            return checked_links

        links_to_check = filter_new_links(links_to_check)
        seen_links.update(links_to_check)

        print(f"\nFound {len(links_to_check)} links on {start_url}")
        print("-" * 50)

        results = await self.check_all_links_async(links_to_check)

        for link, status_code, note, final_url, redirect_count, chain in results:
            checked_links.append(LinkInfo(
                url=link,
                status_code=status_code,
                note=note,
                source_type='link',
                source_url=start_url,
                final_url=final_url,
                redirect_count=redirect_count,
                redirect_chain=chain
            ))
            logging.info(f"Checked {link} - {status_code} - {note}")

        # Recursive crawling if enabled
        if follow_internal_links:
            await self.crawl_recursive(start_url, current_depth=1, max_depth=max_depth,
                                       seen_links=seen_links, checked_links=checked_links)

        # Step 2: Try sitemap.xml
        sitemap_url = urljoin(start_url, '/sitemap.xml')
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sitemap_url) as response:
                    if response.status == 200:
                        text = await response.text()
                        soup = BeautifulSoup(text, 'xml')
                        urls = [loc.text for loc in soup.find_all('loc')]
                        new_links = filter_new_links(urls)
                        seen_links.update(new_links)

                        sitemap_results = await self.check_all_links_async(new_links)
                        for sm_link, sm_status, sm_note, sm_final, sm_redirects, sm_chain in sitemap_results:
                            checked_links.append(LinkInfo(
                                url=sm_link,
                                status_code=sm_status,
                                note=sm_note,
                                source_type='sitemap',
                                source_url=start_url,
                                final_url=sm_final,
                                redirect_count=sm_redirects,
                                redirect_chain=sm_chain
                            ))
                            logging.info(f"Checked sitemap {sm_link} - {sm_status} - {sm_note}")
                    else:
                        logging.info(f"Sitemap not found at {sitemap_url}, status: {response.status}")
        except Exception as e:
            logging.error(f"Error fetching sitemap.xml: {e}")

        # Step 3: Parse form actions
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(start_url) as response:
                    if response.status == 200:
                        text = await response.text()
                        soup = BeautifulSoup(text, 'html.parser')
                        form_actions = [urljoin(start_url, form.get('action'))
                                        for form in soup.find_all('form') if form.get('action')]
                        form_links = filter_new_links(form_actions)
                        seen_links.update(form_links)

                        form_results = await self.check_all_links_async(form_links)
                        for form_link, form_status, form_note, form_final, form_redirects, form_chain in form_results:
                            checked_links.append(LinkInfo(
                                url=form_link,
                                status_code=form_status,
                                note=form_note,
                                source_type='form',
                                source_url=start_url,
                                final_url=form_final,
                                redirect_count=form_redirects,
                                redirect_chain=form_chain
                            ))
                            logging.info(f"Checked form {form_link} - {form_status} - {form_note}")
        except Exception as e:
            logging.error(f"Error extracting form actions: {e}")

        return checked_links

    def save_html_report(self, checked_links: list[LinkInfo], filename=None):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_file = filename or f"test-results/link_report_{now}.html"

        # Count stats
        successful = sum(1 for link in checked_links if link.status_code == 200 and link.redirect_count == 0)
        errors = sum(1 for link in checked_links if link.status_code == "ERROR")
        broken = sum(1 for link in checked_links if
                     link.status_code != 200 and link.status_code != "ERROR" and link.redirect_count == 0)
        redirected = sum(1 for link in checked_links if getattr(link, "redirect_count", 0) > 0)

        csv_content = "URL,Status,SourceType,SourceURL\n"

        render_links = []
        for link in checked_links:
            safe_note = self.get_status_notes(link.status_code).replace(",", " ").replace("\n", " ")
            csv_content += f'"{link.url}",{link.status_code},"{safe_note}","{link.source_url}"\n'

            domain = urlparse(link.url).netloc
            source_domain = urlparse(link.source_url).netloc
            if ".gov" in domain or ".edu" in domain:
                source_class = "trusted"
            elif domain == source_domain:
                source_class = "internal"
            else:
                source_class = ""

            render_links.append({
                "url": link.url,
                "status_code": link.status_code,
                "note": link.note,
                "source_type": link.source_type,
                "redirect_count": link.redirect_count,
                "final_url": link.final_url or link.url,
                "is_binary": getattr(link, 'is_binary', False),
                "class": source_class
            })

        # Jinja2 templating
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('report.html')

        rendered_html = template.render(
            total=len(checked_links),
            successful=successful,
            broken=broken,
            errors=errors,
            redirected=redirected,
            links=render_links,
            csv_content=csv_content,
            timestamp=now
        )

        os.makedirs("test-results", exist_ok=True)
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        full_path = os.path.abspath(report_file)
        print(f"\n✅ Detailed report saved to: file://{full_path}")
        print(f"🪵 Error log saved to: file://{log_path.resolve()}")

    def save_json_report(self, checked_links: list[LinkInfo], filename="test-results/link_info.json"):
        os.makedirs("test-results", exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump([link.to_dict() for link in checked_links], f, indent=2, ensure_ascii=False)
        print(f"📝 JSON report saved to: file://{os.path.abspath(filename)}")

async def main():
    parser = argparse.ArgumentParser(description="Link checker")
    parser.add_argument('--url', type=str, help='Starting URL (must include http/https)')
    parser.add_argument('--follow', action='store_true', help='Follow internal links')
    parser.add_argument('--fail-on-broken', action='store_true', help='Exit with error if any broken or error links found')
    parser.add_argument('--max-depth', type=int, help='Maximum depth for internal link crawling')

    args = parser.parse_args()

    if args.url:
        start_url = args.url
        follow_internal = args.follow
        fail_on_broken = args.fail_on_broken
    else:
        start_url = input("Enter the starting URL (must include http/https): ").strip()
        follow_input = input("Would you like to follow internal links? (yes/no): ").strip().lower()
        follow_internal = follow_input in ["yes", "y"]
        fail_input = input("Fail if broken links are found? (yes/no): ").strip().lower()
        fail_on_broken = fail_input in ["yes", "y"]

    max_depth = args.max_depth

    # Ask for max depth only if following internal links
    if follow_internal:
        if max_depth is None:
            try:
                max_depth = int(input("Enter max crawl depth (e.g., 2): "))
            except ValueError:
                print("Invalid input. Using default depth of 1.")
                max_depth = 1
    else:
        max_depth = 0  # Not used, but explicitly set

    checker = LinkChecker()
    checked_links = await checker.crawl_and_check_links(
        start_url,
        follow_internal_links=follow_internal,
        max_depth=max_depth
    )

    checker = LinkChecker()  # Create an instance of your class

    # Call the method on your instance and await it
    result = await checker.crawl_and_check_links(start_url, follow_internal_links=follow_internal)

    if result:
        checker.save_html_report(result)  # Generate HTML report
        checker.save_json_report(result)  # <-- Save JSON file

        if fail_on_broken:
            broken_count = sum(
                1 for link in result if link.status_code != 200 and link.status_code != "ERROR"
            )
            if broken_count > 0:
                print(f"\n❌ {broken_count} broken/error links found. Exiting with error code 1.")
                sys.exit(1)
    else:
        print("No links found or an error occurred.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
