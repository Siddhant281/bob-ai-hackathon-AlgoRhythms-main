# Problem Statement

## Background

Policing at the district level has to answer one question every day: **where should limited officers go, and when?**

Today that question is handled in two disconnected ways:

- **Prevention.** Beat officers patrol fixed routes. Delhi Police's ZIPNET holds years of location-tagged crime data, but according to the hackathon brief it has no predictive layer to show emerging patterns.
- **Response.** When a person, especially a child, goes missing, the first 24 hours are critical. India records 80,000+ missing children a year (NCRB 2022, as cited in the hackathon brief). Family details, public tips and CCTV sightings arrive from different sources, and investigators lack a single correlated view of them.

*(Statistics are quoted from the IBM x NFSU hackathon problem statements and were not independently verified.)*

This project combines two of the hackathon's problem statements: **Problem 12 (Predictive Crime Hotspot Mapping Assistant)** and **Problem 07 (Missing Person Investigation Assistant)**.

## The Problem

A Station House Officer (SHO) has no tool that links **where crime is likely to happen next** with **where a missing person is likely to be right now**. As a result:

1. **Patrols are static.** Routes stay the same even when the data shows a market lane spiking on Friday nights, a bus stand attracting weekend incidents, or a festival week changing where crime concentrates.
2. **Missing-person leads are handled one by one.** Tips, CCTV sighting descriptions and family statements are read separately. Contradictory or physically impossible tips (for example, a sighting 6 km from the previous one within 10 minutes) are not filtered systematically, so time is spent chasing weak leads.
3. **Search and patrol planning never meet.** The search for a missing child does not take into account which nearby areas are already high-risk, and patrol allocation does not take into account an active search.
4. **Paperwork competes with the search.** Families and officers spend early hours on forms, appeal notices and case files instead of on the search itself.

The specific gap: there is no single, explainable view that turns a station's historical crime data and a live missing-person case into **one ranked, time-aware patrol and search plan**.

## Who Is Affected

- **Primary user: the Station House Officer (SHO) of a district police station**, who decides beat allocation each week and must act on a missing-person report in its first hours, with limited staff.
- **Beat officers and investigating officers**, who receive patrol instructions and lead lists, and currently work from fixed routes and unranked tips.
- **Families of missing persons**, especially of missing children, who depend on the speed and quality of the early search.
- **Communities in high-risk areas**, who are affected when patrols do not follow emerging patterns.

## Why It Matters

- **Time is the critical resource.** For a missing child, each hour widens the possible search area and lowers the value of every lead. Early hours are the most valuable, and they are the ones most often lost to paperwork and unranked tips.
- **Wasted patrol effort.** Fixed routes send officers to low-risk areas while emerging hotspots go uncovered. Bengaluru's 2023 predictive-policing pilot is reported in the hackathon brief to have cut property crime by 18% in test zones, which suggests data-driven deployment can help (the figure is from the brief and was not verified).
- **Safety risk.** The two failures compound: an area can be both a likely place for a missing person to be taken through and a high-risk zone, yet nobody sees that overlap.
- **Trust and accountability.** Decisions about where to deploy officers or which lead to follow must be explainable. A black-box score is not usable in a police setting.

*The project does not claim to measure the size of these costs. It addresses the decision-making gap they point to.*

## Why Existing Solutions Fall Short

| What happens today | Why it falls short |
|---|---|
| Fixed beat patrol routes | Do not adapt to time-of-day, weekly rhythm, festivals or rising trends in the data |
| Crime data stored in systems such as ZIPNET, per the brief | Records history but gives no forecast, no ranked micro-zones and no patrol recommendation |
| Manual handling of tips and CCTV notes | Slow, inconsistent, and does not check whether a lead is physically possible given the previous sighting |
| Separate paperwork for appeal notices and case files | Takes early hours away from the search |
| Generic predictive-policing dashboards | Usually show a heatmap only, without a rationale for each zone, without linking to a live search, and often without checking whether the method works on held-out data |

**What is missing is a tool that is explainable, time-aware, and covers both prevention and response in a single view for the officer who has to make the decision.**

## Our Response (summary)

GoldenHour Grid gives the SHO one map with three views: a **risk layer** (top 5 at-risk micro-zones for the coming week, with reasons and a backtest), a **search layer** (a probability area around a missing person that grows over time, with ranked leads), and a **fused layer** that combines the two into a patrol and search allocation. It then generates a patrol brief, a public appeal notice and a pre-filled case file for officer review.

## Scope and Limits

- The prototype uses **synthetic data only**, with fictional people and places.
- The risk score is a **relative index, not a calibrated probability**.
- The tool is **decision support**: it supports the officer's judgment and does not replace it, and it makes no judgement about people or neighbourhoods.
