const fs=require('fs');const {JSDOM}=require('jsdom');
const dom=new JSDOM(fs.readFileSync('UnityLens.html','utf8'),{runScripts:'dangerously',pretendToBeVisual:true,url:'http://localhost/'});
const w=dom.window,d=w.document;
setTimeout(()=>{
  fs.writeFileSync('unitylens-report.md',w.__exportMd(),'utf8');
  const item=[...d.querySelectorAll('.ritem')].find(x=>x.dataset.type==='PlayerShooting');
  item.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  const v=[...d.querySelectorAll('.vitem')].find(x=>x.dataset.var==='PlayerShooting.bulletPrefab');
  if(v)v.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  [...d.querySelectorAll('#tabs button')].find(b=>b.dataset.tab==='source').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  console.log('report bytes:',fs.statSync('unitylens-report.md').size);
  console.log('source highlight rows:',d.querySelectorAll('#v-source .cl.hit').length,'lines:',d.querySelectorAll('#v-source .cl').length);
  console.log('report starts:',fs.readFileSync('unitylens-report.md','utf8').slice(0,120).replace(/\n/g,' | '));
},900);
