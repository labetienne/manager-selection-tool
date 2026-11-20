"""Fiche gérant d'une page (PDF A4) générée avec matplotlib.

Pensée pour être imprimée ou jointe à une note de comité : verdict, chiffres clés,
graphiques, décomposition du rendement et synthèse rédigée.
"""
from __future__ import annotations

import io
import re
import textwrap
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

LEVEL_COLORS = {"success": "#1a7f37", "error": "#c62828", "warning": "#c77700", "info": "#5b6470"}
INK, MUTED, GRID = "#1f2328", "#5b6470", "#e6e8eb"
FUND_C, BENCH_C = "#1f5fa8", "#1f2328"
POS, NEG = "#2a9d8f", "#e76f51"


def _pct(x, d=2, sign=False):
    if x is None or pd.isna(x):
        return "–"
    return f"{x * 100:{'+' if sign else ''}.{d}f} %".replace(".", ",")


def _num(x, d=2):
    return "–" if x is None or pd.isna(x) else f"{x:.{d}f}".replace(".", ",")


def _style_ax(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=7, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def build_fiche(
    *,
    ticker: str,
    meta: dict,
    m: pd.Series,
    fr: dict,
    pair: pd.DataFrame,  # colonnes [ticker, bench] : rendements hebdomadaires
    bench_col: str,
    bench_label: str,
    seg_name: str,
    currency: str,
    rf_ann: float,
    badge: str,
    why: str,
    level: str,
    synthesis: str,
    asof: datetime,
) -> bytes:
    pair = pair.dropna()
    fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
    fig.patch.set_facecolor("white")
    L, R = 0.06, 0.94

    # --- En-tête -------------------------------------------------------------------
    fig.text(L, 0.965, "FICHE GÉRANT", fontsize=8, color=MUTED, weight="bold")
    fig.text(R, 0.965, f"Appel d'offres {seg_name}", fontsize=8, color=MUTED, ha="right")
    fig.text(L, 0.938, meta["name"], fontsize=17, color=INK, weight="bold")
    fig.text(
        L, 0.918,
        f"{ticker}  ·  {meta['style']}  ·  benchmark : {bench_label}  ·  "
        f"{pair.index[0]:%d/%m/%Y} → {pair.index[-1]:%d/%m/%Y}  ·  {currency}, net de frais",
        fontsize=7.5, color=MUTED,
    )

    # --- Bandeau verdict -------------------------------------------------------------
    color = LEVEL_COLORS.get(level, MUTED)
    ax_v = fig.add_axes([L, 0.862, R - L, 0.042])
    ax_v.axis("off")
    ax_v.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.08",
                                  transform=ax_v.transAxes, facecolor=color, alpha=0.10,
                                  edgecolor=color, linewidth=1))
    clean_badge = badge.split(" ", 1)[1] if " " in badge else badge  # retire l'emoji
    ax_v.text(0.015, 0.5, clean_badge.upper(), fontsize=11, weight="bold", color=color, va="center")
    ax_v.text(0.985, 0.5, why[0].upper() + why[1:], fontsize=8, color=INK, va="center", ha="right")

    # --- Chiffres clés ---------------------------------------------------------------
    kpis = [
        ("Rendement annualisé", _pct(m["Rdt annualisé"]), f"indice {_pct(m['Rdt benchmark'])}"),
        ("Surperformance / an", _pct(m["Surperf. annualisée"], sign=True), "vs indice"),
        ("Information ratio", _num(m["Information ratio"]), f"TE {_pct(m['Tracking error'])}"),
        ("Alpha factoriel / an", _pct(m["Alpha factoriel"], sign=True), f"t-stat {_num(m['Alpha t-stat'], 1)}"),
        ("Max drawdown", _pct(m["Max drawdown"]), f"indice {_pct((1 + pair[bench_col]).cumprod().div((1 + pair[bench_col]).cumprod().cummax()).sub(1).min())}"),
        ("Frais (TER)", "–" if pd.isna(m["TER"]) else f"{m['TER']:.2f} %".replace(".", ","), "par an"),
    ]
    w = (R - L) / len(kpis)
    for i, (lab, val, sub) in enumerate(kpis):
        x = L + i * w
        fig.text(x + 0.004, 0.836, lab, fontsize=7, color=MUTED)
        good = None
        if lab.startswith(("Surperf", "Alpha")):
            v = m["Surperf. annualisée"] if lab.startswith("Surperf") else m["Alpha factoriel"]
            good = v > 0
        fig.text(x + 0.004, 0.812, val, fontsize=14, weight="bold",
                 color=INK if good is None else (LEVEL_COLORS["success"] if good else LEVEL_COLORS["error"]))
        fig.text(x + 0.004, 0.797, sub, fontsize=6.5, color=MUTED)

    # --- Graphique 1 : performance cumulée ---------------------------------------------
    ax1 = fig.add_axes([L + 0.02, 0.575, 0.52, 0.19])
    cum = (1 + pair).cumprod() * 100
    ax1.plot(cum.index, cum[ticker], color=FUND_C, lw=1.8, label=meta.get("short", ticker))
    ax1.plot(cum.index, cum[bench_col], color=BENCH_C, lw=1.1, ls=(0, (2, 2)), label="Indice")
    ax1.set_title("Performance cumulée (base 100)", fontsize=8.5, loc="left", color=INK, weight="bold")
    ax1.legend(fontsize=7, frameon=False, loc="upper left")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0f}"))
    _style_ax(ax1)

    # --- Graphique 2 : décomposition du rendement --------------------------------------
    ax2 = fig.add_axes([0.66, 0.575, 0.28, 0.19])
    contrib = fr["table"]["Contribution annualisée"].drop("Alpha")
    parts = pd.Series({"Taux\ncourt": rf_ann, "Crédit": contrib.iloc[0], "Taux": contrib.iloc[1],
                       "Actions": contrib.iloc[2], "Alpha": fr["alpha_ann"]})
    bottoms = np.concatenate([[0], np.cumsum(parts.values)[:-1]])
    cols = [MUTED if k != "Alpha" else (POS if v >= 0 else NEG) for k, v in parts.items()]
    cols = [FUND_C if k in ("Crédit", "Taux", "Actions") else c for k, c in zip(parts.index, cols)]
    ax2.bar(range(len(parts)), parts.values, bottom=bottoms, color=cols, width=0.65)
    total = parts.sum()
    ax2.bar(len(parts), total, color=INK, width=0.65)
    for i, (v, b0) in enumerate(zip(list(parts.values) + [total], list(bottoms) + [0])):
        ax2.text(i, b0 + v + (0.0015 if v >= 0 else -0.0015), _pct(v, 1), ha="center",
                 va="bottom" if v >= 0 else "top", fontsize=6, color=INK)
    ax2.set_xticks(range(len(parts) + 1), list(parts.index) + ["Total"], fontsize=6.5)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y * 100:.0f} %"))
    lo, hi = ax2.get_ylim()
    ax2.set_ylim(min(lo, 0), hi + (hi - min(lo, 0)) * 0.15)
    ax2.set_title("D'où vient le rendement ? (par an)", fontsize=8.5, loc="left", color=INK, weight="bold")
    _style_ax(ax2)

    # --- Graphique 3 : surperformance 12 mois glissants --------------------------------
    ax3 = fig.add_axes([L + 0.02, 0.375, 0.52, 0.14])
    roll = (1 + pair).rolling(52).apply(np.prod, raw=True) - 1
    ex = (roll[ticker] - roll[bench_col]).dropna()
    ax3.bar(ex.index, ex.values, width=6, color=np.where(ex.values >= 0, POS, NEG))
    ax3.axhline(0, color=MUTED, lw=0.6)
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y * 100:.1f} %".replace(".", ",")))
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    ax3.set_title("Surperformance sur 12 mois glissants (régularité)",
                  fontsize=8.5, loc="left", color=INK, weight="bold")
    _style_ax(ax3)

    # --- Tableau : profil de risque ------------------------------------------------------
    ax_t = fig.add_axes([0.66, 0.36, 0.28, 0.16])
    ax_t.axis("off")
    ax_t.set_title("Profil de risque", fontsize=8.5, loc="left", color=INK, weight="bold")
    rows = [
        ("Volatilité", _pct(m["Volatilité"])),
        ("Tracking error", _pct(m["Tracking error"])),
        ("Bêta vs indice", _num(m["Bêta"])),
        ("Sharpe", _num(m["Sharpe"])),
        ("Up capture", _pct(m["Up capture"], 0)),
        ("Down capture", _pct(m["Down capture"], 0)),
        ("% semaines surperf.", _pct(m["% semaines surperf."], 0)),
        ("R² du modèle factoriel", _pct(fr["r2"], 0)),
    ]
    for i, (k, v) in enumerate(rows):
        y = 0.92 - i * 0.122
        ax_t.text(0.0, y, k, fontsize=7.5, color=MUTED, transform=ax_t.transAxes, va="center")
        ax_t.text(1.0, y, v, fontsize=7.5, color=INK, weight="bold", ha="right", transform=ax_t.transAxes, va="center")
        ax_t.plot([0, 1], [y - 0.061] * 2, color=GRID, lw=0.5, transform=ax_t.transAxes)

    # --- Synthèse rédigée ---------------------------------------------------------------
    fig.text(L, 0.315, "Synthèse", fontsize=10, weight="bold", color=INK)
    synthesis = re.sub(r"(\d)\.(\d)", r"\1,\2", synthesis).replace("%", " %").replace("  %", " %")
    lines = textwrap.wrap(synthesis, width=118)
    fig.text(L, 0.300, "\n".join(lines), fontsize=8, color=INK, va="top", linespacing=1.55)
    y_next = 0.300 - len(lines) * 0.0155 - 0.030

    # --- Lecture des sensibilités ----------------------------------------------------
    coefs = fr["table"]["Coefficient"]
    sens = (
        f"Sensibilités estimées : un écartement des spreads de crédit de 1 point coûterait environ "
        f"{abs(coefs.iloc[1]):.1f} % au fonds (hors effet taux). Il réplique {coefs.iloc[2] * 100:.0f} % des "
        f"mouvements des emprunts d'État et {coefs.iloc[3] * 100:.0f} % de ceux du marché actions."
    ).replace(f"{abs(coefs.iloc[1]):.1f}", f"{abs(coefs.iloc[1]):.1f}".replace(".", ","))
    fig.text(L, y_next, "Lecture des sensibilités", fontsize=10, weight="bold", color=INK)
    sens_txt = sens.split(" : ", 1)[1]
    sens_lines = textwrap.wrap(sens_txt[0].upper() + sens_txt[1:], width=118)
    fig.text(L, y_next - 0.015, "\n".join(sens_lines), fontsize=8, color=INK, va="top", linespacing=1.55)
    y_next = y_next - 0.015 - len(sens_lines) * 0.0155 - 0.035

    fig.text(L, y_next, "Points à approfondir en due diligence", fontsize=10, weight="bold", color=INK)
    todo = [
        "Processus d'investissement et sources de l'alpha (sélection d'émetteurs, allocation par notation, duration)",
        "Stabilité et taille de l'équipe de gestion ; capacité de la stratégie au regard de l'encours",
        "Gestion du risque : limites de concentration, liquidité en période de stress, politique ESG",
    ]
    for i, t in enumerate(todo):
        fig.text(L + 0.01, y_next - 0.022 - i * 0.017, "•  " + t, fontsize=7.5, color=INK)

    # --- Pied de page -------------------------------------------------------------------
    fig.add_artist(plt.Line2D([L, R], [0.035, 0.035], color=GRID, lw=0.8))
    fig.text(
        L, 0.022,
        "Sources : Yahoo Finance, FRED (ICE BofA). Rendements hebdomadaires total return, nets de frais. "
        "Alpha factoriel : régression crédit / taux / actions (Newey-West).",
        fontsize=6, color=MUTED,
    )
    fig.text(L, 0.012, f"Données au {asof:%d/%m/%Y} · Document de travail généré automatiquement — "
             "ne constitue pas une recommandation d'investissement.", fontsize=6, color=MUTED)

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        pdf.savefig(fig)
    plt.close(fig)
    return buf.getvalue()
