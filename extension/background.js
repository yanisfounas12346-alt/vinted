'use strict';
async function send(rows){
  const {repere}=await chrome.storage.local.get('repere');
  if(!repere?.token||!/^http:\/\/127\.0\.0\.1:\d+$/.test(repere.url))throw new Error('Coller la configuration depuis Connexions dans Repère.');
  const response=await fetch(repere.url+'/api/bridge',{method:'POST',headers:{'Content-Type':'application/json','X-Bridge-Token':repere.token},body:JSON.stringify({rows})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||'Connexion refusée');
  return result;
}
const allowed=url=>/^https:\/\/(www\.)?(vinted\.fr|leboncoin\.fr)\//.test(url||'');
async function watches(){return (await chrome.storage.session.get('repereWatches')).repereWatches||{};}
async function stopWatch(tabId,message){const values=await watches();delete values[tabId];await chrome.storage.session.set({repereWatches:values});await chrome.alarms.clear('repere:'+tabId);if(message){await chrome.storage.local.set({repereLastError:message});try{const {repere}=await chrome.storage.local.get('repere');if(repere)await fetch(repere.url+'/api/bridge',{method:'POST',headers:{'Content-Type':'application/json','X-Bridge-Token':repere.token},body:JSON.stringify({rows:[],error:message})});}catch{}}}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(message.type==='repere:rows'){
    if(!sender.tab||!allowed(sender.url)){reply({error:'Page non autorisée'});return;}
    send(message.rows).then(result=>reply({result})).catch(error=>reply({error:error.message}));return true;
  }
  if(message.type==='repere:start'){
    (async()=>{const tab=await chrome.tabs.get(message.tabId);if(!allowed(tab.url))throw new Error('Recherche Vinted/Leboncoin requise.');const values=await watches();values[tab.id]={url:tab.url,pending:false};await chrome.storage.session.set({repereWatches:values});await chrome.alarms.create('repere:'+tab.id,{periodInMinutes:1.5});reply({ok:true});})().catch(error=>reply({error:error.message}));return true;
  }
  if(message.type==='repere:stop'){stopWatch(message.tabId).then(()=>reply({ok:true}));return true;}
});
chrome.alarms.onAlarm.addListener(alarm=>{
  if(!alarm.name.startsWith('repere:'))return;
  const tabId=Number(alarm.name.split(':')[1]);
  (async()=>{const values=await watches();const job=values[tabId];if(!job){await chrome.alarms.clear(alarm.name);return;}const tab=await chrome.tabs.get(tabId);if(!allowed(tab.url)||tab.url!==job.url)throw new Error('Recherche modifiée : réactiver la surveillance sur la nouvelle page.');if(job.pending)throw new Error('La recherche précédente n’a pas terminé son chargement. Surveillance arrêtée.');job.pending=true;await chrome.storage.session.set({repereWatches:values});await chrome.tabs.reload(tabId);})().catch(error=>stopWatch(tabId,error.message));
});
chrome.tabs.onUpdated.addListener((tabId,change)=>{
  if(change.status!=='complete')return;
  (async()=>{const values=await watches();const job=values[tabId];if(!job?.pending)return;const tab=await chrome.tabs.get(tabId);if(!allowed(tab.url)||tab.url!==job.url)throw new Error('Page de recherche modifiée ; surveillance arrêtée.');await chrome.scripting.executeScript({target:{tabId},files:['capture.js']});const [{result}]=await chrome.scripting.executeScript({target:{tabId},func:async()=>await globalThis.repereCapture.run('once')});if(result.error)throw new Error(result.error);const current=await watches();if(current[tabId]){current[tabId].pending=false;await chrome.storage.session.set({repereWatches:current});}})().catch(error=>stopWatch(tabId,error.message));
});
chrome.tabs.onRemoved.addListener(tabId=>stopWatch(tabId));
