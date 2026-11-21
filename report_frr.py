"""Rapport PDF de suivi des gérants du FRR (crédit euro IG, HY euro, HY US), style « CSG Performance ».

Pages : couverture et synthèse · contexte de marché · une page par segment · évolutions et alertes.
Tous les chiffres sont recalculés à partir des données de l'app (rendements hebdomadaires, nets de frais).
"""
from __future__ import annotations

import io
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

import analytics as A  # noqa: E402
import data as D  # noqa: E402
from report import BENCH_C, GRID, INK, MUTED, NEG, POS, _num, _pct, _style_ax  # noqa: E402

NAVY = "#14325c"
PALETTE = ["#1f5fa8", "#e76f51", "#2a9d8f", "#c77700", "#7b4fa0", "#5b6470"]
VERDICT_SHORT = {"success": "Robuste", "error": "Destruction", "warning": "Non démontré", "info": "Proche indice"}
VERDICT_COLOR = {"success": "#e6f4ea", "error": "#fdecea", "warning": "#fff4e5", "info": "#eef0f3"}


# ======================================================================================
# Calculs
# ======================================================================================
def _sp(v, d=1):
    """Pourcentage signé, sans « −0,0 % »."""
    return _pct(0.0 if pd.notna(v) and abs(v) < 0.5 * 10 ** (-d - 2) else v, d, sign=True)


def _ord(n) -> str:
    return "1ᵉʳ" if int(n) == 1 else f"{int(n)}ᵉ"


def _cum(r: pd.Series) -> float:
    r = r.dropna()
    return (1 + r).prod() - 1 if len(r) else np.nan


def _segment(seg_name: str, data: dict, rets: pd.DataFrame, sfdr: dict) -> dict:
    seg = D.SEGMENTS[seg_name]
    bench = list(seg["benchmarks"].values())[0]
    bench_label = list(seg["benchmarks"])[0]
    last = rets.index.max()
    rf_all = A.weekly_rf(data["fred"][seg["rf"]]).reindex(rets.index).ffill().fillna(0)
    fac_all = A.factor_frame(data, seg, rets)
    universe = [t for t, m in D.FUNDS.items() if m["segment"] == seg_name]
    frr = [t for t in universe if D.FUNDS[t]["style"] == "Gérant FRR"]

    def window(end):
        idx = rets.index[(rets.index > end - pd.DateOffset(years=3)) & (rets.index <= end)]
        return rets.loc[idx], rf_all.loc[idx], fac_all.loc[idx]

    def alphas(end):
        R, rf, F = window(end)
        out = {}
        for t in universe:
            if R[t].dropna().shape[0] >= 104:
                out[t] = A.factor_regression(R[t], rf, F)["alpha_ann"]
        return pd.Series(out).rank(ascending=False, method="min").astype(int)

    R3, rf3, F3 = window(last)
    prev = last - pd.DateOffset(weeks=13)
    rank_now, rank_prev = alphas(last), alphas(prev)
    rows = []
    for t in frr:
        m = A.perf_metrics(R3[t], R3[bench], rf3)
        fr = A.factor_regression(R3[t], rf3, F3)
        m.update({"Alpha factoriel": fr["alpha_ann"], "Alpha t-stat": fr["alpha_t"]})
        badge, why, level = A.verdict(m)
        r, b = rets[t], rets[bench]
        ytd = rets.index >= pd.Timestamp(last.year, 1, 1)
        ex12_now = _cum(r.iloc[-52:]) - _cum(b.iloc[-52:])
        ex12_prev = _cum(r.iloc[-65:-13]) - _cum(b.iloc[-65:-13])
        rows.append({
            "ticker": t, "Gérant": D.FUNDS[t]["short"], "Segment": seg_name,
            "3 mois": _cum(r.iloc[-13:]) - _cum(b.iloc[-13:]), "YTD": _cum(r[ytd]) - _cum(b[ytd]),
            "1 an": ex12_now, "1 an (il y a 3 mois)": ex12_prev, "3 ans ann.": m["Surperf. annualisée"],
            "Rdt 3 ans ann.": m["Rdt annualisé"], "IR": m["Information ratio"], "Alpha": m["Alpha factoriel"],
            "t": m["Alpha t-stat"], "Max DD": m["Max drawdown"], "Down capture": m["Down capture"],
            "Verdict": VERDICT_SHORT[level], "level": level,
            "Rang": rank_now.get(t, np.nan), "Rang -3m": rank_prev.get(t, np.nan), "Univers": len(rank_now),
            "SFDR": (f"Art. {sfdr[t]['article']}" if sfdr.get(t, {}).get("article") else "n.d.") if t in sfdr else "n.a.",
        })
    bench_r = rets[bench]
    ytd = rets.index >= pd.Timestamp(last.year, 1, 1)
    return dict(name=seg_name, bench=bench, bench_label=bench_label, currency=seg["currency"], table=pd.DataFrame(rows),
                R3=R3, bench_perf={"3 mois": _cum(bench_r.iloc[-13:]), "YTD": _cum(bench_r[ytd]),
                                   "1 an": _cum(bench_r.iloc[-52:]), "3 ans ann.": A.ann_return(R3[bench].dropna())},
                n_universe=len(rank_now), last=last)


def _alerts(t: pd.DataFrame) -> list[str]:
    out = []
    for _, r in t.iterrows():
        g = f"{r['Gérant']} ({r['Segment']})"
        if r["level"] == "error":
            out.append(f"{g} : alpha factoriel négatif et significatif ({_pct(r['Alpha'])}, t = {_num(r['t'], 1)}).")
        if r["1 an"] < -0.01:
            out.append(f"{g} : sous-performance de {_pct(r['1 an'])} sur 12 mois glissants.")
        if pd.notna(r["Rang -3m"]) and r["Rang"] - r["Rang -3m"] >= 3:
            out.append(f"{g} : recul de {int(r['Rang'] - r['Rang -3m'])} places en 3 mois ({_ord(r['Rang -3m'])} → {_ord(r['Rang'])} sur {r['Univers']}).")
        if r["SFDR"] in ("n.d.", "Art. 6"):
            out.append(f"{g} : classification SFDR du fonds proxy {r['SFDR']} (à vérifier sur le mandat).")
    return out


# ======================================================================================
# Mise en page
# ======================================================================================
def _page(pdf, title: str, subtitle: str, page_no: int, asof):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    fig.add_artist(plt.Rectangle((0, 0.955), 1, 0.045, color=NAVY, transform=fig.transFigure))
    fig.text(0.06, 0.972, "FRR · GESTION DÉLÉGUÉE — SUIVI DES MANDATS CRÉDIT", fontsize=7.5, color="white", weight="bold")
    fig.text(0.94, 0.972, f"Données au {asof:%d/%m/%Y}", fontsize=7.5, color="white", ha="right")
    fig.text(0.06, 0.925, title, fontsize=15, color=INK, weight="bold")
    fig.text(0.06, 0.905, subtitle, fontsize=8, color=MUTED)
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.03, 0.03], color=GRID, lw=0.8))
    fig.text(0.06, 0.017, "Document de travail généré automatiquement à partir de fonds proxies publics — "
             "ne reflète pas la performance réelle des mandats du FRR.", fontsize=6, color=MUTED)
    fig.text(0.94, 0.017, f"{page_no}", fontsize=7, color=MUTED, ha="right")
    return fig


def _table(fig, rect, df: pd.DataFrame, fmt: dict, colors: list | None = None, fontsize=7, col_widths=None):
    ax = fig.add_axes(rect); ax.axis("off")
    cells = [[fmt.get(c, str)(v) for c, v in row.items()] for _, row in df.iterrows()]
    tb = ax.table(cellText=cells, colLabels=list(df.columns), loc="upper center", cellLoc="center",
                  colWidths=col_widths)
    tb.auto_set_font_size(False); tb.set_fontsize(fontsize); tb.scale(1, 1.35)
    for (i, j), cell in tb.get_celld().items():
        cell.set_edgecolor(GRID)
        if i == 0:
            cell.set_facecolor(NAVY); cell.set_text_props(color="white", weight="bold")
        elif colors is not None and colors[i - 1] is not None and df.columns[j] == "Verdict":
            cell.set_facecolor(colors[i - 1])
        elif j == 0:
            cell.set_text_props(ha="left", weight="bold")
    return ax


def _bullets(fig, x, y, items: list[str], width=110, size=8.2, gap=0.0145):
    for it in items:
        lines = textwrap.wrap(it, width=width)
        fig.text(x, y, "•  " + lines[0], fontsize=size, color=INK, va="top")
        for k, ln in enumerate(lines[1:], 1):
            fig.text(x + 0.018, y - k * gap, ln, fontsize=size, color=INK, va="top")
        y -= gap * len(lines) + 0.004
    return y


def build_frr_report(data: dict, rets: pd.DataFrame, sfdr: dict) -> bytes:
    asof = data["asof"]
    segs = [_segment(s, data, rets, sfdr) for s in D.SEGMENTS]
    allt = pd.concat([s["table"] for s in segs], ignore_index=True)
    fred, px = data["fred"], data["prices"]
    pctf = _sp
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # --- 1. couverture & synthèse ---------------------------------------------------------
        n_beat = int((allt["3 ans ann."] > 0).sum()); robust = allt[allt["level"] == "success"]
        fig = _page(pdf, "Rapport de suivi des gérants du FRR",
                    f"Crédit euro investment grade, haut rendement euro et High Yield US · {len(allt)} gérants · "
                    f"période d'analyse 3 ans · {segs[0]['last']:%d/%m/%Y}", 1, asof)
        msgs = [
            f"{n_beat} gérants sur {len(allt)} battent leur indice sur 3 ans (nets de frais) ; "
            f"{len(robust)} {'affichent' if len(robust) > 1 else 'affiche'} un alpha factoriel statistiquement significatif"
            + (f" : {', '.join(robust['Gérant'] + ' (' + robust['Segment'] + ')')}." if len(robust) else "."),
        ]
        for s in segs:
            t = s["table"].sort_values("1 an", ascending=False)
            msgs.append(f"{s['name']} : indice {_pct(s['bench_perf']['1 an'], 1)} sur 12 mois. Meilleur gérant FRR sur 12 mois : "
                        f"{t.iloc[0]['Gérant']} ({pctf(t.iloc[0]['1 an'])} vs indice) ; moins bon : {t.iloc[-1]['Gérant']} "
                        f"({pctf(t.iloc[-1]['1 an'])}). Meilleur rang du FRR dans l'univers : "
                        f"{_ord(s['table']['Rang'].min())} sur {s['n_universe']}.")
        alerts = _alerts(allt)
        msgs.append(f"{len(alerts)} point(s) de vigilance relevé(s) : voir page 6.")
        fig.text(0.06, 0.875, "Messages clés", fontsize=11, weight="bold", color=NAVY)
        y = _bullets(fig, 0.06, 0.855, msgs)
        fig.text(0.06, y - 0.01, "Tableau de bord — surperformance vs indice (nette de frais) et création de valeur",
                 fontsize=10, weight="bold", color=NAVY)
        tab = allt[["Gérant", "Segment", "3 mois", "YTD", "1 an", "3 ans ann.", "IR", "Alpha", "t", "Verdict", "Rang", "SFDR"]].copy()
        tab["Rang"] = [f"{int(r)}/{u}" for r, u in zip(allt["Rang"], allt["Univers"], strict=True)]
        fmt = {"3 mois": pctf, "YTD": pctf, "1 an": pctf, "3 ans ann.": pctf, "IR": _num, "Alpha": pctf, "t": lambda v: _num(v, 1)}
        _table(fig, [0.04, y - 0.43, 0.92, 0.41], tab, fmt, colors=[VERDICT_COLOR[lv] for lv in allt["level"]], fontsize=6.5,
               col_widths=[0.19, 0.11, 0.065, 0.065, 0.065, 0.075, 0.055, 0.065, 0.045, 0.1, 0.06, 0.055])
        ax = fig.add_axes([0.26, 0.1, 0.66, y - 0.47])
        al = allt.iloc[::-1]
        ax.barh(al["Gérant"] + " · " + al["Segment"], al["Alpha"],
                color=[POS if a > 0 else NEG for a in al["Alpha"]], height=0.6)
        ax.axvline(0, color=MUTED, lw=0.6)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v * 100:.1f} %".replace(".", ",")))
        ax.tick_params(axis="y", labelsize=6.5)
        ax.set_title("Alpha factoriel annualisé sur 3 ans (valeur ajoutée du gérant)", fontsize=9, loc="left", weight="bold",
                     color=INK)
        _style_ax(ax)
        fig.text(0.06, 0.045, "Lecture : surperformance = rendement du fonds − rendement de l'indice ; alpha factoriel = valeur ajoutée "
                 "après neutralisation du crédit, des taux et des actions ; rang = classement par alpha dans l'univers (gérants FRR, "
                 "candidats, ETF).", fontsize=6.2, color=MUTED, wrap=True)
        pdf.savefig(fig); plt.close(fig)

        # --- 2. contexte de marché ----------------------------------------------------------
        fig = _page(pdf, "Contexte de marché", "Spreads de crédit, indices de référence, taux et change", 2, asof)
        last = segs[0]["last"]; start = last - pd.DateOffset(years=3)
        oas = fred[["OAS_HY_US", "OAS_HY_EUR"]].loc[start:].dropna()
        ax = fig.add_axes([0.08, 0.62, 0.84, 0.24])
        ax.plot(oas.index, oas["OAS_HY_US"], color=PALETTE[0], lw=1.5, label="Spread HY US (OAS)")
        ax.plot(oas.index, oas["OAS_HY_EUR"], color=PALETTE[1], lw=1.5, label="Spread HY euro (OAS)")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1f} %".replace(".", ",")))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y")); ax.legend(fontsize=7, frameon=False)
        ax.set_title("Spreads du haut rendement sur 3 ans", fontsize=9, loc="left", weight="bold", color=INK); _style_ax(ax)
        ax = fig.add_axes([0.08, 0.33, 0.84, 0.24])
        for i, s in enumerate(segs):
            c = (1 + s["R3"][s["bench"]].fillna(0)).cumprod() * 100
            ax.plot(c.index, c, color=PALETTE[i], lw=1.5, label=s["bench_label"])
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y")); ax.legend(fontsize=7, frameon=False)
        ax.set_title("Indices de référence (base 100, 3 ans)", fontsize=9, loc="left", weight="bold", color=INK); _style_ax(ax)
        yr = oas.loc[: last - pd.DateOffset(years=1)].iloc[-1]
        ctx = pd.DataFrame({
            "Indicateur": ["Spread HY US", "Spread HY euro", "Taux US 5 ans", "EUR/USD"] + [s["bench_label"] for s in segs],
            "Niveau / 1 an": [f"{_num(oas['OAS_HY_US'].iloc[-1])} % ({oas['OAS_HY_US'].iloc[-1] - yr['OAS_HY_US']:+.2f} pt sur 1 an)".replace(".", ","),
                              f"{_num(oas['OAS_HY_EUR'].iloc[-1])} % ({oas['OAS_HY_EUR'].iloc[-1] - yr['OAS_HY_EUR']:+.2f} pt sur 1 an)".replace(".", ","),
                              f"{_num(fred['UST5Y'].dropna().iloc[-1])} %",
                              _num(px["EURUSD=X"].dropna().iloc[-1], 4)] + [_pct(s["bench_perf"]["1 an"], 1) for s in segs],
            "YTD": ["", "", "", pctf(px["EURUSD=X"].dropna().iloc[-1] / px["EURUSD=X"].dropna().loc[f"{last.year}-01-01":].iloc[0] - 1)]
                   + [_pct(s["bench_perf"]["YTD"], 1) for s in segs],
            "3 ans ann.": ["", "", "", ""] + [_pct(s["bench_perf"]["3 ans ann."], 1) for s in segs],
        })
        _table(fig, [0.06, 0.06, 0.88, 0.22], ctx, {}, fontsize=7.2, col_widths=[0.38, 0.26, 0.18, 0.18])
        pdf.savefig(fig); plt.close(fig)

        # --- 3-5. une page par segment -------------------------------------------------------
        for k, s in enumerate(segs):
            t = s["table"]
            fig = _page(pdf, f"{s['name']} — gérants du FRR", f"Indice : {s['bench_label']} · devise {s['currency']} · "
                        f"{len(t)} mandats · univers de comparaison : {s['n_universe']} fonds", 3 + k, asof)
            ax = fig.add_axes([0.08, 0.64, 0.84, 0.23])
            for i, tk in enumerate(t["ticker"]):
                c = (1 + s["R3"][tk].fillna(0)).cumprod() * 100
                ax.plot(c.index, c, color=PALETTE[i % len(PALETTE)], lw=1.4, label=D.FUNDS[tk]["short"])
            cb = (1 + s["R3"][s["bench"]].fillna(0)).cumprod() * 100
            ax.plot(cb.index, cb, color=BENCH_C, lw=1.2, ls=(0, (2, 2)), label="Indice")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y")); ax.legend(fontsize=6.5, frameon=False, ncol=3)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}"))
            ax.set_title("Performance cumulée sur 3 ans (base 100)", fontsize=9, loc="left", weight="bold", color=INK); _style_ax(ax)
            ax = fig.add_axes([0.08, 0.40, 0.84, 0.18])
            for i, tk in enumerate(t["ticker"]):
                ex = A.rolling_excess(s["R3"][tk], s["R3"][s["bench"]])["Surperf. 12M glissante"].dropna()
                ax.plot(ex.index, ex, color=PALETTE[i % len(PALETTE)], lw=1.2)
            ax.axhline(0, color=MUTED, lw=0.6)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v * 100:.1f} %".replace(".", ",")))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
            ax.set_title("Surperformance sur 12 mois glissants — régularité de la création de valeur", fontsize=9, loc="left",
                         weight="bold", color=INK); _style_ax(ax)
            tab = t[["Gérant", "3 mois", "YTD", "1 an", "3 ans ann.", "IR", "Alpha", "t", "Max DD", "Down capture", "Verdict"]].copy()
            tab["Down capture"] = tab["Down capture"].map(lambda v: _pct(v, 0))
            tab = tab.rename(columns={"Down capture": "Down capt.", "3 ans ann.": "3 ans/an"})
            fmt = {"3 mois": pctf, "YTD": pctf, "1 an": pctf, "3 ans/an": pctf, "IR": _num, "Alpha": pctf,
                   "t": lambda v: _num(v, 1), "Max DD": lambda v: _pct(v, 1)}
            _table(fig, [0.04, 0.19, 0.92, 0.18], tab, fmt, colors=[VERDICT_COLOR[lv] for lv in t["level"]], fontsize=6.8,
                   col_widths=[0.2, 0.07, 0.07, 0.07, 0.08, 0.06, 0.07, 0.05, 0.08, 0.08, 0.12])
            best = t.loc[t["Alpha"].idxmax()]; worst = t.loc[t["1 an"].idxmin()]
            notes = [f"Indice : {_pct(s['bench_perf']['3 mois'], 1)} sur 3 mois, {_pct(s['bench_perf']['YTD'], 1)} depuis le 1er janvier, "
                     f"{_pct(s['bench_perf']['1 an'], 1)} sur 12 mois.",
                     f"Meilleure création de valeur : {best['Gérant']} (alpha {_pct(best['Alpha'])}/an, t = {_num(best['t'], 1)}, "
                     f"{_ord(best['Rang'])} sur {s['n_universe']}).",
                     f"Moins bonne dynamique sur 12 mois : {worst['Gérant']} ({pctf(worst['1 an'])} vs indice, contre "
                     f"{pctf(worst['1 an (il y a 3 mois)'])} il y a trois mois)."]
            fig.text(0.06, 0.165, "Commentaires", fontsize=10, weight="bold", color=NAVY)
            _bullets(fig, 0.06, 0.145, notes)
            pdf.savefig(fig); plt.close(fig)

        # --- 6. évolutions, alertes, méthode -------------------------------------------------
        fig = _page(pdf, "Évolutions sur 3 mois et points de vigilance",
                    "Classement dans l'univers et surperformance 12 mois : aujourd'hui vs il y a 13 semaines", 6, asof)
        ev = allt[["Gérant", "Segment", "Rang -3m", "Rang", "1 an (il y a 3 mois)", "1 an"]].copy()
        ev["Évol. rang"] = (ev["Rang -3m"] - ev["Rang"]).map(
            lambda d: "–" if pd.isna(d) else ("stable" if d == 0 else (f"▲ +{int(d)}" if d > 0 else f"▼ {int(d)}")))
        ev = ev.rename(columns={"Rang -3m": "Rang −3 mois", "Rang": "Rang actuel", "1 an (il y a 3 mois)": "Surperf. 12M −3 mois",
                                "1 an": "Surperf. 12M"})
        fmt = {"Rang −3 mois": lambda v: "–" if pd.isna(v) else str(int(v)), "Rang actuel": lambda v: str(int(v)),
               "Surperf. 12M −3 mois": pctf, "Surperf. 12M": pctf}
        _table(fig, [0.04, 0.52, 0.92, 0.36], ev, fmt, fontsize=7,
               col_widths=[0.21, 0.13, 0.12, 0.11, 0.16, 0.13, 0.11])
        fig.text(0.06, 0.49, "Points de vigilance", fontsize=10, weight="bold", color=NAVY)
        y = _bullets(fig, 0.06, 0.47, alerts or ["Aucun point de vigilance selon les règles retenues."])
        fig.text(0.06, y - 0.015, "Méthode et limites", fontsize=10, weight="bold", color=NAVY)
        _bullets(fig, 0.06, y - 0.035, [
            "Gérants : attributaires des marchés 2020FRR01 (crédit euro IG et HY) et 2022FRR01 (HY US) ; chaque mandat est "
            "représenté par un fonds ouvert de la même stratégie (proxy), d'où des écarts possibles avec le mandat réel "
            "(contraintes ESG du FRR, frais négociés, indice).",
            "Rendements hebdomadaires total return nets de frais (Yahoo Finance / Morningstar), indices ICE BofA (FRED).",
            "Alpha factoriel : régression des rendements excédentaires sur le crédit (−ΔOAS), les taux et les actions, "
            "erreurs Newey-West ; significatif si |t| ≥ 2. Trois ans de données restent courts pour conclure.",
            "Règles de vigilance : alpha négatif significatif, sous-performance 12 mois < −1 %, recul de 3 places ou plus "
            "en 3 mois, classification SFDR du proxy inférieure à l'article 8 ou non trouvée.",
        ], size=7.6)
        pdf.savefig(fig); plt.close(fig)
    return buf.getvalue()
