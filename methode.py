"""Onglet « Méthode et formules » : indicateurs (question, formule, calcul en mots, sens), hypothèses, données, limites."""

# Chaque indicateur : (nom, question à laquelle il répond, formule LaTeX, ce que calcule la formule, ce que ça veut dire,
# où le trouver dans l'outil)
INDICATORS = {
    "Performance et risque": [
        ("Rendement hebdomadaire",
         "De combien le fonds a-t-il bougé cette semaine ?",
         r"r_t = \frac{P_t}{P_{t-1}} - 1",
         "On divise le prix du fonds ce vendredi (P_t) par son prix le vendredi précédent (P_{t-1}), puis on retire 1 "
         "pour obtenir un pourcentage. Le prix intègre les coupons réinvestis et les frais déjà prélevés.",
         "Un prix qui passe de 100 à 101 donne r = +1 %. Tous les autres indicateurs sont construits à partir de ces "
         "rendements de la semaine.",
         "Partout"),
        ("Rendement annualisé",
         "Combien le fonds a-t-il rapporté en moyenne chaque année ?",
         r"R = \Big[\prod_{t=1}^{n}(1+r_t)\Big]^{52/n} - 1",
         "On multiplie entre eux tous les (1 + rendement de la semaine) : cela donne ce que sont devenus 1 € sur toute la "
         "période. Puis on ramène ce résultat à une année avec la puissance 52/n (52 semaines par an, n semaines au total).",
         "5 % par an veut dire que 100 € sont devenus en moyenne 105 € chaque année, intérêts composés compris.",
         "Classement, Fiche gérant"),
        ("Volatilité",
         "Le fonds bouge-t-il beaucoup d'une semaine à l'autre ?",
         r"\sigma = \text{écart-type}(r_t)\times\sqrt{52}",
         "On mesure à quel point les rendements de la semaine s'éloignent de leur moyenne (l'écart-type), puis on "
         "multiplie par la racine de 52 pour passer d'une semaine à une année.",
         "C'est la mesure du risque. Une volatilité de 5 % veut dire qu'une année « normale », le rendement s'écarte "
         "d'environ 5 points de sa moyenne. Plus c'est bas, plus le fonds est régulier.",
         "Fiche gérant (vue détaillée)"),
        ("Sharpe",
         "Combien le fonds rapporte-t-il pour chaque unité de risque prise ?",
         r"\text{Sharpe} = \frac{R - R_f}{\sigma}",
         "On prend le rendement du fonds (R), on retire ce qu'on aurait gagné sans aucun risque en laissant l'argent "
         "placé au jour le jour (R_f, le taux €STR ou SOFR), puis on divise par la volatilité (σ).",
         "Il dit si le risque pris a été bien payé. Un Sharpe de 1 veut dire 1 % de gain en plus du sans-risque pour 1 % "
         "de volatilité. Peu utilisé ici : un gérant délégué se juge par rapport à son indice, pas dans l'absolu.",
         "Tableau complet (vue détaillée)"),
        ("Sortino",
         "Même question que le Sharpe, en ne comptant que le « mauvais » risque.",
         r"\text{Sortino} = \frac{R - R_f}{\sigma_-}, \quad \sigma_- = \text{écart-type}(r_t \mid r_t<0)\times\sqrt{52}",
         "Même calcul que le Sharpe, mais on divise par la volatilité des seules semaines de baisse (σ₋) au lieu de "
         "toutes les semaines.",
         "Un investisseur ne se plaint pas des fortes hausses. Le Sortino ne pénalise donc que les baisses. Il est plus "
         "élevé que le Sharpe quand le fonds monte plus fort qu'il ne baisse.",
         "Tableau complet (vue détaillée)"),
        ("Max drawdown (pire baisse)",
         "Quelle a été la pire perte qu'un investisseur a pu subir ?",
         r"\text{MDD} = \min_t\Big(\frac{V_t}{\max_{s\le t} V_s} - 1\Big), \quad V_t = \prod_{u\le t}(1+r_u)",
         "On suit la valeur de 1 € placé (V_t). Chaque semaine, on compare cette valeur au plus haut atteint avant. Le "
         "max drawdown est le plus grand écart observé entre un sommet et le creux qui le suit.",
         "−10 % veut dire qu'au pire moment, quelqu'un entré au plus haut avait perdu 10 %. Ça mesure la douleur "
         "maximale, ce qu'un comité regarde en premier en période de crise.",
         "Classement, Fiche gérant"),
    ],
    "Gestion active (comparaison à l'indice)": [
        ("Surperformance",
         "Le gérant fait-il mieux que son indice ?",
         r"R - R_b",
         "On retire le rendement annualisé de l'indice (R_b) à celui du fonds (R).",
         "+1 % veut dire que le gérant a rapporté 1 % de plus par an que l'indice, frais déduits. C'est ce que le FRR "
         "paie quand il choisit une gestion active plutôt qu'un ETF.",
         "Classement, Fiche gérant"),
        ("Tracking error",
         "De combien le gérant s'éloigne-t-il de son indice ?",
         r"TE = \text{écart-type}(r_t - b_t)\times\sqrt{52}",
         "Chaque semaine, on calcule l'écart entre le fonds et l'indice (r_t − b_t). On mesure ensuite à quel point cet "
         "écart varie (écart-type), ramené à l'année.",
         "C'est le risque pris par rapport à l'indice. 1 % : le gérant colle à l'indice. 5 % : il fait des paris très "
         "différents. Au FRR, chaque mandat a un budget de tracking error à ne pas dépasser.",
         "Fiche gérant (vue détaillée)"),
        ("Information ratio",
         "La surperformance vaut-elle le risque pris par rapport à l'indice ?",
         r"IR = \frac{R - R_b}{TE}",
         "On divise la surperformance (R − R_b) par la tracking error (TE).",
         "C'est le Sharpe du gérant actif : combien il gagne de plus que l'indice pour chaque point d'écart. Faire +1 % "
         "avec 1 % de tracking error (IR = 1) vaut mieux que +2 % avec 8 % (IR = 0,25). Au-dessus de 0,5 c'est bon, "
         "au-dessus de 1 c'est excellent.",
         "Classement (vue détaillée), Appel d'offres"),
        ("Up / down capture",
         "Le fonds suit-il les hausses et amortit-il les baisses ?",
         r"\text{Up} = \frac{\overline{r_t \mid b_t>0}}{\overline{b_t \mid b_t>0}}, \quad "
         r"\text{Down} = \frac{\overline{r_t \mid b_t<0}}{\overline{b_t \mid b_t<0}}",
         "On ne garde que les semaines où l'indice monte, et on divise le rendement moyen du fonds par celui de l'indice "
         "ces semaines-là : c'est l'up capture. Même chose avec les semaines de baisse pour le down capture.",
         "Down capture de 80 % : quand l'indice perd 1 %, le fonds ne perd que 0,8 %. L'idéal est un up capture élevé et "
         "un down capture bas : profiter des hausses, amortir les baisses.",
         "Fiche gérant, Appel d'offres"),
        ("Régularité",
         "Le gérant bat-il son indice souvent, ou seulement par à-coups ?",
         r"\frac{\#\{t : r_t > b_t\}}{n}",
         "On compte les semaines où le fonds a fait mieux que l'indice, et on divise par le nombre total de semaines.",
         "55 % veut dire que le gérant gagne plus souvent qu'il ne perd. Un gérant qui surperforme grâce à deux coups de "
         "chance aura une régularité proche de 50 %.",
         "Appel d'offres"),
        ("Surperformance sur 12 mois glissants",
         "Le gérant est-il en train de décrocher ou de se redresser ?",
         r"\prod_{52\ \text{sem.}}(1+r_t) - \prod_{52\ \text{sem.}}(1+b_t)",
         "Chaque semaine, on calcule la performance du fonds et celle de l'indice sur les 52 dernières semaines, et on "
         "fait la différence.",
         "C'est un film plutôt qu'une photo : on voit si la surperformance tient dans le temps. Un passage durable sous "
         "zéro est le premier signal d'une mise sous surveillance.",
         "Fiche gérant (vue détaillée), rapport PDF"),
    ],
    "Valeur ajoutée du gérant (alpha)": [
        ("Alpha de Jensen",
         "Une fois corrigé du risque de marché, le gérant a-t-il apporté quelque chose ?",
         r"r_t - rf_t = \alpha + \beta\,(b_t - rf_t) + \varepsilon_t, \quad \alpha_{\text{an}} = 52\,\alpha",
         "On cherche la droite qui relie le rendement du fonds à celui de l'indice (régression). La pente β dit à quel "
         "point le fonds amplifie le marché. Le point de départ α est ce que le fonds gagne quand le marché ne fait rien.",
         "Un gérant à β = 1,2 bat mécaniquement son indice quand le marché monte, sans aucun talent. L'alpha retire cet "
         "effet : il ne garde que ce qui ne s'explique pas par le marché.",
         "Tableau complet (vue détaillée)"),
        ("Alpha factoriel",
         "Que reste-t-il au gérant une fois retirés tous ses paris de marché ?",
         r"r_t - rf_t = \alpha + \beta_c\,(-\Delta OAS_t) + \beta_\tau\, g_t + \beta_a\, a_t + \varepsilon_t",
         "Même idée que l'alpha de Jensen, avec trois explications au lieu d'une : le crédit (−ΔOAS, la baisse des "
         "spreads), les taux (g, le rendement des obligations d'État) et les actions (a). La régression mesure combien "
         "le fonds dépend de chacun (les β). Ce qui reste, α × 52 par an, est l'alpha factoriel.",
         "En crédit, on peut battre son indice simplement en prenant plus de risque crédit, plus de duration ou des "
         "émetteurs plus fragiles. L'alpha factoriel retire ces paris : ce qui reste, c'est la vraie sélection "
         "d'émetteurs du gérant. C'est l'indicateur central de l'outil.",
         "Classement (« Valeur ajoutée du gérant »), Fiche gérant"),
        ("Contribution d'un facteur",
         "D'où vient le rendement du fonds ?",
         r"\text{contribution}_k = \beta_k \times \overline{\text{facteur}_k} \times 52",
         "Pour chaque facteur, on multiplie la sensibilité du fonds (β) par ce que le facteur a rapporté en moyenne, puis "
         "on passe à l'année.",
         "On découpe le rendement en morceaux : « sur 6 % par an, 4 % viennent du portage crédit, 1 % des taux et 1 % "
         "du gérant ». On voit ainsi ce qui est du talent et ce qui est du marché.",
         "Fiche gérant (vue détaillée)"),
        ("t-stat et Newey-West",
         "L'alpha est-il dû au talent ou au hasard ?",
         r"\begin{aligned} t &= \frac{\hat\alpha}{\text{se}_{NW}(\hat\alpha)} \\ "
         r"\widehat{\text{Var}}(\hat\beta) &= (X'X)^{-1}\, \hat S\, (X'X)^{-1} \\ "
         r"\hat S &= \sum_t \varepsilon_t^2 x_t x_t' + \sum_{l=1}^{4}\Big(1-\tfrac{l}{5}\Big)\sum_t \varepsilon_t\varepsilon_{t-l}"
         r"\,(x_t x_{t-l}' + x_{t-l} x_t') \end{aligned}",
         "On divise l'alpha par son incertitude (son erreur-type). L'erreur-type est calculée avec la méthode de "
         "Newey-West, qui tient compte du fait que les semaines se ressemblent : la deuxième ligne mélange les écarts "
         "d'une semaine avec ceux des 4 semaines précédentes.",
         "Le t répond à : « combien de fois l'alpha est-il plus grand que le bruit ? ». Au-delà de 2, il y a moins de 5 % "
         "de chances que ce soit de la chance. Sans Newey-West, on surestimerait le t, car les prix des obligations peu "
         "liquides sont « lissés » d'une semaine à l'autre.",
         "Verdict"),
        ("Verdict",
         "En une icône : le gérant crée-t-il de la valeur ?",
         r"\begin{cases}\alpha>0,\ t\ge 2 & ✅\ \text{robuste}\\ \alpha<0,\ t\le -2 & ❌\ \text{destruction}\\ "
         r"|\alpha|<0{,}25\,\% & ⚪\ \text{proche de l'indice}\\ \alpha>0,\ t<2 & 🟡\ \text{non démontré}\\ "
         r"\alpha<0,\ t>-2 & 🟠\ \text{pas de valeur ajoutée}\end{cases}",
         "On combine le signe de l'alpha factoriel (positif ou négatif) et son t-stat (fiable ou non).",
         "✅ : le gérant apporte de la valeur, et c'est prouvé. 🟡 : il apporte quelque chose, mais 3 ans ne suffisent pas "
         "à le prouver. ⚪ : il fait comme l'indice ; 0,25 % par an, c'est à peu près le niveau des frais.",
         "Classement, Fiche gérant, rapport PDF"),
    ],
    "Appel d'offres": [
        ("Score sur 100",
         "Quel candidat retenir, selon ce qui compte le plus ?",
         r"\text{centile}_k(i) = \frac{\text{rang}_k(i)}{N}\times 100, \quad "
         r"\text{Score}(i) = \frac{\sum_k w_k\,\text{centile}_k(i)}{\sum_k w_k}",
         "Pour chaque critère, on classe les N candidats et on transforme le rang en note de 0 à 100 (centile). On fait "
         "ensuite la moyenne de ces notes, pondérée par l'importance de chaque critère (w).",
         "On ne peut pas additionner un IR de 0,5, des frais de 0,6 % et un article SFDR : les centiles mettent tout sur "
         "la même échelle. Un score de 80 veut dire que le candidat est meilleur que 80 % des autres, une fois les "
         "critères pondérés. Le rang est inversé quand « plus bas = mieux » (frais, down capture).",
         "Appel d'offres"),
    ],
    "Cades et passif": [
        ("Valeur actuelle du passif",
         "Combien vaut aujourd'hui ce que le FRR doit encore à la Cades ?",
         r"VA = \sum_{k} F\,(1+y)^{-t_k}, \quad F = 1{,}45\ \text{Md€},\ t_k = \text{année}_k - 2025 - 0{,}5",
         "Chaque versement futur de 1,45 Md€ est divisé par (1 + taux) autant de fois qu'il y a d'années à attendre, "
         "puis on additionne. Le taux y est celui de l'OAT 10 ans.",
         "Un euro versé en 2033 coûte moins qu'un euro versé demain, car on peut le placer d'ici là. Les 11,6 Md€ dus "
         "valent ainsi environ 10,1 Md€ aujourd'hui.",
         "Cades et passif"),
        ("Marge de couverture",
         "Le FRR a-t-il plus que ce qu'il doit ?",
         r"\text{Marge} = \text{Actif} - VA",
         "On retire la valeur actuelle des versements dus (VA) à tout ce que possède le FRR (l'actif).",
         "C'est le matelas : 10,6 Md€ selon l'outil, 10,3 Md€ publiés par le FRR fin 2025. C'est l'argent que le FRR "
         "peut exposer au risque pour faire mieux que le coût de la dette. Si la marge tombait à zéro, il ne pourrait "
         "plus prendre de risque.",
         "Cades et passif"),
        ("Sensibilité aux taux",
         "Si les taux montent de 1 point, de combien la valeur baisse-t-elle ?",
         r"D_{\text{passif}} = \frac{\sum_k t_k F (1+y)^{-t_k}}{VA\,(1+y)}, \quad "
         r"D_{\text{actif}} = \sum_i \text{poids}_i \times \text{sensi}_i",
         "Pour le passif : la date moyenne des versements, pondérée par leur valeur actuelle, divisée par (1 + taux). "
         "Pour l'actif : la moyenne des sensibilités de chaque ligne, pondérée par son poids.",
         "Une sensibilité de 3,7 veut dire que la valeur baisse de 3,7 % si les taux montent de 1 point. Le FRR veut que "
         "l'actif et le passif réagissent de la même façon, pour que la marge ne dépende pas des taux.",
         "Cades et passif (vue détaillée)"),
        ("Stress test",
         "Que deviendrait le matelas en cas de crise ?",
         r"\text{choc}_i = \beta_i\,\Delta A - S^{\tau}_i\,\Delta\tau - S^{s}_i\, m_i\,\Delta s, \quad "
         r"\Delta\text{Actif} = \sum_i \text{montant}_i\,\text{choc}_i, \quad \Delta\text{Passif} = -D\,\Delta\tau\, VA",
         "Pour chaque ligne du portefeuille, on applique trois chocs : la baisse des actions (ΔA) multipliée par son "
         "bêta, la hausse des taux (Δτ) multipliée par sa sensibilité, et la hausse des spreads (Δs) multipliée par sa "
         "sensibilité au crédit. On additionne pour tout l'actif, et on applique aussi le choc de taux au passif.",
         "On voit si le FRR resterait capable de payer la Cades après un krach. Dans le scénario de novembre 2026, le "
         "matelas passerait de 10,6 à 9,4 Md€.",
         "Cades et passif"),
        ("Création de valeur d'un mandat",
         "Ce mandat rapporte-t-il plus que ce que coûte la dette de l'État ?",
         r"\text{Valeur} = \text{encours}\times(R_{€} - \overline{OAT}), \quad "
         r"\text{Apport du gérant} = \text{encours}\times(R_{€} - R_{b,€})",
         "On multiplie l'argent confié au gérant (l'encours) par l'écart entre son rendement en euros et le taux de l'OAT. "
         "La deuxième ligne fait la même chose avec l'indice au lieu de l'OAT. Pour le High Yield US, on retire d'abord "
         "le coût de couverture du dollar.",
         "La première ligne dit combien le mandat crée de valeur pour le FRR, la deuxième quelle part revient au talent "
         "du gérant. La différence vient du marché du crédit lui-même.",
         "Cades et passif"),
        ("Futures pour revenir à l'allocation",
         "Combien acheter ou vendre pour respecter l'allocation décidée ?",
         r"\text{Futures} = -(\text{poids réel} - \text{poids cible})\times\text{Actif}",
         "On mesure l'écart entre le poids réel d'une poche et son poids cible, et on le convertit en euros.",
         "Positif : il manque de cette poche, on achète des futures. Le mandat overlay corrige ainsi les écarts sans "
         "toucher aux mandats des gérants.",
         "Cades et passif"),
    ],
    "Couverture de change": [
        ("Notionnel couvert",
         "Quel montant de devises faut-il vendre à terme ?",
         r"N = h \times \text{valeur du placement en devise}",
         "On multiplie la valeur du placement en dollars (ou en yens…) par le ratio de couverture visé, h.",
         "Avec h = 90 %, pour 1 Md$ placé, on vend 900 M$ à terme. Si le dollar baisse, ces contrats gagnent et "
         "compensent la perte sur le placement.",
         "Couverture de change"),
        ("Résultat de la couverture",
         "Combien la couverture a-t-elle rapporté ou coûté ?",
         r"\text{P\&L}_t = -N\Big(\frac{1}{X_t} - \frac{1}{X_{t-1}}\Big), \quad "
         r"\text{portage}_t = \frac{N}{X_{t-1}}\,(€STR - \text{taux devise})\,\frac{j}{360}",
         "Première partie : l'effet de la variation du cours de change (X) sur les devises vendues à terme. Deuxième "
         "partie : le coût de portage, l'écart entre le taux euro et le taux de la devise sur la durée.",
         "Quand le dollar baisse, la couverture gagne : +163 M€ pour le FRR en 2025. Mais quand les taux américains "
         "dépassent les taux européens, se couvrir coûte cet écart, environ 1,5 % par an aujourd'hui.",
         "Couverture de change"),
        ("Écart au ratio cible",
         "La couverture est-elle encore au bon niveau ?",
         r"\text{ratio} = \frac{N}{\text{valeur du placement}}, \quad \text{écart} = \text{ratio} - h",
         "On divise le montant couvert par la valeur actuelle du placement, et on compare à la cible de 90 %.",
         "Le placement bouge entre deux réajustements, donc le ratio dérive. S'il sort de la bande de tolérance, il faut "
         "racheter ou vendre des devises : c'est le suivi des écarts par devise de la mission 3.",
         "Couverture de change"),
        ("Exposition au change",
         "Quelle part du FRR reste exposée aux devises ?",
         r"\frac{\sum_{\text{devises}}(1-\text{ratio})\times\text{exposition} + \text{émergents}}{\text{Actif}} \le 20\,\%",
         "On additionne la partie non couverte de chaque devise et les devises émergentes (jamais couvertes), puis on "
         "divise par l'actif total.",
         "Le FRR n'a pas le droit de dépasser 20 % (16,9 % fin 2025). Plus on est loin de la limite, plus on a de marge "
         "de manœuvre.",
         "Couverture de change"),
    ],
    "Options (protection actions)": [
        ("Prix d'un put (Black-Scholes)",
         "Combien coûte une assurance contre la baisse d'un indice ?",
         r"d_1 = \frac{\ln(S/K) + (r - q + \sigma^2/2)T}{\sigma\sqrt T}, \quad d_2 = d_1 - \sigma\sqrt T, \quad "
         r"\text{Put} = K e^{-rT} N(-d_2) - S e^{-qT} N(-d_1)",
         "d₁ et d₂ mesurent la distance entre le niveau de l'indice (S) et le seuil de protection (K), en tenant compte "
         "de la volatilité (σ), de la durée (T), des taux (r) et des dividendes (q). N() transforme ces distances en "
         "probabilités. Le prix est ce qu'on toucherait en moyenne, ramené à aujourd'hui.",
         "Plus le marché est agité (σ élevée) ou plus la protection est longue (T), plus l'assurance coûte cher. C'est "
         "pour ça que se protéger après une hausse de la volatilité coûte plus cher.",
         "Protection actions"),
        ("Put spread",
         "Comment se protéger moins cher ?",
         r"\text{Valeur} = \text{Put}(K_1) - \text{Put}(K_2), \quad "
         r"\text{Payoff} = \max(K_1 - S, 0) - \max(K_2 - S, 0)",
         "On achète une protection à 95 % du niveau de l'indice (K₁) et on en revend une à 85 % (K₂). À l'échéance, on "
         "touche la baisse de l'indice entre ces deux niveaux.",
         "On est protégé entre −5 % et −15 %, pas au-delà. En échange, la protection coûte beaucoup moins cher. Le FRR "
         "a payé 43,3 M€ en 2025 pour ces assurances, une année où la bourse a monté.",
         "Protection actions"),
        ("Grecques",
         "Comment la valeur de la protection réagit-elle au marché ?",
         r"\Delta_{put} = -e^{-qT}N(-d_1), \quad \Gamma = \frac{e^{-qT}\varphi(d_1)}{S\sigma\sqrt T}, \quad "
         r"\nu = S e^{-qT}\varphi(d_1)\sqrt T",
         "Ce sont les dérivées du prix : par rapport à l'indice (delta), à la variation du delta (gamma), à la volatilité "
         "(vega), et au temps qui passe (theta).",
         "Delta : la protection équivaut à vendre tant d'actions. Gamma : la protection devient plus efficace à mesure "
         "que l'indice baisse. Vega : elle prend de la valeur quand le marché s'agite. Theta : elle perd un peu de "
         "valeur chaque jour.",
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
    st.markdown("Pour chaque indicateur : la question à laquelle il répond, la formule, ce qu'elle calcule en mots, "
                "et ce que le résultat veut dire. Puis les hypothèses retenues et leurs raisons.")
    t_ind, t_hyp, t_data = st.tabs(["📐 Indicateurs et formules", "🧭 Hypothèses et choix", "🗂️ Données, vérifications, limites"])
    with t_ind:
        for family, items in INDICATORS.items():
            st.markdown(f"#### {family}")
            for name, question, formula, calc, meaning, where in items:
                with st.expander(f"**{name}** : {question}"):
                    if r", \quad " in formula:  # une équation par ligne, lisible même sur écran étroit
                        formula = r"\begin{gathered}" + formula.replace(r", \quad ", r" \\ ") + r"\end{gathered}"
                    st.latex(formula)
                    st.markdown(f"**Ce que calcule la formule.** {calc}\n\n**Ce que ça veut dire.** {meaning}")
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
