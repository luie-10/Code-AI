const fs=require('fs');const {JSDOM,VirtualConsole}=require('jsdom');
const vc=new VirtualConsole();const errs=[];
vc.on('jsdomError',e=>errs.push((e.stack||e.message||'').split('\n').slice(0,2).join(' | ')));
const dom=new JSDOM(fs.readFileSync('preview_class.html','utf8'),{runScripts:'dangerously',pretendToBeVisual:true,url:'http://localhost/',virtualConsole:vc});
const w=dom.window,d=w.document;
setTimeout(()=>{
  console.log('errors:',errs.length?errs.join(' || '):'none');
  console.log('sections:',d.querySelectorAll('.ai-section').length,'flow rows:',d.querySelectorAll('.flow-row').length,'risks:',d.querySelectorAll('.risk-item').length);
  console.log('badge:',(d.querySelector('.idbadge')||{}).textContent);
  const t=w.__UL.data.types.find(x=>x.name==='PlayerMove');
  const parsed=w.Explainer.parseJson('```json\n{"summary":"`speed`는 `Start`에서 쓰인다","flow":[{"field":"speed","writes":["Start"],"reads":["Update"],"note":"기본 0"}],"risks":[{"severity":"high","title":"테스트","detail":"`fakeVar` 누락"}]}\n```');
  console.log('parsed flow:',parsed.flow.length,'risk:',parsed.risks[0].severity);
  w.Explainer.applyJson(t,{summary:'`speed`와 `speed = playerSpeed * 5`',flow:[{field:'speed',writes:['Start'],reads:['Update'],note:''},{field:'ghostField',writes:[],reads:['Update'],note:''}],risks:[{severity:'high',title:'위험',detail:'`fakeVar`'}]},'test-model');
  setTimeout(()=>{
    console.log('after apply badge:',(d.querySelector('.idbadge')||{}).textContent);
    console.log('flow bad:',d.querySelectorAll('.flow-row.bad').length,'idcode bad:',d.querySelectorAll('.idcode.bad').length);
  },100);
},900);
