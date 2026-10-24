import requireSupabaseUser from "../_lib/require-supabase-user.js";

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store, max-age=0");
  if (!(await requireSupabaseUser(req, res))) return;
 if (req.method !== "GET") { res.setHeader("Allow", "GET"); return res.status(405).json({ok:false,error:"Method not allowed"}); }
 const base=process.env.MT5_BRIDGE_URL, token=process.env.MT5_BRIDGE_TOKEN;
 if(!base||!token)return res.status(500).json({ok:false,error:"Configuration du pont MT5 manquante"});
 try {
  const r=await fetch(base.replace(/\/+$/,"")+"/signals",{headers:{Authorization:"Bearer "+token},signal:AbortSignal.timeout(12000),cache:"no-store"});
  const body=await r.text(); let data; try{data=JSON.parse(body)}catch{data={ok:false,error:body.slice(0,300)}}
  res.setHeader("Cache-Control","no-store, max-age=0"); return res.status(r.ok?200:502).json(data);
 } catch { return res.status(502).json({ok:false,error:"Pont MT5 inaccessible"}); }
}