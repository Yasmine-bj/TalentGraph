# seed/ — Données de démonstration

`demo_offers.json` : **1 794 offres d'emploi** chargées automatiquement par le conteneur
`loader` au premier démarrage (`docker compose up`).

- **Source** : offres d'emploi fournies par [Adzuna](https://www.adzuna.fr), via son API,
  utilisées ici à des fins académiques (projet ENSIIE).
- **Échantillon stratifié** de nos 7 298 offres : 20 % de chaque groupe (région × contrats),
  plus toutes les alternances. Fabriqué par `worker/make_demo_seed.py` (tirage reproductible).

Les fichiers complets (`offers_sample.json`, `raw/`) ne sont pas versionnés.
