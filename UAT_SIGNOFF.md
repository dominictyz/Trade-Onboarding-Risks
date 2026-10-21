# UAT Sign-off: Trade Onboarding & Risk Pipeline

Valuation date: 2026-10-16 | Run date: 2026-10-19 | Result: **11/11 criteria passed**

| ID | Acceptance criterion | Result |
|---|---|---|
| AC-01 | Every received trade is either loaded or rejected with a reason (zero reconciliation break). | ✅ PASS |
| AC-02 | Client CSV formats are mapped: DD/MM/YYYY dates, '50,000,000' notionals, % rates, mixed-case flags. | ✅ PASS |
| AC-03 | The FpML swap confirmation maps to the same trade model with the correct pay/receive direction. | ✅ PASS |
| AC-04 | Each known-bad trade is rejected by the expected check, and no good trade is rejected. | ✅ PASS |
| AC-05 | The bootstrapped SOFR curve reprices every input OIS quote to within 0.01bp. | ✅ PASS |
| AC-06 | QuantLib option prices and deltas match an independent closed-form Black-Scholes (1e-8). | ✅ PASS |
| AC-07 | Put-call parity holds for every option strike and expiry: C - P = S e^-qT - K e^-rT. | ✅ PASS |
| AC-08 | Swap DV01 is positive for pay-fixed and negative for receive-fixed, and +1bp/-1bp bumps agree within 1%. | ✅ PASS |
| AC-09 | Swap NPV agrees with (fair rate - fixed rate) x DV01 within 2% (an independent sense check). | ✅ PASS |
| AC-10 | VaR uses all 250 scenarios, ES >= VaR, and portfolio VaR <= sum of standalone VaRs. | ✅ PASS |
| AC-11 | The Excel report contains every agreed sheet and the run summary is written. | ✅ PASS |

## Onboarding reconciliation

| Received | Loaded | Rejected | Unexplained |
|---|---|---|---|
| 14 | 9 | 5 | 0 |

## Rejected trades returned to client

| Trade | Check | Reason |
|---|---|---|
| EQO-1005 | V01_DUPLICATE | Trade id already received in this file |
| EQO-1006 | V05_EXPIRED | Option expired on or before valuation date 2026-10-16 |
| EQO-1007 | V03_UNKNOWN_CPTY | Counterparty CP-MAYBANK-MY not set up in static data |
| IRS-2004 | V02_MISSING_FIELD | Swap missing notional |
| IRS-2005 | V04_BAD_DATES | Maturity 2026-10-20 is not after start 2026-10-20 |

## Headline risk

- Portfolio NPV: -456,706.85 USD
- Portfolio DV01: 4,031.88 USD per +1bp
- 99% 1-day historical VaR: 78,068.74 USD (ES 87,093.55; sum of standalone VaR 1,127,786.66)

Sign-off: ____________________ (client)      ____________________ (implementation)
