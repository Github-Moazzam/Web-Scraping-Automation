# Automated URL Processing & NER Pipeline

An automated pipeline that retrieves URLs from a backend API, visits them using a headless browser, detects **person names** using AI/NLP models, and triggers crawl jobs for valid pages — all in parallel.

---

## How It Works

1. Fetches pending URLs from the backend API
2. Opens each URL in a headless Chromium browser (via Playwright)
3. Extracts and cleans visible page text
4. Runs **Named Entity Recognition (NER)** to detect person names
5. If a name is found → triggers a crawl job via the extension API
6. Monitors crawl status and updates each instance accordingly
7. Flags invalid/unreachable pages with appropriate error types

---

## Models Used

| Model | Source |
|-------|--------|
| `Davlan/bert-base-multilingual-cased-ner-hrl` | HuggingFace | 
| `urchade/gliner_multi_pii-v1` | HuggingFace / GLiNER |

Both models are loaded once at startup to avoid repeated overhead.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Github-Moazzam/Web-Scraping-Automation

cd Web-Scraping-Automation
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser

```bash
playwright install chromium
```

---

## Configuration

### 1. Copy the example env file

```bash
cp .env.example .env
```

## Usage

```bash
python main.py
```

You will be prompted to enter the number of URLs to process:

```
How many URLs to process: 50
```

The script will then start processing URLs in parallel (up to 12 concurrent browser sessions by default).

---

## Project Structure

```
aml-watcher/
├── main.py              # Main script
├── .env                 # Your local secrets (never commit this)
├── .env.example         # Template env file (safe to commit)
├── requirements.txt     # Python dependencies
├── .gitignore           # Files excluded from Git
└── README.md            # This file
```

---

## Configuration Options

Inside `main.py`, you can adjust these values:

```python
MAX_CONCURRENT_BROWSERS = 12   # Max parallel browser sessions
```

Increasing this beyond 12 may cause memory issues depending on your machine.

---

## Error Types

The script automatically categorizes failed URLs:

| Error Type | Meaning |
|------------|---------|
| `invalid_source` | No person name found, or crawl could not be triggered |
| `proxy_issue` | Page is blocked by IP-based protection |
| `google_captcha_v2` | Page requires CAPTCHA verification |
| `source_issue` | Website did not load within the timeout |
| `deo_backend_issues` | Crawl job failed on the backend |
| `data_in_document` | URL points to a PDF, not a webpage |
