"""Chargement des données : cours des fonds (Yahoo Finance) et séries de marché (FRED).

Toutes les données sont mises en cache localement (data/cache.pkl) pour que l'app
fonctionne même sans connexion (utile en entretien).
"""
from __future__ import annotations

import io
import os
import urllib.request
from datetime import datetime

import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")
CACHE_FILE = os.path.join(CACHE_DIR, "cache.pkl")
START = "2019-10-01"  # début de l'€STR

# --------------------------------------------------------------------------------------
# Univers : les fonds jouent le rôle de "gérants candidats" dans un appel d'offres.
# --------------------------------------------------------------------------------------
FUNDS = {
    # ---- High Yield US (USD) : gérants actifs + ETF passifs -------------------------
    "VWEHX": dict(short="Vanguard HY", name="Vanguard High-Yield Corp (Wellington)", segment="HY US", style="Actif"),
    "PHIYX": dict(short="PIMCO HY", name="PIMCO High Yield Instl", segment="HY US", style="Actif"),
    "BHYIX": dict(short="BlackRock HY", name="BlackRock High Yield Instl", segment="HY US", style="Actif"),
    "FAGIX": dict(short="Fidelity Cap. & Inc.", name="Fidelity Capital & Income", segment="HY US", style="Hors style",
                   off_style="fonds mixte : détient aussi des actions, sa performance ne se compare pas à un indice HY pur"),
    "OHYFX": dict(short="JPMorgan HY", name="JPMorgan High Yield I", segment="HY US", style="Actif"),
    "MWHYX": dict(short="TCW MetWest HY", name="TCW MetWest High Yield M", segment="HY US", style="Actif"),
    "HYG": dict(short="iShares HY (HYG)", name="iShares iBoxx $ HY Corp", segment="HY US", style="Passif"),
    "JNK": dict(short="SPDR HY (JNK)", name="SPDR Bloomberg HY Bond", segment="HY US", style="Passif"),
    "USHY": dict(short="iShares Broad HY", name="iShares Broad USD HY Corp", segment="HY US", style="Passif"),
    "ANGL": dict(short="VanEck Fallen Angels", name="VanEck Fallen Angel HY", segment="HY US", style="Smart beta"),
    "SJNK": dict(short="SPDR HY court terme", name="SPDR Short Term HY Bond", segment="HY US", style="Smart beta"),
    # ---- High Yield Euro (EUR) ------------------------------------------------------
    "IHYG.L": dict(short="iShares € HY", name="iShares € High Yield Corp", segment="HY Euro", style="Passif"),
    "XHYA.DE": dict(short="Xtrackers € HY", name="Xtrackers EUR High Yield Corp", segment="HY Euro", style="Passif"),
    "SYBJ.DE": dict(short="SPDR € HY", name="SPDR Bloomberg Euro HY", segment="HY Euro", style="Passif"),
    # ---- Crédit Euro Investment Grade (EUR) -----------------------------------------
    "D5BG.DE": dict(short="Xtrackers € Corp", name="Xtrackers EUR Corporate Bond", segment="Crédit Euro IG", style="Passif"),
    "SYBC.DE": dict(short="SPDR € Corp", name="SPDR Bloomberg Euro Corporate", segment="Crédit Euro IG", style="Passif"),
    "EUNS.DE": dict(short="iShares € Corp 1-5 ESG", name="iShares € Corp ex-Fin 1-5 ESG SRI", segment="Crédit Euro IG", style="ESG / court"),
}

# Séries de marché Yahoo (facteurs, change, benchmarks proxy)
MARKET_TICKERS = {
    "IEAC.L": "iShares Core € Corp Bond (benchmark proxy IG €)",
    "IEF": "UST 7-10 ans (facteur taux US)",
    "EUNH.DE": "iShares Core € Govt Bond (facteur taux €)",
    "^GSPC": "S&P 500",
    "^STOXX50E": "Euro Stoxx 50",
    "EURUSD=X": "EUR/USD",
}

# Séries FRED
FRED_SERIES = {
    "ICE_HY_US_TR": "BAMLHYH0A0HYM2TRIV",  # ICE BofA US High Yield – Total Return
    "ICE_HY_EUR_TR": "BAMLHE00EHYITRIV",  # ICE BofA Euro High Yield – Total Return
    "OAS_HY_US": "BAMLH0A0HYM2",  # spread OAS HY US (%)
    "OAS_HY_EUR": "BAMLHE00EHYIOAS",  # spread OAS HY Euro (%)
    "SOFR": "SOFR",  # taux court USD (%)
    "ESTR": "ECBESTRVOLWGTTRMDMNRT",  # €STR (%)
    "UST5Y": "DGS5",  # taux 5 ans US (%)
}

# Paramétrage de chaque segment d'appel d'offres
SEGMENTS = {
    "HY US": dict(
        currency="USD",
        benchmarks={"ICE BofA US High Yield (TR)": "ICE_HY_US_TR", "HYG (proxy ETF)": "HYG"},
        rf="SOFR",
        spread="OAS_HY_US",
        rates="IEF",
        equity="^GSPC",
    ),
    "HY Euro": dict(
        currency="EUR",
        benchmarks={"ICE BofA Euro High Yield (TR)": "ICE_HY_EUR_TR", "IHYG (proxy ETF)": "IHYG.L"},
        rf="ESTR",
        spread="OAS_HY_EUR",
        rates="EUNH.DE",
        equity="^STOXX50E",
    ),
    "Crédit Euro IG": dict(
        currency="EUR",
        benchmarks={"IEAC – iShares Core € Corp (proxy)": "IEAC.L"},
        rf="ESTR",
        spread="OAS_HY_EUR",  # pas de série OAS IG € gratuite : proxy HY €
        rates="EUNH.DE",
        equity="^STOXX50E",
    ),
}


def _fetch_fred(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    raw = urllib.request.urlopen(url, timeout=30).read().decode()
    df = pd.read_csv(io.StringIO(raw))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    s = pd.to_numeric(df["value"], errors="coerce")
    s.index = df["date"]
    return s.dropna()


def _fetch_yahoo(tickers: list[str]) -> pd.DataFrame:
    import yfinance as yf

    px = yf.download(tickers, start=START, auto_adjust=True, progress=False)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    return px


def _fetch_fund_info(tickers: list[str]) -> pd.DataFrame:
    """Frais (TER) et encours via Yahoo — best effort, NaN si indisponible."""
    import yfinance as yf

    rows = []
    for t in tickers:
        ter, aum = None, None
        try:
            info = yf.Ticker(t).info
            ter = info.get("netExpenseRatio")
            aum = info.get("totalAssets")
        except Exception:
            pass
        rows.append(dict(ticker=t, ter=ter, aum=aum))
    return pd.DataFrame(rows).set_index("ticker")


def download_all() -> dict:
    tickers = list(FUNDS) + list(MARKET_TICKERS)
    prices = _fetch_yahoo(tickers)
    fred = pd.DataFrame({k: _fetch_fred(v) for k, v in FRED_SERIES.items()})
    info = _fetch_fund_info(list(FUNDS))
    data = dict(prices=prices, fred=fred, info=info, asof=datetime.now())
    os.makedirs(CACHE_DIR, exist_ok=True)
    pd.to_pickle(data, CACHE_FILE)
    return data


def load_data(refresh: bool = False) -> dict:
    """Retourne le cache local s'il existe, sinon télécharge."""
    if not refresh and os.path.exists(CACHE_FILE):
        return pd.read_pickle(CACHE_FILE)
    try:
        return download_all()
    except Exception:
        if os.path.exists(CACHE_FILE):
            return pd.read_pickle(CACHE_FILE)
        raise


def build_levels(data: dict) -> pd.DataFrame:
    """Un seul DataFrame quotidien : cours des fonds + séries de niveau FRED (indices TR)."""
    px = data["prices"].copy()
    fred = data["fred"]
    for col in ["ICE_HY_US_TR", "ICE_HY_EUR_TR"]:
        px[col] = fred[col]
    return px.sort_index()
