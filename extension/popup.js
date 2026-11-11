const token = document.querySelector('#token');
const plan = document.querySelector('#plan');
const result = document.querySelector('#result');
const send = document.querySelector('#send');
const selection = document.querySelector('#selection');
chrome.storage.session.get(['token','plan','result']).then(s => {
  token.value=s.token||''; plan.value=s.plan||'';
  if(s.result) result.textContent=s.result;
});
function parsePlan(text) {
  return JSON.parse(text.trim().replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,''));
}
selection.addEventListener('click',async()=>{
  try {
    const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
    const url=new URL(tab.url);
    if(url.protocol!=='https:' || !['arena.ai','www.arena.ai'].includes(url.hostname)) throw new Error('Open Arena.ai and select its JSON plan first.');
    const [response]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>window.getSelection().toString()});
    if(!response.result.trim()) throw new Error('Select the complete JSON block first.');
    plan.value=JSON.stringify(parsePlan(response.result),null,2);
    await chrome.storage.session.set({plan:plan.value});
    result.textContent='Plan loaded. Review it, then send for desktop approval.';
  }catch(e){result.textContent=e.message;}
});
send.addEventListener('click',async()=>{
  send.disabled=selection.disabled=true;
  try {
    const body=JSON.stringify(parsePlan(plan.value));
    if(!token.value.trim()) throw new Error('Paste the desktop pairing token first.');
    await chrome.storage.session.set({token:token.value.trim(),plan:plan.value});
    result.textContent='Waiting for desktop approval (up to 2 minutes)…';
    const response=await fetch('http://127.0.0.1:47831/actions',{
      method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token.value.trim()},body,signal:AbortSignal.timeout(130000)
    });
    result.textContent=JSON.stringify(await response.json(),null,2);
    await chrome.storage.session.set({result:result.textContent});
  }catch(e){result.textContent=e.message+'\nCheck desktop activity before resending: approved actions may have completed.';}
  finally{send.disabled=selection.disabled=false;}
});
document.querySelector('#copy').addEventListener('click',async()=>{
  try{await navigator.clipboard.writeText(result.textContent);}catch(e){result.textContent=e.message;}
});
