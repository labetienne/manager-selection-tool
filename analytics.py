"""Calculs : performance, risque, régression factorielle, scoring, couverture de change, options."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

PERIODS = 52  # données hebdomadaires


# ======================================================================================
# Préparation
# ======================================================================================
def weekly_returns(levels: pd.DataFrame) -> pd.DataFrame:
    """Rendements hebdomadaires (vendredi) — synchronise les fuseaux US / Europe."""
    w = levels.resample("W-FRI").last()
    return w.pct_change(fill_method=None)


def weekly_rf(rate_pct: pd.Series) -> pd.Series:
    """Taux court annuel (%) -> rendement hebdomadaire sans risque."""
    return rate_pct.resample("W-FRI").mean() / 100 / PERIODS


def factor_frame(data: dict, seg: dict, rets: pd.DataFrame) -> pd.DataFrame:
    fred = data["fred"]
    spread = fred[seg["spread"]].resample("W-FRI").last() / 100  # en décimal
    return pd.DataFrame(
        {
            # resserrement des spreads => gain pour un porteur de crédit.
            # Le coefficient se lit comme une "duration spread" (≈ perte en % pour +1 % de spread)
            "Crédit (-ΔOAS)": -spread.diff(),
            "Taux (oblig. d'État)": rets[seg["rates"]],
            "Actions": rets[seg["equity"]],
        }
    )


# ======================================================================================
# Indicateurs de performance / risque
# ======================================================================================
def ann_return(r: pd.Series) -> float:
    return (1 + r).prod() ** (PERIODS / len(r)) - 1


def drawdown(r: pd.Series) -> pd.Series:
    wealth = (1 + r).cumprod()
    return wealth / wealth.cummax() - 1


def perf_metrics(r: pd.Series, b: pd.Series, rf: pd.Series) -> dict:
    df = pd.concat({"r": r, "b": b, "rf": rf}, axis=1).dropna()
    r, b, rf = df["r"], df["b"], df["rf"]
    active = r - b
    vol = r.std() * np.sqrt(PERIODS)
    te = active.std() * np.sqrt(PERIODS)
    downside = r[r < 0].std() * np.sqrt(PERIODS)
    ra, ba = ann_return(r), ann_return(b)
    rfa = ann_return(rf)

    X = sm.add_constant(b - rf)
    ols = sm.OLS(r - rf, X).fit()
    alpha = ols.params.iloc[0] * PERIODS
    beta = ols.params.iloc[1]

    up, dn = b > 0, b < 0
    return {
        "Rdt annualisé": ra,
        "Rdt benchmark": ba,
        "Surperf. annualisée": ra - ba,
        "Volatilité": vol,
        "Sharpe": (ra - rfa) / vol if vol else np.nan,
        "Sortino": (ra - rfa) / downside if downside else np.nan,
        "Tracking error": te,
        "Information ratio": (ra - ba) / te if te else np.nan,
        "Alpha (Jensen)": alpha,
        "Bêta": beta,
        "Corrélation": r.corr(b),
        "Max drawdown": drawdown(r).min(),
        "Up capture": r[up].mean() / b[up].mean(),
        "Down capture": r[dn].mean() / b[dn].mean(),
        "% semaines surperf.": (active > 0).mean(),
        "Nb semaines": len(r),
    }


def rolling_excess(r: pd.Series, b: pd.Series, window: int = 52) -> pd.DataFrame:
    df = pd.concat({"r": r, "b": b}, axis=1).dropna()
    a = df["r"] - df["b"]
    roll_ret = (1 + df).rolling(window).apply(np.prod, raw=True) - 1
    return pd.DataFrame(
        {
            "Surperf. 12M glissante": roll_ret["r"] - roll_ret["b"],
            "Tracking error 12M": a.rolling(window).std() * np.sqrt(PERIODS),
        }
    )


# ======================================================================================
# Régression multi-facteurs : "création de valeur du gérant"
# ======================================================================================
def factor_regression(r: pd.Series, rf: pd.Series, factors: pd.DataFrame) -> dict:
    df = pd.concat([(r - rf).rename("y"), factors], axis=1).dropna()
    y, X = df["y"], sm.add_constant(df.drop(columns="y"))
    # erreurs-types robustes Newey-West (autocorrélation des rendements crédit)
    ols = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    means = X.mean()
    contrib = ols.params * means * PERIODS  # contribution annualisée de chaque facteur
    table = pd.DataFrame(
        {
            "Coefficient": ols.params,
            "t-stat": ols.tvalues,
            "p-value": ols.pvalues,
            "Contribution annualisée": contrib,
        }
    ).rename(index={"const": "Alpha"})
    table.loc["Alpha", "Coefficient"] = ols.params["const"] * PERIODS  # alpha annualisé
    fitted = ols.fittedvalues - ols.params["const"]
    return dict(
        table=table,
        r2=ols.rsquared,
        n=int(ols.nobs),
        alpha_ann=ols.params["const"] * PERIODS,
        alpha_t=ols.tvalues["const"],
        residuals=ols.resid,
        explained=fitted,
        y=y,
    )


# ======================================================================================
# Scoring multicritère (grille d'appel d'offres)
# ======================================================================================
CRITERIA = {
    # clé : (libellé, plus_haut_est_mieux, poids par défaut)
    "Information ratio": ("Information ratio", True, 25),
    "Alpha factoriel": ("Alpha factoriel (net des bêtas)", True, 20),
    "Sharpe": ("Sharpe", True, 10),
    "Max drawdown": ("Max drawdown", True, 10),  # moins négatif = mieux
    "Down capture": ("Down capture", False, 15),
    "% semaines surperf.": ("Régularité (% semaines surperf.)", True, 10),
    "TER": ("Frais (TER)", False, 10),
}


def score(table: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Rang centile par critère (0-100) puis moyenne pondérée. Critère ignoré si absent."""
    scores = pd.DataFrame(index=table.index)
    w_used = {}
    for key, (label, higher, _) in CRITERIA.items():
        w = weights.get(key, 0)
        if w <= 0 or key not in table or table[key].isna().all():
            continue
        col = table[key]
        rank = col.rank(pct=True, ascending=higher)
        scores[label] = (rank * 100).round(0)
        w_used[label] = w
    if not w_used:
        return scores
    tot = sum(w_used.values())
    scores["Score global"] = sum(scores[k].fillna(50) * v for k, v in w_used.items()) / tot
    scores["Rang"] = scores["Score global"].rank(ascending=False, method="min").astype(int)
    return scores.sort_values("Score global", ascending=False)


# ======================================================================================
# Overlay change : simulation d'une couverture EUR/USD avec rebalancement périodique
# ======================================================================================
def fx_hedge_simulation(
    price_usd: pd.Series,
    eurusd: pd.Series,
    sofr: pd.Series,
    estr: pd.Series,
    target: float = 1.0,
    freq: str = "M",
) -> pd.DataFrame:
    """Investisseur EUR détenant un fonds USD et vendant des USD à terme (forward).

    - Exposition couverte N (USD) remise à target x valeur du fonds à chaque date de rebalancement
    - Entre deux rebalancements, le ratio de couverture dérive avec la valeur du fonds
    - Portage du forward ≈ (€STR - SOFR) : coût de couverture quand les taux USD > EUR
    """
    df = pd.concat({"P": price_usd, "X": eurusd, "sofr": sofr, "estr": estr}, axis=1)
    df = df.ffill().dropna()
    # date de rebalancement = dernier jour ouvré de chaque période ("W", "M" ou "Q")
    rebal_dates = set(df.groupby(df.index.to_period(freq)).tail(1).index)

    P, X = df["P"].values, df["X"].values
    sofr_v, estr_v = df["sofr"].values / 100, df["estr"].values / 100
    dates = df.index
    holdings_usd = 100 * X[0]  # 100 € investis
    notional = target * holdings_usd
    cash_eur = 0.0
    out = []
    for i in range(len(df)):
        if i > 0:
            dt = (dates[i] - dates[i - 1]).days / 360
            holdings_usd *= P[i] / P[i - 1]
            fx_pnl = -notional * (1 / X[i] - 1 / X[i - 1])  # vendeur d'USD
            carry = notional / X[i - 1] * (estr_v[i - 1] - sofr_v[i - 1]) * dt
            cash_eur += fx_pnl + carry
        ratio = notional / holdings_usd
        out.append(
            dict(
                date=dates[i],
                local_usd=100 * P[i] / P[0],
                unhedged_eur=holdings_usd / X[i],
                hedged_eur=holdings_usd / X[i] + cash_eur,
                ratio=ratio,
                rebal=dates[i] in rebal_dates,
            )
        )
        if dates[i] in rebal_dates:
            notional = target * holdings_usd
    res = pd.DataFrame(out).set_index("date")
    res["deviation"] = res["ratio"] - target
    res["carry_ann"] = (df["estr"] - df["sofr"]) / 100
    return res


# ======================================================================================
# Options : Black-Scholes (overlay actions – put spread de protection)
# ======================================================================================
def bs(S, K, T, r, q, sigma, kind="put"):
    T = np.maximum(T, 1e-8)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if kind == "call":
        price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = np.exp(-q * T) * norm.cdf(d1)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
        delta = -np.exp(-q * T) * norm.cdf(-d1)
    gamma = np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) / 100  # pour 1 pt de vol
    theta = (
        -S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
        + (q * S * np.exp(-q * T) * norm.cdf(-d1) - r * K * np.exp(-r * T) * norm.cdf(-d2)
           if kind == "put"
           else -q * S * np.exp(-q * T) * norm.cdf(d1) + r * K * np.exp(-r * T) * norm.cdf(d2))
    ) / 365
    return dict(price=price, delta=delta, gamma=gamma, vega=vega, theta=theta)


def put_spread(S, K_long, K_short, T, r, q, sigma):
    """Achat put K_long, vente put K_short (K_short < K_long). Grecques par unité d'indice."""
    a = bs(S, K_long, T, r, q, sigma, "put")
    b = bs(S, K_short, T, r, q, sigma, "put")
    return {k: a[k] - b[k] for k in a}
