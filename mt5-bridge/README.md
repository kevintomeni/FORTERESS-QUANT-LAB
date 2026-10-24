# FORTERESS QUANT LAB — pont MT5 Windows (lecture seule)

Ce service relie le terminal MetaTrader 5 installé sur **ton PC Windows** aux endpoints Vercel. Il lit uniquement les données du compte, les positions, les deals, les cotations, l'historique M15 et une tendance descriptive SMA 8/21. **Aucune fonction d'envoi, modification ou clôture d'ordre n'existe dans ce service.**

## Architecture et limites

Vercel ne peut pas appeler directement un terminal qui tourne sur ton PC. Il faut que Windows, MT5 et le processus Python restent allumés et connectés, et exposer le service local au moyen d'un tunnel HTTPS. Le tunnel Cloudflare Quick Tunnel fournit une URL temporaire qui peut changer au redémarrage. Pour une URL stable, il faut configurer un tunnel Cloudflare nommé avec un domaine que tu contrôles.

Le bridge écoute uniquement sur `127.0.0.1:8787`, pas sur toutes les interfaces réseau. Toutes les routes sont protégées par `Authorization: Bearer <token>`. Ne partage jamais le token et ne le committe pas dans Git.

## 1. Préparer MT5

1. Sur Windows, installe/ouvre le terminal MetaTrader 5 officiel de ton courtier.
2. Connecte-toi à ton compte et vérifie qu'une cotation apparaît dans Observatoire du marché.
3. Vérifie le nom exact du symbole or chez ton courtier. Il peut être `XAUUSD`, `XAUUSD.`, `GOLD` ou un autre nom. La configuration par défaut est `XAUUSD`; adapte `MT5_DEFAULT_SYMBOL` si nécessaire.
4. Laisse MT5 ouvert pendant les tests.

## 2. Installer le bridge

Dans PowerShell, depuis le dossier du dépôt :

```powershell
cd mt5-bridge
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si PowerShell bloque l'activation, utilise l'invite de commandes (cmd) ou lance directement `.venv\Scripts\python.exe -m pip install -r requirements.txt`.

Génère un jeton secret fort. Exemple PowerShell :

```powershell
$bytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$TOKEN = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
$env:MT5_BRIDGE_TOKEN = $TOKEN
$env:MT5_DEFAULT_SYMBOL = "XAUUSD"
# Facultatif si MT5 n'est pas détecté automatiquement :
# $env:MT5_TERMINAL_PATH = "C:\Program Files\MetaTrader 5\terminal64.exe"
```

**Conserve ce terminal PowerShell ouvert** : les variables d'environnement et le jeton sont définis dans sa session. Ne colle pas le jeton dans le chat ni dans un fichier commité.

Démarre le bridge :

```powershell
uvicorn bridge:app --host 127.0.0.1 --port 8787
```

Dans un deuxième PowerShell, vérifie le serveur local avec le même token :

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health -Headers @{ Authorization = "Bearer $env:MT5_BRIDGE_TOKEN" }
```

Si le deuxième terminal ne connaît pas la variable, définis temporairement le token dans ce terminal avec la valeur conservée localement, sans l'imprimer ni le partager. Le résultat attendu inclut `ok: true`, `connected: true` et `read_only: true`. Si l'initialisation MT5 échoue, vérifie que Python et MT5 sont installés sur la même machine, que MT5 est ouvert/connecté et que l'architecture/version Python est compatible avec le paquet MetaTrader5.

## 3. Exposer le bridge en HTTPS

Installe `cloudflared` depuis la documentation officielle Cloudflare, puis dans un troisième PowerShell :

```powershell
cloudflared tunnel --url http://127.0.0.1:8787
```

Cloudflare affiche une URL HTTPS temporaire de forme `https://....trycloudflare.com`. Ne partage pas cette URL publiquement : elle expose le point d'accès du bridge, même si les routes exigent un jeton. Pour un usage durable, configure un tunnel nommé avec ton propre domaine et les règles de sécurité adaptées.

## 4. Configurer Vercel

Dans le projet Vercel **forteress-quant-lab** → Settings → Environment Variables, définis les deux variables en **Production** (et Preview si tu en as besoin) :

- `MT5_BRIDGE_URL` = URL HTTPS du tunnel, sans ajouter `/health` ni `/api`, par exemple `https://ton-sous-domaine.example.com`
- `MT5_BRIDGE_TOKEN` = le même jeton généré sur Windows

Saisis les valeurs directement dans Vercel. **Ne les ajoute pas à GitHub, ne les mets pas dans une capture d'écran et ne me les envoie pas dans le chat.** Puis redéploie le projet Vercel pour charger les variables.

## 5. Vérifier la connexion

Ouvre d'abord `https://TON-DASHBOARD/api/mt5/health`. Le résultat doit avoir `ok: true` et `status: "connected"`. Ensuite vérifie :

- `/api/mt5/accounts`
- `/api/mt5/positions`
- `/api/mt5/deals?days=30&count=100`
- `/api/mt5/quote?symbol=XAUUSD`
- `/api/mt5/history?count=100`
- `/api/mt5/signals`

Si le courtier utilise un autre nom de symbole, change `MT5_DEFAULT_SYMBOL` dans le processus bridge et utilise ce symbole dans la cotation du dashboard. L'historique utilise ce symbole configuré et l'unité M15.

## Notes de sécurité

- Service conçu pour lecture seule ; il n'expose pas les fonctions de trading MT5.
- Ne redirige pas le port 8787 directement sur ton routeur. Utilise HTTPS via le tunnel.
- Le token doit rester privé et comporter au moins 32 caractères.
- Le bridge n'est disponible que lorsque le PC, MT5, Python et le tunnel fonctionnent.
- La tendance SMA est descriptive, pas une recommandation d'achat/vente.
