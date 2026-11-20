# Manager Selection Tool – Crédit Euro & High Yield US

Prototype d'outil d'aide à la **sélection et au suivi de gérants délégués**, construit en préparation
du stage Gestion Déléguée du FRR (appels d'offres 2027 : mandats Crédit Euro et High Yield US).

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
