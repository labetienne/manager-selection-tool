"""Manager Selection Tool – Crédit Euro & High Yield US

Prototype d'outil de sélection et de suivi de gérants délégués :
performance vs benchmark, analyse factorielle (création de valeur), grille de scoring
d'appel d'offres, overlay de change EUR/USD et reporting d'un put spread actions.

Lancer :  .venv/bin/streamlit run app.py
"""
from __future__ import annotations

import io
import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import importlib

import analytics as A
import data as D
import methode
import report
import report_frr

# Streamlit Cloud ne recharge pas les modules locaux quand seul leur fichier change :
# sans ceci, un nouvel app.py peut tourner avec un ancien analytics.py en mémoire.
for _mod in (A, D, methode, report, report_frr):
    importlib.reload(_mod)
build_fiche = report.build_fiche

st.set_page_config(page_title="Manager Selection Tool", page_icon="📊", layout="wide")

PCT_COLS = {
    "Rdt annualisé", "Rdt benchmark", "Surperf. annualisée", "Volatilité", "Tracking error",
    "Alpha (Jensen)", "Max drawdown", "Up capture", "Down capture", "% semaines surperf.",
    "Alpha factoriel",
}
COLORS = px.colors.qualitative.Safe


def fmt_num(x, d=2):
    """Nombre au format français (virgule décimale)."""
    return "–" if pd.isna(x) else f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def fmt_pct(x, d=2):
    return "–" if pd.isna(x) else fmt_num(x * 100, d) + " %"


def style_metrics(df: pd.DataFrame):
    fmt = {c: "{:.2%}" for c in df.columns if c in PCT_COLS}
    fmt.update({c: "{:.2f}" for c in ["Sharpe", "Sortino", "Information ratio", "Bêta", "Corrélation", "Alpha t-stat", "R²"] if c in df})
    fmt.update({"TER": "{:.2f} %", "Encours (Md$)": "{:.1f}", "Nb semaines": "{:.0f}", "Score": "{:.0f}", "SFDR": "{:.0f}"})
    df = df.copy()
    if "TER" in df:  # frais souvent indisponibles : affichage texte pour éviter « None »
        df["TER"] = df["TER"].map(lambda v: "–" if pd.isna(v) else fmt_num(v) + " %")
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return df.style.format({k: v for k, v in fmt.items() if k in num}, na_rep="–", decimal=",", thousands=" ")


# Définitions affichées en infobulle (en-têtes de tableau et indicateurs)
HELP = {
    "Verdict": "Le gérant crée-t-il de la valeur une fois ses expositions de marché neutralisées ? "
               "Basé sur l'alpha factoriel et sa significativité statistique (t-stat).",
    "Rdt annualisé": "Rendement moyen par an, net de frais, dividendes réinvestis.",
    "Surperf. annualisée": "Rendement annualisé du fonds moins celui de l'indice. Positif = le fonds bat l'indice.",
    "Volatilité": "Amplitude des variations du fonds (écart-type annualisé). Plus c'est bas, plus c'est stable.",
    "Tracking error": "Écart de comportement avec l'indice (écart-type annualisé de la différence de rendement).",
    "Information ratio": "Surperformance obtenue par unité d'écart à l'indice. > 0,5 = bon ; < 0 = le fonds fait moins bien que l'indice.",
    "Alpha factoriel": "Rendement que le gérant apporte au-delà de ce qu'expliquent le crédit, les taux et les actions. "
                       "C'est l'indicateur central de l'outil.",
    "Alpha t-stat": "Fiabilité statistique de l'alpha. |t| ≥ 2 : alpha significatif ; sinon il peut relever du hasard.",
    "Bêta": "Sensibilité au benchmark. 1 = bouge comme l'indice ; < 1 = plus défensif.",
    "Max drawdown": "Pire baisse subie entre un plus haut et un plus bas sur la période.",
    "Up capture": "Part des hausses de l'indice captée par le fonds. > 100 % = fait mieux que l'indice quand il monte.",
    "Down capture": "Part des baisses de l'indice subie par le fonds. < 100 % = protège mieux que l'indice quand il baisse.",
    "TER": "Frais annuels totaux du fonds (en % de l'encours).",
    "Encours (Md$)": "Taille du fonds, en milliards.",
    "SFDR": "Classification européenne du fonds : article 9 (objectif durable), 8 (promeut des caractéristiques "
            "environnementales ou sociales), 6 (aucune). Le FRR sélectionne ses fonds en article 8 ou 9. "
            "Relevée dans la documentation du fonds ; non applicable aux fonds américains.",
}


def short(t: str) -> str:
    """Nom lisible d'un fonds (ticker en secours)."""
    return D.FUNDS[t]["short"] if t in D.FUNDS else t


def tag(t: str) -> str:
    """Nom affiché dans les tableaux, avec 🏛️ pour les gérants actuels du FRR."""
    return ("🏛️ " if D.FUNDS.get(t, {}).get("style") == "Gérant FRR" else "") + short(t)


verdict = A.verdict



# ======================================================================================
# Données
# ======================================================================================
@st.cache_data(show_spinner="Chargement des données de marché…")
def get_data(refresh_token: int, cache_version: float):
    """cache_version = date de modification du fichier cache : un nouveau cache invalide la mémoire."""
    d = D.load_data(refresh=refresh_token > 0)
    if not (set(D.FUNDS).issubset(d["prices"].columns) and set(D.FRED_SERIES).issubset(d["fred"].columns)):  # ancien cache
        d = D.load_data(refresh=True)
    levels = D.build_levels(d)
    rets = A.weekly_returns(levels)
    return d, levels, rets


if "refresh" not in st.session_state:
    st.session_state.refresh = 0

_cache_v = os.path.getmtime(D.CACHE_FILE) if os.path.exists(D.CACHE_FILE) else 0.0
data, levels, rets = get_data(st.session_state.refresh, _cache_v)
fred = data["fred"]
info = data["info"]
SFDR = D.load_sfdr()


def sfdr_label(t: str) -> str:
    if t not in SFDR:
        return "n.a."  # fonds non européen : SFDR non applicable
    a = SFDR[t]["article"]
    return f"Art. {a}" if a else "n.d."

# ======================================================================================
# Barre latérale
# ======================================================================================
with st.sidebar:
    st.title("📊 Manager Selection")
    st.caption("Prototype de sélection et de suivi de gérants délégués")
    EXPERT = st.toggle("🔬 Vue détaillée", value=False,
                       help="Affiche tous les indicateurs techniques, les réglages et les tableaux détaillés. "
                            "Désactivée, l'outil ne montre que l'essentiel, expliqué en clair.")

    seg_name = st.radio("Segment (appel d'offres)", list(D.SEGMENTS), index=0)
    seg = D.SEGMENTS[seg_name]
    bench_label = st.selectbox("Benchmark", list(seg["benchmarks"])) if EXPERT else list(seg["benchmarks"])[0]
    bench = seg["benchmarks"][bench_label]

    seg_funds = [t for t, m in D.FUNDS.items() if m["segment"] == seg_name and t != bench]
    styles = ["Gérant FRR", "Candidat", "Alternative passive"]
    univ = st.segmented_control(
        "Univers", styles, selection_mode="multi", default=styles, key=f"univ_{seg_name}",
        format_func=lambda x: {"Gérant FRR": "🏛️ FRR", "Candidat": "Candidats", "Alternative passive": "Passif"}[x],
        help="🏛️ FRR : gérants actuels des mandats du FRR. Candidats : autres grands gérants du marché "
             "(données Morningstar). Passif : ETF de référence.",
    ) or styles
    candidates = [t for t in seg_funds if D.FUNDS[t]["style"] in univ]
    counts = {s_: sum(D.FUNDS[t]["style"] == s_ for t in candidates) for s_ in styles}
    selected = candidates
    if EXPERT:
        with st.expander(f"Affiner la sélection ({len(candidates)} fonds)"):
            selected = st.multiselect(
                "Fonds analysés", candidates, default=candidates, key=f"sel_{seg_name}_{'_'.join(univ)}",
                format_func=tag,
            )
    st.caption(f"{counts['Gérant FRR']} gérants FRR · {counts['Candidat']} candidats · {counts['Alternative passive']} "
               f"passif{'s' if counts['Alternative passive'] > 1 else ''}")

    first = rets[bench].first_valid_index()
    last = rets.index.max()
    horizon = (st.select_slider("Horizon d'analyse", ["1 an", "2 ans", "3 ans", "5 ans", "Max"], value="3 ans")
               if EXPERT else "3 ans")
    years = {"1 an": 1, "2 ans": 2, "3 ans": 3, "5 ans": 5, "Max": 50}[horizon]
    start = max(first, last - pd.DateOffset(years=years))
    st.caption(f"Période : {start:%d/%m/%Y} → {last:%d/%m/%Y}  ·  devise {seg['currency']}")
    if bench.startswith("ICE"):
        st.caption("ℹ️ Les indices ICE BofA ne sont diffusés gratuitement par FRED que sur ~3 ans.")

    with st.expander("📖 Glossaire"):
        st.markdown("\n".join(f"- **{k}** : {v}" for k, v in HELP.items()))
    st.divider()
    st.caption(f"Gérants : {D.FRR_SOURCE}.")
    st.caption(f"Données au {data['asof']:%d/%m/%Y %H:%M} (Yahoo Finance, FRED)")
    if st.button("🔄 Rafraîchir les données"):
        st.session_state.refresh += 1
        st.cache_data.clear()
        st.rerun()

if not selected:
    st.warning("Sélectionnez au moins un fonds.")
    st.stop()

# ======================================================================================
# Calculs communs au segment
# ======================================================================================
R = rets.loc[rets.index > start]
rf = A.weekly_rf(fred[seg["rf"]]).reindex(R.index).ffill().fillna(0)
factors = A.factor_frame(data, seg, rets).loc[R.index]
b = R[bench]


@st.cache_data(show_spinner=False)
def segment_table(seg_name, bench, start, selected, data_version):
    rows, regs = {}, {}
    for t in selected:
        if R[t].dropna().shape[0] < 26:
            continue
        m = A.perf_metrics(R[t], b, rf)
        fr = A.factor_regression(R[t], rf, factors)
        m["Alpha factoriel"] = fr["alpha_ann"]
        m["Alpha t-stat"] = fr["alpha_t"]
        m["R²"] = fr["r2"]
        m["TER"] = info.loc[t, "ter"] if t in info.index else np.nan
        aum = info.loc[t, "aum"] if t in info.index else np.nan
        m["Encours (Md$)"] = aum / 1e9 if pd.notna(aum) else np.nan
        m["SFDR"] = (SFDR.get(t) or {}).get("article") or np.nan
        rows[t] = m
        regs[t] = fr
    return pd.DataFrame(rows).T.astype(float), regs


DATA_VERSION = (st.session_state.refresh, _cache_v)  # clé de cache des calculs dérivés
table, regs = segment_table(seg_name, bench, start, tuple(selected), DATA_VERSION)


@st.cache_data(show_spinner="Génération du rapport FRR…")
def frr_report(data_version):
    return report_frr.build_frr_report(data, rets, SFDR)


st.sidebar.download_button(
    "📑 Rapport de suivi des gérants FRR (PDF)", frr_report(DATA_VERSION),
    file_name=f"rapport_suivi_gerants_FRR_{data['asof']:%Y%m%d}.pdf", mime="application/pdf",
    width="stretch",
    help="6 pages façon CSG Performance : messages clés, tableau de bord des 14 gérants, contexte de marché, "
         "une page par segment, évolutions sur 3 mois et points de vigilance.",
)
if table.empty:
    st.error("Historique insuffisant sur la période choisie.")
    st.stop()

@st.cache_data(show_spinner="Génération de la fiche PDF…")
def fiche_pdf(f, seg_name, bench, start, data_version, badge, why, level, synthesis):
    """Fiche gérant PDF, mise en cache par gérant / segment / période."""
    return build_fiche(
        ticker=f, meta=D.FUNDS[f], m=table.loc[f], fr=regs[f], pair=R[[f, bench]],
        bench_col=bench, bench_label=bench_label, seg_name=seg_name, currency=seg["currency"],
        rf_ann=A.ann_return(rf.dropna()), badge=badge, why=why, level=level,
        synthesis=synthesis, asof=data["asof"],
    )


label = lambda t: f"{D.FUNDS[t]['short']} — {D.FUNDS[t]['name']}" if t in D.FUNDS else bench_label
table["Verdict"] = [verdict(table.loc[t])[0] for t in table.index]

st.title(f"Gérants du FRR : {seg_name}")
st.caption(
    f"Benchmark : **{bench_label}** · {len(table)} fonds · rendements hebdomadaires "
    f"en {seg['currency']}, total return (dividendes réinvestis), nets de frais"
)

first_visit = st.session_state.setdefault("first_visit", True)
st.session_state.first_visit = False
with st.expander("ℹ️ Mode d'emploi", expanded=first_visit):
    st.markdown(
        "Ce prototype suit les gérants actuels du FRR en crédit euro (investment grade et haut rendement) et en High "
        "Yield US. Le haut rendement pèse à lui seul 21,5 % du portefeuille. Chaque mandat est comparé à son indice, au "
        "marché et au coût du passif ; l'outil montre aussi ce que le FRR détient vraiment, suit la couverture de change "
        "et les options, et sert à préparer les appels d'offres.  \n"
        "*Les mandats du FRR sont dédiés et non publics : chaque gérant est donc représenté par un fonds ouvert qu'il "
        "gère avec la même stratégie.*"
    )
    s1, s2, s3 = st.columns(3)
    s1.markdown("**① Les gérants font-ils bien leur travail ?**  \nOnglets *Classement des gérants* et *Fiche gérant*. "
                "Le segment se choisit dans la barre de gauche.")
    s2.markdown("**② Le FRR est-il bien protégé ?**  \nOnglets *Ce que détient le FRR*, *Cades et passif*, "
                "*Couverture de change* et *Protection actions*.")
    s3.markdown("**③ Qui retenir au prochain appel d'offres ?**  \nOnglet *Appel d'offres* : l'outil classe les "
                "candidats et propose un podium.")
    st.caption("Chaque onglet commence par un encadré « En clair ». La vue détaillée (barre de gauche) affiche tous les "
               "chiffres techniques. Survolez les ⓘ pour les définitions. "
               "Chiffres FRR : rapport annuel 2025 et publications de fondsdereserve.fr.")

t_synth, t_ger, t_ptf, t_alm, t_fx, t_der, t_ao, t_meth = st.tabs(
    ["🏁 Classement des gérants", "🔍 Fiche gérant", "🏛️ Ce que détient le FRR", "🏦 Cades et passif",
     "💱 Couverture de change", "🛡️ Protection actions", "🏆 Appel d'offres", "📘 Méthode et formules"])


def en_clair(where, text):
    where.info("💡 **En clair**  \n" + text)

# ======================================================================================
# 1. Vue d'ensemble
# ======================================================================================
with t_synth:
    best_ir = table["Information ratio"].idxmax()
    best_alpha = table["Alpha factoriel"].idxmax()
    n_beat = int((table["Surperf. annualisée"] > 0).sum())
    n_robust = int(table["Verdict"].str.startswith("✅").sum())
    if EXPERT:
        st.markdown(
            f"#### En bref : {n_beat} fonds sur {len(table)} "
            f"bat{'tent' if n_beat > 1 else ''} l'indice, et **{n_robust}** crée{'nt' if n_robust > 1 else ''} "
            f"de la valeur de façon statistiquement robuste."
        )
    frr_rank = [t for t in table["Alpha factoriel"].sort_values(ascending=False).index if D.FUNDS[t]["style"] == "Gérant FRR"]
    en_clair(st, f"Sur {horizon}, **{n_beat} fonds sur {len(table)}** ont fait mieux que leur indice, frais déduits. "
             + (f"Parmi les gérants du FRR, **{short(frr_rank[0])}** s'en sort le mieux et **{short(frr_rank[-1])}** "
                "le moins bien. " if len(frr_rank) > 1 else "")
             + "Dans le tableau, ✅ veut dire que l'avance du gérant est trop régulière pour être due à la chance, "
               "🟡 qu'il fait mieux sans que ce soit encore prouvé, 🟠 ou ❌ qu'il fait moins bien.")
    ranked = table["Alpha factoriel"].rank(ascending=False, method="min").astype(int)
    if EXPERT:
        frr_in = [t for t in table.index if D.FUNDS[t]["style"] == "Gérant FRR"]
        cand_in = [t for t in table.index if D.FUNDS[t]["style"] == "Candidat"]
        if frr_in and cand_in:
            best_frr = min(frr_in, key=lambda t: ranked[t])
            better = [t for t in cand_in if ranked[t] < ranked[best_frr]]
            st.markdown(
                f"🏛️ Meilleur gérant actuel du FRR : **{short(best_frr)}**, {'1ᵉʳ' if ranked[best_frr] == 1 else str(ranked[best_frr]) + 'ᵉ'} sur {len(table)} par alpha factoriel. "
                + (f"{len(better)} candidat{'s' if len(better) > 1 else ''} externe{'s' if len(better) > 1 else ''} "
                   f"{'font' if len(better) > 1 else 'fait'} mieux : "
                   + ", ".join(short(t) for t in sorted(better, key=lambda t: ranked[t])[:4]) + ("…" if len(better) > 4 else "") + "."
                   if better else "Aucun candidat externe ne fait mieux.")
            )
        c = st.columns(4)
        c[0].metric("Rendement de l'indice (par an)", fmt_pct(A.ann_return(b.dropna())), help="Rendement annualisé du benchmark sur la période.")
        c[1].metric("Meilleur information ratio", short(best_ir), f"IR {fmt_num(table.loc[best_ir, 'Information ratio'])}", help=HELP["Information ratio"])
        c[2].metric("Meilleur alpha factoriel", short(best_alpha), fmt_pct(table.loc[best_alpha, "Alpha factoriel"]), help=HELP["Alpha factoriel"])
        c[3].metric("Fonds battant l'indice", f"{n_beat} / {len(table)}", help=HELP["Surperf. annualisée"])

    left, right = st.columns([3, 2]) if EXPERT else (st.container(), None)
    with left:
        cum = (1 + R[selected + [bench]].fillna(0)).cumprod() * 100
        fig = go.Figure()
        shown_cand = False
        frr_i = 0
        for t in selected:
            stl = D.FUNDS[t]["style"]
            if stl == "Candidat":
                fig.add_scatter(x=cum.index, y=cum[t], name="Candidats", legendgroup="cand", showlegend=not shown_cand,
                                hovertemplate=f"{short(t)} : %{{y:.1f}}<extra></extra>", line=dict(width=1, color="#c4c9d0"))
                shown_cand = True
            elif stl == "Alternative passive":
                fig.add_scatter(x=cum.index, y=cum[t], name=short(t), line=dict(width=1.5, color="#7a8794", dash="dash"))
            else:
                fig.add_scatter(x=cum.index, y=cum[t], name="🏛️ " + short(t), line=dict(width=2, color=COLORS[frr_i % len(COLORS)]))
                frr_i += 1
        fig.add_scatter(x=cum.index, y=cum[bench], name="Benchmark", line=dict(width=3, color="black", dash="dot"))
        fig.update_layout(title="Performance cumulée (base 100)", height=430, margin=dict(t=50, b=10), hovermode="x unified")
        st.plotly_chart(fig, width="stretch")
    if EXPERT:
        with right:
            sc = table.reset_index(names="Ticker")
            sc["Fonds"] = sc["Ticker"].map(short)
            sc["Style"] = sc["Ticker"].map(lambda t: D.FUNDS[t]["style"])
            fig = px.scatter(
                sc, x="Volatilité", y="Rdt annualisé", color="Style", hover_name="Fonds",
                size=sc["Encours (Md$)"].fillna(1).clip(lower=0.5), size_max=22,
                title="Rendement / risque (taille = encours)",
            )
            bv, br = b.std() * np.sqrt(52), A.ann_return(b.dropna())
            fig.add_scatter(x=[bv], y=[br], mode="markers+text", text=["Benchmark"], marker=dict(symbol="x", size=14, color="black"), showlegend=False, textposition="bottom center")
            fig.update_traces(textposition="top center", selector=dict(mode="markers+text"))
            fig.update_layout(height=430, margin=dict(t=50, b=10), xaxis_tickformat=".1%", yaxis_tickformat=".1%")
            st.plotly_chart(fig, width="stretch")

    st.subheader("Tableau comparatif")
    show_all = EXPERT and st.toggle("Afficher tous les indicateurs", value=False)
    essentials = (["Verdict", "Surperf. annualisée", "Information ratio", "Alpha factoriel",
                   "Max drawdown", "Down capture", "TER"] if EXPERT else
                  ["Verdict", "Surperf. annualisée", "Alpha factoriel", "Max drawdown"]) + (["SFDR"] if seg_name != "HY US" else [])
    plain = {} if EXPERT else {"Surperf. annualisée": "Écart avec l'indice (par an)", "Alpha factoriel": "Valeur ajoutée du gérant (par an)",
                               "Max drawdown": "Pire baisse", "SFDR": "Label ESG (SFDR)"}
    extras = ["Rdt annualisé", "Volatilité", "Tracking error", "Alpha t-stat", "Bêta", "Up capture", "Encours (Md$)"]
    cols = essentials + (extras if show_all else [])
    disp = table[cols].sort_values("Alpha factoriel", ascending=False)
    if "SFDR" in disp:
        disp["SFDR"] = [sfdr_label(t) for t in disp.index]
    disp.index = [tag(t) for t in disp.index]

    def _color(v, good_if_positive=True, pivot=0.0):
        if pd.isna(v) or v == pivot:
            return ""
        good = (v > pivot) == good_if_positive
        return "color: #1a7f37; font-weight: 600" if good else "color: #c62828"

    styler = style_metrics(disp)
    for col_name in [c_ for c_ in ["Surperf. annualisée", "Information ratio", "Alpha factoriel"] if c_ in cols]:
        styler = styler.map(_color, subset=[col_name])
    if "Down capture" in cols:
        styler = styler.map(lambda v: _color(v, good_if_positive=False, pivot=1.0), subset=["Down capture"])
    order = list(table[cols].sort_values("Alpha factoriel", ascending=False).index)
    event = st.dataframe(
        styler,
        width="stretch",
        column_config={c: st.column_config.Column(plain.get(c, c), help=HELP.get(c)) for c in cols},
        on_select="rerun", selection_mode="single-row", key=f"synth_{seg_name}",
    )
    if event.selection.rows:
        picked = order[event.selection.rows[0]]
        if st.session_state.get("_last_pick") != picked:  # nouveau clic seulement : ne pas écraser un choix manuel
            st.session_state._last_pick = picked
            st.session_state.gerant = picked
            st.toast(f"{short(picked)} sélectionné : ouvrez l'onglet 🔍 Fiche gérant.")
    st.caption("Du meilleur au moins bon. Vert = favorable, rouge = défavorable. "
               "Cliquez sur une ligne pour ouvrir le fonds dans l'onglet Fiche gérant. Les définitions s'affichent au survol des en-têtes.")

# ======================================================================================
# 2. Analyse gérant
# ======================================================================================
with t_ger:
    if st.session_state.get("gerant") not in table.index:  # défaut : meilleur alpha du segment
        st.session_state.gerant = table["Alpha factoriel"].idxmax()
    f = st.selectbox("Gérant à analyser", list(table.index), format_func=label, key="gerant")
    m, fr = table.loc[f], regs[f]
    meta = D.FUNDS[f]

    badge, why, level = verdict(m)
    getattr(st, level)(
        f"### {badge}\n**{meta['short']}** ({meta['name']}) : {why} "
        f"(alpha {fmt_pct(m['Alpha factoriel'])} par an, t = {fmt_num(m['Alpha t-stat'], 1)}). "
        f"{'Le fonds bat' if m['Surperf. annualisée'] > 0 else 'Le fonds ne bat pas'} son indice "
        f"({fmt_pct(m['Surperf. annualisée'])} par an, net de frais)."
    )
    if meta["style"] == "Gérant FRR":
        st.caption(f"🏛️ Mandat FRR : {meta['mandate']}. Fonds utilisé comme proxy : {meta['name']} ({f}), {meta['proxy']}.")
    elif meta["style"] == "Candidat":
        st.caption(f"Candidat externe (non gérant du FRR) : {meta['name']} ({f}), données Morningstar via Yahoo Finance.")
    else:
        st.caption(f"Alternative passive : {meta['name']} ({f}), sert de point de comparaison.")
    if f in SFDR:
        sf = SFDR[f]
        st.caption(f"🌱 SFDR : {sfdr_label(f)}" + (f" ([source]({sf['source']}))" if sf["source"] else "")
                   + (f" ({sf['note']})" if sf["note"] else ""))

    if not EXPERT:
        c = st.columns(3)
        c[0].metric("Rendement par an", fmt_pct(m["Rdt annualisé"]), fmt_pct(m["Surperf. annualisée"]) + " vs indice",
                    help=HELP["Rdt annualisé"])
        c[1].metric("Pire baisse", fmt_pct(m["Max drawdown"]), fmt_pct(A.drawdown(b.dropna()).min()) + " pour l'indice",
                    delta_color="off", help=HELP["Max drawdown"])
        c[2].metric("Frais", "–" if pd.isna(m["TER"]) else fmt_num(m["TER"]) + " % par an", help=HELP["TER"])
    if EXPERT:
        c = st.columns(6)
        c[0].metric("Rdt annualisé", fmt_pct(m["Rdt annualisé"]), fmt_pct(m["Surperf. annualisée"]) + " vs indice", help=HELP["Rdt annualisé"])
        c[1].metric("Tracking error", fmt_pct(m["Tracking error"]), help=HELP["Tracking error"])
        c[2].metric("Information ratio", fmt_num(m["Information ratio"]), help=HELP["Information ratio"])
        c[3].metric("Alpha factoriel", fmt_pct(m["Alpha factoriel"]), f"t = {fmt_num(m['Alpha t-stat'], 1)}", delta_color="off", help=HELP["Alpha factoriel"] + " " + HELP["Alpha t-stat"])
        c[4].metric("Max drawdown", fmt_pct(m["Max drawdown"]), fmt_pct(A.drawdown(b.dropna()).min()) + " indice", delta_color="off", help=HELP["Max drawdown"])
        c[5].metric("Frais (TER)", "–" if pd.isna(m["TER"]) else fmt_num(m["TER"]) + " %", help=HELP["TER"])

    # --- commentaire automatique (style note de comité) -----------------------------
    signif = abs(m["Alpha t-stat"]) >= 2
    signif_txt = (
        "**significatif** statistiquement (|t| ≥ 2)" if signif
        else "**non significatif** statistiquement (|t| < 2) : la surperformance éventuelle peut relever du bruit"
    )
    asym = m["Up capture"] - m["Down capture"]
    synth_body = (
        f"Sur la période, le fonds a délivré **{fmt_pct(m['Rdt annualisé'])}** par an contre "
        f"{fmt_pct(m['Rdt benchmark'])} pour l'indice, soit **{fmt_pct(m['Surperf. annualisée'])}** "
        f"de surperformance nette de frais, pour une tracking error de {fmt_pct(m['Tracking error'])} "
        f"(IR = {fmt_num(m['Information ratio'])}). Après neutralisation des expositions crédit, taux et actions, "
        f"l'alpha ressort à **{fmt_pct(m['Alpha factoriel'])}** par an, {signif_txt}. "
        f"Le gérant capte {fmt_pct(m['Up capture'], 0)} des hausses et {fmt_pct(m['Down capture'], 0)} des baisses du marché "
        f"({'profil asymétrique favorable' if asym > 0.02 else 'profil défavorable en baisse' if asym < -0.02 else 'profil symétrique'}). "
        f"Le modèle factoriel explique {fr['r2']:.0%} de la variance."
    )
    verdict_txt = ("un résultat trop régulier pour être dû au hasard. " if signif and m["Alpha factoriel"] > 0 else
                   "un retard trop régulier pour être dû au hasard. " if signif else
                   "mais ce résultat peut encore venir du hasard. ")
    plain_body = (
        f"{meta['short']} a rapporté **{fmt_pct(m['Rdt annualisé'], 1)} par an**, contre {fmt_pct(m['Rdt benchmark'], 1)} pour "
        f"son indice : il fait {'mieux' if m['Surperf. annualisée'] > 0 else 'moins bien'} de "
        f"{fmt_pct(abs(m['Surperf. annualisée']), 1)} par an, frais déduits. Une fois retiré ce qui vient simplement du "
        f"marché (crédit, taux, actions), il lui reste **{fmt_pct(m['Alpha factoriel'], 1)} par an** de valeur ajoutée, "
        f"{verdict_txt}Quand le marché baisse, il subit {fmt_pct(m['Down capture'], 0)} de la baisse : il protège "
        f"{'mieux' if m['Down capture'] < 1 else 'moins bien'} que l'indice."
    )
    if EXPERT:
        st.info(f"**{meta['short']} en résumé** ({meta['style'].lower()}). " + synth_body)
    else:
        en_clair(st, plain_body)

    pdf_bytes = fiche_pdf(f, seg_name, bench, start, DATA_VERSION, badge, why, level,
                          synth_body.replace("**", ""))
    st.download_button(
        "📄 Télécharger la fiche gérant (PDF, 1 page)",
        pdf_bytes,
        file_name=f"fiche_{short(f).replace(' ', '_').replace('/', '-')}.pdf",
        mime="application/pdf",
        type="primary",
        help="Verdict, chiffres clés, graphiques, décomposition du rendement et synthèse : prête à imprimer ou à joindre à une note de comité.",
    )

    left, right = st.columns(2) if EXPERT else (st.container(), None)
    with left:
        pair = R[[f, bench]].dropna()
        cum = (1 + pair).cumprod() * 100
        fig = go.Figure()
        fig.add_scatter(x=cum.index, y=cum[f], name=short(f), line=dict(width=2.5))
        fig.add_scatter(x=cum.index, y=cum[bench], name="Benchmark", line=dict(color="black", dash="dot"))
        rel = cum[f] / cum[bench] * 100
        fig.add_scatter(x=rel.index, y=rel, name="Relatif (dr.)", yaxis="y2", line=dict(color="grey", width=1))
        fig.update_layout(title="Performance cumulée et relative", height=380, margin=dict(t=50, b=10),
                          yaxis2=dict(overlaying="y", side="right", showgrid=False), hovermode="x unified",
                          legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, width="stretch")

        dd = pd.DataFrame({short(f): A.drawdown(pair[f]), "Benchmark": A.drawdown(pair[bench])})
        fig = px.area(dd, title="Drawdown", height=300, labels={"value": "", "index": "", "Date": ""})
        fig.update_traces(stackgroup=None, fill="tozeroy")
        fig.update_layout(yaxis_tickformat=".0%", margin=dict(t=50, b=10), legend_title=None)
        st.plotly_chart(fig, width="stretch")
    if EXPERT:
        with right:
            roll = A.rolling_excess(R[f], b)
            fig = go.Figure()
            fig.add_bar(x=roll.index, y=roll["Surperf. 12M glissante"], name="Surperf. 12M glissante",
                        marker_color=np.where(roll["Surperf. 12M glissante"] >= 0, "#2a9d8f", "#e76f51"))
            fig.add_scatter(x=roll.index, y=roll["Tracking error 12M"], name="Tracking error 12M", line=dict(color="black"))
            fig.update_layout(title="Régularité de la création de valeur", height=380, yaxis_tickformat=".1%",
                              margin=dict(t=50, b=10), legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig, width="stretch")

            alpha_cum = (fr["residuals"] + fr["alpha_ann"] / 52).cumsum()
            fig = px.line(alpha_cum, title="Alpha cumulé (rendement non expliqué par les facteurs)", height=300, labels={"value": "", "index": ""})
            fig.update_layout(yaxis_tickformat=".1%", showlegend=False, margin=dict(t=50, b=10))
            st.plotly_chart(fig, width="stretch")

        st.subheader("Décomposition factorielle du rendement excédentaire")
        l2, r2 = st.columns([2, 3])
        with l2:
            tbl = fr["table"].copy()
            st.dataframe(
                tbl.style.format({"Coefficient": "{:.3f}", "t-stat": "{:.2f}", "p-value": "{:.3f}",
                                  "Contribution annualisée": "{:.2%}"})
                .format("{:.2%}", subset=pd.IndexSlice[["Alpha"], ["Coefficient"]]),
                width="stretch",
            )
            st.caption(
                "Lecture : le coefficient crédit ≈ duration spread (perte en % pour +1 pt de spread) ; "
                "taux = bêta aux emprunts d'État ; actions = bêta au marché actions. "
                "Erreurs-types Newey-West (4 retards)."
            )
        with r2:
            contrib = fr["table"]["Contribution annualisée"].drop("Alpha")
            rf_ann = A.ann_return(rf.dropna())
            wf = pd.Series({"Taux sans risque": rf_ann, **contrib.to_dict(), "Alpha": fr["alpha_ann"]})
            wf["Rdt du fonds"] = wf.sum()
            fig = go.Figure(go.Waterfall(
                x=wf.index, y=wf.values, measure=["relative"] * (len(wf) - 1) + ["total"],
                text=[fmt_pct(v) for v in wf.values], textposition="outside",
                connector=dict(line=dict(color="lightgrey")),
            ))
            fig.update_layout(title="D'où vient le rendement ? (contributions annualisées, approx.)",
                              height=360, yaxis_tickformat=".1%", margin=dict(t=50, b=10))
            st.plotly_chart(fig, width="stretch")

# ======================================================================================
# Portefeuille FRR — composition publiée (missions 2 et 4 : analyse et suivi des risques)
# ======================================================================================
@st.cache_data
def load_portfolio():
    d = pd.read_csv(os.path.join(D.CACHE_DIR, "portefeuille_frr_30092026.csv"))
    d["year"] = d["year"].where(d["year"] < 2100)  # années > 2100 = perpétuelles codées
    return d


def opc_category(name: str) -> str:
    n = name.upper()
    if any(k in n for k in ("LIQUIDITY", "MONETAIRE", "TRESORERIE", "COURT TERME", "3 M ")):
        return "Monétaire"
    if "EMERG" in n or "EM ALL CAP" in n or "LOCAL MARKE" in n:
        return "Dette émergente" if any(k in n for k in ("BOND", "DEBT", "LOCAL")) else "Actions émergentes"
    if any(k in n for k in ("ABS", "SECURITIZED", "STRUCTURED")):
        return "Titrisation"
    return "Thématique / autre"


with t_ptf:
    ptf = load_portfolio()
    st.markdown(
        "Voici les titres que le FRR détenait au 30/09/2026, tous mandats confondus, d'après la composition trimestrielle "
        "publiée sur fondsdereserve.fr. On y retrouve ce que surveillent la Gestion déléguée et le département des "
        "Risques : la concentration, les échéances et la limite d'emprise de 3 %."
    )
    tot = ptf.groupby("type")["value"].sum() / 1e9
    _eq = ptf[ptf.type == "Action"].dropna(subset=["emprise"])
    _mx = _eq.loc[_eq["emprise"].idxmax()]
    en_clair(st, f"Fin septembre 2026, le FRR détenait directement **{fmt_num(tot.get('Action', 0), 1)} Md€ d'actions** et "
                 f"**{fmt_num(tot.get('Obligation', 0), 1)} Md€ d'obligations**, plus {fmt_num(tot.get('OPC', 0), 1)} Md€ "
                 f"placés dans des fonds. La loi lui interdit de posséder plus de 3 % d'une entreprise : sa plus grosse "
                 f"participation est de {fmt_pct(_mx['emprise'], 1)} ({_mx['name']}), la règle est donc respectée.")
    k = st.columns(4)
    k[0].metric("Actions détenues en direct", f"{fmt_num(tot.get('Action', 0), 2)} Md€", f"{(ptf.type == 'Action').sum()} lignes", delta_color="off")
    k[1].metric("Obligations", f"{fmt_num(tot.get('Obligation', 0), 2)} Md€", f"{(ptf.type == 'Obligation').sum()} lignes", delta_color="off")
    k[2].metric("OPC (fonds)", f"{fmt_num(tot.get('OPC', 0), 2)} Md€", f"{(ptf.type == 'OPC').sum()} fonds", delta_color="off")
    k[3].metric("Titres de créance (trésorerie)", f"{fmt_num(tot.get('TCN', 0), 2)} Md€", f"{(ptf.type == 'TCN').sum()} lignes", delta_color="off")

    # --- obligations ---------------------------------------------------------------------
    st.markdown("##### Poche obligataire")
    bonds = ptf[ptf.type == "Obligation"].copy()
    w = bonds["value"] / bonds["value"].sum()
    bins = [0, 2027, 2030, 2035, 2045, 2100]
    labels = ["≤ 2027", "2028-2030", "2031-2035", "2036-2045", "> 2045"]
    bonds["Échéance"] = pd.cut(bonds["year"], bins=bins, labels=labels).astype(object).fillna("Perpétuelle / n.d.")
    by_issuer = bonds.groupby("issuer")["value"].sum().sort_values(ascending=False)
    oat = by_issuer.filter(like="FRANCE O").sum()
    corp = by_issuer.drop([i for i in by_issuer.index if "FRANCE O" in i])
    top10 = corp.head(10).sum() / corp.sum()
    if EXPERT:
        k = st.columns(4)
        k[0].metric("Émetteurs distincts", fmt_num(bonds["issuer"].nunique(), 0))
        k[1].metric("Coupon moyen pondéré", fmt_num((bonds["coupon"] * w).sum(), 2) + " %",
                    help="Moyenne des coupons pondérée par la valeur de marché (lignes avec coupon identifié).")
        k[2].metric("OAT (adossement)", f"{fmt_num(oat / 1e9, 2)} Md€", fmt_pct(oat / bonds["value"].sum(), 0) + " de la poche", delta_color="off")
        k[3].metric("Top 10 émetteurs privés", fmt_pct(top10, 1), "de la poche crédit", delta_color="off",
                    help="Concentration : part des 10 premiers émetteurs d'entreprises dans les obligations hors OAT.")
    left, right = st.columns(2) if EXPERT else (st.container(), None)
    with left:
        prof = bonds.groupby("Échéance")["value"].sum().reindex(labels + ["Perpétuelle / n.d."]) / 1e9
        fig = px.bar(prof.rename("Md€"), title="Profil d'échéances (Md€)", height=330, text_auto=".2f")
        fig.update_traces(marker_color="#1f5fa8")
        fig.update_layout(showlegend=False, margin=dict(t=50, b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, width="stretch")
    if EXPERT:
        with right:
            top = (corp.head(12) / 1e6).rename("M€").to_frame()
            top["% poche crédit"] = corp.head(12) / corp.sum()
            st.markdown("**Premiers émetteurs privés**")
            st.dataframe(top.style.format({"M€": "{:,.0f}", "% poche crédit": "{:.2%}"}, decimal=",", thousands=" "),
                         width="stretch", height=330)

    # --- actions : limite d'emprise --------------------------------------------------------
    st.markdown("##### Poche actions : limite d'emprise (≤ 3 % du capital d'un émetteur)")
    eq = ptf[ptf.type == "Action"].dropna(subset=["emprise"])
    mx = eq.loc[eq["emprise"].idxmax()]
    near = eq[eq["emprise"] >= 0.015].sort_values("emprise", ascending=False)
    (st.success if mx["emprise"] < 0.03 else st.error)(
        f"Emprise maximale : **{fmt_pct(mx['emprise'], 2)}** sur **{mx['name']}** "
        f"({'dans' if mx['emprise'] < 0.03 else 'au-delà de'} la limite réglementaire de 3 %). "
        f"{len(near)} lignes dépassent 1,5 % : des petites et moyennes capitalisations françaises (mandats PMC France)."
    )
    if EXPERT:
        left, right = st.columns(2)
        with left:
            st.markdown("**Lignes les plus proches de la limite**")
            st.dataframe(near.head(12).set_index("name")[["value", "emprise"]].rename(columns={"value": "Valeur (M€)", "emprise": "Emprise"})
                         .assign(**{"Valeur (M€)": lambda x: x["Valeur (M€)"] / 1e6})
                         .style.format({"Valeur (M€)": "{:,.1f}", "Emprise": "{:.2%}"}, decimal=",", thousands=" "), width="stretch")
        with right:
            st.markdown("**Premières lignes en valeur**")
            big = eq.nlargest(12, "value").set_index("name")[["value"]] / 1e6
            st.dataframe(big.rename(columns={"value": "Valeur (M€)"}).style.format("{:,.1f}", decimal=",", thousands=" "), width="stretch")

    # --- OPC ---------------------------------------------------------------------------------
    if EXPERT:
        st.markdown("##### Fonds (OPC)")
        opc = ptf[ptf.type == "OPC"].copy()
        opc["Catégorie"] = opc["name"].map(opc_category)
        left, right = st.columns([2, 3])
        with left:
            cat = opc.groupby("Catégorie")["value"].sum().sort_values() / 1e9
            fig = px.bar(cat, orientation="h", title="OPC par catégorie (Md€)", height=300, text_auto=".2f", labels={"value": "", "Catégorie": ""})
            fig.update_traces(marker_color="#2a9d8f"); fig.update_layout(showlegend=False, margin=dict(t=50, b=10))
            st.plotly_chart(fig, width="stretch")
        with right:
            st.dataframe(opc.nlargest(10, "value").set_index("name")[["Catégorie", "value"]]
                         .assign(value=lambda x: x["value"] / 1e6).rename(columns={"value": "Valeur (M€)"})
                         .style.format({"Valeur (M€)": "{:,.0f}"}, decimal=",", thousands=" "), width="stretch", height=300)
    st.caption("Source : « Composition du portefeuille – 30/09/2026 » (fondsdereserve.fr), extraite automatiquement du PDF ; "
               "totaux rapprochés du document. Non disponibles : secteurs, notations, devises par ligne (il faudrait Bloomberg ou "
               "FactSet) ; les titres ne sont pas attribués à un mandat.")

# ======================================================================================
# 3. Scoring appel d'offres
# ======================================================================================
with t_ao:
    en_clair(st, "Cet onglet prépare un appel d'offres : il donne une note sur 100 à chaque candidat selon ce qui compte "
                 "le plus pour vous (choisissez un profil), écarte ceux qui ne remplissent pas les conditions, et propose "
                 "les 3 meilleurs à rencontrer. Ce n'est qu'un premier tri : au FRR, la décision repose surtout sur "
                 "l'analyse qualitative des équipes.")
    st.markdown(
        "L'onglet pré-classe les candidats pour constituer une short-list à rencontrer en due diligence. Choisissez un "
        "profil de pondération, écartez si besoin les fonds non éligibles, puis lisez le podium.  \n"
        "*Le FRR a lancé le 19/10/2026 l'appel d'offres de renouvellement des mandats HY euro : jusqu'à 6 gérants, en "
        "fonds dédiés, pour 5 ans renouvelables 1 an, candidatures jusqu'au 30/11/2026. Les offres y sont surtout jugées "
        "sur des critères qualitatifs (équipe, process, outils, ESG, frais), puis passent devant le Comité de sélection "
        "des gérants (CSG). Cette grille ne fait qu'un premier tri.*"
    )

    # --- 1. Profil de pondération --------------------------------------------------------
    def _apply_profile():
        prof = st.session_state.get("profile")
        if prof in A.PROFILES:
            for key, w in A.PROFILES[prof].items():
                st.session_state[f"w_{key}"] = w

    if "profile" not in st.session_state:
        st.session_state.profile = "Équilibré"
        _apply_profile()
    c1, c2 = st.columns([3, 2])
    with c1:
        st.segmented_control(
            "Profil de pondération", list(A.PROFILES) + ["Personnalisé"], key="profile",
            on_change=_apply_profile, help=" · ".join(f"{k} : {v}" for k, v in A.PROFILE_HELP.items()),
        )
        prof = st.session_state.profile or "Personnalisé"
        st.caption(A.PROFILE_HELP.get(prof, "Pondérations ajustées à la main."))

    with st.expander("🎚️ Ajuster les pondérations", expanded=prof == "Personnalisé"):
        wcols = st.columns(len(A.CRITERIA))
        for col, (key, (lab, higher, _)) in zip(wcols, A.CRITERIA.items(), strict=True):
            col.slider(lab, 0, 50, step=5, key=f"w_{key}",
                       on_change=lambda: st.session_state.update(profile="Personnalisé"),
                       help=HELP.get(key, "") + (" (plus c'est haut, mieux c'est)" if higher else " (plus c'est bas, mieux c'est)"))
    weights = {key: st.session_state[f"w_{key}"] for key in A.CRITERIA}
    tot = sum(weights.values())
    with c2:
        if tot:
            usable = {k: v for k, v in weights.items() if v and k in table and table[k].notna().any()}
            eff = pd.Series({A.CRITERIA[k][0].split(" (")[0]: v / sum(usable.values()) for k, v in usable.items()})
            fig = px.bar(eff.sort_values(), orientation="h", height=170, text_auto=".0%")
            fig.update_layout(showlegend=False, margin=dict(t=10, b=0, l=0, r=10), xaxis=dict(visible=False),
                              yaxis_title=None, title=None)
            fig.update_traces(marker_color="#1f5fa8")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            if tot != 100:
                st.caption(f"Total saisi : {tot} → poids ramenés à 100 %.")

    # --- 2. Critères éliminatoires -------------------------------------------------------
    with st.expander("🚫 Critères éliminatoires (conditions d'éligibilité de l'appel d'offres)"):
        e = st.columns(3)
        ter_max = e[0].slider("Frais maximum (TER)", 0.0, 1.0, 1.0, 0.05, format="%.2f %%")
        dd_floor = e[1].slider("Pire repli toléré", -20.0, 0.0, -20.0, 0.5, format="%.1f %%") / 100
        aum_min = e[2].slider("Encours minimum (Md)", 0.0, 20.0, 0.0, 0.5,
                              help="Un fonds trop petit expose à un risque de concentration du FRR dans le fonds.")
        need_sfdr = st.checkbox("Exiger SFDR article 8 ou 9 (règle du FRR pour les fonds)", value=False,
                                disabled=seg_name == "HY US",
                                help="Exclut les fonds en article 6 et ceux dont le classement n'a pas été trouvé. "
                                     "Non applicable aux fonds américains (HY US).")
    reasons = {}
    for t in table.index:
        r = []
        if pd.notna(table.loc[t, "TER"]) and table.loc[t, "TER"] > ter_max + 1e-9:
            r.append(f"frais {fmt_num(table.loc[t, 'TER'])} %")
        if table.loc[t, "Max drawdown"] < dd_floor:
            r.append(f"repli {fmt_pct(table.loc[t, 'Max drawdown'], 1)}")
        if aum_min > 0 and (pd.isna(table.loc[t, "Encours (Md$)"]) or table.loc[t, "Encours (Md$)"] < aum_min):
            r.append("encours insuffisant")
        if need_sfdr and not (table.loc[t, "SFDR"] >= 8):
            r.append(f"SFDR {sfdr_label(t)}")
        if r:
            reasons[t] = ", ".join(r)
    eligible = [t for t in table.index if t not in reasons]
    if reasons:
        st.warning("**Exclus :** " + " · ".join(f"{short(t)} ({why_})" for t, why_ in reasons.items()))

    if tot == 0:
        st.warning("Attribuez un poids à au moins un critère.")
    elif len(eligible) < 2:
        st.error("Moins de 2 candidats éligibles : assouplissez les critères éliminatoires.")
    else:
        if len(eligible) < 5:
            st.info(f"ℹ️ Seulement {len(eligible)} candidats : les notes (rangs centiles) sont peu discriminantes. "
                    "Lisez plutôt les valeurs réelles.")
        elig_table = table.loc[eligible]
        scores = A.score(elig_table, weights)
        crit = [c for c in scores.columns if c not in ("Score global", "Rang")]

        def strengths(t):
            row = scores.loc[t, crit].sort_values(ascending=False)
            good = [k.split(" (")[0] for k, v in row.items() if v >= 60][:2]
            bad = [k.split(" (")[0] for k, v in row.items() if v <= 40][-1:]
            return good, bad

        # --- 3. Podium -------------------------------------------------------------------
        st.markdown("#### 🏆 Short-list proposée")
        medals = ["🥇", "🥈", "🥉"]
        pod = st.columns(3)
        for i, t in enumerate(scores.index[:3]):
            good, bad = strengths(t)
            with pod[i].container(border=True):
                st.markdown(f"### {medals[i]} {tag(t)}")
                st.caption(f"{D.FUNDS[t]['name']} · {D.FUNDS[t]['style']} · {table.loc[t, 'Verdict']}"
                           + (f" · SFDR {sfdr_label(t)}" if t in SFDR else ""))
                st.progress(int(round(scores.loc[t, "Score global"])), text=f"Score {scores.loc[t, 'Score global']:.0f} / 100")
                st.markdown(
                    f"**Points forts :** {', '.join(good) if good else '—'}  \n"
                    f"**Point de vigilance :** {', '.join(bad) if bad else 'aucun'}  \n"
                    f"Surperf. {fmt_pct(table.loc[t, 'Surperf. annualisée'])} · alpha {fmt_pct(table.loc[t, 'Alpha factoriel'])} · "
                    + (f"frais {fmt_num(table.loc[t, 'TER'])} %" if pd.notna(table.loc[t, "TER"]) else "frais n.d.")
                )

        # --- 4. Classement complet + radar --------------------------------------------------
        left, right = st.columns([3, 2])
        with left:
            mode = st.radio("Afficher", ["Notes (0–100)", "Valeurs réelles"], horizontal=True,
                            help="Notes : rang centile parmi les candidats éligibles (100 = meilleur). "
                                 "Valeurs réelles : les indicateurs bruts.")
            if mode.startswith("Notes"):
                show = scores.copy()
                show.index = [tag(t) for t in show.index]
                st.dataframe(
                    show, width="stretch",
                    column_config={
                        "Score global": st.column_config.ProgressColumn("Score global", min_value=0, max_value=100, format="%.0f"),
                        **{k: st.column_config.NumberColumn(k.split(" (")[0], format="%.0f", help=HELP.get(k.split(" (")[0]))
                           for k in show.columns if k not in ("Score global", "Rang")},
                    },
                )
            else:
                raw = elig_table.loc[scores.index, list(A.CRITERIA)].copy()
                raw.insert(0, "Score", scores["Score global"].round(0))
                raw.index = [tag(t) for t in raw.index]
                st.dataframe(style_metrics(raw.astype(float)), width="stretch",
                             column_config={c: st.column_config.Column(c, help=HELP.get(c)) for c in raw.columns})
        with right:
            fig = go.Figure()
            for t in scores.index[:3]:
                fig.add_scatterpolar(r=scores.loc[t, crit].tolist() + [scores.loc[t, crit[0]]],
                                     theta=[c.split(" (")[0] for c in crit] + [crit[0].split(" (")[0]],
                                     name=short(t), fill="toself", opacity=0.5)
            fig.update_layout(title="Profil des 3 premiers (notes 0–100)", height=420,
                              polar=dict(radialaxis=dict(range=[0, 100])),
                              margin=dict(t=70, b=40, l=80, r=80), legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig, width="stretch")

        # --- 5. Robustesse : le classement change-t-il selon le profil ? --------------------
        if EXPERT:
            st.markdown("#### 🔁 Le classement est-il robuste ?")
        robust = pd.DataFrame({name: A.score(elig_table, w)["Rang"] for name, w in A.PROFILES.items()})
        robust = robust.loc[scores.index]
        in_top3 = (robust <= 3).sum(axis=1)
        robust["Top 3"] = [f"{n} / {len(A.PROFILES)}" for n in in_top3]
        stable = [short(t) for t in robust.index if in_top3[t] == len(A.PROFILES)]
        if EXPERT:
            st.caption(
                "✅ " + ", ".join(stable) + f" reste{'nt' if len(stable) > 1 else ''} dans le top 3 quel que soit le profil : "
                 "choix robuste." if stable else
                 "⚠️ Aucun candidat n'est dans le top 3 pour tous les profils : le classement dépend fortement des pondérations."
            )
        robust.index = [tag(t) for t in robust.index]
        if EXPERT:
            st.dataframe(
                robust.style.map(lambda v: "background-color: #e6f4ea; font-weight: 600" if isinstance(v, (int, np.integer)) and v <= 3 else "",
                                 subset=list(A.PROFILES)),
                width="stretch",
            )
            st.caption("Rang de chaque candidat selon chaque profil de pondération (surligné = top 3).")

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xl:
            scores.rename(index=short).to_excel(xl, sheet_name="Scoring")
            elig_table.rename(index=short).to_excel(xl, sheet_name="Indicateurs")
            robust.to_excel(xl, sheet_name="Robustesse")
            pd.Series(weights, name="Poids").to_excel(xl, sheet_name="Pondérations")
            if reasons:
                pd.Series({short(t): r for t, r in reasons.items()}, name="Motif").to_excel(xl, sheet_name="Exclus")
            for t in scores.index[:3]:
                regs[t]["table"].to_excel(xl, sheet_name=f"Facteurs {short(t)}"[:31].replace("/", "-"))
        st.download_button("📥 Exporter l'analyse (Excel)", buf.getvalue(),
                           file_name=f"appel_offres_{seg_name.replace(' ', '_')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ======================================================================================
# 3 bis. Actif-passif : la Cades, la marge de couverture et la création de valeur
# ======================================================================================
@st.cache_data(show_spinner=False)
def value_creation_table(years, assets, data_version):
    """Par mandat FRR : rendement (en € couvert), indice, coût de la dette française, valeur créée en M€/an."""
    last = rets.index.max()
    start_ = last - pd.DateOffset(years=years)
    idx = rets.index[rets.index > start_]
    carry = ((fred["SOFR"] - fred["ESTR"]).resample("W-FRI").mean() / 100).reindex(idx).ffill().mean()
    oat = fred["OAT10"].dropna()
    debt = oat[oat.index > start_ - pd.DateOffset(months=1)].mean() / 100
    weight = A.FRR_LINES.set_index("Ligne")["Poids"]
    seg_weight = {"HY US": weight["High Yield US"], "HY Euro": weight["High Yield euro"], "Crédit Euro IG": weight["Crédit euro IG"]}
    rows = []
    for seg_name_, seg_ in D.SEGMENTS.items():
        bench_ = list(seg_["benchmarks"].values())[0]
        frr = [t for t, m in D.FUNDS.items() if m["segment"] == seg_name_ and m["style"] == "Gérant FRR"]
        aum = seg_weight[seg_name_] * assets * 1000 / len(frr)  # ponytail: encours réparti à parts égales entre mandats
        hedge = carry if seg_["currency"] == "USD" else 0.0  # coût de couverture USD → EUR ≈ SOFR − €STR
        rb = A.ann_return(rets.loc[idx, bench_].dropna()) - hedge
        for t in frr:
            r = A.ann_return(rets.loc[idx, t].dropna()) - hedge
            rows.append({"Gérant": short(t), "Segment": seg_name_, "Encours estimé (M€)": aum,
                         "Rdt annualisé (€)": r, "Indice (€)": rb, "Surperf.": r - rb,
                         "Valeur ajoutée vs indice (M€/an)": aum * (r - rb),
                         "Création de valeur vs dette (M€/an)": aum * (r - debt)})
    return pd.DataFrame(rows), debt, carry


with t_alm:
    st.markdown(
        "Depuis la réforme de 2010, le FRR ne reçoit plus d'argent : c'est lui qui en verse, chaque année, à la Cades "
        "(Caisse d'amortissement de la dette sociale), chargée de rembourser la dette de la Sécurité sociale. Il a versé "
        "2,1 Md€ par an de 2011 à 2024 et verse 1,45 Md€ par an de 2025 à 2033 (loi du 7 août 2020). Ce passif est connu "
        "d'avance, en montant comme en date. Les actifs de couverture servent à le payer sans surprise. Les actifs de "
        "performance doivent rapporter plus que ce que coûte la dette française, puisque chaque euro versé évite à l'État "
        "d'emprunter. La différence entre l'actif et la valeur actuelle des versements s'appelle la **marge de couverture "
        "du passif** : c'est le capital que le FRR peut se permettre d'exposer au risque."
    )

    alm_box = st.container()
    # --- passif et marge de couverture ---------------------------------------------------
    st.markdown("##### Passif Cades et marge de couverture (au 31/12/2025)")
    oat = fred["OAT10"].dropna()
    oat_2025, oat_now = oat.asof(pd.Timestamp("2025-12-31")), oat.iloc[-1]
    assets_bn, rate, after = 20.7, float(oat_2025) / 100, False
    if EXPERT:
        c = st.columns(3)
        assets_bn = c[0].number_input("Actif du FRR (Md€)", 5.0, 50.0, 20.7, 0.1,
                                      help="20,7 Md€ fin 2025 (rapport annuel 2025).")
        rate = c[1].number_input("Taux d'actualisation (%)", 0.0, 8.0, round(float(oat_2025), 2), 0.05,
                                 help=f"Coût de la dette française : OAT 10 ans à {fmt_num(oat_2025)} % fin 2025, "
                                      f"{fmt_num(oat_now)} % en {oat.index[-1]:%m/%Y} (FRED).") / 100
        after = c[2].toggle("Horizon prolongé après 2033", help="Hypothèse : ≈ 0,5 Md€/an versés à la sphère sociale de 2034 à 2040, "
                                                                "l'horizon du FRR ayant été prolongé au-delà de 2033.")
    flows = A.cades_flows(2025, after=0.5 if after else 0.0)
    pv, l_dur = A.liability_pv(flows, 2025, rate)
    a_dur = float((A.FRR_LINES["Poids"] * A.FRR_LINES["Sensi taux"]).sum())
    marge = assets_bn - pv
    hedge_pocket = A.FRR_LINES.loc[A.FRR_LINES["Poche"] == "Actifs de couverture", "Poids"].sum() * assets_bn
    k = st.columns(4)
    k[0].metric("Passif actualisé", f"{fmt_num(pv, 1)} Md€", f"{len(flows)} versements, {fmt_num(flows.sum(), 1)} Md€ nominal",
                delta_color="off", help="Somme des versements actualisés au taux choisi (versement en milieu d'année).")
    k[1].metric("Marge de couverture", f"{fmt_num(marge, 1)} Md€", "FRR publié : 10,3 Md€", delta_color="off",
                help="Actif − valeur actuelle du passif. L'écart avec le chiffre publié vient de la courbe de taux utilisée.")
    k[2].metric("Actif / passif", f"{fmt_num(assets_bn / pv, 2)}×", help="Actif / passif actualisé.")
    k[3].metric("Versements sécurisés", f"{fmt_num(hedge_pocket / A.CADES_PAYMENT, 1)} ans",
                f"{fmt_num(hedge_pocket, 1)} Md€ d'actifs de couverture", delta_color="off",
                help="Nombre d'années de versements à la Cades que la seule poche de couverture permet de payer.")
    left, right = st.columns([3, 2]) if EXPERT else (st.container(), None)
    with left:
        sched = pd.DataFrame({"Versement nominal": flows,
                              "Valeur actuelle": flows * (1 + rate) ** -(flows.index - 2025 - 0.5)})
        fig = go.Figure([go.Bar(x=sched.index, y=sched[col], name=col, marker_color=clr)
                         for col, clr in zip(sched.columns, ["#B4B3A8", "#14305a"], strict=True)])
        fig.update_layout(title="Échéancier des versements à la Cades (Md€)", barmode="group", height=320,
                          margin=dict(t=50, b=10), legend=dict(orientation="h", y=-0.15), separators=", ")
        st.plotly_chart(fig, width="stretch")
    if EXPERT:
        with right:
            st.markdown("**Sensibilité aux taux**")
            st.markdown(
                f"- Actif : **{fmt_num(a_dur)}** (somme pondérée des lignes ; FRR publié : 2,05)  \n"
                f"- Passif : **{fmt_num(l_dur)}** (FRR publié : 3,71)  \n"
                f"- Pour une baisse des taux de 100 pb, le passif augmente de {fmt_num(l_dur / 100 * pv * 1000, 0)} M€ et l'actif de "
                f"{fmt_num(a_dur / 100 * assets_bn * 1000, 0)} M€ : la marge varie de "
                f"**{(a_dur * assets_bn - l_dur * pv) * 10:+,.0f} M€**. L'actif, deux fois plus gros que le passif, compense "
                f"sa sensibilité plus faible ; le décalage se lit surtout sur les actifs de couverture."
            )
            st.caption("Le FRR a acheté 500 M€ de futures OAT en 2025 et porte les OAT à 10 % de l'allocation 2026 pour "
                       "allonger la duration de l'actif et réduire ce décalage.")

    # --- stress tests ---------------------------------------------------------------------
    st.markdown("##### Stress test : impact sur l'actif, le passif et la marge")
    SCEN = {"Correction actuelle (nov. 2026)": (-10, 80, 50), "Choc d'inflation type 2022": (-18, 250, 250),
            "Crise de crédit sévère (type 2008)": (-35, 800, -100), "Personnalisé": (-20, 200, 0)}
    scen = st.segmented_control("Scénario", list(SCEN), default=list(SCEN)[0], key="alm_scen") or list(SCEN)[0]
    e0, s0, r0 = SCEN[scen]
    eq, spread_bp, rate_bp = e0 / 100, s0, r0
    if EXPERT:
        c = st.columns(3)
        eq = c[0].slider("Actions (%)", -50, 20, e0, 1, key=f"eq_{scen}") / 100
        spread_bp = c[1].slider("Spreads High Yield (pb)", -200, 1000, s0, 10, key=f"sp_{scen}",
                                help="Choc appliqué au HY ; l'IG, la dette émergente et la dette privée en subissent une fraction.")
        rate_bp = c[2].slider("Taux (pb)", -200, 300, r0, 10, key=f"rt_{scen}")
    st_tab, d_a, d_l = A.stress_test(A.FRR_LINES, assets_bn, eq, spread_bp, rate_bp, pv, l_dur)
    k = st.columns(3)
    k[0].metric("Variation de l'actif", f"{fmt_num(d_a, 2)} Md€", f"{fmt_pct(d_a / assets_bn, 1)}", delta_color="off")
    k[1].metric("Variation du passif", f"{fmt_num(d_l, 2)} Md€", f"{fmt_pct(d_l / pv, 1)}", delta_color="off")
    new_m = marge + d_a - d_l
    en_clair(alm_box, f"Le FRR doit encore verser **{fmt_num(flows.sum(), 1)} Md€ à la Cades** d'ici "
                      f"{flows.index[-1]}, soit 1,45 Md€ par an. En euros d'aujourd'hui, cette dette vaut "
                      f"{fmt_num(pv, 1)} Md€. Le FRR possède {fmt_num(assets_bn, 1)} Md€ : il lui reste donc un **matelas "
                      f"de {fmt_num(marge, 1)} Md€** au-delà de ce qu'il doit, qu'il peut investir pour faire mieux que "
                      f"le coût de la dette française. Dans le scénario « {scen} », ce matelas passerait à "
                      f"{fmt_num(new_m, 1)} Md€.")
    k[2].metric("Marge de couverture après choc", f"{fmt_num(new_m, 1)} Md€", f"{fmt_num(new_m - marge, 2)} Md€",
                help="Si la marge devenait négative, l'actif ne suffirait plus à honorer les versements à la Cades.")
    show = (st_tab.groupby("Poche", sort=False)[["Montant (Md€)", "Impact (Md€)"]].sum()
            .assign(**{"Choc (%)": lambda x: x["Impact (Md€)"] / x["Montant (Md€)"]}))
    with st.expander("Détail par ligne et hypothèses de sensibilité"):
        st.dataframe(st_tab.set_index("Ligne")[["Poche", "Montant (Md€)", "Bêta actions", "Sensi taux", "Sensi spread",
                                                 "Mult. spread", "Choc (%)", "Impact (Md€)"]]
                     .style.format({"Montant (Md€)": "{:.2f}", "Bêta actions": "{:.1f}", "Sensi taux": "{:.1f}",
                                    "Sensi spread": "{:.1f}", "Mult. spread": "{:.1f}", "Choc (%)": "{:+.1%}",
                                    "Impact (Md€)": "{:+.2f}"}, decimal=",", thousands=" "), width="stretch")
        st.caption("Hypothèses simplifiées : le non coté reflète partiellement le choc actions (valorisations lissées), les "
                   "actions couvertes en options en subissent la moitié (put spread), la dette émergente 80 % du choc HY, "
                   "l'IG 40 %. Change supposé couvert (90 %) ; corrélations non modélisées.")
    st.dataframe(show.style.format({"Montant (Md€)": "{:.2f}", "Impact (Md€)": "{:+.2f}", "Choc (%)": "{:+.1%}"},
                                   decimal=",", thousands=" "), width="stretch")

    # --- vue par poche ----------------------------------------------------------------------
    st.markdown("##### Les trois poches : portefeuille, allocation 2026 et mandats")
    lines = A.FRR_LINES.assign(**{"Montant (Md€)": A.FRR_LINES["Poids"] * assets_bn})
    in_tool = {"High Yield euro": "✅ HY Euro", "High Yield US": "✅ HY US", "Crédit euro IG": "✅ Crédit Euro IG"}
    lines["Suivi dans l'outil"] = lines["Ligne"].map(in_tool).fillna("")
    poche = lines.groupby("Poche", sort=False)["Poids"].sum().to_frame("Fin 2025")
    poche["Cible 2026"] = pd.Series(A.FRR_TARGET_2026)
    poche["Écart (pts)"] = (poche["Fin 2025"] - poche["Cible 2026"]) * 100
    poche["À ajuster via futures (M€)"] = -poche["Écart (pts)"] / 100 * assets_bn * 1000
    poche["Rôle face au passif"] = ["Battre le coût de la dette à long terme", "Portage (rendement) à risque de perte limité",
                                    "Sécuriser les versements à la Cades"]
    st.dataframe(poche.style.format({"Fin 2025": "{:.1%}", "Cible 2026": "{:.1%}", "Écart (pts)": "{:+.1f}",
                                     "À ajuster via futures (M€)": "{:+,.0f}"}, decimal=",", thousands=" "), width="stretch")
    if EXPERT:
        st.dataframe(lines.set_index("Ligne")[["Poche", "Poids", "Montant (Md€)", "Gestion", "Suivi dans l'outil"]]
                     .style.format({"Poids": "{:.1%}", "Montant (Md€)": "{:.2f}"}, decimal=",", thousands=" "), width="stretch")
    st.caption("Expositions fin 2025, dérivés inclus (rapport annuel 2025) ; allocation stratégique 2026 votée le 4/6/2026 "
               "(actions couvertes en options 4 → 8 %, OAT 10 %, crédit de qualité −3 pts). Les écarts se comblent par les "
               "futures du mandat overlay (onglet *Protection actions*).")

    # --- création de valeur vs coût de la dette --------------------------------------------
    st.markdown("##### Création de valeur des mandats crédit vs coût de la dette française")
    st.caption("Le FRR mesure sa performance par rapport au coût de la dette française : 15,6 Md€ de valeur créée depuis "
               "2010, dont 1,5 Md€ en 2025. Le tableau applique le même calcul à chaque mandat crédit.")
    yrs = st.radio("Période", [1, 3], index=1, horizontal=True, format_func=lambda y: f"{y} an{'s' if y > 1 else ''}", key="vc_years")
    vc, debt, carry = value_creation_table(yrs, assets_bn, DATA_VERSION)
    k = st.columns(3)
    k[0].metric("Coût de la dette (OAT 10 ans moyen)", fmt_pct(debt, 2))
    k[1].metric("Valeur créée vs dette, 14 mandats", f"{fmt_num(vc['Création de valeur vs dette (M€/an)'].sum(), 0)} M€/an")
    k[2].metric("Valeur ajoutée des gérants vs indices", f"{fmt_num(vc['Valeur ajoutée vs indice (M€/an)'].sum(), 0)} M€/an",
                help="Partie de la création de valeur due aux choix des gérants (le reste vient du marché du crédit).")
    if EXPERT:
        st.dataframe(vc.style.format({"Encours estimé (M€)": "{:,.0f}", "Rdt annualisé (€)": "{:.2%}", "Indice (€)": "{:.2%}",
                                      "Surperf.": "{:+.2%}", "Valeur ajoutée vs indice (M€/an)": "{:+,.1f}",
                                      "Création de valeur vs dette (M€/an)": "{:+,.1f}"}, decimal=",", thousands=" ")
                     .background_gradient(subset=["Création de valeur vs dette (M€/an)"], cmap="RdYlGn", vmin=-40, vmax=40),
                     width="stretch", hide_index=True)
    st.caption(f"Lecture : création de valeur = encours × (rendement − coût de la dette) ; elle se décompose en une part due au "
               f"marché (indice − dette) et une part due au gérant (surperformance). HY US converti en € couvert en retranchant le coût de "
               f"couverture SOFR − €STR ({fmt_pct(carry, 2)}/an). Encours estimé : poids du segment fin 2025 réparti à parts "
               f"égales entre mandats ; fonds proxies, nets de frais.")

# ======================================================================================
# 4. Overlay change
# ======================================================================================
with t_fx:
    st.markdown(
        "D'après le rapport annuel 2025, le FRR couvre 90 % de ses actifs de performance en devises développées et 100 % "
        "de ses actifs de couverture. Il ne couvre pas les devises émergentes. Son exposition totale au change doit rester "
        "**sous 20 % de l'actif** (16,9 % fin 2025). La couverture est confiée au mandat overlay « gestion passive du risque "
        "de change », tenu par Mercer avec Mesirow, soit environ 4 Md€ de contrats à terme."
    )
    fx_box = st.container()
    FX = {"USD": ("EURUSD=X", "SOFR", "^GSPC"), "JPY": ("EURJPY=X", "JPY3M", "^N225"),
          "GBP": ("EURGBP=X", "SONIA", "^FTSE"), "CHF": ("EURCHF=X", "CHF3M", "^SSMI")}
    default_book = pd.DataFrame(
        {"Exposition (M€)": [4700, 600, 400, 300], "Cible": [0.90, 0.90, 0.90, 0.90],
         "Hypothèse": ["HY $ (8,6 %) + actions US et couvertes en options", "mandats actions japonaises + indiciel",
                       "actions européennes hors zone euro", "actions européennes hors zone euro"]},
        index=list(FX))
    with st.expander("⚙️ Expositions par devise et paramètres (hypothèses modifiables)", expanded=False):
        st.caption("Estimations à partir de l'allocation fin 2025 (rapport annuel) appliquée à 20,7 Md€ : le FRR ne publie "
                   "pas sa répartition par devise. Modifiez les montants pour tester d'autres hypothèses.")
        book = st.data_editor(
            default_book, width="stretch", key="fx_book",
            column_config={"Exposition (M€)": st.column_config.NumberColumn(min_value=0, step=100),
                           "Cible": st.column_config.NumberColumn("Ratio cible", min_value=0.0, max_value=1.0, step=0.05, format="%.0f%%"),
                           "Hypothèse": st.column_config.TextColumn(disabled=True)},
        )
        c = st.columns(4)
        total_assets = c[0].number_input("Actif total du FRR (M€)", 1000, 50000, 20700, 100)
        em_unhedged = c[1].number_input("Devises émergentes, non couvertes (M€)", 0, 10000, 2000, 100,
                                        help="Actions émergentes (6,2 %) + part en devises locales de la dette émergente (≈ la moitié de 7 %).")
        freq_lab = c[2].selectbox("Réajustement", ["Mensuel", "Trimestriel", "Hebdomadaire"])
        band = c[3].slider("Tolérance (±)", 0.5, 5.0, 2.0, 0.5, format="%.1f %%") / 100
    freq = {"Mensuel": "M", "Trimestriel": "Q", "Hebdomadaire": "W"}[freq_lab]

    sims, rows = {}, []
    for ccy, (fx_t, rate_k, idx_t) in FX.items():
        hs = A.fx_hedge_simulation(levels[idx_t], levels[fx_t], fred[rate_k], fred["ESTR"],
                                   float(book.loc[ccy, "Cible"]), freq)
        hs = hs.loc[hs.index > start]
        sims[ccy] = hs
        expo = float(book.loc[ccy, "Exposition (M€)"])
        ratio, dev = hs["ratio"].iloc[-1], hs["deviation"].iloc[-1]
        pnl = (hs["hedged_eur"].iloc[-1] / hs["hedged_eur"].iloc[0] - hs["unhedged_eur"].iloc[-1] / hs["unhedged_eur"].iloc[0]) * expo
        rows.append({"Devise": ccy, "Exposition (M€)": expo, "Ratio cible": float(book.loc[ccy, "Cible"]),
                     "Ratio actuel": ratio, "Écart (pts)": dev * 100,
                     "À ajuster (M€)": -dev * expo, "Non couvert (M€)": (1 - ratio) * expo,
                     "Gain/coût couverture (M€)": pnl,
                     "Statut": "✅ dans la bande" if abs(dev) <= band else ("⚠️ sous-couvert" if dev < 0 else "⚠️ sur-couvert")})
    fxt = pd.DataFrame(rows).set_index("Devise")
    unhedged = fxt["Non couvert (M€)"].sum() + em_unhedged
    share = unhedged / total_assets
    en_clair(fx_box, f"Quand le dollar ou le yen baisse, les placements du FRR dans ces devises perdent de la valeur en "
                     f"euros. Le FRR se protège en couvrant 90 % de ces placements. Ce qui reste exposé représente environ "
                     f"**{fmt_pct(share, 0)} de l'actif**, sous la limite légale de 20 %. "
                     + ("Toutes les devises sont couvertes au bon niveau." if (fxt["Statut"].str.startswith("✅")).all() else
                        "Certaines devises s'écartent du niveau visé : l'encadré orange indique quoi acheter ou vendre."))

    # --- message clé et limite réglementaire --------------------------------------------
    alerts = fxt[~fxt["Statut"].str.startswith("✅")]
    k = st.columns(4)
    k[0].metric("Exposition de change totale", fmt_pct(share, 1), f"limite {fmt_pct(A.FX_LIMIT, 0)}",
                delta_color="off", help="Part non couverte des devises développées + devises émergentes, rapportée à l'actif total.")
    k[1].metric("Marge sous la limite", f"{fmt_num((A.FX_LIMIT - share) * total_assets, 0)} M€",
                help="Montant d'exposition supplémentaire possible avant d'atteindre 20 % de l'actif.")
    k[2].metric("Devises hors bande", f"{len(alerts)} / {len(fxt)}", ", ".join(alerts.index) or "aucune", delta_color="off")
    k[3].metric("Gain/coût de la couverture sur la période", f"{fmt_num(fxt['Gain/coût couverture (M€)'].sum(), 0)} M€",
                help="Résultat de la couverture vs portefeuille non couvert (effet change + portage des forwards).")
    st.progress(min(share / A.FX_LIMIT, 1.0), text=f"Utilisation de la limite réglementaire : {fmt_pct(share / A.FX_LIMIT, 0)}")
    st.caption("Le FRR publiait 16,9 % fin 2025 : l'écart avec cette estimation vient du périmètre (non coté, OPC, devises "
               "émergentes plus larges, positions tactiques) que ces hypothèses ne captent pas.")
    if len(alerts):
        st.warning("**Action :** " + " · ".join(
            f"{ccy} : {'vendre' if r['À ajuster (M€)'] > 0 else 'racheter'} ≈ {fmt_num(abs(r['À ajuster (M€)']), 0)} M€ de {ccy} à terme"
            for ccy, r in alerts.iterrows()))
    else:
        st.success(f"✅ Toutes les devises sont dans la bande de tolérance (±{fmt_pct(band, 1)}) : aucune action requise.")

    if EXPERT:
        st.dataframe(
            fxt.style.format({"Exposition (M€)": "{:,.0f}", "Ratio cible": "{:.0%}", "Ratio actuel": "{:.1%}", "Écart (pts)": "{:+.1f}",
                              "À ajuster (M€)": "{:+,.0f}", "Non couvert (M€)": "{:,.0f}", "Gain/coût couverture (M€)": "{:+,.0f}"},
                             decimal=",", thousands=" "),
            width="stretch",
            column_config={"À ajuster (M€)": st.column_config.Column(help="Positif = vendre des devises à terme (sous-couverture)."),
                           "Gain/coût couverture (M€)": st.column_config.Column(help="Sur la période d'analyse choisie dans la barre latérale.")},
        )

        left, right = st.columns(2)
        with left:
            fig = go.Figure()
            fig.add_hrect(y0=-band * 100, y1=band * 100, fillcolor="green", opacity=0.08, line_width=0)
            for i, (ccy, hs) in enumerate(sims.items()):
                fig.add_scatter(x=hs.index, y=hs["deviation"] * 100, name=ccy, line=dict(width=1.5, color=COLORS[i]))
            fig.add_hline(y=0, line_dash="dot")
            fig.update_layout(title="Écart au ratio cible par devise (pts, zone verte = tolérance)", height=360,
                              margin=dict(t=50, b=10), legend=dict(orientation="h", y=-0.15), hovermode="x unified")
            st.plotly_chart(fig, width="stretch")
        with right:
            cost = fxt["Gain/coût couverture (M€)"]
            fig = go.Figure(go.Bar(x=cost.index, y=cost.values, marker_color=np.where(cost >= 0, "#2a9d8f", "#e76f51"),
                                   text=[f"{fmt_num(v, 0)} M€" for v in cost], textposition="outside"))
            fig.update_layout(title="Gain / coût de la couverture par devise sur la période (M€)", height=360, margin=dict(t=50, b=10))
            st.plotly_chart(fig, width="stretch")

        episodes = pd.concat({ccy: A.breach_episodes(hs["deviation"], band) for ccy, hs in sims.items()}, names=["Devise"])
        if len(episodes):
            with st.expander(f"Journal des dépassements ({len(episodes)} épisodes)"):
                st.dataframe(episodes.reset_index(level=0).sort_values("Début", ascending=False)
                             .style.format({"Début": "{:%d/%m/%Y}", "Fin": "{:%d/%m/%Y}", "Écart max": "{:+.2%}"}),
                             width="stretch", hide_index=True)
    st.caption("Simulation : actifs en devise représentés par un indice local (S&P 500, Nikkei, FTSE, SMI), forwards valorisés "
               "par différentiel de taux courts (€STR vs SOFR, SONIA, taux 3 mois JPY/CHF), réajustement au dernier jour ouvré "
               "de chaque période. Les expositions par devise sont des hypothèses.")

# ======================================================================================
# 5. Overlay options — protection actions et reporting hebdomadaire
# ======================================================================================
with t_der:
    st.markdown(
        "Les actions couvertes par des options représentaient 7,6 % du portefeuille du FRR fin 2025, et l'allocation 2026 "
        "les porte à 8 %. Le mandat overlay « gestion passive des expositions » (Amundi et BNP Paribas AM) gère environ "
        "1 Md€ de notionnels. Il s'agit d'une assurance contre la baisse des actions de la zone euro et des États-Unis, qui "
        "a coûté 43,3 M€ en 2025. La simulation ci-dessous renouvelle un *put spread* à chaque échéance."
    )
    UNDERLYINGS = {"Euro Stoxx 50": ("^STOXX50E", "ESTR"), "S&P 500": ("^GSPC", "SOFR")}

    with st.expander("⚙️ Paramètres de la stratégie", expanded=False):
        c = st.columns(7)
        idx_name = c[0].selectbox("Sous-jacent", list(UNDERLYINGS))
        notional = c[1].number_input("Montant protégé (M€)", 50, 5000, 1000, 50)
        k_long = c[2].slider("Protection à partir de", 80, 100, 95, 1, format="%d %%",
                             help="Strike du put acheté, en % du niveau de l'indice à l'ouverture.") / 100
        kl = int(round(k_long * 100))
        k_short = c[3].slider("Protection jusqu'à", 50, kl - 1, min(85, kl - 1), 1, format="%d %%",
                              help="Strike du put vendu : en dessous, la protection ne joue plus.") / 100
        mat_m = c[4].selectbox("Durée", [1, 3, 6, 12], index=1, format_func=lambda x: f"{x} mois")
        vol_prem = c[5].slider("Prime de vol (pts)", 0, 10, 3,
                               help="Écart supposé entre volatilité implicite et volatilité réalisée 1 mois.") / 100
        q = c[6].slider("Rendement dividende", 0.0, 5.0, 3.0, 0.5, format="%.1f %%") / 100
    idx_t, rate_k = UNDERLYINGS[idx_name]
    spot_s = levels[idx_t].dropna()
    estr = fred[rate_k].reindex(spot_s.index).ffill() / 100  # taux court de la devise du sous-jacent
    rv = spot_s.pct_change().rolling(21).std() * np.sqrt(252)

    # --- backtest hebdomadaire sur 1 an ----------------------------------------------
    weekly = spot_s.resample("W-FRI").last().loc[lambda s_: s_.index > last - pd.DateOffset(years=1)]
    rep, pos, premiums = A.put_spread_backtest(spot_s, estr, rv + vol_prem, weekly.index, notional,
                                               k_long, k_short, mat_m, q)

    # --- position courante et prix d'une protection neuve ----------------------------
    S_now, r_now = spot_s.iloc[-1], estr.iloc[-1]
    T_now = max((pos["expiry"] - spot_s.index[-1]).days, 1) / 365
    sig_now = rv.iloc[-1] + vol_prem
    g_now = A.put_spread(S_now, pos["K1"], pos["K2"], T_now, r_now, q, sig_now)
    u = pos["units"]
    new = A.put_spread(S_now, k_long * S_now, k_short * S_now, mat_m / 12, r_now, q, sig_now)
    prem_pct = new["price"] / S_now
    max_pay = (k_long - k_short) * notional

    en_clair(st, f"Le FRR paie une sorte d'assurance contre la baisse de la bourse. Une protection achetée aujourd'hui "
                 f"couvrirait **{fmt_num(notional, 0)} M€** d'actions si l'indice baisse de {(1 - k_long) * 100:.0f} % à "
                 f"{(1 - k_short) * 100:.0f} % (entre {fmt_num(k_long * S_now, 0)} et {fmt_num(k_short * S_now, 0)} points). "
                 f"Elle coûte **{fmt_num(prem_pct * notional, 1)} M€** pour {mat_m} mois, soit {fmt_pct(prem_pct, 2)} du "
                 f"montant protégé, et rembourse au maximum **{fmt_num(max_pay, 0)} M€** si l'indice finit sous "
                 f"{fmt_num(k_short * S_now, 0)}.")

    # --- carte « cette semaine » -------------------------------------------------------
    last_row = rep.iloc[-1]
    days_left = (pos["expiry"] - spot_s.index[-1]).days
    cushion = S_now / pos["K1"] - 1
    st.markdown("##### Cette semaine")
    k = st.columns(4)
    k[0].metric("P&L de la semaine", f"{last_row['P&L semaine (M€)']:+.1f} M€",
                help="Variation de valeur de la protection depuis vendredi dernier.")
    k[1].metric("P&L cumulé sur 12 mois", f"{last_row['P&L cumulé (M€)']:+.1f} M€",
                f"primes payées : {premiums / 1e6:.1f} M€", delta_color="off",
                help="Coût net de l'assurance sur l'année : primes payées moins indemnisations et valeur restante.")
    k[2].metric("Indice vs seuil de protection", f"{cushion:+.1%}",
                "la protection joue" if cushion < 0 else "protection pas encore active", delta_color="off",
                help=f"Écart entre le niveau actuel de l'indice ({S_now:,.0f}) et le strike du put acheté ({pos['K1']:,.0f}).")
    k[3].metric("Prochain renouvellement", f"{pos['expiry']:%d/%m/%Y}", f"dans {days_left} jours", delta_color="off")

    # --- scénarios de marché ----------------------------------------------------------
    left, right = st.columns([2, 3])
    with left:
        st.markdown("##### Que se passe-t-il si l'indice baisse demain ?")
        shocks = [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05]
        scen = []
        for sh in shocks:
            v = A.put_spread(S_now * (1 + sh), pos["K1"], pos["K2"], T_now, r_now, q, sig_now)["price"] * u / 1e6
            gain = v - g_now["price"] * u / 1e6
            loss = notional * sh
            scen.append({"Choc": f"{sh:+.0%}", "Actions": loss, "Protection": gain,
                         "Net": loss + gain, "Compensé": f"{-gain / loss:.0%}" if loss < 0 else "–"})
        scen = pd.DataFrame(scen).set_index("Choc")
        st.dataframe(
            scen.style.format({"Actions": "{:+,.0f}", "Protection": "{:+,.0f}", "Net": "{:+,.0f}"})
            .map(lambda v: "color: #1a7f37; font-weight: 600" if isinstance(v, float) and v > 0 else "", subset=["Protection"]),
            width="stretch",
            column_config={
                "Actions": st.column_config.Column("Actions (M€)", help="Variation de valeur des actions protégées."),
                "Protection": st.column_config.Column("Protection (M€)", help="Gain ou perte immédiat du put spread."),
                "Net": st.column_config.Column("Net (M€)", help="Résultat du portefeuille actions + protection."),
                "Compensé": st.column_config.Column("Compensé", help="Part de la perte actions absorbée par la protection."),
            },
        )
        st.caption(f"Choc instantané sur {notional:,.0f} M€ d'actions, protection en vie valorisée à volatilité inchangée.".replace(",", " "))
    with right:
        grid = np.linspace(0.7 * S_now, 1.15 * S_now, 121)
        at_exp = (np.maximum(pos["K1"] - grid, 0) - np.maximum(pos["K2"] - grid, 0)) * u / 1e6
        today = A.put_spread(grid, pos["K1"], pos["K2"], T_now, r_now, q, sig_now)["price"] * u / 1e6
        fig = go.Figure()
        fig.add_vrect(x0=pos["K2"], x1=pos["K1"], fillcolor="#2a9d8f", opacity=0.08, line_width=0,
                      annotation_text="zone protégée", annotation_position="top left")
        fig.add_scatter(x=grid, y=at_exp, name="À l'échéance", line=dict(color="#1f5fa8"))
        fig.add_scatter(x=grid, y=today, name="Aujourd'hui", line=dict(dash="dash", color="#9aa5b1"))
        fig.add_vline(x=S_now, line_dash="dot", annotation_text="niveau actuel")
        fig.update_layout(title="Indemnisation selon le niveau de l'indice (M€)", height=360,
                          margin=dict(t=50, b=10), xaxis_title=idx_name, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, width="stretch")

    # --- reporting hebdomadaire --------------------------------------------------------
    if EXPERT:
        st.markdown("##### Reporting hebdomadaire")
        left, right = st.columns([2, 3])
        with left:
            fig = go.Figure()
            fig.add_bar(x=rep.index, y=rep["P&L semaine (M€)"], name="P&L semaine",
                        marker_color=np.where(rep["P&L semaine (M€)"] >= 0, "#2a9d8f", "#e76f51"))
            fig.add_scatter(x=rep.index, y=rep["P&L cumulé (M€)"], name="P&L cumulé", line=dict(color="black"))
            fig.update_layout(title="P&L sur 12 mois (M€)", height=330, margin=dict(t=50, b=10),
                              legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig, width="stretch")
        with right:
            n_show = st.radio("Afficher", ["8 dernières semaines", "12 mois"], horizontal=True, label_visibility="collapsed")
            view = rep.sort_index(ascending=False)
            view = view.head(8) if n_show.startswith("8") else view
            view = view.copy()
            view.index = view.index.strftime("%d/%m/%Y")
            st.dataframe(
                view.style.format({"Indice": "{:,.0f}", "Valeur (M€)": "{:.1f}", "Delta (M€)": "{:+.0f}",
                                   "P&L semaine (M€)": "{:+.1f}", "P&L cumulé (M€)": "{:+.1f}"}, na_rep=""),
                width="stretch", height="auto" if n_show.startswith("8") else 360,
            )
            st.download_button("📥 Exporter le reporting (CSV)", rep.to_csv().encode("utf-8-sig"), "reporting_options.csv", "text/csv")

        with st.expander("🔬 Grecques de la position en vie (pour spécialistes)"):
            k = st.columns(4)
            k[0].metric("Delta", f"{g_now['delta'] * u * S_now / 1e6:,.0f} M€", f"{g_now['delta']:.1%} du notionnel", delta_color="off",
                        help="Exposition actions équivalente de la protection : variation de valeur pour une variation de l'indice.")
            k[1].metric("Gamma (1 %)", f"{g_now['gamma'] * u * S_now ** 2 / 100 / 1e6:,.1f} M€",
                        help="Variation du delta pour un mouvement de 1 % de l'indice.")
            k[2].metric("Vega (1 pt)", f"{g_now['vega'] * u / 1e6:.2f} M€", help="Variation de valeur pour +1 point de volatilité.")
            k[3].metric("Theta (1 jour)", f"{g_now['theta'] * u / 1e3:,.0f} k€", help="Perte de valeur liée au passage du temps, par jour.")
            st.caption("Valorisation Black-Scholes ; volatilité implicite approchée par la volatilité réalisée 1 mois + prime de vol.")

# ======================================================================================
# 6. Méthodologie
# ======================================================================================
with t_meth:
    methode.render(st)
