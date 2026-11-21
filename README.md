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

**Candidats externes** (filtre « Univers » dans la barre latérale) : 63 fonds d'autres grands gérants
(PIMCO, T. Rowe Price, Neuberger Berman, Amundi, Robeco, Pictet, Muzinich, Lazard, Ostrum…), données
Morningstar via Yahoo Finance, pour situer les gérants du FRR face au marché comme dans un appel d'offres.

## Fonctionnalités
| Onglet | Contenu | Mission du stage |
|---|---|---|
| Synthèse gérants | gérants FRR vs candidats vs ETF : perf., IR, alpha factoriel, verdicts | 1, 2 – suivi des mandats |
| Gérant | diagnostic d'un gérant, décomposition du rendement, **fiche PDF** (rapport au CSG) | 2, 4 – création de valeur, CSG Performance |
| Portefeuille FRR | **titres détenus au 30/09/2026** : échéances, émetteurs, concentration, **limite d'emprise 3 %**, OPC | 2, 4 – risques, suivi |
| Overlay change | couverture **par devise** (USD, JPY, GBP, CHF), cible 90 %/100 %, **limite 20 %**, actions à mener | 3 – déviations par devise |
| Overlay dérivés | put spread Euro Stoxx 50 / S&P 500, reporting hebdo, scénarios ; **futures tactiques** vs allocation | 3 – options, exposition tactique |
| Appel d'offres | scoring pondérable, critères éliminatoires, podium, robustesse, export Excel | 5 – AO HY € 2026 |

Contexte FRR (gouvernance, allocation, overlay, risques) : voir `NOTES_FRR.md`.

**ESG** : classification SFDR (article 6/8/9) de chaque fonds européen, sourcée, dans `data/sfdr.csv` ; utilisée comme critère de scoring et comme filtre « article 8 minimum » (règle de sélection de fonds du FRR).

## Lancer
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
.venv/bin/python test_analytics.py   # vérifications des calculs (données synthétiques)
```
Les données (Yahoo Finance + FRED) sont mises en cache dans `data/cache.pkl` : l'app tourne hors ligne.
Bouton « Rafraîchir » dans la barre latérale pour mettre à jour.

## Fichiers
- `data.py` — univers de fonds, téléchargement et cache des données
- `analytics.py` — métriques, régression Newey-West, scoring, simulation de couverture, Black-Scholes
- `app.py` — interface Streamlit
- `report.py` — fiche gérant PDF (matplotlib)
- `report_frr.py` — rapport de suivi des 14 gérants FRR (PDF 6 pages, bouton dans la barre latérale)
- `test_analytics.py` — 7 vérifications : régression, scoring, couverture, Black-Scholes, backtest options

## Limites
ETF/fonds ouverts ≠ mandats dédiés · biais du survivant · ~3 ans d'historique pour les indices ICE ·
vol implicite approchée · forward = parité des taux couverte sans basis. Le quantitatif sert à
**pré-sélectionner** ; la décision repose sur la due diligence qualitative.
