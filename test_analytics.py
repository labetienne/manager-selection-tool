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


def test_verdict_thresholds():
    lvl = lambda a, t: A.verdict({"Alpha factoriel": a, "Alpha t-stat": t})[2]
    assert lvl(0.02, 2.5) == "success" and lvl(-0.02, -2.5) == "error"
    assert lvl(0.001, 0.3) == "info" and lvl(0.01, 1.0) == "warning" and lvl(-0.01, -1.0) == "warning"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
