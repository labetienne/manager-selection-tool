# Manager Selection Tool – Crédit Euro & High Yield US

Prototype d'outil d'aide à la **sélection et au suivi de gérants délégués**, construit en préparation
du stage Gestion Déléguée du FRR (appels d'offres 2027 : mandats Crédit Euro et High Yield US).

## Univers : les gérants actuels du FRR
Source : *Listes des marchés publics conclus par le FRR* (fondsdereserve.fr, rubrique Publications).

| Segment | Marché | Gérants attributaires |
|---|---|---|
| High Yield US | 2022FRR01 (février 2023) | BFT IM, JPMorgan AM, Nomura AM, AllianceBernstein |
| Crédit € haut rendement | 2020FRR01 lot 2 (2021) | BlackRock, Candriam, Degroof Petercam, DWS, Columbia Threadneedle |
| Crédit € investment grade | 2020FRR01 lot 1 (2021) | AXA IM (BNP Paribas AM), BFT IM – M&G, BFT IM – Union Investment, BlackRock, DWS |

Les mandats étant dédiés et non publics, chaque gérant est représenté par un **fonds ouvert de la même
stratégie** (proxy, détaillé dans `data.py`), et comparé à une alternative passive (ETF).

## Fonctionnalités
| Onglet | Contenu | Lien avec les missions du stage |
|---|---|---|
| Vue d'ensemble | perf. cumulée, couple rendement/risque, tableau comparatif | suivi des classes d'actifs cotées |
| Analyse gérant | TE, IR, capture ratios, drawdown, **régression crédit / taux / actions → alpha factoriel**, synthèse auto | analyse perf./facteurs/risques, création de valeur des gérants |
| Scoring appel d'offres | grille multicritère pondérable, radar, short-list, export Excel | analyses d'appels d'offres |
| Overlay change | simulation couverture EUR/USD par forwards, coût de portage €STR–SOFR, suivi des déviations du ratio | suivi de la couverture devise |
| Overlay options | put spread Euro Stoxx 50 (Black-Scholes), grecques, **reporting hebdomadaire** P&L | reporting de suivi options |

## Lancer
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```
Les données (Yahoo Finance + FRED) sont mises en cache dans `data/cache.pkl` : l'app tourne hors ligne.
Bouton « Rafraîchir » dans la barre latérale pour mettre à jour.

## Fichiers
- `data.py` — univers de fonds, téléchargement et cache des données
- `analytics.py` — métriques, régression Newey-West, scoring, simulation de couverture, Black-Scholes
- `app.py` — interface Streamlit

## Limites
ETF/fonds ouverts ≠ mandats dédiés · biais du survivant · ~3 ans d'historique pour les indices ICE ·
vol implicite approchée · forward = parité des taux couverte sans basis. Le quantitatif sert à
**pré-sélectionner** ; la décision repose sur la due diligence qualitative.
