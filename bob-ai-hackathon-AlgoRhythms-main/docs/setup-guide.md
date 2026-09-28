# Setup Guide

> **This file is read by the automated evaluation pipeline. Be precise and complete.**

GoldenHour Grid is a single Python application (Streamlit UI plus Python engines). It needs **no database, no Node.js and no Docker**. All data is synthetic and generated locally. The AI text layer is optional: without credentials the app falls back to built-in templates and still runs fully.

## Prerequisites

Before you begin, ensure you have the following installed:

- [ ] Python 3.10 or newer (`python --version`)
- [ ] pip (bundled with Python)
- [ ] Git
- [ ] A modern web browser (Chrome, Edge or Firefox)
- [ ] *(Optional)* An LLM/AI service account, for example IBM Cloud with watsonx.ai access, to enable AI-written text. Not required to run the app.

## Environment Variables

All variables are **optional**. If none are set, `llm.py` uses its template-based fallback and every feature still works.

Copy `.env.example` to `.env` and fill in only what you use:

```bash
cp .env.example .env
```

On Windows (Command Prompt): `copy .env.example .env`

| Variable | Description | Required |
|---|---|---|
| `LLM_PROVIDER` | AI provider name used by `llm.py` (for example `watsonx`). Leave empty to use the template fallback | No |
| `WATSONX_API_KEY` | IBM watsonx.ai API key (only if `LLM_PROVIDER=watsonx`) | No |
| `WATSONX_PROJECT_ID` | watsonx.ai project ID (only if `LLM_PROVIDER=watsonx`) | No |
| `WATSONX_URL` | watsonx.ai endpoint URL for your region (only if `LLM_PROVIDER=watsonx`) | No |

Never commit `.env` to git. It must be listed in `.gitignore`.

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/[your-org]/[your-repo].git
cd [your-repo]

# 2. (Recommended) Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate the synthetic data (required, run once)
python mockdata.py
```

Step 4 creates `data/crimes.csv`, `data/events.csv` and `data/case.json`. The app will not show results until these files exist. There is no database to set up.

`requirements.txt` includes: `streamlit`, `pandas`, `numpy`, `folium`, `streamlit-folium`, `python-docx`.

## Running the Application

```bash
streamlit run app.py
```

The application will be available at: `http://localhost:8501`

If the browser does not open automatically, open that address manually. To use another port: `streamlit run app.py --server.port 8080`.

## Running Tests

The prototype has no separate test suite. Use these checks to confirm the core engines work:

```bash
# Prints the top 5 at-risk zones and the backtest result (model vs baseline)
python hotspot.py

# Syntax check of all modules
python -m compileall .
```

Expected result: `hotspot.py` prints five zones with a risk index and rationale, and a backtest hit rate for the model and for the "same as last week" baseline. If you add tests later, run them with `pytest tests/ -v`.

## Quick Demo (Optional)

```bash
python mockdata.py
streamlit run app.py
```

Then open `http://localhost:8501` and:

1. Turn on **Demo mode** in the sidebar (preloads the missing-person case and the presentation settings).
2. Open the **Prevention** tab to see the top 5 zones and the backtest.
3. Open the **Search** tab and move the "hours since last seen" slider.
4. Open the **SHO Brief** tab and download the patrol brief, appeal notice and case file.

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again, and make sure your virtual environment is active |
| `FileNotFoundError` for `data/crimes.csv` or `data/case.json` | Run `python mockdata.py` from the project root, then restart the app |
| Blank tab or error in the app | Check the terminal running Streamlit for the full traceback. Confirm you launched from the project root |
| `streamlit: command not found` | Use `python -m streamlit run app.py` |
| Port 8501 already in use | Run `streamlit run app.py --server.port 8502` |
| AI text is generic or template-like | No AI credentials are set, so the fallback is being used. Set the variables in `.env` (see above) if you want AI-written text |
| watsonx.ai 401 error | Check `WATSONX_API_KEY`, `WATSONX_PROJECT_ID` and `WATSONX_URL` in `.env`. The app still works without them by using the template fallback |
| Map does not render | Confirm `folium` and `streamlit-folium` are installed. Basemap tiles need an internet connection |
| Documents do not download | Confirm `python-docx` is installed and the `data/` folder exists |
