# Trade Onboarding & Risk Pipeline

A one-day practice implementation: take a bank's messy trade files, map them into a canonical model, load and validate them in SQL, price equity options and SOFR swaps with QuantLib, compute Greeks, DV01 and 99% historical VaR, and sign it off against written acceptance criteria.

It is built the way an implementation engineer would deliver a valuation platform to a client: **requirements → mapping → load & validate → price → risk → UAT → report.**

```
python run_pipeline.py          # map, validate, price, risk, report
python scripts/uat_signoff.py   # run 11 acceptance tests, write UAT_SIGNOFF.md
```

```
Received 14 | loaded 9 | rejected 5 | unexplained 0
  REJECT EQO-1005  V01_DUPLICATE      Trade id already received in this file
  REJECT EQO-1006  V05_EXPIRED        Option expired on or before valuation date 2026-10-16
  REJECT EQO-1007  V03_UNKNOWN_CPTY   Counterparty CP-MAYBANK-MY not set up in static data
  REJECT IRS-2004  V02_MISSING_FIELD  Swap missing notional
  REJECT IRS-2005  V04_BAD_DATES      Maturity 2026-10-20 is not after start 2026-10-20
Portfolio NPV  :    -456,706.85 USD
Portfolio DV01 :       4,031.88 USD per +1bp
99% 1-day VaR  :      78,068.74 USD (ES 87,093.55; sum of standalone VaR 1,127,786.66)
```

> **Data note.** The client, trades and market data are illustrative. Market quotes are realistic for a USD SOFR / US equity environment, and the 250-day risk history is simulated with fat tails and realistic correlations (`scripts/generate_scenarios.py`) so the project runs offline. Swap in real FRED / Yahoo Finance history by writing the same columns to `data/market/history_scenarios.csv`.

## Setup

```
pip install -r requirements.txt
python scripts/generate_scenarios.py   # only if you want to regenerate the history
python run_pipeline.py
python scripts/uat_signoff.py
```

## Architecture

```
 data/client/                 src/mapping.py           sql/validation.sql          src/pricing.py           src/var.py
 ┌───────────────────┐       ┌───────────────┐        ┌────────────────────┐      ┌────────────────┐       ┌──────────────────┐
 │ bank CSV export   │──────▶│ field mapping │──────▶ │ staging_trades     │      │ SOFR curve     │       │ 250 scenarios    │
 │ FpML confirmation │──────▶│ format fixes  │        │  ├ V01..V06 checks │      │ vol surface    │──────▶│ full revaluation │
 └───────────────────┘       └───────────────┘        │  ├ rejections      │─────▶│ NPV, Greeks,   │       │ VaR / ES 99% 1d  │
 data/static/ counterparties ────────────────────────▶│  └ trades          │      │ DV01 (bump)    │       └────────┬─────────┘
 data/market/ quotes ──────────────────────── src/market.py ──────────────────────▶│                │                │
                                                      └─────────┬──────────┘      └───────┬────────┘                │
                                                                ▼                         ▼                         ▼
                                                     output/onboarding.db  ──▶  output/valuation_risk_report.xlsx, UAT_SIGNOFF.md
```

| Path | What it does |
|---|---|
| `REQUIREMENTS.md` | Client brief: scope, inputs, functional requirements, 11 acceptance criteria, agreed assumptions |
| `src/mapping.py` | Maps the bank's CSV columns and an FpML swap confirmation into one canonical trade model |
| `sql/schema.sql` | Staging, trades, rejections, counterparties, valuations and VaR tables |
| `sql/validation.sql` | Six validation checks (V01–V06) as SQL; loads only rows that fail none |
| `sql/reconciliation.sql` | Received = loaded + rejected, with an unexplained-break column |
| `sql/reports.sql` | Counterparty exposure and risk-by-product queries for the report |
| `src/market.py` | Bootstraps the SOFR curve (deposits + OIS) and builds sticky-strike vol surfaces; applies shocks |
| `src/pricing.py` | OIS swap and European option pricing, Greeks, bump-and-reprice DV01 |
| `src/black_scholes.py` | Independent closed-form Black-Scholes used to reconcile QuantLib |
| `src/var.py` | Historical-simulation VaR and Expected Shortfall by full revaluation |
| `tests/test_uat.py` | One pytest per acceptance criterion |
| `scripts/uat_signoff.py` | Runs the tests and writes the client sign-off document |

## The trade lifecycle, and where this pipeline sits

| Stage | Who | What happens | In this project |
|---|---|---|---|
| **Front office** | Traders, sales | Trade is agreed and captured in the booking system | The bank's CSV export is the output of this stage |
| **Middle office** | Product control, market risk | Trade is validated, enriched with static data, valued daily, and its risk (Greeks, DV01, VaR) monitored against limits | **This pipeline**: mapping, validation, valuation, risk, reporting |
| **Back office** | Operations, settlements | Confirmations are matched (often FpML), cash flows settled, positions reconciled with counterparties | The FpML confirmation input and the reconciliation step |

Market data runs alongside all three: a curve built from deposit and OIS quotes gives discount factors and forward SOFR rates; a vol surface (expiry × strike) gives the implied volatility for each option.

## How this maps to an enterprise valuation platform

A platform like Numerix Oneview solves these problems at bank scale. The steps here are a small-scale version of a client implementation:

| Implementation step | This project | At enterprise scale |
|---|---|---|
| Requirements & scoping | `REQUIREMENTS.md` | Workshops with front office, risk and IT; signed-off scope |
| Trade data mapping | `mapping.py` (CSV + FpML) | Mapping many booking systems and products to the platform's trade model |
| Static data | Counterparties table | Counterparties, legal entities, netting sets, calendars, conventions |
| Market data | CSV quotes → QuantLib curve and vol surface | Vendor feeds, curve and surface configuration, snapshots per close |
| Pricing configuration | QuantLib engines, agreed assumptions | Model selection and calibration per product, using the vendor's analytics library |
| Validation & reconciliation | SQL checks V01–V06, recon query | Data quality rules, parallel runs vs the client's legacy numbers |
| Risk | Bump-and-reprice DV01, historical VaR | Full sensitivity sets, VaR, XVA, limits |
| UAT & go-live | `tests/test_uat.py`, `UAT_SIGNOFF.md` | Client UAT cycles, defect triage, go-live and hypercare |

## Questions to expect, and the answers

- **Why is DV01 positive for a pay-fixed swap?** Here DV01 = NPV(rates +1bp) − NPV(base). If you pay fixed, higher rates raise the floating leg you receive, so the swap gains value. Some desks define DV01 with the opposite sign, so always state the convention.
- **Why does the portfolio VaR (78k) sit far below the sum of standalone VaRs (1.13m)?** The book has offsetting swaps: two pay-fixed and two receive-fixed with similar DV01, so most rate risk nets out. VaR rewards diversification; summing standalone numbers ignores it.
- **Why check QuantLib against your own Black-Scholes?** A library can be configured wrongly (day counts, rate compounding, vol lookup). Matching to 1e-8 shows the inputs and conventions are right, not just the formula.
- **Why does the curve repricing test matter?** If the curve doesn't return its own input quotes, every swap valued off it is wrong. It is the first check after any curve configuration change.
- **What would you change for production?** Real history; multi-curve setups (separate discount and projection curves); historical SOFR fixings for seasoned swaps; payment lags; American options; data quality checks on market data itself; scheduling and audit logging.
