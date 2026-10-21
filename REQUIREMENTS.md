# Requirements: Trade Onboarding & Risk for a Regional Bank

*Fictional engagement used to practise an implementation project end to end. The client, trades and market data are illustrative.*

## 1. Background

A Singapore-based regional bank books equity options and USD interest rate swaps in its own system. It wants these trades loaded into a central valuation and risk platform, priced daily, and reported with risk numbers its market risk team can use. Before go-live, the bank requires every acceptance criterion below to pass on a sample book.

## 2. Scope

| In scope | Out of scope |
|---|---|
| European equity options on SPY and QQQ | American / exotic options |
| USD vanilla swaps, fixed vs compounded SOFR (OIS) | Cross-currency, basis and amortising swaps |
| Trades delivered as the bank's CSV export, plus FpML confirmations | Live feeds / message queues |
| End-of-day valuation as of a given date | Intraday pricing, P&L attribution |

## 3. Inputs

| Input | Format | Owner |
|---|---|---|
| Trade file | `trades_bank_format.csv` (bank's column names, DD/MM/YYYY dates, % rates, thousands separators) | Client front office |
| Swap confirmations | FpML-style XML, one file per trade | Client middle office |
| Counterparty static data | `counterparties.csv` | Client operations |
| Market data | SOFR deposit + OIS par quotes, equity spots and dividend yields, vol surface (expiry × moneyness) | Market data team |
| Risk history | 250 daily moves in curve, spots and vol | Market risk |

## 4. Functional requirements

- **FR-1 Mapping.** Translate both trade formats into one canonical trade model without dropping any row.
- **FR-2 Validation.** Reject trades that are duplicated, incomplete, booked against unknown counterparties, have invalid dates, are already expired, or are out of scope. Every rejection carries a reason the client can act on.
- **FR-3 Reconciliation.** Received = loaded + rejected, with zero unexplained breaks.
- **FR-4 Pricing.** NPV for every loaded trade; fair rate for swaps; delta, gamma, vega and theta for options.
- **FR-5 Rates risk.** DV01 per trade, defined as the NPV change for a +1bp parallel shift in the curve's input quotes.
- **FR-6 VaR.** 99% 1-day historical-simulation VaR and Expected Shortfall, by full revaluation, per trade and for the portfolio.
- **FR-7 Reporting.** One Excel report covering reconciliation, rejections, valuations, risk by product, counterparty exposure, VaR and scenario P&L.

## 5. Acceptance criteria

| ID | Criterion |
|---|---|
| AC-01 | Every received trade is either loaded or rejected with a reason (zero reconciliation break) |
| AC-02 | Client CSV formats are mapped: DD/MM/YYYY dates, '50,000,000' notionals, % rates, mixed-case flags |
| AC-03 | The FpML swap confirmation maps to the same trade model with the correct pay/receive direction |
| AC-04 | Each known-bad trade is rejected by the expected check, and no good trade is rejected |
| AC-05 | The bootstrapped SOFR curve reprices every input OIS quote to within 0.01bp |
| AC-06 | QuantLib option prices and deltas match an independent closed-form Black-Scholes (1e-8) |
| AC-07 | Put-call parity holds for every option strike and expiry |
| AC-08 | Swap DV01 is positive for pay-fixed and negative for receive-fixed, and +1bp/-1bp bumps agree within 1% |
| AC-09 | Swap NPV agrees with (fair rate − fixed rate) × DV01 within 2% |
| AC-10 | VaR uses all 250 scenarios, ES ≥ VaR, and portfolio VaR ≤ sum of standalone VaRs |
| AC-11 | The Excel report contains every agreed sheet and the run summary is written |

## 6. Assumptions agreed with the client

- Single-curve SOFR: the OIS curve both projects and discounts.
- Swaps: annual fixed and floating payments, ACT/360, no payment lag, all start on or after the valuation spot date (no historical fixings needed).
- Options: European, 100 shares per contract, Black-Scholes-Merton with the SOFR curve as the risk-free rate, flat dividend yield, sticky-strike vol surface.
- Sign convention: all numbers from the bank's side; positive NPV is an asset.
