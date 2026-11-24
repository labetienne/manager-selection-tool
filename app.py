"""Manager Selection Tool – Crédit Euro & High Yield US

Analyse des gérants délégués du FRR (performance, facteurs, risques) et préparation des appels d'offres
sur les mandats crédit euro et High Yield US.

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
        "Ce prototype analyse les sociétés de gestion à qui le FRR confie ses mandats crédit (crédit euro et High "
        "Yield US), et prépare les appels d'offres sur ces segments. Il répond à deux questions : **les gérants "
        "actuels font-ils bien leur travail ?** (mission 2 du stage) et **qui retenir au prochain appel d'offres ?** "
        "(mission 5).  \n"
        "*Les mandats du FRR sont dédiés et non publics : chaque gérant est donc représenté par un fonds ouvert qu'il "
        "gère avec la même stratégie.*"
    )
    s1, s2, s3 = st.columns(3)
    s1.markdown("**① Les gérants font-ils bien leur travail ?**  \nOnglets *Classement des gérants* et *Fiche gérant* : "
                "performance, risques, et part due au talent du gérant.")
    s2.markdown("**② Qui retenir au prochain appel d'offres ?**  \nOnglet *Appel d'offres* : l'outil note les "
                "candidats et propose un podium.")
    s3.markdown("**③ Comment c'est calculé ?**  \nOnglet *Méthode et formules* : chaque indicateur expliqué, "
                "les hypothèses et les limites.")
    st.caption("Chaque onglet commence par un encadré « En clair ». La vue détaillée (barre de gauche) affiche tous les "
               "chiffres techniques. Survolez les ⓘ pour les définitions. "
               "Chiffres FRR : rapport annuel 2025 et publications de fondsdereserve.fr.")

t_synth, t_ger, t_ao, t_meth = st.tabs(
    ["🏁 Classement des gérants", "🔍 Fiche gérant", "🏆 Appel d'offres", "📘 Méthode et formules"])


def en_clair(where, text):
    where.info("💡 **En clair**  \n" + text)

# ======================================================================================
# 1. Classement des gérants (mission 2)
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
# 2. Fiche gérant (mission 2)
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
# 3. Appel d'offres (mission 5)
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
# 4. Méthode et formules
# ======================================================================================
with t_meth:
    methode.render(st)
