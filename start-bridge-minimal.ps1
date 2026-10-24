# FORTERESS QUANT LAB — démarrage minimal du pont MT5 en lecture seule
# Nécessite Windows, MetaTrader 5 installé/ouvert et mt5-engine\.venv déjà créé.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$secure = Read-Host "MT5_BRIDGE_TOKEN (même valeur que Vercel, saisie masquée)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $env:MT5_BRIDGE_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if ([string]::IsNullOrWhiteSpace($env:MT5_BRIDGE_TOKEN)) { throw "MT5_BRIDGE_TOKEN est obligatoire." }

# Telegram est facultatif : le pont doit pouvoir démarrer sans bot.
$env:TELEGRAM_BOT_TOKEN = ""
$env:TELEGRAM_CHAT_ID = ""
$python = Join-Path $root "mt5-engine\.venv\Scripts\python.exe"
$bridge = Join-Path $root "mt5-engine\bridge.py"
if (!(Test-Path $python)) { throw "Python du projet introuvable : $python. Le venv doit être installé d'abord." }
if (!(Test-Path $bridge)) { throw "Pont MT5 introuvable : $bridge" }

Write-Host "Vérifie que MetaTrader 5 est ouvert et connecté à ton compte de démonstration." -ForegroundColor Yellow
Write-Host "Pont lecture seule sur http://127.0.0.1:8765 — ne ferme pas cette fenêtre." -ForegroundColor Cyan
& $python $bridge
