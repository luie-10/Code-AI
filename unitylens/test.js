const fs=require('fs'),path=require('path');
const {analyzeSources}=require('./analyzer.js');
const dir='/home/user/workspace/unity_in';
const srcs=fs.readdirSync(dir).filter(f=>f.endsWith('.cs')).map(f=>({name:f,code:fs.readFileSync(path.join(dir,f),'utf8')}));
const r=analyzeSources(srcs);
for(const t of r.types){
  console.log(`\n=== ${t.name} (${t.kind}) : ${t.base||'-'} | ${t.interfaces.join(',')} | ${t.file} L${t.startLine}-${t.endLine}`);
  console.log('  roles:',t.roles.map(x=>x.name+'('+x.score+')').join(', '));
  console.log('  fields:',t.fields.map(f=>`${f.name}:${f.type}${f.isSerialized?'[S]':''} r${f.usages.filter(u=>u.rw!=='write').length}/w${f.usages.filter(u=>u.rw!=='read').length}`).join(' | '));
  console.log('  props:',t.props.map(p=>p.name+':'+p.type).join(', '));
  console.log('  methods:',t.methods.map(m=>m.name+'('+m.params.map(p=>p.name).join(',')+')'+(m.isLifecycle?'*':'')).join(' '));
  console.log('  ext:',t.externals.map(e=>e.target+'.'+e.member).join(', '));
  console.log('  issues:',t.issues.map(i=>i.sev[0].toUpperCase()+':'+i.title).join(' | '));
}
console.log('\nEDGES',r.edges.map(e=>e.from+'->'+e.to+'('+e.label+')').join(', '));
console.log('UNRESOLVED',r.unresolved.map(u=>u.name+'@'+u.usedBy).join(', '));
