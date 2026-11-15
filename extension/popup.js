'use strict';
const status=document.getElementById('status');
async function run(fn){try{status.textContent='Traitement…';await fn();}catch(error){status.textContent=error.message;}}
chrome.storage.local.get('repere').then(({repere})=>{if(repere)document.getElementById('pair').value=JSON.stringify(repere);});
document.getElementById('save').onclick=()=>run(async()=>{const config=JSON.parse(document.getElementById('pair').value);if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(config.url)||typeof config.token!=='string'||config.token.length<20)throw new Error('Configuration locale invalide');await chrome.storage.local.set({repere:{url:config.url,token:config.token}});status.textContent='Connexion locale enregistrée.';});
async function operate(mode){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id||!/^https:\/\/(www\.)?(vinted\.fr|leboncoin\.fr)\//.test(tab.url||''))throw new Error('Ouvrez une recherche Vinted.fr ou Leboncoin.fr dans cet onglet.');
  const results=await chrome.scripting.executeScript({target:{tabId:tab.id},files:['capture.js']});
  const [{result}]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:async function(mode){return await globalThis.repereCapture.run(mode);},args:[mode]});
  if(result.error)throw new Error(result.error);
  status.textContent=result.message;
}
document.getElementById('capture').onclick=()=>run(()=>operate('once'));
document.getElementById('watch').onclick=()=>run(async()=>{await operate('once');const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const reply=await chrome.runtime.sendMessage({type:'repere:start',tabId:tab.id});if(reply.error)throw new Error(reply.error);status.textContent='Surveillance activée. Cette recherche sera actualisée toutes les 90 s. Arrêt automatique au premier refus ou échec.';});
document.getElementById('stop').onclick=()=>run(async()=>{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});await chrome.runtime.sendMessage({type:'repere:stop',tabId:tab.id});await operate('stop');status.textContent='Surveillance de cet onglet arrêtée.';});
