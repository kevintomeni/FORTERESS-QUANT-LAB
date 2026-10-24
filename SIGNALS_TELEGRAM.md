# Signaux MT5 et alertes Telegram

## Fonctionnement
- Le pont Python calcule un croisement SMA 8/21 à partir des bougies XAUUSD M15 clôturées.
- Les signaux sont désactivés si la cotation MT5 a plus de 30 minutes.
- Le dashboard interroge `/api/mt5/signals` et n'affiche pas de signal exploitable si le flux est périmé ou inaccessible.
- Le pont peut envoyer une alerte Telegram une seule fois par bougie et direction pendant son exécution.
- Ce projet ne transmet aucun ordre au courtier. BUY/SELL signifie signal technique uniquement.

## Configuration Telegram (sur le PC qui exécute le pont)
1. Créer un bot auprès de `@BotFather` et copier son jeton dans un gestionnaire de secrets local.
2. Ouvrir une conversation avec le bot et lui envoyer `/start`.
3. Récupérer l'identifiant de chat avec l'API Telegram `getUpdates` depuis un navigateur ou un outil local sécurisé. Ne pas publier le jeton ni l'identifiant.
4. Dans la fenêtre PowerShell qui lancera le pont, définir les trois variables suivantes. Remplacer les valeurs entre guillemets uniquement sur son propre PC :

```powershell
$env:MT5_BRIDGE_TOKEN = Read-Host "Jeton MT5 partagé avec Vercel"
$env:TELEGRAM_BOT_TOKEN = Read-Host "Jeton du bot Telegram" 
$env:TELEGRAM_CHAT_ID = Read-Host "Identifiant du chat Telegram"
.mt5-engine\.venv\Scripts\python.exe .\mt5-engine\bridge.py
```

Les valeurs saisies par `Read-Host` ne sont pas masquées par défaut. Pour une saisie masquée du jeton du bot, utiliser `Read-Host -AsSecureString` puis convertir en mémoire avant de lancer le pont. Ne jamais committer les secrets dans Git.

## Limites à connaître
- Les alertes ne peuvent partir que si le PC, MT5, le pont et le tunnel sont en fonctionnement et que le marché fournit des cotations récentes.
- La détection SMA 8/21 est un exemple technique, pas une stratégie validée ni une recommandation d'investissement.
- L'identifiant de dernier signal est conservé en mémoire : un redémarrage du pont peut donc permettre une nouvelle alerte sur la même bougie.
