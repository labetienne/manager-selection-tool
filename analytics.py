"""Calculs : performance, risque, régression factorielle, verdict et scoring d'appel d'offres."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

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
    "Sharpe": ("Sharpe", True, 0),
    "Max drawdown": ("Max drawdown", True, 10),  # moins négatif = mieux
    "Down capture": ("Down capture", False, 15),
    "% semaines surperf.": ("Régularité (% semaines surperf.)", True, 10),
    "TER": ("Frais (TER)", False, 10),
    "SFDR": ("Classification SFDR", True, 10),  # 9 > 8 > 6 ; ignoré si non applicable (fonds US)
}


# Profils de pondération prêts à l'emploi (somme = 100)
PROFILES = {
    "Équilibré": {k: v[2] for k, v in CRITERIA.items()},
    "Défensif": {"Information ratio": 10, "Alpha factoriel": 10, "Sharpe": 5, "Max drawdown": 25,
                 "Down capture": 30, "% semaines surperf.": 5, "TER": 5, "SFDR": 10},
    "Recherche d'alpha": {"Information ratio": 30, "Alpha factoriel": 40, "Sharpe": 0, "Max drawdown": 5,
                          "Down capture": 5, "% semaines surperf.": 10, "TER": 5, "SFDR": 5},
    "Coûts maîtrisés": {"Information ratio": 20, "Alpha factoriel": 15, "Sharpe": 0, "Max drawdown": 10,
                        "Down capture": 10, "% semaines surperf.": 5, "TER": 30, "SFDR": 10},
}
PROFILE_HELP = {
    "Équilibré": "Pondération par défaut : création de valeur d'abord, risque et frais ensuite.",
    "Défensif": "Priorité à la protection : faible drawdown et bonne tenue quand le marché baisse.",
    "Recherche d'alpha": "Priorité à la valeur ajoutée du gérant, au-delà des expositions de marché.",
    "Coûts maîtrisés": "Les frais pèsent lourd : utile pour un mandat proche de la gestion indicielle.",
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



def verdict(m) -> tuple[str, str, str]:
    """(badge, explication, niveau) à partir de l'alpha factoriel et de son t-stat."""
    a, t = m["Alpha factoriel"], m["Alpha t-stat"]
    if a > 0 and t >= 2:
        return "✅ Création de valeur robuste", "alpha positif et statistiquement significatif", "success"
    if a < 0 and t <= -2:
        return "❌ Destruction de valeur", "alpha négatif et statistiquement significatif", "error"
    if abs(a) < 0.0025:
        return "⚪ Proche de l'indice", "alpha quasi nul : le fonds se comporte comme son marché", "info"
    if a > 0:
        return "🟡 Valeur ajoutée non démontrée", "alpha positif mais pas assez régulier pour exclure le hasard", "warning"
    return "🟠 Pas de valeur ajoutée", "alpha négatif, mais pas de façon statistiquement certaine", "warning"
