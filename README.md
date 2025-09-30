# Commonize

Commonize turns U.S. Securities and Exchange Commission (SEC) filings into common size financial statements. The project ships
with both a command line interface and a modern FastAPI web experience that renders statements, complete with CSV and Excel
export options.


## Features

- Convert balance sheets or income statements into common size format
- Retrieve data directly from the SEC's XBRL API
- Cache ticker-to-CIK mappings locally for faster repeated use
- Modern web UI for viewing statements and downloading CSV or Excel exports
- Friendly command line interface with optional GitHub-flavored markdown output

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set a descriptive user agent via the `COMMONIZE_USER_AGENT` environment variable to comply with SEC rate limiting guidance.

```bash
export COMMONIZE_USER_AGENT="CommonizeApp/0.1 (contact@example.com)"
```

## Usage

```bash
python main.py AAPL --statement income --period annual
```

Available options:

- `ticker`: Ticker symbol or CIK
- `--statement`: `income` or `balance`
- `--period`: `annual` or `quarterly`
- `--force-refresh`: Refreshes the cached ticker metadata

### Running the web application

```bash
uvicorn commonize.web:create_app --factory --reload
```

Then open <http://127.0.0.1:8000> in your browser, enter a ticker symbol (for example, `AAPL`), and generate a statement. The
interface renders the common size view and exposes download buttons for CSV and Excel exports.

## Development roadmap

1. **Local CLI** – Fetch SEC data and render common size statements in the terminal.
2. **Interactive web experience (current stage)** – Serve the statements through FastAPI with downloadable exports.
3. **Deployment** – Package and deploy the application to a managed cloud platform.
4. **Automation & monitoring** – Add background jobs, logging, and observability to ensure reliability.

Contributions and ideas are welcome!
