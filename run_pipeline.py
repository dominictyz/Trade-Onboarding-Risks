"""End-to-end onboarding run: map -> stage -> validate -> load -> price -> risk -> report.

    python run_pipeline.py            # valuation date 2026-10-16
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src import database as db
from src.mapping import read_client_csv, read_fpml_swap
from src.market import load_quotes
from src.pricing import value_and_greeks
from src.var import load_scenarios, run_var

ROOT = Path(__file__).resolve().parent
DATA, OUT = ROOT / "data", ROOT / "output"


def main(valuation_date: str = "2026-10-16", db_path: Path | None = None) -> dict:
    OUT.mkdir(exist_ok=True)
    db_path = db_path or OUT / "onboarding.db"
    if db_path.exists():
        db_path.unlink()
    con = db.connect(db_path)

    # 1. static data + staging -------------------------------------------------------
    db.create_schema(con)
    db.load_counterparties(con, DATA / "static" / "counterparties.csv")
    staged = read_client_csv(DATA / "client" / "trades_bank_format.csv")
    staged += [read_fpml_swap(p) for p in sorted((DATA / "client").glob("*_fpml.xml"))]
    db.load_staging(con, staged)

    # 2. validation + load + reconciliation -----------------------------------------
    db.run_validation(con, valuation_date)
    recon = db.reconciliation(con)
    trades = [dict(r) for r in con.execute("SELECT * FROM trades ORDER BY trade_id")]

    # 3. pricing + greeks --------------------------------------------------------------
    quotes = load_quotes(DATA / "market", valuation_date)
    vals = value_and_greeks(trades, quotes)
    con.executemany(
        "INSERT INTO valuations VALUES (:trade_id, :product, :npv_usd, :fair_rate, :delta_usd, :gamma, "
        ":vega_usd, :theta_usd_day, :dv01_usd)", vals)

    # 4. historical VaR ----------------------------------------------------------------
    scenarios = load_scenarios(DATA / "market" / "history_scenarios.csv")
    var, pnl, dates = run_var(trades, quotes, scenarios)
    con.executemany("INSERT INTO risk_var VALUES (?, ?, ?)", [(k, v[0], v[1]) for k, v in var.items()])
    con.commit()

    # 5. report ------------------------------------------------------------------------
    rejections = pd.read_sql("SELECT r.trade_id, r.check_code, r.reason, s.source_file "
                             "FROM rejections r JOIN staging_trades s USING(row_id) ORDER BY r.row_id", con)
    val_df = pd.read_sql("SELECT t.trade_id, t.product, t.cpty_id, t.direction, t.underlying, t.option_type, "
                         "t.strike, t.expiry_date, t.notional, t.fixed_rate, t.maturity_date, v.npv_usd, "
                         "v.fair_rate, v.delta_usd, v.gamma, v.vega_usd, v.theta_usd_day, v.dv01_usd "
                         "FROM trades t JOIN valuations v USING(trade_id) ORDER BY t.trade_id", con)
    var_df = pd.read_sql("SELECT * FROM risk_var ORDER BY scope = 'PORTFOLIO' DESC, scope", con)
    cpty_df = pd.read_sql(db.named_queries("exposure_by_counterparty"), con)
    prod_df = pd.read_sql(db.named_queries("risk_by_product"), con)
    pnl_df = pd.DataFrame(pnl, columns=[t["trade_id"] for t in trades], index=dates)
    pnl_df["PORTFOLIO"] = pnl_df.sum(axis=1)

    with pd.ExcelWriter(OUT / "valuation_risk_report.xlsx") as xw:
        pd.DataFrame([{"valuation_date": valuation_date, **recon}]).to_excel(xw, sheet_name="Reconciliation", index=False)
        rejections.to_excel(xw, sheet_name="Rejections", index=False)
        val_df.round(4).to_excel(xw, sheet_name="Valuations", index=False)
        prod_df.to_excel(xw, sheet_name="Risk by product", index=False)
        cpty_df.to_excel(xw, sheet_name="Counterparty exposure", index=False)
        var_df.round(2).to_excel(xw, sheet_name="VaR 99% 1d", index=False)
        pnl_df.round(2).to_excel(xw, sheet_name="Scenario P&L")

    summary = {
        "valuation_date": valuation_date, "reconciliation": recon,
        "rejections": rejections.to_dict("records"),
        "portfolio_npv_usd": round(float(val_df.npv_usd.sum()), 2),
        "portfolio_dv01_usd": round(float(val_df.dv01_usd.sum()), 2),
        "portfolio_var_99_1d_usd": round(var["PORTFOLIO"][0], 2),
        "portfolio_es_99_1d_usd": round(var["PORTFOLIO"][1], 2),
        "sum_standalone_var_usd": round(sum(v[0] for k, v in var.items() if k != "PORTFOLIO"), 2),
        "scenarios": len(scenarios),
    }
    (OUT / "pipeline_summary.json").write_text(json.dumps(summary, indent=2))
    con.close()
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--valuation-date", default="2026-10-16")
    s = main(ap.parse_args().valuation_date)
    r = s["reconciliation"]
    print(f"Received {r['received']} | loaded {r['loaded']} | rejected {r['rejected']} | "
          f"unexplained {r['unexplained_break']}")
    for rej in s["rejections"]:
        print(f"  REJECT {rej['trade_id']:<9} {rej['check_code']:<18} {rej['reason']}")
    print(f"Portfolio NPV  : {s['portfolio_npv_usd']:>14,.2f} USD")
    print(f"Portfolio DV01 : {s['portfolio_dv01_usd']:>14,.2f} USD per +1bp")
    print(f"99% 1-day VaR  : {s['portfolio_var_99_1d_usd']:>14,.2f} USD "
          f"(ES {s['portfolio_es_99_1d_usd']:,.2f}; sum of standalone VaR {s['sum_standalone_var_usd']:,.2f})")
    print("Report -> output/valuation_risk_report.xlsx")
