"""Vérifications des calculs sur données synthétiques (aucun accès réseau).

Lancer :  .venv/bin/python test_analytics.py   (ou pytest s'il est installé)
"""
import numpy as np
import pandas as pd

import analytics as A

rng = np.random.default_rng(0)
IDX = pd.date_range("2022-01-07", periods=260, freq="W-FRI")


def test_perf_metrics_identical_series():
    b = pd.Series(rng.normal(0.001, 0.01, len(IDX)), IDX)
    m = A.perf_metrics(b, b, pd.Series(0.0, IDX))
    assert abs(m["Tracking error"]) < 1e-12 and abs(m["Bêta"] - 1) < 1e-9 and abs(m["Alpha (Jensen)"]) < 1e-9


def test_factor_regression_recovers_alpha_and_betas():
    f = pd.DataFrame(rng.normal(0, 0.01, (len(IDX), 3)), IDX, ["Crédit", "Taux", "Actions"])
    alpha_w = 0.02 / 52
    r = alpha_w + f @ [2.0, 0.5, 0.1] + rng.normal(0, 1e-4, len(IDX))
    fr = A.factor_regression(r, pd.Series(0.0, IDX), f)
    coefs = fr["table"]["Coefficient"]
    assert abs(fr["alpha_ann"] - 0.02) < 2e-3
    assert np.allclose(coefs[["Crédit", "Taux", "Actions"]], [2.0, 0.5, 0.1], atol=0.02)


def test_score_ranks_better_fund_first():
    t = pd.DataFrame({"Information ratio": [1.0, -1.0], "Alpha factoriel": [0.02, -0.02], "Sharpe": [1.0, 0.0],
                      "Max drawdown": [-0.02, -0.10], "Down capture": [0.8, 1.2], "% semaines surperf.": [0.6, 0.4],
                      "TER": [0.3, 0.9]}, index=["bon", "mauvais"])
    s = A.score(t, A.PROFILES["Équilibré"])
    assert s.index[0] == "bon" and s.loc["bon", "Rang"] == 1


def test_fx_hedge_neutral_when_fx_and_rates_flat():
    d = pd.bdate_range("2024-01-01", periods=120)
    price = pd.Series(np.linspace(100, 110, len(d)), d)
    flat = pd.Series(1.10, d)
    zero = pd.Series(0.0, d)
    h = A.fx_hedge_simulation(price, flat, zero, zero, target=1.0, freq="M")
    assert np.allclose(h["hedged_eur"], h["unhedged_eur"])
    assert h["ratio"].iloc[0] == 1.0


def test_put_call_parity():
    S, K, T, r, q, v = 100, 95, 0.5, 0.03, 0.02, 0.2
    c, p = A.bs(S, K, T, r, q, v, "call")["price"], A.bs(S, K, T, r, q, v, "put")["price"]
    assert abs((c - p) - (S * np.exp(-q * T) - K * np.exp(-r * T))) < 1e-9


def test_breach_episodes():
    dev = pd.Series([0, 0.03, 0.04, 0, -0.05, 0], pd.bdate_range("2024-01-01", periods=6))
    ep = A.breach_episodes(dev, 0.02)
    assert list(ep["Jours"]) == [2, 1] and ep["Écart max"].tolist() == [0.04, -0.05]
    assert A.breach_episodes(dev * 0, 0.02).empty


def test_put_spread_backtest_pnl_adds_up():
    d = pd.bdate_range("2025-01-01", periods=300)
    spot = pd.Series(5000 * np.exp(np.cumsum(rng.normal(0, 0.01, len(d)))), d)
    weeks = spot.resample("W-FRI").last().index
    rep, pos, premiums = A.put_spread_backtest(spot, pd.Series(0.02, d), pd.Series(0.18, d), weeks,
                                               1000, 0.95, 0.85, 3, 0.03)
    assert abs(rep["P&L semaine (M€)"].sum() - rep["P&L cumulé (M€)"].iloc[-1]) < 1e-9
    assert premiums > 0 and pos is not None
    assert (rep["Valeur (M€)"] <= (0.95 - 0.85) * 1000 + 1e-6).all()  # jamais plus que l'indemnisation max


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
