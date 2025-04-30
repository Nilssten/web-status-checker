# 🌐 Web Status Checker using WebCrawler

This Python script checks the HTTP status codes of all links found on a given webpage.  
It uses a web crawler approach to extract and validate links — ideal for automation engineers, QA testers, SEO audits, and developers.

---

## 🔍 Features

- Crawls a webpage and collects all internal and external links
- Validates each link's HTTP status code
- Displays real-time progress using `tqdm`
- Designed to run as a standalone test tool
- Works across macOS, Windows, and Dockerized environments

---

## 🧰 Requirements

Python 3.7 or higher.  
Required packages:

- `requests`
- `beautifulsoup4`
- `tqdm`

You can install all dependencies with:

```bash
pip install -r requirements.txt
```

Your `requirements.txt` should contain:

```
requests
beautifulsoup4
tqdm
```

---

## 🚀 How to Use the Script

### ✅ Option 1: Run in Terminal (macOS / Linux)

```bash
cd /path/to/WebStatusChecker
python3 WebCrawler.py
```

### ✅ Option 2: Run in Windows Command Prompt

```cmd
cd path\to\WebStatusChecker
python WebCrawler.py
```

### ✅ Option 3: Run from PyCharm or another IDE

1. Open the folder in PyCharm
2. (Optional) Create and activate a virtual environment
3. Run `WebCrawler.py` via the built-in terminal or Run menu

If you're using Miniconda inside PyCharm, make sure:
- Your project interpreter is set to the correct Conda environment
- The terminal is opened within that environment to use Python commands

---

## 💻 Making It Standalone (for automation use)

To make the script universally usable:

- All core functionality remains the same
- `tqdm` is used for user-friendly progress tracking
- The script is now a CLI-style utility with minimal setup required

---

## 📦 Optional: Run in Docker

### Create a Dockerfile

```Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY link_checker.py .
CMD ["python", "link_checker.py"]
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
├── WebCrawler.py            # Main script
├── requirements.txt           # Dependencies
├── run_web_status_checker_mac.command   # macOS launcher (optional)
├── run_web_status_checker_windows.bat       # Windows launcher (optional)
├── Dockerfile                 # For Dockerized usage (optional)
└── README.md                  # Documentation
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