#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tqdm import tqdm
from datetime import datetime
import argparse
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed


def extract_links(url, attempts=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    for _ in range(attempts):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            links = set()
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    absolute_url = urljoin(url, href)
                    links.add(absolute_url)
            return links, None
        except Exception as e:
            return set(), str(e)


def check_link(link):
    try:
        response = requests.head(link, timeout=10, allow_redirects=True)
        return (link, response.status_code)
    except Exception as e:
        return (link, str(e))

def check_all_links_concurrently(links, max_workers=10):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(check_link, url): url for url in links}
        for future in as_completed(future_to_url):
            link, status = future.result()
            results.append((link, status))
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


def crawl_and_check_links(start_url, follow_internal_links=False):
    checked_links = []
    links_to_check, error_message = extract_links(start_url)

    if error_message:
        print(f"Error extracting links: {error_message}")
        return checked_links

    print(f"\nFound {len(links_to_check)} links on {start_url}")
    print("-" * 50)

    # Main batch of links (first layer)
    results = check_links_concurrently(links_to_check)
    for link, status_code in results:
        note = get_status_notes(status_code)
        checked_links.append((link, status_code, note))

        # If --follow is set and the link is OK, crawl internal links too
        if follow_internal_links and status_code == 200:
            internal_links, _ = extract_links(link)
            internal_results = check_links_concurrently(internal_links)
            for int_link, int_status_code in internal_results:
                note = get_status_notes(int_status_code)
                checked_links.append((int_link, int_status_code, note))

    return checked_links


def save_html_report(checked_links, filename=None):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_file = filename or f"test-results/link_report_{now}.html"

    successful = sum(1 for _, code, _ in checked_links if code == 200)
    errors = sum(1 for _, code, _ in checked_links if code == "ERROR")
    broken = sum(1 for _, code, _ in checked_links if code != 200 and code != "ERROR")

    # Prepare CSV content
    csv_content = "URL,Status,Note\n"
    for url, status, note in checked_links:
        safe_note = note.replace(",", " ").replace("\n", " ")
        csv_content += f'"{url}",{status},"{safe_note}"\n'

    # JavaScript for CSV download + filtering
    scripts = f"""
    <script>
    function downloadCSV() {{
        const csvData = `{csv_content}`;
        const blob = new Blob([csvData], {{ type: 'text/csv' }});
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', 'link_report_{now}.csv');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }}

    function filterLinks(statusType) {{
        const items = document.querySelectorAll('li');
        items.forEach(item => {{
            if (statusType === 'all') {{
                item.style.display = 'list-item';
            }} else if (item.classList.contains(statusType)) {{
                item.style.display = 'list-item';
            }} else {{
                item.style.display = 'none';
            }}
        }});
    }}
    </script>
    """

    # Begin HTML report
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("<html><head><title>Link Report</title></head><body>")
        f.write("<h1>Link Status Report</h1>")
        f.write(f"<p>Total Links Checked: {len(checked_links)}</p>")
        f.write(f"<p>✅ Successful: {successful}</p>")
        f.write(f"<p>❌ Broken: {broken}</p>")
        f.write(f"<p>⚠️ Errors: {errors}</p><hr>")

        # Buttons for filtering and CSV
        f.write("""
            <button onclick="filterLinks('all')">Show All</button>
            <button onclick="filterLinks('success')">✅ Passed Only</button>
            <button onclick="filterLinks('fail')">❌ Failed Only</button>
            <button onclick="filterLinks('error')">⚠️ Errors Only</button>
            <button onclick="downloadCSV()">⬇️ Download CSV</button>
            <hr>
        """)
        f.write(scripts)

        # Link list
        f.write("<ul>")
        for url, status, note in checked_links:
            if status == 200:
                css_class = "success"
                color = "green"
            elif status == "ERROR":
                css_class = "error"
                color = "orange"
            else:
                css_class = "fail"
                color = "red"

            f.write(f"<li class='{css_class}'><b style='color:{color}'>{status}</b> - <a href='{url}' target='_blank'>{url}</a>: {note}</li>")
        f.write("</ul></body></html>")

    print(f"\n✅ Detailed report saved to {report_file}")


def main():
    parser = argparse.ArgumentParser(description="Link checker")
    parser.add_argument('--url', type=str, help='Starting URL (must include http/https)')
    parser.add_argument('--follow', action='store_true', help='Follow internal links')
    parser.add_argument('--fail-on-broken', action='store_true', help='Exit with error if any broken or error links found')  # <-- NEW FLAG

    args = parser.parse_args()

    if args.url:
        start_url = args.url
        follow_internal = args.follow
    else:
        start_url = input("Enter the starting URL (must include http/https): ").strip()
        follow_internal = input("Would you like to follow internal links? (yes/no): ").strip().lower() == "yes"

    result = crawl_and_check_links(start_url, follow_internal_links=follow_internal)

    if result:
        save_html_report(result)

        if args.fail_on_broken:
            broken_count = sum(1 for _, code, _ in result if code != 200)
            if broken_count > 0:
                print(f"\n❌ {broken_count} broken/error links found. Exiting with error code 1.")
                sys.exit(1)

    else:
        print("No links found or error occurred.")


if __name__ == "__main__":
    main()