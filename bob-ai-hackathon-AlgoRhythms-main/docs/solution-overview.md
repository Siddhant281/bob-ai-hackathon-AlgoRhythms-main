# Solution Overview

## What We Built

**GoldenHour Grid** is a decision-support tool for a district police Station House Officer (SHO). It puts two jobs on one map that are normally handled separately:

- **Prevention:** it looks at six months of location-tagged crime data and predicts the five micro-zones most at risk in the coming week, with a plain-language reason for each and a flag when a festival or market day is driving a spike.
- **Response:** when a person goes missing, it turns family details, public tips and CCTV sightings into a search area that grows as time passes, and ranks the leads worth following first. Tips that contradict each other or are physically impossible are pushed down the list.

It then combines both views into one patrol and search plan, and drafts the paperwork: a patrol redeployment brief for the SHO, a public appeal notice, and a pre-filled missing-person case file. The officer reviews everything before use.

The prototype runs entirely on synthetic data with fictional people and places.

## How It Works

1. **Load data.** The app reads six months of mock crime records, an event calendar (festivals, market days) and one fictional missing-person case with tips and CCTV notes.
2. **Score risk (prevention).** The district is divided into a 10x10 grid. Each cell gets a relative risk index from recent, crime-weighted incidents, the day-and-hour pattern for the target week, and any event linked to that week. The top five cells are shown with reasons.
3. **Check the method (backtest).** The model is trained on earlier weeks and tested on the last few. Its hit rate is compared with a simple baseline: "patrol last week's hotspots".
4. **Rank leads (search).** Each tip and CCTV sighting becomes a structured record with a credibility score. The tool checks whether the movement between sightings is physically possible, and down-ranks anything that isn't.
5. **Map the search area.** From the last credible sighting, the probability area expands with elapsed time, with extra weight at transit points such as the bus stand and railway station. The officer can drag a slider to see how it grows.
6. **Fuse.** Search probability is combined with the risk layer, so an area that is both a likely search location and a high-risk zone rises to the top. Available patrol beats are then assigned to the highest-priority zones with time windows.
7. **Generate documents.** The brief, appeal notice and case file are written and offered as downloads.

## Architecture Diagram

> See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the detailed diagram.

```
Crime data + Event calendar          Missing-person case
(6 months, synthetic)                (family data, tips, CCTV)
        |                                     |
        v                                     v
 [Prevention engine]                   [Search engine]
 risk index per cell                   credibility, feasibility,
 top 5 zones + backtest                growing search area, ranked leads
        \                                     /
         \                                   /
          v                                 v
              [Fusion engine]
     priority = search probability x (1 + 0.5 x risk)
     + beat allocation
                     |
                     v
   [Document layer]  ->  Patrol brief | Appeal notice | Case file
                     |
                     v
       [Streamlit UI + Folium map]  ->  SHO / officer
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Code computes all numbers; AI writes and explains | Risk, probability and allocation must be reproducible and auditable. The AI is used for language tasks such as structuring messy tips and drafting documents, so it can't change a score |
| Show a relative risk index, not a "probability of crime" | With synthetic data there is nothing to calibrate against, so claiming a true probability would be dishonest. Each zone gets an index plus its reasons |
| Backtest against a simple baseline | Since the data is synthetic, the backtest is the honest way to show the method behaves sensibly rather than just looking plausible |
| Fuse search and prevention in one priority score | An area can be both a likely place for a missing person and a high-risk zone. Seeing both in one view is the point of the tool |
| Physical-feasibility check on tips | Rejects impossible or contradictory sightings so the first hours are not spent on weak leads |
| Template fallback for all AI text | The app works without network or credentials, which also makes the demo reliable |
| Streamlit with local CSV/JSON files | Fastest route to a working, demonstrable prototype in a four-hour hackathon; no database to maintain |
| Human review on every output | The tool supports the officer's judgment. The appeal notice omits home address and family phone number |

## IBM Technologies Used

- **IBM Bob:** the AI development assistant used throughout the build. It scaffolded the Streamlit project, generated the synthetic data generator, the prevention, search and fusion engines, and the document builder, and was used to debug errors and improve the interface. *(Add one or two concrete examples from your own session, for example an error Bob helped fix or a module it wrote.)*
- **[IBM watsonx.ai, if used]:** *Include this bullet only if your `llm.py` really calls watsonx.ai. State the model name and what it does, for example structuring tips or writing the brief. If you did not use it, delete this line so the document matches your code.*

## Limitations

- The risk score is a relative index, not a calibrated probability.
- The backtest runs on synthetic data with planted patterns, so it shows how the method behaves, not how it would perform on real crime.
- The search model uses simple speed and radius assumptions, not real road networks.
- Predictive patrol tools can create a feedback loop (more patrols lead to more recorded crime). We treat the output as decision support and would audit it on real data before any deployment.
