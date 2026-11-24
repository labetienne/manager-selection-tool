# Manager Selection Tool – Crédit Euro & High Yield US

Prototype construit pour le stage Gestion déléguée du FRR. Il couvre deux missions :
- **mission 2** : analyser la performance, les facteurs et les risques des mandats et des fonds ;
- **mission 5** : préparer les analyses des appels d'offres, cette année sur le crédit euro et le High Yield US.

## Univers : les gérants actuels du FRR
Sources : *Listes des marchés publics conclus par le FRR* et rapport annuel 2025 (fondsdereserve.fr).

| Segment | Marché | Sociétés de gestion titulaires |
|---|---|---|
| High Yield US | 2022FRR01 | CPR AM (sous-gérant PGIM), JPMorgan AM, Nomura AM, AllianceBernstein |
| Crédit € haut rendement | 2020FRR01 lot 2 | BlackRock, Candriam, Degroof Petercam, DWS, Columbia Threadneedle |
| Crédit € investment grade | 2020FRR01 lot 1 | BNP PAM (ex-AXA IM), CPR/M&G, CPR/Union Investment, BlackRock, DWS |

Les mandats étant dédiés et non publics, chaque gérant est représenté par un fonds ouvert de la même stratégie
(détaillé dans `data.py`). 63 candidats externes et des ETF servent de points de comparaison.

## Onglets
| Onglet | Contenu | Mission |
|---|---|---|
| Classement des gérants | gérants du FRR face aux candidats et aux ETF, verdict sur la valeur ajoutée | 2 |
| Fiche gérant | performance, pire baisse, comportement en baisse, alpha factoriel, fiche PDF d'une page | 2 |
| Appel d'offres | note sur 100 pondérable, critères éliminatoires (dont SFDR), podium, robustesse, export Excel | 5 |
| Méthode et formules | chaque indicateur (question, formule, calcul en mots, sens), hypothèses, données, limites | 2, 5 |

Une vue simple (par défaut) montre l'essentiel avec un encadré « En clair » ; la vue détaillée affiche tous les
indicateurs. Le bouton de la barre latérale produit un rapport PDF de suivi des 14 gérants.

## Lancer
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
.venv/bin/python test_analytics.py   # vérifications des calculs
```
Les données (Yahoo Finance, FRED) sont en cache dans `data/cache.pkl` ; bouton « Rafraîchir » pour les mettre à jour.

## Fichiers
- `data.py` : univers de fonds, téléchargement et cache des données
- `analytics.py` : indicateurs, régression factorielle (Newey-West), verdict, scoring
- `app.py` : interface Streamlit
- `methode.py` : contenu de l'onglet Méthode et formules
- `report.py` : fiche gérant PDF ; `report_frr.py` : rapport de suivi des gérants (PDF)
- `test_analytics.py` : 4 vérifications (indicateurs, régression, scoring, verdict)
- `NOTES_FRR.md` : synthèse du site du FRR

## Limites
Fonds ouverts ≠ mandats dédiés · biais du survivant · environ 3 ans d'historique pour les indices ICE · pas de
positions par mandat, donc pas d'analyse par secteur. Le quantitatif sert à présélectionner ; la décision repose
sur la due diligence qualitative.
