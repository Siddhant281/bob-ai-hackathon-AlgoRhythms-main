# GoldenHour Grid

**One map to prevent the next case and find the current one.**

A decision-support tool for a district police Station House Officer (SHO), built for the IBM Bob AI Hackathon x NFSU. It combines **Problem 12 (Predictive Crime Hotspot Mapping Assistant)** and **Problem 07 (Missing Person Investigation Assistant)** into a single product.

> Prototype on **synthetic data only** (fictional people and places). It supports the officer's judgment and does not replace it.

---

## 60-second explanation

Police stations handle prevention and response separately. Patrols follow fixed routes, and when a child goes missing, tips, CCTV notes and paperwork are scattered. Nothing links the search to the risks in the area.

GoldenHour Grid puts both on one map:

1. **Prevent:** predicts the top 5 at-risk micro-zones for the coming week, with a reason for each.
2. **Search:** turns family details, tips and CCTV sightings into a search area that grows with time, and ranks the leads worth following first.
3. **Act:** combines both into one patrol and search plan and drafts the paperwork (patrol brief, appeal notice, case file).

Code computes every number so it can be audited. AI is used for language: structuring messy tips, explaining rankings and drafting documents.

---

## The problem

- Patrol routes do not adapt to time of day, weekly rhythm, festivals or rising trends.
- Missing-person leads are read one by one, and contradictory or physically impossible tips waste early hours.
- The search and the patrol plan never meet.
- Paperwork competes with the search for the first hours.

Statistics such as 80,000+ missing children a year (NCRB 2022) come from the hackathon brief and were not independently verified. See [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md).

---

## Features

| Feature | What it does |
|---|---|
| **Hotspot prediction** | Scores each cell of a 10x10 grid using recent, crime-weighted incidents, day and hour patterns, and an event calendar. Shows the top 5 zones with reasons |
| **Backtest** | Trains on earlier weeks, tests on the last weeks, and compares the top-5 hit rate with a "same as last week" baseline |
| **Event and seasonal spikes** | Flags zones raised by festivals or market days |
| **Lead ranking** | Structures each tip and CCTV sighting, scores credibility, and checks whether the movement between sightings is physically possible |
| **Growing search area** | A probability map that expands with elapsed time, with extra weight at bus stands and railway stations. A slider shows how it grows |
| **Fused priority map** | Combines search probability with risk, so a likely and high-risk area rises to the top, then allocates available beats |
| **Document generation** | Patrol redeployment brief, public appeal notice (no home address or family phone), and pre-filled case file as DOCX |

---

## How it works

```
Crime data + Event calendar          Missing-person case
(6 months, synthetic)                (family data, tips, CCTV)
        |                                     |
        v                                     v
 [Prevention engine]                   [Search engine]
 hotspot.py                            search.py
        \                                     /
         v                                   v
              [Fusion engine] fusion.py
       priority = search probability x (1 + 0.5 x risk)
                     |
                     v
       [Document layer] docs.py  ->  DOCX downloads
                     |
                     v
          [Streamlit UI + Folium map] app.py
```

- **Prevention engine:** `risk = sum(crime weight x exp(-age / 21 days)) x day/hour match x event multiplier`, normalised to a 0-100 relative risk index.
- **Search engine:** search radius = travel speed x elapsed time, centred on the latest credible sighting. Lead score combines credibility, recency and physical feasibility.
- **Fusion engine:** multiplies the two layers and assigns beats to the highest-priority zones with time windows.
- **AI layer (`llm.py`):** all AI text goes through one module with a template fallback, so the app works without network or credentials.

Full detail: [ARCHITECTURE.md](ARCHITECTURE.md) and [SOLUTION_OVERVIEW.md](SOLUTION_OVERVIEW.md).

---

## Where AI is used, and where it is not

| Task | Method |
|---|---|
| Risk index, search probability, priority, beat allocation | Deterministic code (pandas, numpy) |
| Backtest | Deterministic code |
| Structuring free-text tips and CCTV notes | AI, with template fallback |
| Explaining why a zone or lead ranks where it does | AI, with template fallback |
| Drafting brief, appeal notice and case file text | AI, with template fallback |

This keeps every score reproducible and lets the officer check the reasoning.

---

## Tech stack

Python, Streamlit, pandas, numpy, Folium (streamlit-folium), python-docx. Data stored as local CSV and JSON files.

**IBM technology:** IBM Bob was used as the AI development partner. It scaffolded the project, generated the data generator, the three engines and the document builder, and helped debug and refine the interface. *(Add a concrete example from your session. If you also use watsonx.ai, state the model and what it does.)*

---

## Quick start

```bash
pip install -r requirements.txt
python mockdata.py
python -m streamlit run app.py
```

Open `http://localhost:8501`. Full instructions and troubleshooting: [SETUP.md](SETUP.md).

---

## Demo walkthrough

1. **Prevention tab:** heatmap, top 5 zones, one reason read aloud, backtest result.
2. **Search tab:** load the case, drag the "hours since last seen" slider, and note that the contradictory tip ranks lower.
3. **Fused view:** an area that is both a likely search location and a high-risk zone.
4. **SHO Brief tab:** download the patrol brief, appeal notice and case file.

---

## Results

- Backtest on synthetic data: top-5 hit rate **[X]%** vs baseline **[Y]%**. *(Fill in from your real run.)*
- These numbers show how the method behaves on planted patterns. They are not a claim about real-world accuracy.

---

## Limitations

- The risk score is a **relative index, not a calibrated probability**.
- The backtest uses synthetic data with planted patterns.
- The search model uses simple speed and radius assumptions, not road networks.
- Predictive patrol tools can create a feedback loop (more patrols lead to more recorded crime). Outputs are decision support, and the approach would need auditing on real data.
- Every generated document is a draft for officer review.

---

## Future scope

- Connect to real CCTNS and ZIPNET data and calibrate the risk index into true probabilities.
- Detect clusters of disappearances across cases.
- Support Hindi and regional-language tips.
- Use road networks for movement estimates.
- Add role-based access, audit logs and a fairness audit.

---

## Repository contents

| Path | Purpose |
|---|---|
| `app.py` | Streamlit interface |
| `mockdata.py` | Generates synthetic crime data, events and the missing-person case |
| `hotspot.py` | Prevention engine and backtest |
| `search.py` | Search engine and lead ranking |
| `fusion.py` | Combines layers and allocates beats |
| `docs.py` | Builds the DOCX documents |
| `llm.py` | AI text generation with template fallback |
| `data/` | Generated data files |

## Team

[Name 1 - role] · [Name 2 - role] · [Name 3 - role]
