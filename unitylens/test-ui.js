const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');
const html=fs.readFileSync('UnityLens.html','utf8');
const vc=new VirtualConsole();
const errs=[];
vc.on('jsdomError',e=>errs.push('jsdomError: '+(e.message||e)));
vc.on('error',(...a)=>errs.push('console.error: '+a.join(' ')));
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'http://localhost/',virtualConsole:vc});
const w=dom.window,d=w.document;
setTimeout(()=>{
  try{
    const q=s=>d.querySelector(s);
    console.log('rail items:',d.querySelectorAll('.ritem').length);
    console.log('hero:',(q('.hero h2')||{}).textContent);
    console.log('overview table rows:',d.querySelectorAll('#v-overview tbody tr').length);
    console.log('class content len:',d.querySelector('#v-class').innerHTML.length);
    console.log('vars content len:',d.querySelector('#v-vars').innerHTML.length);
    console.log('graph nodes:',d.querySelectorAll('.gnode').length,'edges:',d.querySelectorAll('.gedge').length);
    console.log('source lines:',d.querySelectorAll('#v-source .cl').length);
    // switch class + tab via clicks
    const item=[...d.querySelectorAll('.ritem')].find(x=>x.dataset.type==='PlayerMove');
    item.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    console.log('after select, class head:',(q('#v-class h2')||{}).textContent.trim());
    const varsTab=[...d.querySelectorAll('#tabs button')].find(b=>b.dataset.tab==='vars');
    varsTab.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    console.log('active view:',q('.view.on').id,'trace title:',(q('.trace-decl .td-name')||{}).textContent);
    const vitem=[...d.querySelectorAll('.vitem')].find(x=>x.dataset.var==='PlayerMove.mainCamera');
    if(vitem){vitem.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));console.log('trace after var click:',(q('.trace-decl .td-name')||{}).textContent,'hits:',d.querySelectorAll('.tr').length);}
    const allBtn=d.querySelector('#scopeAll'); if(allBtn){allBtn.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));console.log('scope all vars:',d.querySelectorAll('.vitem').length);}
    console.log('errors:',errs.length?errs.join('\n'):'none');
  }catch(e){console.log('TEST EXCEPTION',e.stack);}
},900);
