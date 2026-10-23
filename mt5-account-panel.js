(() => {
  "use strict";
  const css = `
    #mt5-account-panel{margin:16px auto;max-width:1200px;padding:16px;border:1px solid #334155;border-radius:14px;background:#101827;color:#edf3ff;font:14px system-ui}
    #mt5-account-panel .mt5-row{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
    #mt5-account-panel .mt5-muted{color:#92a0b7;font-size:12px}
    #mt5-account-panel .mt5-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px;margin-top:14px}
    #mt5-account-panel .mt5-card{padding:10px;border:1px solid #233149;border-radius:9px;background:#0b1220;overflow-wrap:anywhere}
    #mt5-account-panel button,#mt5-account-panel select{padding:9px 13px;border-radius:8px;border:1px solid #334155;background:#1d2a40;color:#edf3ff}
  `;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);
  const panel = document.createElement("section");
  panel.id = "mt5-account-panel";
  panel.innerHTML = `
    <div class="mt5-row">
      <div><strong>Comptes MetaTrader 5</strong><div id="mt5-status" style="color:#f2c66d;margin-top:5px">Connexion en cours…</div></div>
      <div class="mt5-row">
        <label for="mt5-account-choice">Compte mémorisé</label>
        <select id="mt5-account-choice" aria-label="Choisir un compte mémorisé"><option value="">Compte détecté dans MT5</option></select>
        <button id="mt5-refresh" type="button">Actualiser depuis MT5</button>
      </div>
    </div>
    <div class="mt5-grid" id="mt5-details"></div>
    <p class="mt5-muted">Lecture seule. Le choix mémorisé sert à comparer le compte attendu avec celui réellement connecté. Pour changer de compte, connecte-toi manuellement dans MT5 puis actualise. Aucun ordre n’est envoyé.</p>
  `;
  const body = document.body;
  if (!body || document.getElementById(panel.id)) return;
  body.insertBefore(panel, body.firstChild);
  const status = panel.querySelector("#mt5-status");
  const details = panel.querySelector("#mt5-details");
  const choice = panel.querySelector("#mt5-account-choice");
  const button = panel.querySelector("#mt5-refresh");
  const esc = v => String(v ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const money = (v, cur) => Number.isFinite(Number(v)) ? new Intl.NumberFormat("fr-BE",{style:"currency",currency:/^[A-Z]{3}$/.test(cur||"")?cur:"EUR"}).format(Number(v)) : "—";
  const savedKey = "forteress-mt5-account-labels-v1";
  let actual = null;
  function getSaved(){ try { return JSON.parse(localStorage.getItem(savedKey)||"[]").filter(x=>x&&typeof x.id==="string"); } catch { return []; } }
  function saveSaved(items){ try { localStorage.setItem(savedKey,JSON.stringify(items)); } catch {} }
  function renderChoice(){
    const saved=getSaved(); const current=choice.value;
    choice.innerHTML='<option value="">Compte détecté dans MT5</option>'+saved.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.label)+' — '+esc(x.id)+'</option>').join("");
    if(saved.some(x=>x.id===current)) choice.value=current;
  }
  function renderAccount(a){
    const rows=[["Login",a.login],["Nom",a.name],["Serveur",a.server],["Société",a.company],["Devise",a.currency],["Solde",money(a.balance,a.currency)],["Équité",money(a.equity,a.currency)],["Profit flottant",money(a.profit,a.currency)],["Marge libre",money(a.margin_free,a.currency)],["Dernière lecture",a.observed_at?new Date(a.observed_at).toLocaleString("fr-BE"):"—"]];
    details.innerHTML=rows.map(([k,v])=>'<div class="mt5-card"><div class="mt5-muted">'+esc(k)+'</div><strong>'+esc(v)+'</strong></div>').join("");
    const selected=choice.value; const saved=getSaved().find(x=>x.id===selected);
    if(saved && String(a.login)!==saved.id){
      status.textContent="Attention : MT5 est connecté au compte "+a.login+", pas au compte mémorisé "+saved.id+".";
      status.style.color="#ff7385";
    } else {
      status.textContent="Connecté — compte "+a.login+" — "+(a.server||"serveur inconnu");
      status.style.color="#4adea2";
    }
  }
  async function refresh(){
    button.disabled=true; status.textContent="Lecture du compte réellement connecté…"; status.style.color="#f2c66d";
    try{
      const response=await fetch("/api/mt5/accounts",{method:"GET",cache:"no-store",headers:{"Accept":"application/json"}});
      const data=await response.json();
      if(!response.ok||!data.ok||!data.account||!data.account.connected) throw new Error(data.error||data.account?.error||"MT5 n’est pas connecté");
      actual=data.account; renderAccount(actual);
    }catch(e){ status.textContent="Compte indisponible : "+e.message; status.style.color="#ff7385"; details.innerHTML=""; }
    finally{button.disabled=false;}
  }
  choice.addEventListener("change",()=>{if(actual)renderAccount(actual);});
  const saveBtn=document.createElement("button"); saveBtn.type="button"; saveBtn.textContent="Mémoriser ce compte";
  saveBtn.addEventListener("click",()=>{
    if(!actual||actual.login==null){status.textContent="Aucun compte détecté à mémoriser.";return;}
    const id=String(actual.login); const old=getSaved().find(x=>x.id===id);
    const label=window.prompt("Nom à afficher pour le compte MT5 "+id+":",old?.label||("Compte "+id));
    if(label===null)return;
    const clean=label.trim().slice(0,60)||("Compte "+id);
    const list=getSaved().filter(x=>x.id!==id); list.push({id,label:clean}); saveSaved(list); renderChoice(); choice.value=id; renderAccount(actual);
  });
  button.parentElement.appendChild(saveBtn);
  renderChoice(); button.addEventListener("click",refresh); refresh(); window.setInterval(refresh,30000);
})();