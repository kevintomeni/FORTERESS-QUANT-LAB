# FORTERESS QUANT LAB — démarrage local sécurisé
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Read-SecretText([string]$Prompt) {
  $secure = Read-Host $Prompt -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

$env:MT5_BRIDGE_TOKEN = Read-SecretText "Colle MT5_BRIDGE_TOKEN depuis Vercel (saisie masquée)"
$env:TELEGRAM_BOT_TOKEN = Read-SecretText "Colle le jeton du bot Telegram (saisie masquée)"
$env:TELEGRAM_CHAT_ID = Read-Host "Identifiant du chat Telegram"
if ([string]::IsNullOrWhiteSpace($env:MT5_BRIDGE_TOKEN)) { throw "MT5_BRIDGE_TOKEN est obligatoire." }
if ([string]::IsNullOrWhiteSpace($env:TELEGRAM_BOT_TOKEN)) { throw "TELEGRAM_BOT_TOKEN est obligatoire pour activer Telegram." }
if ([string]::IsNullOrWhiteSpace($env:TELEGRAM_CHAT_ID)) { throw "TELEGRAM_CHAT_ID est obligatoire pour activer Telegram." }

$python = Join-Path $root "mt5-engine\.venv\Scripts\python.exe"
$bridge = Join-Path $root "mt5-engine\bridge.py"
if (!(Test-Path $python)) { throw "Python du projet introuvable : $python" }
if (!(Test-Path $bridge)) { throw "Pont MT5 introuvable : $bridge" }
Write-Host "Démarrage du pont MT5 en lecture seule. Ne fermez pas cette fenêtre." -ForegroundColor Cyan
& $python $bridge
