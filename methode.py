"""Onglet « Méthode et formules » : indicateurs (sens, formule, lecture), hypothèses, données et limites."""

# Chaque indicateur : (nom, ce que ça mesure, formule LaTeX, comment le lire, où le trouver dans l'outil)
INDICATORS = {
    "Performance et risque": [
        ("Rendement hebdomadaire", "La variation du prix du fonds (coupons réinvestis) d'un vendredi à l'autre.",
         r"r_t = \frac{P_t}{P_{t-1}} - 1",
         "Toutes les mesures partent de ces rendements hebdomadaires, nets de frais.", "Partout"),
        ("Rendement annualisé", "Le gain moyen par an, en tenant compte des intérêts composés.",
         r"R = \Big[\prod_{t=1}^{n}(1+r_t)\Big]^{52/n} - 1",
         "5 % veut dire que 100 € deviennent en moyenne 105 € chaque année.", "Classement, Fiche gérant"),
        ("Volatilité", "L'amplitude des variations du fonds.",
         r"\sigma = \text{écart-type}(r_t)\times\sqrt{52}",
         "Plus elle est basse, plus le fonds est régulier. La racine de 52 passe de la semaine à l'année.",
         "Fiche gérant (vue détaillée)"),
        ("Sharpe", "Le rendement obtenu au-delà du taux sans risque, par unité de risque total.",
         r"\text{Sharpe} = \frac{R - R_f}{\sigma}",
         "Au-dessus de 1, c'est bon. Peu utilisé ici : un gérant délégué se juge par rapport à son indice.",
         "Tableau complet (vue détaillée)"),
        ("Sortino", "Comme le Sharpe, mais ne compte que la volatilité des semaines négatives.",
         r"\text{Sortino} = \frac{R - R_f}{\sigma_-}, \quad \sigma_- = \text{écart-type}(r_t \mid r_t<0)\times\sqrt{52}",
         "Utile quand les hausses et les baisses ne se ressemblent pas.", "Tableau complet (vue détaillée)"),
        ("Max drawdown (pire baisse)", "La plus forte perte subie entre un sommet et le creux qui suit.",
         r"\text{MDD} = \min_t\Big(\frac{V_t}{\max_{s\le t} V_s} - 1\Big), \quad V_t = \prod_{u\le t}(1+r_u)",
         "−10 % veut dire qu'au pire moment, un investisseur a perdu 10 % depuis le dernier sommet.",
         "Classement, Fiche gérant"),
    ],
    "Gestion active (comparaison à l'indice)": [
        ("Surperformance", "Ce que le fonds gagne de plus (ou de moins) que son indice.",
         r"R - R_b", "Positif : le gérant bat son indice, frais déduits.", "Classement, Fiche gérant"),
        ("Tracking error", "De combien le gérant s'écarte de son indice.",
         r"TE = \text{écart-type}(r_t - b_t)\times\sqrt{52}",
         "1 % : gestion proche de l'indice. Au FRR, chaque mandat a un budget de tracking error.",
         "Fiche gérant (vue détaillée)"),
        ("Information ratio", "La surperformance obtenue par unité d'écart à l'indice.",
         r"IR = \frac{R - R_b}{TE}",
         "Au-dessus de 0,5 c'est bon, au-dessus de 1 c'est excellent. C'est la mesure clé du talent d'un gérant actif.",
         "Classement (vue détaillée), Appel d'offres"),
        ("Up / down capture", "La part des hausses et des baisses de l'indice que subit le fonds.",
         r"\text{Up} = \frac{\overline{r_t \mid b_t>0}}{\overline{b_t \mid b_t>0}}, \quad "
         r"\text{Down} = \frac{\overline{r_t \mid b_t<0}}{\overline{b_t \mid b_t<0}}",
         "Un down capture de 80 % veut dire que le fonds ne subit que 80 % des baisses : il protège.",
         "Fiche gérant, Appel d'offres"),
        ("Régularité", "La part des semaines où le fonds fait mieux que son indice.",
         r"\frac{\#\{t : r_t > b_t\}}{n}", "Au-dessus de 50 %, le gérant gagne plus souvent qu'il ne perd.",
         "Appel d'offres"),
        ("Surperformance sur 12 mois glissants", "La surperformance de l'année écoulée, recalculée chaque semaine.",
         r"\prod_{52\ \text{sem.}}(1+r_t) - \prod_{52\ \text{sem.}}(1+b_t)",
         "Montre si un gérant décroche ou se redresse : c'est le premier signal d'une mise sous surveillance.",
         "Fiche gérant (vue détaillée), rapport PDF"),
    ],
    "Valeur ajoutée du gérant (alpha)": [
        ("Alpha de Jensen", "Le rendement non expliqué par le marché, une fois corrigé du bêta.",
         r"r_t - rf_t = \alpha + \beta\,(b_t - rf_t) + \varepsilon_t, \quad \alpha_{\text{an}} = 52\,\alpha",
         "Un gérant à bêta 1,2 bat mécaniquement son indice quand le marché monte : l'alpha retire cet effet.",
         "Tableau complet (vue détaillée)"),
        ("Alpha factoriel", "Ce que le gérant apporte une fois payées ses expositions au crédit, aux taux et aux actions.",
         r"r_t - rf_t = \alpha + \beta_c\,(-\Delta OAS_t) + \beta_\tau\, g_t + \beta_a\, a_t + \varepsilon_t",
         "En crédit, on peut battre l'indice en prenant plus de risque crédit, plus de duration ou un profil plus "
         "« actions ». La régression retire ces paris de marché : ce qui reste (α × 52 par an) est la sélection "
         "d'émetteurs du gérant. ΔOAS = variation du spread, g = rendement des obligations d'État, a = rendement "
         "des actions.",
         "Classement (« Valeur ajoutée du gérant »), Fiche gérant"),
        ("Contribution d'un facteur", "La part du rendement venant de chaque exposition de marché.",
         r"\text{contribution}_k = \beta_k \times \overline{\text{facteur}_k} \times 52",
         "Exemple : sur 6 % par an, 4 % de portage crédit, 1 % de taux et 1 % d'alpha.", "Fiche gérant (vue détaillée)"),
        ("t-stat et Newey-West", "La fiabilité statistique de l'alpha.",
         r"\begin{aligned} t &= \frac{\hat\alpha}{\text{se}_{NW}(\hat\alpha)} \\ "
         r"\widehat{\text{Var}}(\hat\beta) &= (X'X)^{-1}\, \hat S\, (X'X)^{-1} \\ "
         r"\hat S &= \sum_t \varepsilon_t^2 x_t x_t' + \sum_{l=1}^{4}\Big(1-\tfrac{l}{5}\Big)\sum_t \varepsilon_t\varepsilon_{t-l}"
         r"\,(x_t x_{t-l}' + x_{t-l} x_t') \end{aligned}",
         "Au-delà de |t| = 2, l'alpha n'est probablement pas dû au hasard (seuil de 95 %). Newey-West corrige le fait "
         "que les rendements crédit d'une semaine ressemblent à ceux de la semaine d'avant.",
         "Verdict"),
        ("Verdict", "Une lecture en une icône de l'alpha factoriel et de son t-stat.",
         r"\begin{cases}\alpha>0,\ t\ge 2 & ✅\ \text{robuste}\\ \alpha<0,\ t\le -2 & ❌\ \text{destruction}\\ "
         r"|\alpha|<0{,}25\,\% & ⚪\ \text{proche de l'indice}\\ \alpha>0,\ t<2 & 🟡\ \text{non démontré}\\ "
         r"\alpha<0,\ t>-2 & 🟠\ \text{pas de valeur ajoutée}\end{cases}",
         "0,25 % par an correspond à peu près à des frais de gestion : en dessous, le gérant ne se distingue pas de l'indice.",
         "Classement, Fiche gérant, rapport PDF"),
    ],
    "Appel d'offres": [
        ("Score sur 100", "Une note qui combine les critères selon les pondérations choisies.",
         r"\text{centile}_k(i) = \frac{\text{rang}_k(i)}{N}\times 100, \quad "
         r"\text{Score}(i) = \frac{\sum_k w_k\,\text{centile}_k(i)}{\sum_k w_k}",
         "Chaque critère est d'abord transformé en rang (0 à 100) pour pouvoir mélanger des unités différentes. "
         "Le rang est inversé quand « plus bas = mieux » (frais, down capture). Un critère manquant compte pour 50.",
         "Appel d'offres"),
    ],
    "Cades et passif": [
        ("Valeur actuelle du passif", "Ce que valent aujourd'hui les versements futurs à la Cades.",
         r"VA = \sum_{k} F\,(1+y)^{-t_k}, \quad F = 1{,}45\ \text{Md€},\ t_k = \text{année}_k - 2025 - 0{,}5",
         "y est le taux de l'OAT 10 ans. Un euro versé en 2033 vaut moins qu'un euro versé en 2026.", "Cades et passif"),
        ("Marge de couverture", "Le capital que le FRR possède au-delà de ce qu'il doit.",
         r"\text{Marge} = \text{Actif} - VA",
         "C'est le « matelas » que le FRR peut exposer au risque. Le FRR publie 10,3 Md€ fin 2025.", "Cades et passif"),
        ("Sensibilité aux taux", "De combien la valeur baisse quand les taux montent de 1 point.",
         r"D_{\text{passif}} = \frac{\sum_k t_k F (1+y)^{-t_k}}{VA\,(1+y)}, \quad "
         r"D_{\text{actif}} = \sum_i \text{poids}_i \times \text{sensi}_i",
         "Une sensibilité de 3,7 veut dire que la valeur baisse de 3,7 % si les taux montent de 1 point.",
         "Cades et passif (vue détaillée)"),
        ("Stress test", "L'effet d'un choc de marché sur l'actif, le passif et la marge.",
         r"\text{choc}_i = \beta_i\,\Delta A - S^{\tau}_i\,\Delta\tau - S^{s}_i\, m_i\,\Delta s, \quad "
         r"\Delta\text{Actif} = \sum_i \text{montant}_i\,\text{choc}_i, \quad \Delta\text{Passif} = -D\,\Delta\tau\, VA",
         "ΔA = choc actions, Δτ = choc de taux, Δs = choc de spread High Yield, m = part du choc de spread subie par la ligne.",
         "Cades et passif"),
        ("Création de valeur d'un mandat", "Ce que rapporte le mandat par rapport au coût de la dette française.",
         r"\text{Valeur} = \text{encours}\times(R_{€} - \overline{OAT}), \quad "
         r"\text{Apport du gérant} = \text{encours}\times(R_{€} - R_{b,€})",
         "R€ est le rendement en euros. Pour le High Yield US, on retranche le coût de couverture du dollar "
         "(SOFR − €STR). La différence entre les deux lignes est la part due au marché du crédit.",
         "Cades et passif"),
        ("Futures pour revenir à l'allocation", "Le montant à acheter ou vendre pour coller à l'allocation décidée.",
         r"\text{Futures} = -(\text{poids réel} - \text{poids cible})\times\text{Actif}",
         "Positif : acheter des futures. Le mandat overlay fait ces ajustements sans toucher aux mandats.",
         "Cades et passif"),
    ],
    "Couverture de change": [
        ("Notionnel couvert", "Le montant de devises vendu à terme à chaque réajustement.",
         r"N = h \times \text{valeur du placement en devise}", "h est le ratio cible : 90 % au FRR.", "Couverture de change"),
        ("Résultat de la couverture", "Le gain ou la perte des contrats à terme.",
         r"\text{P\&L}_t = -N\Big(\frac{1}{X_t} - \frac{1}{X_{t-1}}\Big), \quad "
         r"\text{portage}_t = \frac{N}{X_{t-1}}\,(€STR - \text{taux devise})\,\frac{j}{360}",
         "X est le cours EUR/devise. Quand le dollar baisse, le contrat gagne et compense la perte du placement. "
         "Le portage est le coût de la couverture quand les taux américains dépassent les taux européens.",
         "Couverture de change"),
        ("Écart au ratio cible", "De combien la couverture réelle s'écarte de 90 %.",
         r"\text{ratio} = \frac{N}{\text{valeur du placement}}, \quad \text{écart} = \text{ratio} - h",
         "Le placement bouge entre deux réajustements, donc le ratio dérive. Au-delà de la tolérance, il faut ajuster.",
         "Couverture de change"),
        ("Exposition au change", "La part de l'actif exposée aux devises.",
         r"\frac{\sum_{\text{devises}}(1-\text{ratio})\times\text{exposition} + \text{émergents}}{\text{Actif}} \le 20\,\%",
         "La limite légale du FRR est de 20 % (16,9 % fin 2025).", "Couverture de change"),
    ],
    "Options (protection actions)": [
        ("Prix d'un put (Black-Scholes)", "La valeur d'une option de vente, avec un dividende q.",
         r"d_1 = \frac{\ln(S/K) + (r - q + \sigma^2/2)T}{\sigma\sqrt T}, \quad d_2 = d_1 - \sigma\sqrt T, \quad "
         r"\text{Put} = K e^{-rT} N(-d_2) - S e^{-qT} N(-d_1)",
         "S = niveau de l'indice, K = prix d'exercice, T = durée en années, σ = volatilité, r = taux.",
         "Protection actions"),
        ("Put spread", "Achat d'un put à 95 % et vente d'un put à 85 % de l'indice.",
         r"\text{Valeur} = \text{Put}(K_1) - \text{Put}(K_2), \quad "
         r"\text{Payoff} = \max(K_1 - S, 0) - \max(K_2 - S, 0)",
         "Le put vendu finance une partie de la protection. On est protégé entre −5 % et −15 %, pas au-delà.",
         "Protection actions"),
        ("Grecques", "Les sensibilités de la protection.",
         r"\Delta_{put} = -e^{-qT}N(-d_1), \quad \Gamma = \frac{e^{-qT}\varphi(d_1)}{S\sigma\sqrt T}, \quad "
         r"\nu = S e^{-qT}\varphi(d_1)\sqrt T",
         "Delta : exposition actions équivalente. Gamma : vitesse à laquelle le delta change. Vega : effet d'un point "
         "de volatilité en plus. Theta : perte de valeur liée au temps qui passe.",
         "Protection actions (vue détaillée)"),
    ],
}

HYPOTHESES = [
    ("Fonds proxies",
     "Pour chaque mandat, un fonds ouvert de la même société de gestion et de la même stratégie.",
     "Les mandats du FRR ne publient pas leurs performances ; le fonds ouvert est géré par la même équipe, avec le même processus.",
     "Le mandat a ses propres contraintes (exclusions ESG, frais négociés, taille)."),
    ("Sensibilités des stress tests",
     "Actions bêta 1 (émergentes 1,1) ; non coté et actions couvertes par options bêta 0,5 ; High Yield duration 3,2 à 3,5 ; "
     "dette émergente 6 (80 % du choc de spread) ; dette privée 0,5 en taux (60 % du spread) ; IG 4,5 (40 % du spread) ; "
     "OAT 10 ans 8,5 ; adossement 4.",
     "Durations typiques de chaque classe d'actifs. Le non coté est valorisé avec retard, le put spread absorbe une partie "
     "de la baisse, les spreads IG bougent bien moins que ceux du HY. Avec ces valeurs, la sensibilité de l'actif "
     "ressort à 1,96 contre 2,05 publié par le FRR.",
     "Corrélations entre chocs non modélisées ; change supposé couvert."),
    ("Expositions par devise",
     "Environ 4,7 Md€ en dollar, 0,6 en yen, 0,4 en livre, 0,3 en franc suisse, 2 Md€ en devises émergentes non couvertes.",
     "Le FRR ne publie pas sa répartition par devise : reconstruite à partir de l'allocation fin 2025 (High Yield US, "
     "actions américaines et japonaises, Europe hors zone euro). Modifiable dans l'onglet.",
     "L'outil trouve environ 10 % d'exposition contre 16,9 % publié (non coté, fonds et positions tactiques non captés)."),
    ("Encours de chaque mandat",
     "Le poids du segment, réparti à parts égales entre ses gérants (ex. High Yield euro : 2,67 Md€ / 5 = 534 M€).",
     "La taille de chaque mandat n'est pas publiée ; une répartition égale est l'hypothèse la plus neutre.",
     "Change les montants en M€, pas le classement des gérants."),
    ("Coût de la dette",
     "Le taux moyen de l'OAT 10 ans sur la période.",
     "Le FRR mesure sa création de valeur par rapport au coût de la dette française : chaque euro versé à la Cades "
     "évite à l'État d'emprunter, et l'OAT 10 ans est son taux de référence.",
     "Mieux : actualiser chaque versement au taux de sa maturité, ou utiliser le coût de financement de la Cades."),
    ("Versements en milieu d'année",
     "Chaque versement à la Cades est daté du milieu de l'année.",
     "Les versements sont étalés dans l'année ; avec cette convention, la sensibilité du passif ressort à 3,69 contre 3,71 publié.",
     "Les dates exactes des versements ne sont pas publiées."),
    ("Données hebdomadaires, 3 ans",
     "Rendements arrêtés le vendredi, sur 3 ans par défaut.",
     "Compare les marchés américain et européen à la même date, avec environ 156 points ; les indices ICE gratuits "
     "ne remontent qu'à 3 ans.",
     "3 ans, c'est court pour prouver un alpha."),
    ("Rendement en euros couverts",
     "Rendement en dollar moins (SOFR − €STR).",
     "Parité des taux couverte : se couvrir coûte l'écart de taux entre les deux devises.",
     "Suppose une couverture à 100 % (90 % au FRR)."),
    ("Newey-West à 4 retards",
     "Erreurs-types robustes sur 4 semaines.",
     "Environ un mois : la durée pendant laquelle les prix d'obligations peu liquides restent « lissés ».",
     "Choix conventionnel."),
    ("Seuils du verdict",
     "|t| ≥ 2 pour « robuste » ; |α| < 0,25 % par an pour « proche de l'indice ».",
     "2 est le seuil statistique classique de 95 % ; 0,25 % correspond à peu près à des frais de gestion.",
     "Un seuil plus strict rendrait presque tous les gérants « non démontrés »."),
    ("Volatilité des options",
     "Volatilité réalisée sur un mois plus une prime.",
     "Les volatilités implicites ne sont pas disponibles gratuitement.",
     "Pas de smile de volatilité ni de coûts de transaction."),
    ("Facteur crédit de l'IG",
     "Le spread du High Yield euro sert de facteur crédit pour le segment IG.",
     "Il n'existe pas de série gratuite de spreads IG en euros.",
     "Le bêta crédit des gérants IG est donc sous-estimé."),
    ("Pondérations du scoring",
     "IR 25, alpha 20, down capture 15, pire baisse, régularité, frais et ESG 10 chacun ; Sharpe 0.",
     "La valeur ajoutée du gérant d'abord, puis la protection en baisse, puis les coûts. Le Sharpe est à 0 car le risque "
     "total est décidé par l'allocation du FRR, pas par le gérant.",
     "Trois autres profils sont proposés, et l'onglet vérifie si le podium change selon le profil."),
]

DATA = """
- **Gérants** : attributaires des marchés 2020FRR01 (crédit euro IG et HY, 2021) et 2022FRR01 (HY US, 2023), d'après les
  *Listes des marchés publics conclus par le FRR* (fondsdereserve.fr) et le rapport annuel 2025.
- **Fonds proxies et candidats** : cours Yahoo Finance (codes Morningstar), nets de frais, coupons réinvestis. 63 candidats
  (29 en HY US, 17 en HY €, 17 en crédit € IG), retenus pour leur corrélation à l'indice (0,80 à 0,98).
- **Indices et facteurs** (FRED) : ICE BofA US et Euro High Yield Total Return, spreads OAS, SOFR, €STR, SONIA, taux 3 mois
  JPY et CHF, OAT 10 ans. ETF d'emprunts d'État (IEF, iShares Core € Govt) et indices actions via Yahoo Finance.
- **FRR** : rapport annuel 2025 (allocation, politique de change, overlay, sensibilités, marge de couverture), composition
  du portefeuille au 30/09/2026 (4 165 lignes, totaux rapprochés), allocation stratégique 2026, communiqués d'appels
  d'offres, loi du 7 août 2020 (versements à la Cades).
- **ESG** : article SFDR de chaque fonds européen relevé dans sa documentation, avec la source, dans `data/sfdr.csv`.

**Vérifications** : 8 tests automatiques sur des cas connus (`test_analytics.py`) ; rapprochement avec les chiffres publiés
par le FRR (marge 10,6 contre 10,3 Md€, sensibilité du passif 3,69 contre 3,71, de l'actif 1,96 contre 2,05).
"""

LIMITS = """
- Les fonds proxies ne sont pas les mandats du FRR. Certains collent mal à la stratégie du mandat ; la fiche gérant le
  signale fonds par fonds.
- Les candidats forment un échantillon de grands gérants, pas l'univers complet ; un vrai appel d'offres porterait sur les
  sociétés qui ont candidaté.
- Biais du survivant : l'univers ne contient que des fonds qui existent encore.
- Environ 156 points hebdomadaires : un alpha est rarement significatif, d'où l'importance de la due diligence qualitative.
- Pas de données de positions par mandat : ni attribution par secteur (Brinson), ni facteurs Barra, ni DTS exact.
"""


def render(st):
    st.markdown("Ce que mesure chaque indicateur, comment il se calcule et comment le lire, puis les hypothèses "
                "retenues et leurs raisons.")
    t_ind, t_hyp, t_data = st.tabs(["📐 Indicateurs et formules", "🧭 Hypothèses et choix", "🗂️ Données, vérifications, limites"])
    with t_ind:
        for family, items in INDICATORS.items():
            st.markdown(f"#### {family}")
            for name, what, formula, read, where in items:
                with st.expander(f"{name} : {what}"):
                    if r", \quad " in formula:  # une équation par ligne, lisible même sur écran étroit
                        formula = r"\begin{gathered}" + formula.replace(r", \quad ", r" \\ ") + r"\end{gathered}"
                    st.latex(formula)
                    st.markdown(f"**Comment le lire.** {read}")
                    st.caption(f"Dans l'outil : {where}")
    with t_hyp:
        for name, choice, why, limit in HYPOTHESES:
            with st.expander(name):
                st.markdown(f"**Le choix.** {choice}\n\n**Pourquoi.** {why}\n\n**Limite.** {limit}")
    with t_data:
        st.markdown("#### Données")
        st.markdown(DATA)
        st.markdown("#### Limites")
        st.markdown(LIMITS)
