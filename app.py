"""Manager Selection Tool – Crédit Euro & High Yield US

Prototype d'outil de sélection et de suivi de gérants délégués :
performance vs benchmark, analyse factorielle (création de valeur), grille de scoring
d'appel d'offres, overlay de change EUR/USD et reporting d'un put spread actions.

Lancer :  .venv/bin/streamlit run app.py
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analytics as A
import data as D
from report import build_fiche

st.set_page_config(page_title="Manager Selection Tool", page_icon="📊", layout="wide")

PCT_COLS = {
    "Rdt annualisé", "Rdt benchmark", "Surperf. annualisée", "Volatilité", "Tracking error",
    "Alpha (Jensen)", "Max drawdown", "Up capture", "Down capture", "% semaines surperf.",
    "Alpha factoriel",
}
COLORS = px.colors.qualitative.Safe


def fmt_pct(x, d=2):
    return "–" if pd.isna(x) else f"{x * 100:.{d}f} %"


def style_metrics(df: pd.DataFrame):
    fmt = {c: "{:.2%}" for c in df.columns if c in PCT_COLS}
    fmt.update({c: "{:.2f}" for c in ["Sharpe", "Sortino", "Information ratio", "Bêta", "Corrélation", "Alpha t-stat", "R²"] if c in df})
    fmt.update({"TER": "{:.2f} %", "Encours (Md$)": "{:.1f}", "Nb semaines": "{:.0f}", "Score": "{:.0f}"})
    return df.style.format({k: v for k, v in fmt.items() if k in df.columns}, na_rep="–")


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
                       "C'est la vraie valeur ajoutée du gérant.",
    "Alpha t-stat": "Fiabilité statistique de l'alpha. |t| ≥ 2 : alpha significatif ; sinon il peut relever du hasard.",
    "Bêta": "Sensibilité au benchmark. 1 = bouge comme l'indice ; < 1 = plus défensif.",
    "Max drawdown": "Pire baisse subie entre un plus haut et un plus bas sur la période.",
    "Up capture": "Part des hausses de l'indice captée par le fonds. > 100 % = fait mieux que l'indice quand il monte.",
    "Down capture": "Part des baisses de l'indice subie par le fonds. < 100 % = protège mieux que l'indice quand il baisse.",
    "TER": "Frais annuels totaux du fonds (en % de l'encours).",
    "Encours (Md$)": "Taille du fonds, en milliards.",
}


def short(t: str) -> str:
    """Nom lisible d'un fonds (ticker en secours)."""
    return D.FUNDS[t]["short"] if t in D.FUNDS else t


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


# ======================================================================================
# Données
# ======================================================================================
@st.cache_data(show_spinner="Chargement des données de marché…")
def get_data(refresh_token: int):
    d = D.load_data(refresh=refresh_token > 0)
    levels = D.build_levels(d)
    rets = A.weekly_returns(levels)
    return d, levels, rets


if "refresh" not in st.session_state:
    st.session_state.refresh = 0

data, levels, rets = get_data(st.session_state.refresh)
fred = data["fred"]
info = data["info"]

# ======================================================================================
# Barre latérale
# ======================================================================================
with st.sidebar:
    st.title("📊 Manager Selection")
    st.caption("Prototype de sélection et de suivi de gérants délégués")

    seg_name = st.radio("Segment (appel d'offres)", list(D.SEGMENTS), index=0)
    seg = D.SEGMENTS[seg_name]
    bench_label = st.selectbox("Benchmark", list(seg["benchmarks"]))
    bench = seg["benchmarks"][bench_label]

    seg_funds = [t for t, m in D.FUNDS.items() if m["segment"] == seg_name and t != bench]
    off_style = [t for t in seg_funds if D.FUNDS[t].get("off_style")]
    include_off = False
    if off_style:
        include_off = st.checkbox(
            "Inclure les fonds hors style",
            value=False,
            help="Fonds dont la stratégie ne correspond pas au mandat : "
            + " ; ".join(f"{short(t)} ({D.FUNDS[t]['off_style']})" for t in off_style),
        )
    candidates = [t for t in seg_funds if include_off or t not in off_style]
    selected = st.multiselect(
        "Gérants / fonds candidats",
        candidates,
        default=candidates,
        format_func=short,
    )

    first = rets[bench].first_valid_index()
    last = rets.index.max()
    horizon = st.select_slider("Horizon d'analyse", ["1 an", "2 ans", "3 ans", "5 ans", "Max"], value="3 ans")
    years = {"1 an": 1, "2 ans": 2, "3 ans": 3, "5 ans": 5, "Max": 50}[horizon]
    start = max(first, last - pd.DateOffset(years=years))
    st.caption(f"Période : {start:%d/%m/%Y} → {last:%d/%m/%Y}  ·  devise {seg['currency']}")
    if bench.startswith("ICE"):
        st.caption("ℹ️ Les indices ICE BofA ne sont diffusés gratuitement par FRED que sur ~3 ans.")

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
def segment_table(seg_name, bench, start, selected, refresh_token):
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
        rows[t] = m
        regs[t] = fr
    return pd.DataFrame(rows).T.astype(float), regs


table, regs = segment_table(seg_name, bench, start, tuple(selected), st.session_state.refresh)
if table.empty:
    st.error("Historique insuffisant sur la période choisie.")
    st.stop()

@st.cache_data(show_spinner="Génération de la fiche PDF…")
def fiche_pdf(f, seg_name, bench, start, refresh_token, badge, why, level, synthesis):
    """Fiche gérant PDF, mise en cache par gérant / segment / période."""
    return build_fiche(
        ticker=f, meta=D.FUNDS[f], m=table.loc[f], fr=regs[f], pair=R[[f, bench]],
        bench_col=bench, bench_label=bench_label, seg_name=seg_name, currency=seg["currency"],
        rf_ann=A.ann_return(rf.dropna()), badge=badge, why=why, level=level,
        synthesis=synthesis, asof=data["asof"],
    )


label = lambda t: f"{D.FUNDS[t]['short']} — {D.FUNDS[t]['name']}" if t in D.FUNDS else bench_label
table["Verdict"] = [verdict(table.loc[t])[0] for t in table.index]

st.title(f"Sélection de gérants — {seg_name}")
st.caption(
    f"Benchmark : **{bench_label}** · {len(table)} candidats · rendements hebdomadaires "
    f"en {seg['currency']}, total return (dividendes réinvestis), nets de frais"
)

with st.expander("ℹ️ À quoi sert cet outil ? — mode d'emploi en 3 étapes", expanded=True):
    st.markdown(
        "Cet outil évalue **les gérants actuels du FRR** sur les segments Crédit Euro (IG et haut rendement) "
        "et High Yield US, en vue des appels d'offres 2027. Il les compare à leur indice et à une alternative "
        "passive (ETF), et identifie ceux qui **créent réellement de la valeur**, c'est-à-dire au-delà de ce "
        "que rapportent mécaniquement le crédit, les taux et les actions.  \n"
        "*Les mandats du FRR étant dédiés et non publics, chaque gérant est représenté par un fonds ouvert "
        "de la même stratégie (proxy).*"
    )
    s1, s2, s3 = st.columns(3)
    s1.markdown("**① Choisir le mandat**  \nDans la barre latérale : segment (HY US, HY Euro, Crédit Euro IG), indice et période.")
    s2.markdown("**② Comparer les gérants**  \nOnglet *Synthèse* pour la vue globale, onglet *Gérant* pour le diagnostic détaillé d'un fonds.")
    s3.markdown("**③ Établir la short-list**  \nOnglet *Scoring* : pondérez vos critères, obtenez un classement et exportez-le en Excel.")
    st.caption("Les onglets *Change* et *Options* illustrent le suivi de l'overlay (couverture EUR/USD, protection actions). "
               "Survolez les ⓘ et les en-têtes de colonnes pour les définitions.")

tabs = st.tabs(["🏁 Synthèse", "🔍 Gérant", "🏆 Scoring", "💱 Change", "🛡️ Options", "📘 Méthode"])

# ======================================================================================
# 1. Vue d'ensemble
# ======================================================================================
with tabs[0]:
    best_ir = table["Information ratio"].idxmax()
    best_alpha = table["Alpha factoriel"].idxmax()
    n_beat = int((table["Surperf. annualisée"] > 0).sum())
    n_robust = int(table["Verdict"].str.startswith("✅").sum())
    st.markdown(
        f"#### En bref : {n_beat} candidat{'s' if n_beat > 1 else ''} sur {len(table)} "
        f"bat{'tent' if n_beat > 1 else ''} l'indice, et **{n_robust}** crée{'nt' if n_robust > 1 else ''} "
        f"de la valeur de façon statistiquement robuste."
    )
    c = st.columns(4)
    c[0].metric("Rendement de l'indice (par an)", fmt_pct(A.ann_return(b.dropna())), help="Rendement annualisé du benchmark sur la période.")
    c[1].metric("Meilleur information ratio", short(best_ir), f"IR {table.loc[best_ir, 'Information ratio']:.2f}", help=HELP["Information ratio"])
    c[2].metric("Meilleur alpha factoriel", short(best_alpha), fmt_pct(table.loc[best_alpha, "Alpha factoriel"]), help=HELP["Alpha factoriel"])
    c[3].metric("Candidats battant l'indice", f"{n_beat} / {len(table)}", help=HELP["Surperf. annualisée"])

    left, right = st.columns([3, 2])
    with left:
        cum = (1 + R[selected + [bench]].fillna(0)).cumprod() * 100
        fig = go.Figure()
        for i, t in enumerate(selected):
            fig.add_scatter(x=cum.index, y=cum[t], name=short(t), line=dict(width=1.5, color=COLORS[i % len(COLORS)]))
        fig.add_scatter(x=cum.index, y=cum[bench], name="Benchmark", line=dict(width=3, color="black", dash="dot"))
        fig.update_layout(title="Performance cumulée (base 100)", height=430, margin=dict(t=50, b=10), hovermode="x unified")
        st.plotly_chart(fig, width="stretch")
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
    show_all = st.toggle("Afficher tous les indicateurs", value=False)
    essentials = ["Verdict", "Surperf. annualisée", "Information ratio", "Alpha factoriel",
                  "Max drawdown", "Down capture", "TER"]
    extras = ["Rdt annualisé", "Volatilité", "Tracking error", "Alpha t-stat", "Bêta", "Up capture", "Encours (Md$)"]
    cols = essentials + (extras if show_all else [])
    disp = table[cols].sort_values("Alpha factoriel", ascending=False)
    disp.index = [short(t) for t in disp.index]

    def _color(v, good_if_positive=True, pivot=0.0):
        if pd.isna(v) or v == pivot:
            return ""
        good = (v > pivot) == good_if_positive
        return "color: #1a7f37; font-weight: 600" if good else "color: #c62828"

    styler = style_metrics(disp)
    for col_name in ["Surperf. annualisée", "Information ratio", "Alpha factoriel"]:
        styler = styler.map(_color, subset=[col_name])
    styler = styler.map(lambda v: _color(v, good_if_positive=False, pivot=1.0), subset=["Down capture"])
    st.dataframe(
        styler,
        width="stretch",
        column_config={c: st.column_config.Column(c, help=HELP.get(c)) for c in cols},
    )
    st.caption("Classement par alpha factoriel. Vert = favorable, rouge = défavorable. "
               "Survolez les en-têtes pour la définition de chaque indicateur.")

# ======================================================================================
# 2. Analyse gérant
# ======================================================================================
with tabs[1]:
    f = st.selectbox("Gérant à analyser", list(table.index), format_func=label)
    m, fr = table.loc[f], regs[f]
    meta = D.FUNDS[f]

    badge, why, level = verdict(m)
    getattr(st, level)(
        f"### {badge}\n**{meta['short']}** ({meta['name']}) : {why} "
        f"(alpha {fmt_pct(m['Alpha factoriel'])} par an, t = {m['Alpha t-stat']:.1f}). "
        f"{'Le fonds bat' if m['Surperf. annualisée'] > 0 else 'Le fonds ne bat pas'} son indice "
        f"({fmt_pct(m['Surperf. annualisée'])} par an, net de frais)."
    )
    if meta.get("mandate"):
        st.caption(f"🏛️ **Mandat FRR :** {meta['mandate']} · **Fonds utilisé comme proxy :** {meta['name']} ({f}) — {meta['proxy']}.")
    else:
        st.caption(f"Alternative passive : {meta['name']} ({f}), sert de point de comparaison.")

    c = st.columns(6)
    c[0].metric("Rdt annualisé", fmt_pct(m["Rdt annualisé"]), fmt_pct(m["Surperf. annualisée"]) + " vs indice", help=HELP["Rdt annualisé"])
    c[1].metric("Tracking error", fmt_pct(m["Tracking error"]), help=HELP["Tracking error"])
    c[2].metric("Information ratio", f"{m['Information ratio']:.2f}", help=HELP["Information ratio"])
    c[3].metric("Alpha factoriel", fmt_pct(m["Alpha factoriel"]), f"t = {m['Alpha t-stat']:.1f}", delta_color="off", help=HELP["Alpha factoriel"] + " " + HELP["Alpha t-stat"])
    c[4].metric("Max drawdown", fmt_pct(m["Max drawdown"]), fmt_pct(A.drawdown(b.dropna()).min()) + " indice", delta_color="off", help=HELP["Max drawdown"])
    c[5].metric("Frais (TER)", "–" if pd.isna(m["TER"]) else f"{m['TER']:.2f} %", help=HELP["TER"])

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
        f"(IR = {m['Information ratio']:.2f}). Après neutralisation des expositions crédit, taux et actions, "
        f"l'alpha ressort à **{fmt_pct(m['Alpha factoriel'])}** par an, {signif_txt}. "
        f"Le gérant capte {fmt_pct(m['Up capture'], 0)} des hausses et {fmt_pct(m['Down capture'], 0)} des baisses du marché "
        f"({'profil asymétrique favorable' if asym > 0.02 else 'profil défavorable en baisse' if asym < -0.02 else 'profil symétrique'}). "
        f"Le modèle factoriel explique {fr['r2']:.0%} de la variance."
    )
    st.info(f"**Synthèse — {meta['short']}** ({meta['style'].lower()}). " + synth_body)

    pdf_bytes = fiche_pdf(f, seg_name, bench, start, st.session_state.refresh, badge, why, level,
                          synth_body.replace("**", ""))
    st.download_button(
        "📄 Télécharger la fiche gérant (PDF, 1 page)",
        pdf_bytes,
        file_name=f"fiche_{short(f).replace(' ', '_').replace('/', '-')}.pdf",
        mime="application/pdf",
        type="primary",
        help="Verdict, chiffres clés, graphiques, décomposition du rendement et synthèse : prête à imprimer ou à joindre à une note de comité.",
    )

    left, right = st.columns(2)
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
# 3. Scoring appel d'offres
# ======================================================================================
with tabs[2]:
    st.markdown(
        "**Objectif :** classer les candidats pour établir une **short-list** à rencontrer en due diligence. "
        "Choisissez un profil de pondération, excluez si besoin les fonds non éligibles, puis lisez le podium."
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
        for col, (key, (lab, higher, w0)) in zip(wcols, A.CRITERIA.items()):
            col.slider(lab, 0, 50, step=5, key=f"w_{key}",
                       on_change=lambda: st.session_state.update(profile="Personnalisé"),
                       help=HELP.get(key, "") + (" (plus c'est haut, mieux c'est)" if higher else " (plus c'est bas, mieux c'est)"))
    weights = {key: st.session_state[f"w_{key}"] for key in A.CRITERIA}
    tot = sum(weights.values())
    with c2:
        if tot:
            eff = pd.Series({A.CRITERIA[k][0].split(" (")[0]: v / tot for k, v in weights.items() if v})
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
    reasons = {}
    for t in table.index:
        r = []
        if pd.notna(table.loc[t, "TER"]) and table.loc[t, "TER"] > ter_max + 1e-9:
            r.append(f"frais {table.loc[t, 'TER']:.2f} %")
        if table.loc[t, "Max drawdown"] < dd_floor:
            r.append(f"repli {fmt_pct(table.loc[t, 'Max drawdown'], 1)}")
        if aum_min > 0 and (pd.isna(table.loc[t, "Encours (Md$)"]) or table.loc[t, "Encours (Md$)"] < aum_min):
            r.append("encours insuffisant")
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
                st.markdown(f"### {medals[i]} {short(t)}")
                st.caption(f"{D.FUNDS[t]['name']} · {D.FUNDS[t]['style']} · {table.loc[t, 'Verdict']}")
                st.progress(int(round(scores.loc[t, "Score global"])), text=f"Score {scores.loc[t, 'Score global']:.0f} / 100")
                st.markdown(
                    f"**Points forts :** {', '.join(good) if good else '—'}  \n"
                    f"**Point de vigilance :** {', '.join(bad) if bad else 'aucun'}  \n"
                    f"Surperf. {fmt_pct(table.loc[t, 'Surperf. annualisée'])} · alpha {fmt_pct(table.loc[t, 'Alpha factoriel'])} · "
                    + (f"frais {table.loc[t, 'TER']:.2f} %" if pd.notna(table.loc[t, "TER"]) else "frais n.d.")
                )

        # --- 4. Classement complet + radar --------------------------------------------------
        left, right = st.columns([3, 2])
        with left:
            mode = st.radio("Afficher", ["Notes (0–100)", "Valeurs réelles"], horizontal=True,
                            help="Notes : rang centile parmi les candidats éligibles (100 = meilleur). "
                                 "Valeurs réelles : les indicateurs bruts.")
            if mode.startswith("Notes"):
                show = scores.copy()
                show.index = [short(t) for t in show.index]
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
                raw.index = [short(t) for t in raw.index]
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
        st.markdown("#### 🔁 Le classement est-il robuste ?")
        robust = pd.DataFrame({name: A.score(elig_table, w)["Rang"] for name, w in A.PROFILES.items()})
        robust = robust.loc[scores.index]
        in_top3 = (robust <= 3).sum(axis=1)
        robust["Top 3"] = [f"{n} / {len(A.PROFILES)}" for n in in_top3]
        stable = [short(t) for t in robust.index if in_top3[t] == len(A.PROFILES)]
        st.caption(
            ("✅ " + ", ".join(stable) + f" reste{'nt' if len(stable) > 1 else ''} dans le top 3 quel que soit le profil : "
             "choix robuste." if stable else
             "⚠️ Aucun candidat n'est dans le top 3 pour tous les profils : le classement dépend fortement des pondérations.")
        )
        robust.index = [short(t) for t in robust.index]
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
# 4. Overlay change
# ======================================================================================
with tabs[3]:
    st.markdown(
        "**Le problème :** un mandat HY US est investi en dollars, alors que le fonds raisonne en euros. "
        "**La solution simulée :** vendre des dollars à terme pour neutraliser le change, en réajustant la "
        "couverture à intervalle régulier."
    )
    usd_funds = [t for t, mm in D.FUNDS.items() if mm["segment"] == "HY US"]
    with st.expander("⚙️ Paramètres de la couverture", expanded=False):
        c = st.columns(5)
        hf = c[0].selectbox("Fonds USD couvert", usd_funds, format_func=short, key="fx_fund")
        mandate = c[1].number_input("Encours du mandat (M€)", 100, 10000, 1000, 100)
        target = c[2].slider("Ratio de couverture cible", 0, 100, 100, 5, format="%d %%") / 100
        freq_lab = c[3].selectbox("Réajustement", ["Mensuel", "Trimestriel", "Hebdomadaire"])
        band = c[4].slider("Tolérance (±)", 0.5, 5.0, 2.0, 0.5, format="%.1f %%") / 100
    freq = {"Mensuel": "M", "Trimestriel": "Q", "Hebdomadaire": "W"}[freq_lab]

    hs = A.fx_hedge_simulation(levels[hf], levels["EURUSD=X"], fred["SOFR"], fred["ESTR"], target, freq)
    hs = hs.loc[hs.index > start]
    base = hs[["local_usd", "unhedged_eur", "hedged_eur"]]
    base = base / base.iloc[0] * 100
    wk = base.resample("W-FRI").last().pct_change().dropna()
    vol = wk.std() * np.sqrt(52)
    mdd = {k: A.drawdown(wk[k]).min() for k in wk}
    yrs = (hs.index[-1] - hs.index[0]).days / 365.25
    ann = (base.iloc[-1] / 100) ** (1 / yrs) - 1
    cost = ann["hedged_eur"] - ann["unhedged_eur"]

    # épisodes de dépassement (jours consécutifs hors bande)
    out = hs["deviation"].abs() > band
    ep_id = (out & ~out.shift(fill_value=False)).cumsum()[out]
    episodes = (
        hs.loc[out].assign(ep=ep_id).groupby("ep")
        .agg(Début=("ratio", lambda x: x.index[0]), Fin=("ratio", lambda x: x.index[-1]),
             Jours=("ratio", "size"), **{"Écart max": ("deviation", lambda x: x.loc[x.abs().idxmax()])})
    )

    # --- message clé -------------------------------------------------------------------
    st.info(
        f"#### En bref\n"
        f"Sur la période, couvrir le dollar a **{'coûté' if cost < 0 else 'rapporté'} {fmt_pct(abs(cost))} par an** "
        f"({fmt_pct(ann['unhedged_eur'])} non couvert → {fmt_pct(ann['hedged_eur'])} couvert), "
        f"principalement à cause du différentiel de taux €STR – SOFR ({fmt_pct(hs['carry_ann'].mean())} en moyenne). "
        f"En contrepartie, la volatilité du mandat en euros passe de **{fmt_pct(vol['unhedged_eur'], 1)} à "
        f"{fmt_pct(vol['hedged_eur'], 1)}** et le pire repli de {fmt_pct(mdd['unhedged_eur'], 1)} à "
        f"{fmt_pct(mdd['hedged_eur'], 1)}."
    )

    # --- statut du jour ----------------------------------------------------------------
    ratio_now, dev_now = hs["ratio"].iloc[-1], hs["deviation"].iloc[-1]
    expo_usd = mandate * levels["EURUSD=X"].dropna().iloc[-1]  # exposition en M$
    adjust = -dev_now * expo_usd
    if abs(dev_now) <= band:
        st.success(
            f"✅ **Aujourd'hui : couverture dans la bande** — ratio {ratio_now:.1%} pour une cible de {target:.0%} "
            f"(tolérance ±{band:.1%}). Aucune action requise."
        )
    else:
        st.error(
            f"⚠️ **Aujourd'hui : couverture hors bande** — ratio {ratio_now:.1%} pour une cible de {target:.0%}. "
            f"Action : **{'vendre' if adjust > 0 else 'racheter'} environ {abs(adjust):,.0f} M$ à terme**.".replace(",", " ")
        )

    k = st.columns(4)
    k[0].metric("Coût / gain de la couverture", fmt_pct(cost, 2) + " / an", help="Rendement couvert moins rendement non couvert, en euros.")
    k[1].metric("Volatilité en EUR", fmt_pct(vol["hedged_eur"], 1), f"{(vol['hedged_eur'] - vol['unhedged_eur']) * 100:+.1f} pts vs non couvert",
                delta_color="inverse", help="Écart-type annualisé des rendements hebdomadaires en euros.")
    k[2].metric("Pire repli en EUR", fmt_pct(mdd["hedged_eur"], 1), f"{(mdd['hedged_eur'] - mdd['unhedged_eur']) * 100:+.1f} pts vs non couvert",
                help="Max drawdown du mandat couvert, comparé au mandat non couvert.")
    k[3].metric("Dépassements de la bande", f"{len(episodes)} épisode{'s' if len(episodes) > 1 else ''}",
                f"{episodes['Jours'].mean():.0f} jours en moyenne" if len(episodes) else "aucun", delta_color="off",
                help="Périodes consécutives pendant lesquelles le ratio de couverture est sorti de la bande de tolérance.")

    left, right = st.columns(2)
    with left:
        fig = px.line(base.rename(columns={"local_usd": "En dollars", "unhedged_eur": "En euros, non couvert", "hedged_eur": "En euros, couvert"}),
                      title="Performance du mandat (base 100)", height=360, labels={"value": "", "date": "", "Date": ""},
                      color_discrete_sequence=["#9aa5b1", "#e76f51", "#1f5fa8"])
        fig.update_layout(legend_title=None, margin=dict(t=50, b=10), hovermode="x unified", legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = go.Figure()
        fig.add_hrect(y0=target - band, y1=target + band, fillcolor="green", opacity=0.08, line_width=0)
        fig.add_scatter(x=hs.index, y=hs["ratio"], name="Ratio de couverture", line=dict(color="#264653"))
        fig.add_hline(y=target, line_dash="dot")
        fig.add_scatter(x=hs.index[out], y=hs["ratio"][out], mode="markers", name="Hors bande", marker=dict(color="red", size=4))
        fig.update_layout(title="Ratio de couverture (zone verte = tolérance)", height=360,
                          yaxis_tickformat=".0%", margin=dict(t=50, b=10), legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, width="stretch")

    if len(episodes):
        with st.expander(f"Journal des dépassements ({len(episodes)} épisodes)"):
            st.dataframe(
                episodes.sort_values("Début", ascending=False).reset_index(drop=True)
                .style.format({"Début": "{:%d/%m/%Y}", "Fin": "{:%d/%m/%Y}", "Écart max": "{:+.2%}"}),
                width="stretch", hide_index=True,
            )
    st.caption("Hypothèses : forward valorisé par différentiel de taux courts (sans base cross-currency), "
               "réajustement au dernier jour ouvré de chaque période. La couverture neutralise le change, pas le risque de crédit.")

# ======================================================================================
# 5. Overlay options — protection actions et reporting hebdomadaire
# ======================================================================================
with tabs[4]:
    st.markdown(
        "**Le principe :** une **assurance contre la baisse des actions**. Le fonds achète un *put spread* sur "
        "l'Euro Stoxx 50 : il est indemnisé si l'indice baisse entre deux niveaux, en échange d'une prime payée d'avance. "
        "La position est renouvelée à chaque échéance."
    )
    spot_s = levels["^STOXX50E"].dropna()
    estr = fred["ESTR"].reindex(spot_s.index).ffill() / 100
    rv = spot_s.pct_change().rolling(21).std() * np.sqrt(252)

    with st.expander("⚙️ Paramètres de la stratégie", expanded=False):
        c = st.columns(6)
        notional = c[0].number_input("Montant protégé (M€)", 50, 5000, 1000, 50)
        k_long = c[1].slider("Protection à partir de", 80, 100, 95, 1, format="%d %%",
                             help="Strike du put acheté, en % du niveau de l'indice à l'ouverture.") / 100
        kl = int(round(k_long * 100))
        k_short = c[2].slider("Protection jusqu'à", 50, kl - 1, min(85, kl - 1), 1, format="%d %%",
                              help="Strike du put vendu : en dessous, la protection ne joue plus.") / 100
        mat_m = c[3].selectbox("Durée", [1, 3, 6, 12], index=1, format_func=lambda x: f"{x} mois")
        vol_prem = c[4].slider("Prime de vol (pts)", 0, 10, 3,
                               help="Écart supposé entre volatilité implicite et volatilité réalisée 1 mois.") / 100
        q = c[5].slider("Rendement dividende", 0.0, 5.0, 3.0, 0.5, format="%.1f %%") / 100

    # --- backtest hebdomadaire sur 1 an ----------------------------------------------
    weekly = spot_s.resample("W-FRI").last().loc[lambda s: s.index > last - pd.DateOffset(years=1)]
    rows, pos, cum_pnl, premiums = [], None, 0.0, 0.0
    for dte in weekly.index:
        S = spot_s.loc[:dte].iloc[-1]
        sig = rv.loc[:dte].iloc[-1] + vol_prem
        r_ = estr.loc[:dte].iloc[-1]
        event = ""
        if pos is not None and dte >= pos["expiry"]:
            payoff = max(pos["K1"] - S, 0) - max(pos["K2"] - S, 0)
            pnl = (payoff - pos["last_mtm"]) * pos["units"]
            cum_pnl += pnl
            rows.append({"Date": dte, "Euro Stoxx 50": S, "Strikes": f"{pos['K1']:.0f} / {pos['K2']:.0f}",
                         "Valeur (M€)": payoff * pos["units"] / 1e6, "Delta (M€)": 0.0,
                         "P&L semaine (M€)": pnl / 1e6, "P&L cumulé (M€)": cum_pnl / 1e6,
                         "Évènement": "Échéance" + (" (indemnisation)" if payoff > 0 else "")})
            pos = None
            event = "Renouvellement"
        if pos is None:
            units = notional * 1e6 / S
            g0 = A.put_spread(S, k_long * S, k_short * S, mat_m / 12, r_, q, sig)
            pos = dict(K1=k_long * S, K2=k_short * S, expiry=dte + pd.DateOffset(months=mat_m),
                       units=units, last_mtm=g0["price"])
            premiums += g0["price"] * units
            rows.append({"Date": dte, "Euro Stoxx 50": S, "Strikes": f"{pos['K1']:.0f} / {pos['K2']:.0f}",
                         "Valeur (M€)": g0["price"] * units / 1e6, "Delta (M€)": g0["delta"] * units * S / 1e6,
                         "P&L semaine (M€)": 0.0, "P&L cumulé (M€)": cum_pnl / 1e6,
                         "Évènement": f"{event or 'Ouverture'} — prime {g0['price'] * units / 1e6:.1f} M€"})
            continue
        T = max((pos["expiry"] - dte).days, 0) / 365
        g = A.put_spread(S, pos["K1"], pos["K2"], T, r_, q, sig)
        pnl = (g["price"] - pos["last_mtm"]) * pos["units"]
        cum_pnl += pnl
        pos["last_mtm"] = g["price"]
        rows.append({"Date": dte, "Euro Stoxx 50": S, "Strikes": f"{pos['K1']:.0f} / {pos['K2']:.0f}",
                     "Valeur (M€)": g["price"] * pos["units"] / 1e6, "Delta (M€)": g["delta"] * pos["units"] * S / 1e6,
                     "P&L semaine (M€)": pnl / 1e6, "P&L cumulé (M€)": cum_pnl / 1e6, "Évènement": ""})
    rep = pd.DataFrame(rows).set_index("Date")

    # --- position courante et prix d'une protection neuve ----------------------------
    S_now, r_now = spot_s.iloc[-1], estr.iloc[-1]
    T_now = max((pos["expiry"] - spot_s.index[-1]).days, 1) / 365
    sig_now = rv.iloc[-1] + vol_prem
    g_now = A.put_spread(S_now, pos["K1"], pos["K2"], T_now, r_now, q, sig_now)
    u = pos["units"]
    new = A.put_spread(S_now, k_long * S_now, k_short * S_now, mat_m / 12, r_now, q, sig_now)
    prem_pct = new["price"] / S_now
    max_pay = (k_long - k_short) * notional

    st.info(
        f"#### En bref\n"
        f"Une protection neuve couvrirait **{notional:,.0f} M€** d'actions contre une baisse de l'indice comprise entre "
        f"**−{(1 - k_long) * 100:.0f} % et −{(1 - k_short) * 100:.0f} %** "
        f"(niveaux {k_long * S_now:,.0f} et {k_short * S_now:,.0f}). "
        f"**Coût : {prem_pct * notional:,.1f} M€** pour {mat_m} mois, soit {prem_pct:.2%} du montant protégé "
        f"(≈ {prem_pct * 12 / mat_m:.1%} par an). **Indemnisation maximale : {max_pay:,.0f} M€** si l'indice finit "
        f"sous {k_short * S_now:,.0f}.".replace(",", " ")
    )

    # --- carte « cette semaine » -------------------------------------------------------
    last_row = rep.iloc[-1]
    days_left = (pos["expiry"] - spot_s.index[-1]).days
    cushion = S_now / pos["K1"] - 1
    st.markdown("##### 🗓️ Cette semaine")
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
                          margin=dict(t=50, b=10), xaxis_title="Euro Stoxx 50", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, width="stretch")

    # --- reporting hebdomadaire --------------------------------------------------------
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
            view.style.format({"Euro Stoxx 50": "{:,.0f}", "Valeur (M€)": "{:.1f}", "Delta (M€)": "{:+.0f}",
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
with tabs[5]:
    st.markdown(
        """
### Objectif
Prototype d'outil d'aide à la **sélection et au suivi de gérants délégués**, sur les segments
Crédit Euro et High Yield US, appliqué aux **gérants actuels du FRR**.

### Données
- **Gérants** : attributaires des marchés 2020FRR01 (crédit euro IG et HY, 2021) et 2022FRR01 (HY US, 2023),
  d'après les *Listes des marchés publics conclus par le FRR* (fondsdereserve.fr).
- **Fonds proxies** : pour chaque gérant, un fonds ouvert de la même stratégie (parts de capitalisation ou
  ajustées des coupons, Yahoo Finance / Morningstar) → rendements *total return* nets de frais.
  Historique disponible depuis mars 2022 pour les fonds UCITS européens. Frais non disponibles pour la plupart d'entre eux.
- **Benchmarks** : indices ICE BofA US / Euro High Yield Total Return (FRED, ~3 ans d'historique gratuit)
  ou ETF proxy pour un historique plus long.
- **Facteurs** : spreads OAS ICE BofA HY (FRED), ETF d'emprunts d'État (IEF / iShares Core € Govt),
  indices actions (S&P 500 / Euro Stoxx 50). Taux courts : SOFR et €STR.
- Fréquence **hebdomadaire** (vendredi) pour synchroniser les places US et européennes.

### Indicateurs
| Indicateur | Définition |
|---|---|
| Tracking error | écart-type annualisé de (fonds − indice) |
| Information ratio | surperformance annualisée / tracking error |
| Alpha de Jensen | constante de la régression (r − rf) = α + β (rb − rf) |
| **Alpha factoriel** | constante de (r − rf) = α + β₁·(−ΔOAS) + β₂·r_taux + β₃·r_actions — la valeur ajoutée *après* rémunération des expositions de marché |
| Up / down capture | rendement moyen du fonds / de l'indice les semaines de hausse / de baisse |

### Limites (à garder en tête)
- Les **fonds proxies ne sont pas les mandats du FRR** : contraintes ESG, frais négociés et taille diffèrent.
  Certains proxies sont imparfaits (AllianceBernstein, BFT IM, Degroof Petercam), voir l'onglet Gérant.
- **Biais du survivant** : l'univers ne contient que des fonds encore existants.
- 3 ans d'historique hebdomadaire = ~156 points : les alphas sont rarement significatifs → la statistique
  ne suffit pas, d'où l'importance de la **due diligence qualitative** (process, équipe, risques, ESG).
- Pas de série OAS IG € gratuite : le facteur crédit du segment IG utilise le spread HY € en proxy.
- Options : volatilité implicite approchée par la vol réalisée + prime ; pas de smile ni de coûts de transaction.
- Couverture de change : forward modélisé par le différentiel de taux courts (parité des taux couverte),
  sans base cross-currency.
"""
    )
