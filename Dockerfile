FROM python:3.11-slim

WORKDIR /app

# Copy requirement file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python script and run it when container starts
COPY WebCrawler.py .

CMD ["python", "WebCrawler.py"]