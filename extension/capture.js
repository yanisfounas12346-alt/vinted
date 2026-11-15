// Ce script ne lit que les éléments rendus de la page autorisée par un clic utilisateur.
if(!globalThis.repereCapture){
  globalThis.repereCapture=(()=>{
    let timer=null;
    const source=location.hostname.includes('vinted')?'vinted':'leboncoin';
    function collect(){
      const seen=new Set(),rows=[];
      const anchors=document.querySelectorAll(source==='vinted'?'a[href*="/items/"]':'a[href*="/ad/"]');
      for(const link of anchors){
        const url=new URL(link.href,location.origin);const match=url.pathname.match(source==='vinted'?/^\/items\/(\d+)/:/^\/ad\/[^/]+\/(\d+)/);
        if(!match||seen.has(match[1])||!link.getBoundingClientRect().width)continue;
        let card=link;for(let i=0;i<6;i++){if((card.innerText||'').includes('€')&&card.querySelector('img'))break;if(!card.parentElement)break;card=card.parentElement;}
        const text=card.innerText||'';if(text.length>3500)continue;
        const priceText=card.querySelector('[data-testid$="--price-text"], [data-test-id="ad-price"], [data-qa-id="aditem_price"]')?.textContent||text;
        const price=priceText.match(/(\d[\d\s\u00a0\u202f]*(?:[,.]\d{1,2})?)\s*€/);if(!price)continue;
        const image=card.querySelector('img');
        const title=(card.querySelector('[data-testid$="--title"], [data-qa-id="aditem_title"],h2,h3')?.textContent||image?.alt||link.title||'').trim();
        if(!title)continue;
        const value=price[1].replace(/[\s\u00a0\u202f]/g,'').replace(',','.');if(!Number.isFinite(Number(value)))continue;
        url.search='';url.hash='';seen.add(match[1]);
        rows.push({id:source+':'+match[1],title:title.slice(0,500),price:value,url:url.href,image_url:image?.currentSrc||image?.src||'',description:''});
        if(rows.length>=200)break;
      }
      return rows;
    }
    async function readyRows(){
      const first=collect();if(first.length)return first;
      return await new Promise(resolve=>{let done=false;let timer;const finish=rows=>{if(done)return;done=true;observer.disconnect();clearTimeout(timer);resolve(rows);};const observer=new MutationObserver(()=>{const rows=collect();if(rows.length)finish(rows);});observer.observe(document.body,{childList:true,subtree:true});timer=setTimeout(()=>finish(collect()),8000);});
    }
    async function transmit(){const visible=(document.body.innerText||'').slice(0,2000).toLowerCase();if(/verify you are human|vérifiez que vous êtes humain|checking your browser|automated traffic|access denied|accès refusé|confirmez que vous êtes humain/.test(visible))return {error:'La page demande une vérification ou refuse l’accès. Surveillance arrêtée, aucun contournement.'};const rows=await readyRows();if(!rows.length)return {error:'Aucune carte exploitable trouvée. Ouvrez une page de résultats, avec titres et prix en euros visibles. Le site peut avoir modifié sa présentation.'};try{const reply=await chrome.runtime.sendMessage({type:'repere:rows',rows});if(reply.error)return {error:reply.error};return {message:reply.result.received+' annonce(s) transmise(s), '+reply.result.new+' nouvelle(s). Frais et état à confirmer dans Repère.'};}catch{return {error:'Application locale inaccessible. Lancez Lancer.bat et vérifiez la configuration du pont.'};}}
    async function run(mode){if(mode==='stop'){clearInterval(timer);timer=null;return {message:'Surveillance de cet onglet arrêtée.'};}const result=await transmit();if(mode==='watch'&&!result.error){clearInterval(timer);timer=setInterval(async()=>{const next=await transmit();if(next.error){clearInterval(timer);timer=null;console.info('Repère : '+next.error);}},60000);result.message+='\nSurveillance de la page active (lecture toutes les 60 s). Actualisez manuellement la recherche.';}return result;}
    return {run};
  })();
}
