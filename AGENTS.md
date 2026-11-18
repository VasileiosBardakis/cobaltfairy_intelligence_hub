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

# Run LLM theme labeling (requires DEEPSEEK_API_KEY)
.\.venv\Scripts\python.exe theme_labeling.py

# Generate deterministic signals
.\.venv\Scripts\python.exe signals.py

# Run tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Node/JS tooling
pnpm <command>
```

## Conventions

- Keep the implementation minimal; avoid unnecessary abstraction.
- All data lives under `data/`: supplied sources, captured pricing/social data, mappings, themes, and `intel.db`.
- Use a single SQLite database, `data/intel.db`.
- Taxonomy mappings live in `data/mappings.csv`; do not hardcode category mappings in analysis code.
- Captured public pricing lives in `data/pricing_current.csv` with source URLs.
- Captured public social posts live in `data/social_posts.csv`; coverage gaps are in `data/social_coverage.csv`.
- Theme taxonomy is data-driven in `data/theme_taxonomy.csv`; LLM labels are written to `data/theme_labels.csv`.
- Never commit `.env` or API keys.
