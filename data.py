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
# Univers : les GÉRANTS DU FRR sur les segments concernés par les appels d'offres 2027.
#
# Source : « Listes des marchés publics conclus par le FRR » (fondsdereserve.fr, rubrique
# Publications), marchés 2020FRR01 (crédit euro, attribués en 2021) et 2022FRR01 (HY US,
# attribués en février 2023). Les mandats sont dédiés et non publics : chaque gérant est
# représenté par un FONDS OUVERT de la même stratégie (proxy), d'où les écarts possibles
# avec le mandat réel (contraintes ESG du FRR, frais, taille).
# Les ETF « Alternative passive » servent de point de comparaison.
# --------------------------------------------------------------------------------------
CANDIDATES_SOURCE = "Fonds ouverts des principaux gérants du marché (données Morningstar via Yahoo Finance)"
FRR_SOURCE = "Listes des marchés publics conclus par le FRR et rapport annuel 2025 (fondsdereserve.fr)"
FUNDS = {
    # ---- High Yield US (USD) — marché 2022FRR01, attribué en février 2023 ------------
    "OHYFX": dict(short="JPMorgan AM", name="JPMorgan High Yield I", segment="HY US", style="Gérant FRR",
                  mandate="HY US · 2022FRR01 · attribué le 20/02/2023", proxy="fonds HY US phare du gérant"),
    "0P0000JSAN": dict(short="Nomura AM", name="Nomura Funds US High Yield Bond I USD", segment="HY US", style="Gérant FRR",
                       mandate="HY US · 2022FRR01 · attribué le 20/02/2023", proxy="fonds UCITS HY US du gérant"),
    "AGDYX": dict(short="AllianceBernstein", name="AB High Income Advisor", segment="HY US", style="Gérant FRR",
                  mandate="HY US · 2022FRR01 · attribué le 21/02/2023",
                  proxy="proxy imparfait : stratégie high income incluant du HY mondial et de la dette émergente"),
    "PHYQX": dict(short="CPR AM / PGIM", name="PGIM High Yield R6", segment="HY US", style="Gérant FRR",
                  mandate="HY US · 2022FRR01 · attribué le 20/02/2023 (BFT IM, devenu CPR AM ; sous-gérant PGIM Fixed Income)",
                  proxy="fonds HY US phare du sous-gérant PGIM Fixed Income (rapport annuel FRR 2025)"),
    "HYG": dict(short="ETF iShares HY", name="iShares iBoxx $ HY Corp", segment="HY US", style="Alternative passive"),
    "USHY": dict(short="ETF iShares Broad HY", name="iShares Broad USD HY Corp", segment="HY US", style="Alternative passive"),
    # ---- High Yield Euro (EUR) — marché 2020FRR01 lot 2, attribué en 2021 ------------
    "0P00016H0K.F": dict(short="BlackRock", name="BGF European High Yield Bond A2", segment="HY Euro", style="Gérant FRR",
                         mandate="HY Euro · 2020FRR01 lot 2 · attribué le 29/09/2021", proxy="fonds HY européen du gérant"),
    "0P00018KKM.F": dict(short="Candriam", name="Candriam Bonds Euro High Yield S", segment="HY Euro", style="Gérant FRR",
                         mandate="HY Euro · 2020FRR01 lot 2 · attribué le 27/09/2021", proxy="fonds HY euro du gérant"),
    "0P0000WLB3.F": dict(short="DWS", name="DWS Invest Euro High Yield Corporates LD", segment="HY Euro", style="Gérant FRR",
                         mandate="HY Euro · 2020FRR01 lot 2 · attribué le 27/09/2021", proxy="fonds HY euro du gérant"),
    "0P0000ZNJQ.F": dict(short="Degroof Petercam", name="DPAM L Bonds Higher Yield W", segment="HY Euro", style="Gérant FRR",
                         mandate="HY Euro · 2020FRR01 lot 2 · attribué le 29/09/2021",
                         proxy="proxy imparfait : stratégie haut rendement plus large que le HY euro"),
    "0P0001E1E1.F": dict(short="Columbia Threadneedle", name="CT (Lux) European High Yield Bond IE", segment="HY Euro", style="Gérant FRR",
                         mandate="HY Euro · 2020FRR01 lot 2 · attribué le 30/09/2021", proxy="fonds HY européen du gérant"),
    "IHYG.L": dict(short="ETF iShares € HY", name="iShares € High Yield Corp", segment="HY Euro", style="Alternative passive"),
    # ---- Crédit Euro Investment Grade (EUR) — marché 2020FRR01 lot 1, attribué en 2021
    "0P00001RX7.F": dict(short="AXA IM (BNP PAM)", name="AXA WF Euro Credit Plus I", segment="Crédit Euro IG", style="Gérant FRR",
                         mandate="Crédit € IG · 2020FRR01 lot 1 · attribué le 29/09/2021 (AXA IM, devenu BNP Paribas AM Europe)",
                         proxy="fonds crédit euro du gérant"),
    "0P0001DFO1.F": dict(short="M&G (via CPR)", name="M&G (Lux) Euro Corporate Bond C", segment="Crédit Euro IG", style="Gérant FRR",
                         mandate="Crédit € IG · 2020FRR01 lot 1 · attribué le 28/10/2021 (BFT IM, devenu CPR AM – M&G)", proxy="fonds crédit euro du sous-gérant"),
    "0P00000ECM.F": dict(short="Union Inv. (via CPR)", name="UniEuroRenta Corporates A", segment="Crédit Euro IG", style="Gérant FRR",
                         mandate="Crédit € IG · 2020FRR01 lot 1 · attribué le 29/09/2021 (BFT IM, devenu CPR AM – Union Investment)",
                         proxy="fonds crédit euro du sous-gérant"),
    "0P00000S3H.F": dict(short="BlackRock", name="BGF Euro Corporate Bond A2", segment="Crédit Euro IG", style="Gérant FRR",
                         mandate="Crédit € IG · 2020FRR01 lot 1 · attribué le 29/09/2021", proxy="fonds crédit euro du gérant"),
    "0P00009D09.F": dict(short="DWS", name="DWS Invest Euro Corporate Bonds FC", segment="Crédit Euro IG", style="Gérant FRR",
                         mandate="Crédit € IG · 2020FRR01 lot 1 · attribué le 27/09/2021", proxy="fonds crédit euro du gérant"),
    "D5BG.DE": dict(short="ETF Xtrackers € Corp", name="Xtrackers EUR Corporate Bond", segment="Crédit Euro IG", style="Alternative passive"),
    # ---- Candidats potentiels (hors gérants actuels du FRR) — fonds ouverts, données Morningstar via Yahoo
    # HY US
    "PHIYX": dict(short="PIMCO", name="PIMCO High Yield Instl", segment="HY US", style="Candidat"),
    "BHYIX": dict(short="BlackRock", name="BlackRock High Yield Instl", segment="HY US", style="Candidat"),
    "VWEAX": dict(short="Vanguard (Wellington)", name="Vanguard High-Yield Corporate Adm", segment="HY US", style="Candidat"),
    "MWHIX": dict(short="TCW MetWest", name="TCW MetWest High Yield Bond I", segment="HY US", style="Candidat"),
    "PRHIX": dict(short="T. Rowe Price", name="T. Rowe Price High Yield I", segment="HY US", style="Candidat"),
    "SPHIX": dict(short="Fidelity", name="Fidelity High Income", segment="HY US", style="Candidat"),
    "LAHYX": dict(short="Lord Abbett", name="Lord Abbett High Yield I", segment="HY US", style="Candidat"),
    "NHILX": dict(short="Neuberger Berman", name="Neuberger High Income Bond Instl", segment="HY US", style="Candidat"),
    "MHYIX": dict(short="MacKay Shields", name="NYLI MacKay High Yield Corporate Bond I", segment="HY US", style="Candidat"),
    "HAHYX": dict(short="Hartford (Wellington)", name="Hartford High Yield Y", segment="HY US", style="Candidat"),
    "HYIFX": dict(short="Invesco", name="Invesco High Yield R6", segment="HY US", style="Candidat"),
    # HY Euro
    "0P00000I0Z.F": dict(short="Amundi", name="Amundi Funds Euro High Yield Bond A EUR C", segment="HY Euro", style="Candidat"),
    "0P000015HC.F": dict(short="Muzinich", name="Muzinich Europeyield HEUR Acc A", segment="HY Euro", style="Candidat"),
    "0P0000ZDHO.F": dict(short="Robeco", name="Robeco European High Yield Bonds FH EUR", segment="HY Euro", style="Candidat"),
    "0P00001A3Z.F": dict(short="Nordea", name="Nordea European High Yield A EUR", segment="HY Euro", style="Candidat"),
    "0P0000N9KP.F": dict(short="Allianz GI", name="Allianz Euro High Yield Bond AT EUR", segment="HY Euro", style="Candidat"),
    "0P00000MYT.F": dict(short="Pictet AM", name="Pictet EUR High Yield I", segment="HY Euro", style="Candidat"),
    "0P0000ABTK.F": dict(short="Eurizon", name="Eurizon Bond High Yield Z EUR Acc", segment="HY Euro", style="Candidat"),
    "0P0000KNVW.F": dict(short="Lazard Frères Gestion", name="Lazard Euro Corp High Yield PVC EUR", segment="HY Euro", style="Candidat"),
    # Crédit Euro IG
    "0P0001HOTN.F": dict(short="Amundi", name="Amundi Funds Euro Corporate Bond Select I2 EUR C", segment="Crédit Euro IG", style="Candidat"),
    "0P0000237A.F": dict(short="Robeco", name="Robeco Euro Credit Bonds I EUR", segment="Crédit Euro IG", style="Candidat"),
    "0P00018HP9.F": dict(short="Allianz GI", name="Allianz Euro Credit SRI IT EUR", segment="Crédit Euro IG", style="Candidat"),
    "0P00001WNK.F": dict(short="Candriam", name="Candriam Bonds Euro Corporate I EUR Cap", segment="Crédit Euro IG", style="Candidat"),
    "0P00000LKF.F": dict(short="Pictet AM", name="Pictet EUR Corporate Bonds I", segment="Crédit Euro IG", style="Candidat"),
    "0P00019L2L.F": dict(short="JPMorgan AM", name="JPM Euro Corporate Bond I acc EUR", segment="Crédit Euro IG", style="Candidat"),
    "0P0000A9GS.F": dict(short="PIMCO", name="PIMCO GIS Euro Credit Instl EUR Acc", segment="Crédit Euro IG", style="Candidat"),
    "0P0000VDEG.F": dict(short="Eurizon", name="Eurizon Bond Corporate EUR Z Acc", segment="Crédit Euro IG", style="Candidat"),
    "0P0000SGIP.F": dict(short="Ostrum AM", name="Ostrum SRI Credit Euro I", segment="Crédit Euro IG", style="Candidat"),
}

# Séries de marché Yahoo (facteurs, change, benchmarks proxy)
MARKET_TICKERS = {
    "IEAC.L": "iShares Core € Corp Bond (benchmark proxy IG €)",
    "IEF": "UST 7-10 ans (facteur taux US)",
    "EUNH.DE": "iShares Core € Govt Bond (facteur taux €)",
    "^GSPC": "S&P 500",
    "^STOXX50E": "Euro Stoxx 50",
    "EURUSD=X": "EUR/USD",
    "EURJPY=X": "EUR/JPY",
    "EURGBP=X": "EUR/GBP",
    "EURCHF=X": "EUR/CHF",
    "^N225": "Nikkei 225 (actifs en JPY)",
    "^FTSE": "FTSE 100 (actifs en GBP)",
    "^SSMI": "SMI (actifs en CHF)",
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
    "SONIA": "IUDSOIA",  # taux court GBP (%)
    "JPY3M": "IR3TIB01JPM156N",  # taux 3 mois JPY (%, mensuel)
    "CHF3M": "IR3TIB01CHM156N",  # taux 3 mois CHF (%, mensuel)
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
