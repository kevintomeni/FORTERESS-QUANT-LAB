import requireSupabaseUser from "../_lib/require-supabase-user.js";

function sendError(res, status, code, message, extra = {}) {
  return res.status(status).json({ ok: false, error: message, code, ...extra });
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");
  if (!(await requireSupabaseUser(req, res))) return;
  res.setHeader("Cache-Control", "no-store, max-age=0");
  if (req.method !== "GET") { res.setHeader("Allow", "GET"); return sendError(res,405,"METHOD_NOT_ALLOWED","Méthode non autorisée"); }
  const base = process.env.MT5_BRIDGE_URL;
  const token = process.env.MT5_BRIDGE_TOKEN;
  if (!base || !token) return sendError(res,500,"BRIDGE_CONFIG_MISSING","Configuration du pont MT5 manquante", { checks: { urlConfigured: Boolean(base), tokenConfigured: Boolean(token) } });
  let target;
  try { target = new URL(base); } catch { return sendError(res,500,"BRIDGE_URL_INVALID","L’URL du pont MT5 est invalide"); }
  if (!["https:", "http:"].includes(target.protocol)) return sendError(res,500,"BRIDGE_URL_INVALID","Le protocole de l’URL du pont MT5 est invalide");
  const symbol = String(req.query.symbol || "XAUUSD").trim().toUpperCase();
  if (!/^[A-Z0-9._-]{3,20}$/.test(symbol)) return sendError(res,400,"INVALID_SYMBOL","Symbole invalide");
  target.pathname = target.pathname.replace(/\/+$/, "") + "/quote";
  target.search = new URLSearchParams({symbol}).toString();
  try {
    const upstream = await fetch(target, { headers: { Authorization: `Bearer ${token}`, Accept: "application/json" }, signal: AbortSignal.timeout(12000), cache: "no-store" });
    const raw = await upstream.text();
    let data; try { data = JSON.parse(raw); } catch { return sendError(res,502,"BRIDGE_INVALID_RESPONSE","Le pont MT5 a renvoyé une réponse non JSON", { bridgeStatus: upstream.status, responsePreview: raw.slice(0,200) }); }
    if (!upstream.ok) return sendError(res,502,"BRIDGE_REJECTED","Le pont MT5 a refusé la demande", { bridgeStatus: upstream.status, bridgeError: data.error || "Erreur du pont", symbol });
    return res.status(200).json(data);
  } catch (error) {
    const timeout = error?.name === "TimeoutError" || error?.name === "AbortError";
    return sendError(res,502,timeout ? "BRIDGE_TIMEOUT" : "BRIDGE_UNREACHABLE", timeout ? "Le pont MT5 ne répond pas dans le délai imparti" : "Impossible de joindre le pont MT5", { diagnostic: error?.cause?.code || error?.name || "FETCH_FAILED" });
  }
}