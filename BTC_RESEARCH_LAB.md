# BTC/USD Research Lab — FORTERESS QUANT LAB

## Objectif
Prototype de recherche séparé du dashboard de trading. BTC/USD est le premier instrument de recherche. Le mode de travail choisi est simulation et backtests historiques, sans risque financier et sans exécution automatique.

## Démarrer
Ouvrir `btc-lab.html` dans un navigateur, ou la page publiée par Vercel après déploiement de la branche/PR.

## Sources et étiquetage
- **Coinbase public** : historique spot BTC-USD, bougies de 15 minutes obtenues via l'API publique Coinbase Exchange. Ce n'est pas un flux Weltrade ni MT5 et ne doit pas être étiqueté comme tel.
- **Simulation locale** : OHLCV artificiels générés côté navigateur. Toujours étiquetés SIMULATION; aucune donnée simulée n'est présentée comme une cotation réelle.
- La validation vérifie les champs OHLC, valeurs positives, ordre chronologique, doublons et ancienneté de la dernière bougie. Si la requête réelle échoue, il n'y a pas de remplacement silencieux par la simulation.

## Modules
- **ICT/OPR prototype** : OPR = première heure UTC (quatre bougies M15); détection explicable de cassure récente et FVG approximée. Ceci n'est pas une implémentation exhaustive de la méthodologie ICT.
- **Order Flow** : explicitement indisponible avec les seules bougies OHLCV. Aucun delta/CVD/footprint inventé. Une source de transactions ou de footprint avec côté agresseur est nécessaire.
- **Backtest** : règles exploratoires avec frais et slippage réglables; entrée à la bougie suivante; rapport des trades, rendement composé et drawdown. Ce prototype doit être audité et validé hors échantillon avant de tirer toute conclusion. Les frais/slippage sont des hypothèses saisies par l'utilisateur et non des tarifs garantis.

## Sécurité
Page sans connecteur de courtier, sans API de trading, sans formulaire d'ordre et sans exécution automatique. Les mots LONG/SHORT du tableau de backtest sont des positions hypothétiques dans un calcul historique, pas des ordres.
