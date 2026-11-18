# AGENTS.md

## Project

Market & Competitive Intelligence Hub prototype for Cobalt Fairy and FairyMail.

## Stack

- Python 3.13 + pandas + SQLite + Streamlit
- DeepSeek API (OpenAI-compatible) for the AI-assisted capability
- pnpm is the package manager for any Node/JS tooling (never npm or yarn)
- Python dependencies use `.venv` + `pip` (pnpm does not manage Python)

## Commands

```powershell
# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install Python dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run the dashboard
.\.venv\Scripts\python.exe -m streamlit run app.py

# Run ingestion
.\.venv\Scripts\python.exe ingest.py

# Run the analysis smoke check
.\.venv\Scripts\python.exe analysis.py

# Run the pricing comparison smoke check
.\.venv\Scripts\python.exe pricing.py

# Node/JS tooling
pnpm <command>
```

## Conventions

- Keep the implementation minimal; avoid unnecessary abstraction.
- Raw supplied data stays in `cobaltfairy-data/`.
- Use a single SQLite database, `intel.db`, at the repo root.
- Taxonomy mappings live in `mappings.csv`; do not hardcode category mappings in analysis code.
- Captured public pricing lives in `pricing_current.csv` with source URLs.
- Captured public social posts live in `social_posts.csv`; coverage gaps are in `social_coverage.csv`.
- Never commit `.env` or API keys.
