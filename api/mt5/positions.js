import requireSupabaseUser from "../_lib/require-supabase-user.js";

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");
  if (!(await requireSupabaseUser(req, res))) return;
  if (req.method !== "GET") { res.setHeader("Allow", "GET"); return res.status(405).json({ok:false,error:"Method not allowed"}); }
  const base=process.env.MT5_BRIDGE_URL, token=process.env.MT5_BRIDGE_TOKEN;
  if(!base||!token)return res.status(500).json({ok:false,error:"Configuration du pont MT5 manquante"});
  try { const r=await fetch(base.replace(/\/+$/,"")+"/positions",{headers:{Authorization:"Bearer "+token},signal:AbortSignal.timeout(12000),cache:"no-store"}); const t=await r.text();let d;try{d=JSON.parse(t)}catch{d={error:t.slice(0,500)}}return res.status(r.ok?200:502).json(d); }
  catch{return res.status(502).json({ok:false,error:"Pont MT5 inaccessible"});}
}