# Commonize

Commonize is a command line tool that retrieves public financial statement data from the U.S. Securities and Exchange Commission (SEC) and presents it as a common size statement. The project is designed to act as the foundation for a future web application that provides the same functionality.

## Features

- Convert balance sheets or income statements into common size format
- Retrieve data directly from the SEC's XBRL API
- Cache ticker-to-CIK mappings locally for faster repeated use
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

## Development roadmap

1. **Local CLI (current stage)** – Fetch SEC data and render common size statements in the terminal.
2. **API service** – Expose the functionality through a lightweight REST API.
3. **Web application** – Build a front-end that calls the API and deploy both components to the cloud.
4. **Automation & monitoring** – Add background jobs, logging, and observability to ensure reliability.

Contributions and ideas are welcome!
