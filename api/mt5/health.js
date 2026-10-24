export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");
  if (req.method !== "GET") { res.setHeader("Allow", "GET"); return res.status(405).json({ok:false,error:"Méthode non autorisée",code:"METHOD_NOT_ALLOWED"}); }
  const base=process.env.MT5_BRIDGE_URL, token=process.env.MT5_BRIDGE_TOKEN;
  if (!base || !token) return res.status(500).json({ok:false,status:"configuration_missing",error:"Configuration du pont MT5 manquante",checks:{urlConfigured:Boolean(base),tokenConfigured:Boolean(token)}});
  let target;
  try { target=new URL(base); } catch { return res.status(500).json({ok:false,status:"configuration_invalid",error:"L’URL du pont MT5 est invalide"}); }
  if (!["https:","http:"].includes(target.protocol)) return res.status(500).json({ok:false,status:"configuration_invalid",error:"Le protocole de l’URL du pont MT5 est invalide"});
  target.pathname=target.pathname.replace(/\/+$/,"")+"/health";
  target.search="";
  try {
    const upstream=await fetch(target,{headers:{Authorization:"Bearer "+token,Accept:"application/json"},signal:AbortSignal.timeout(8000),cache:"no-store"});
    const raw=await upstream.text(); let data;
    try {data=JSON.parse(raw);} catch {return res.status(502).json({ok:false,status:"invalid_response",error:"Le pont MT5 a renvoyé une réponse non JSON",bridgeStatus:upstream.status,responsePreview:raw.slice(0,200)});}
    const ok=upstream.ok && data.ok===true;
    return res.status(ok?200:502).json({ok,status:ok?"connected":"bridge_error",bridgeStatus:upstream.status,bridge:data});
  } catch(error) {
    const timeout=error?.name==="TimeoutError"||error?.name==="AbortError";
    return res.status(502).json({ok:false,status:timeout?"bridge_timeout":"bridge_unreachable",error:timeout?"Délai de connexion au pont MT5 dépassé":"Impossible de joindre le pont MT5",diagnostic:error?.cause?.code||error?.name||"FETCH_FAILED"});
  }
}