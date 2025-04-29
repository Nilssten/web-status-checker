import requests
from bs4 import BeautifulSoup
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from urllib.parse import urljoin
import time


# Function to extract links from a URL
def extract_links(url, attempts=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for attempt in range(attempts):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            links = set()
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    absolute_url = urljoin(url, href)
                    links.add(absolute_url)
            return links, None  # Return links and no error message
        except Exception as e:
            return set(), f"Failed to extract links from {url}: {str(e)}"


# Function to check the status of each link
def check_link(link):
    try:
        r = requests.head(link, allow_redirects=True, timeout=5)
        return (link, r.status_code)
    except requests.RequestException as e:
        return (link, 'ERROR', str(e))


# Function to generate notes for statuses
def get_status_notes(status_code):
    status_notes = {
        200: "OK: The request was successful.",
        400: "Bad Request: The server could not understand the request due to invalid syntax.",
        403: "Forbidden: The server understood the request, but refuses to authorize it.",
        404: "Not Found: The resource could not be found.",
        408: "Request Timeout: The server timed out waiting for the request.",
        429: "Too Many Requests: The user has sent too many requests in a given amount of time.",
        500: "Internal Server Error: The server encountered an unexpected condition.",
        502: "Bad Gateway: The server was unable to process the request due to a problem with a downstream server.",
        503: "Service Unavailable: The server cannot handle the request at the moment, usually due to maintenance.",
        504: "Gateway Timeout: The server did not receive a timely response from the upstream server.",
        999: "Unknown Error: This status code is often used by some servers to indicate an unhandled error.",
        "ERROR": "An error occurred while checking the link."
    }
    return status_notes.get(status_code, "Unexpected status code.")


# Function to crawl and check links for broken status
def crawl_and_check_links(start_url, follow_internal_links=False):
    checked_links = []
    links_to_check, error_message = extract_links(start_url)

    if error_message:
        checked_links.append((start_url, error_message))  # Log the error

    total_links = len(links_to_check)  # Total number of links to check
    print(f"\nLinks extracted from the starting URL: {total_links} links found.")
    print("-" * 50)

    for index, link in enumerate(links_to_check):
        link_data = check_link(link)
        status_code = link_data[1]
        note = get_status_notes(status_code)

        # Store the link entry along with its status and notes
        checked_links.append((link_data[0], status_code, note))

        # Calculate percentage of completion
        progress_percentage = (index + 1) / total_links * 100
        print(f"Progress: {progress_percentage:.2f}% completed.")

        if follow_internal_links and status_code == 200:
            internal_links, _ = extract_links(link)  # Get internal links
            for internal_link in internal_links:
                internal_link_data = check_link(internal_link)
                internal_status_code = internal_link_data[1]
                internal_note = get_status_notes(internal_status_code)
                checked_links.append((internal_link_data[0], internal_status_code, internal_note))

    return pd.DataFrame(checked_links, columns=["Link", "Status Code", "Notes"])


# Function to export results to CSV
def export_to_csv(results, filename='link_statuses.csv'):
    results.to_csv(filename, index=False)
    print(f"\nResults have been exported to '{filename}'.")


# Function to generate statistics and visualize
def generate_statistics(results):
    print("\nSummary Statistics:")

    # Check and convert status to string
    results['Status Code'] = results['Status Code'].astype(str)

    total_links = len(results)
    successful_links = len(results[results['Status Code'] == '200'])
    error_404_links = len(results[results['Status Code'].str.contains('404', na=False)])
    error_429_links = len(results[results['Status Code'].str.contains('429', na=False)])
    error_links = len(results[results['Status Code'].str.contains('ERROR', na=False)])

    # Calculate percentages
    successful_percentage = (successful_links / total_links) * 100 if total_links > 0 else 0
    error_404_percentage = (error_404_links / total_links) * 100 if total_links > 0 else 0
    error_429_percentage = (error_429_links / total_links) * 100 if total_links > 0 else 0
    error_percentage = (error_links / total_links) * 100 if total_links > 0 else 0

    print(f"Total Links Checked: {total_links}")
    print(f"Successful Links: {successful_links} ({successful_percentage:.2f}%)")
    print(f"404 Errors: {error_404_links} ({error_404_percentage:.2f}%)")
    print(f"429 Errors: {error_429_links} ({error_429_percentage:.2f}%)")
    print(f"Other Errors: {error_links} ({error_percentage:.2f}%)")

    # Create a count of status types
    status_counts = results['Status Code'].value_counts(normalize=True).reset_index()
    status_counts.columns = ['Status Code', 'Proportion']

    # Create a bar plot using Seaborn
    plt.figure(figsize=(10, 6))
    sns.barplot(data=status_counts, x='Status Code', y='Proportion', hue='Status Code', palette='viridis', legend=False)
    plt.title('Link Status Proportions')
    plt.xlabel('Status Code')
    plt.ylabel('Proportion')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


# User input for starting URL
if __name__ == "__main__":
    start_url = input("Enter the starting URL (must include http/https): ").strip()
    follow_internal_links = input("Would you like to follow internal links? (yes/no): ").strip().lower() == 'yes'

    results = crawl_and_check_links(start_url, follow_internal_links)

    # Export results to a CSV file
    export_to_csv(results)

    # Generate and display statistics for the collected results
    generate_statistics(results)

    print("Link status check completed.")