#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tqdm import tqdm
from datetime import datetime


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
        r = requests.head(link, allow_redirects=True, timeout=5)
        return (link, r.status_code, None)
    except requests.RequestException as e:
        return (link, "ERROR", str(e))


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

    total_links = len(links_to_check)
    print(f"\nFound {total_links} links on {start_url}")
    print("-" * 50)

    for link in tqdm(links_to_check, desc="Checking links", unit="link"):
        link_data = check_link(link)
        status_code = link_data[1]
        note = get_status_notes(status_code)
        checked_links.append((link_data[0], status_code, note))

        if follow_internal_links and status_code == 200:
            internal_links, _ = extract_links(link)
            for internal_link in internal_links:
                internal_data = check_link(internal_link)
                internal_status_code = internal_data[1]
                internal_note = get_status_notes(internal_status_code)
                checked_links.append((internal_data[0], internal_status_code, internal_note))

    return checked_links


def save_html_report(checked_links):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_file = f"link_report_{now}.html"

    successful = sum(1 for _, code, _ in checked_links if code == 200)
    errors = sum(1 for _, code, _ in checked_links if code == "ERROR")
    broken = sum(1 for _, code, _ in checked_links if code != 200 and code != "ERROR")

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("<html><head><title>Link Report</title></head><body>")
        f.write("<h1>Link Status Report</h1>")
        f.write(f"<p>Total Links Checked: {len(checked_links)}</p>")
        f.write(f"<p>Successful: {successful}</p>")
        f.write(f"<p>Broken: {broken}</p>")
        f.write(f"<p>Errors: {errors}</p><hr>")
        f.write("<ul>")
        for url, status, note in checked_links:
            color = 'green' if status == 200 else 'red'
            f.write(
                f"<li><b style='color:{color}'>{status}</b> - <a href='{url}' target='_blank'>{url}</a>: {note}</li>")
        f.write("</ul></body></html>")

    print(f"\nDetailed report saved to {report_file}")


if __name__ == "__main__":
    start_url = input("Enter the starting URL (must include http/https): ").strip()
    follow_internal = input("Would you like to follow internal links? (yes/no): ").strip().lower() == "yes"

    result = crawl_and_check_links(start_url, follow_internal_links=follow_internal)

    if result:
        save_html_report(result)
    else:
        print("No links found or error occurred.")