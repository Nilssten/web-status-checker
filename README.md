# 🌐 Web Status Checker using WebCrawler

This project checks the HTTP status codes of all links found on a given webpage.  
It uses a web crawler approach to extract and validate links — ideal for automation engineers, QA testers, SEO audits, and developers.

---

## 🔍 Features

- Crawls a webpage and collects all internal and external links
- Validates each link's HTTP status code
- Displays real-time progress using `tqdm`
- Accepts command-line arguments for easy automation
- Integrates with Playwright for end-to-end test automation
- Works across macOS, Windows, and Dockerized environments

---

## 🧰 Requirements

### Python Dependencies

Python 3.7 or higher.  
Install the required packages with:

```bash
pip install -r requirements.txt
```

Your `requirements.txt` should contain:

```
requests
beautifulsoup4
tqdm
```

### Node.js Dependencies
Install Node.js (v16+ recommended), then install Playwright:

```bash
npm install -D @playwright/test
npx playwright inst
```
---

## 🚀 How to Use the Script

### ✅ Option 1: Run in Terminal (macOS / Linux)

```bash
cd /path/to/WebStatusChecker
python3 webcrawler.py --url https://example.com --follow
```

### ✅ Option 2: Run in Windows Command Prompt

```cmd
cd path\to\WebStatusChecker
python webcrawler.py --url https://example.com --follow
```

### ✅ Option 3: Run from PyCharm or another IDE

1.	Open the folder in PyCharm
2. (Optional) Create and activate a virtual environment
3. Run webcrawler.py via the built-in terminal or Run menu
If no arguments are provided, it will prompt you for:
	•	A starting URL
	•	Whether to follow internal links (yes / no)

If you're using Miniconda inside PyCharm, make sure:
- Your project interpreter is set to the correct Conda environment
- The terminal is opened within that environment to use Python commands

### ✅ Option 4: Run as a Playwright Test
This project includes a Playwright test that runs the Python script and captures its output.
To execute it:
```bash
npx playwright test
```
Ensure python3 points to the correct environment or adjust to python based on your setup.

#### 📝 Results are saved as html file in test-results folder

---

## ⚙️ CLI Arguments

You can pass arguments directly to skip prompts, useful for automated tests or scripting:

| Argument       | Description                                           | Example                               |
|----------------|-------------------------------------------------------|---------------------------------------|
| `--url`        | Starting URL to crawl (must include http/https)      | `--url https://linkedin.com`          |
| `--follow`     | Follow internal links found during crawling           | `--follow`                            |

* If `--url` is provided, the script **won’t prompt you** for input. Use `--follow` if you want to crawl internal pages as well.
---

## 📦 Optional: Run in Docker

### Create a Dockerfile

```Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY webcrawler.py .
CMD ["python", "webcrawler.py"]
```

### Build & Run

```bash
docker build -t link-checker .
docker run -it link-checker
```

---

## 🖱️ Optional: Run by Double-Click

### macOS (.command file)

1. Double-click a file called `run_web_status_checker_mac.command`

### Windows (.bat file)

1. Double-click a file called `run_web_status_checker_windows.command`


## 📁 Project Structure

```
WebStatusChecker/
│
├── webcrawler.py                        # Main script
├── requirements.txt                    # Python dependencies
├── tests/
│   └── webcrawler.spec.ts              # Playwright test runner
├── Dockerfile                          # For Dockerized usage (optional)
├── run_web_status_checker_mac.command  # macOS launcher (optional)
├── run_web_status_checker_windows.bat  # Windows launcher (optional)
└── README.md                           # Documentation
```

---

## 🧪 Automation Engineering Tips

- Schedule runs via `cron` (Unix) or Task Scheduler (Windows)
- Add CSV/JSON export for link status results
- Modify to accept multiple URLs as input
- Integrate into CI/CD for automated uptime or SEO checks

---

## 📜 License

MIT — feel free to use, modify, and distribute responsibly.

---

## 👨‍🔧 Author

Created by Nils Stenkēvičs 
Automation-ready and lightweight by design.