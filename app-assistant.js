(function(){
  if(window.__AI_FLOW_APP_ASSISTANT__) return;
  window.__AI_FLOW_APP_ASSISTANT__ = true;
  window.__AI_FLOW_WIDGET_LOADED__ = true;

  const css=document.createElement("style");
  css.textContent=`
    #afa-launch{position:fixed;right:20px;bottom:20px;z-index:999999;width:48px;height:48px;border:1px solid #34443c;border-radius:12px;background:#b8f36b;color:#14200e;font:800 15px system-ui;box-shadow:0 10px 30px rgba(0,0,0,.28);cursor:pointer}
    #afa-panel{position:fixed;right:20px;bottom:78px;z-index:999999;width:min(360px,calc(100vw - 28px));height:min(520px,calc(100vh - 110px));display:none;flex-direction:column;overflow:hidden;border:1px solid #2b3933;border-radius:14px;background:#0d1417;color:#eef5f1;box-shadow:0 24px 70px rgba(0,0,0,.48);font:13px/1.45 system-ui}
    #afa-panel.open{display:flex}#afa-head{display:flex;align-items:center;justify-content:space-between;padding:13px 14px;border-bottom:1px solid #24312c;background:#111a1e}#afa-head strong{font-size:14px}#afa-head span{display:block;color:#8fa099;font-size:11px}
    #afa-close{border:0;background:transparent;color:#aebbb5;font-size:20px;cursor:pointer}#afa-messages{flex:1;overflow:auto;padding:12px}.afa-msg{max-width:88%;margin:7px 0;padding:9px 10px;border-radius:9px;white-space:pre-wrap}.afa-ai{background:#18221e;border:1px solid #28372f}.afa-user{margin-left:auto;background:#b8f36b;color:#14200e}
    #afa-quick{display:flex;gap:6px;padding:0 12px 10px;overflow:auto}.afa-chip{white-space:nowrap;border:1px solid #314139;border-radius:999px;background:#111a1e;color:#dbe5e0;padding:6px 9px;font:700 11px system-ui;cursor:pointer}
    #afa-contact{margin:0 12px 10px;padding:8px 10px;border:1px solid #314139;border-radius:8px;color:#dfffbd;text-decoration:none;text-align:center;font-weight:750}
    #afa-form{display:flex;gap:7px;padding:10px 12px;border-top:1px solid #24312c}#afa-input{flex:1;min-width:0;border:1px solid #314139;border-radius:8px;background:#080e11;color:#fff;padding:9px 10px;outline:none}#afa-send{border:0;border-radius:8px;background:#b8f36b;color:#14200e;padding:0 12px;font-weight:800;cursor:pointer}
    @media(max-width:600px){#afa-launch{right:14px;bottom:14px}#afa-panel{right:14px;bottom:70px}}
  `;
  document.head.appendChild(css);

  const launch=document.createElement("button");launch.id="afa-launch";launch.type="button";launch.setAttribute("aria-label","Open AI FLOW Help");launch.textContent="AI";
  const panel=document.createElement("section");panel.id="afa-panel";panel.setAttribute("aria-label","AI FLOW Help");
  panel.innerHTML=`<div id="afa-head"><div><strong>AI FLOW Help</strong><span>Product assistant · Online</span></div><button id="afa-close" aria-label="Close">×</button></div><div id="afa-messages"><div class="afa-msg afa-ai">Hi! I can explain this page, help connect your channels or calendar, and guide you through bookings, payments, and CRM.</div></div><div id="afa-quick"><button class="afa-chip">Explain this page</button><button class="afa-chip">Connect Calendar</button><button class="afa-chip">Contact support</button></div><a id="afa-contact" href="mailto:baskinltd@gmail.com?subject=AI%20FLOW%20Support">Contact AI FLOW Support</a><form id="afa-form"><input id="afa-input" autocomplete="off" placeholder="Ask about AI FLOW…"><button id="afa-send" type="submit">Send</button></form>`;
  document.body.append(panel,launch);
  const messages=panel.querySelector("#afa-messages"),input=panel.querySelector("#afa-input"),send=panel.querySelector("#afa-send");
  function add(text,kind){const el=document.createElement("div");el.className="afa-msg "+(kind==="user"?"afa-user":"afa-ai");el.textContent=text;messages.appendChild(el);messages.scrollTop=messages.scrollHeight;return el}
  launch.onclick=()=>{panel.classList.toggle("open");if(panel.classList.contains("open"))input.focus()};panel.querySelector("#afa-close").onclick=()=>panel.classList.remove("open");
  async function ask(text){text=String(text||"").trim();if(!text)return;add(text,"user");input.value="";send.disabled=true;const waiting=add("Thinking…","ai");try{const res=await fetch("/api/support/chat",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text,page:location.pathname})});const data=await res.json();waiting.textContent=(res.ok&&data.reply)?data.reply:(data.error||"Support is temporarily unavailable. Use the contact button below.")}catch(e){waiting.textContent="Support is temporarily unavailable. Use the contact button below."}finally{send.disabled=false;input.focus()}}
  panel.querySelector("#afa-form").onsubmit=e=>{e.preventDefault();ask(input.value)};
  panel.querySelectorAll(".afa-chip").forEach(btn=>btn.onclick=()=>{if(btn.textContent==="Contact support"){panel.querySelector("#afa-contact").click();return}ask(btn.textContent==="Explain this page"?`Explain what I can do on ${location.pathname}.`:"How do I connect Google Calendar?")});
  fetch("/api/me",{credentials:"same-origin"}).then(r=>r.json()).then(data=>{const u=data.user||{};const id=u.company_id||data.activeCompanyId||"";const link=panel.querySelector("#afa-contact");link.href=`mailto:baskinltd@gmail.com?subject=${encodeURIComponent("AI FLOW Support")}&body=${encodeURIComponent(`Account: ${u.email||""}\nClient ID: ${id||"Platform Admin"}\nPage: ${location.pathname}\n\nHow can we help?`)}`}).catch(()=>{});
})();
