(()=>{
'use strict';
const $=id=>document.getElementById(id);
const main=document.querySelector('main'), personal=main.dataset.kind==='personal';
const stages=JSON.parse($('stage-data').textContent), days=new Set();
const panes=[...main.querySelectorAll(':scope > section')], steps=[...$('steps').children];
const csrf=document.querySelector('[name=csrfmiddlewaretoken]').value;
let preview=JSON.parse($('initial').textContent), workbook=null, scope=null, busy=false;
const stage=()=>stages.find(s=>s.id===$('stage').value);
const chosen=id=>[...$(id).querySelectorAll('input:checked')].map(e=>e.value);
const checks=()=>[...document.querySelectorAll('[name=checks]:checked')].map(e=>e.value);
const el=(tag,text)=>Object.assign(document.createElement(tag),{textContent:text??''});
function go(n){
 panes.forEach((p,i)=>p.hidden=i!==n-1);
 steps.forEach((s,i)=>{s.classList.toggle('is-active',i===n-1);s.querySelector('.steps-marker').textContent=i<n-1?'✓':i+1;s.setAttribute('aria-current',i===n-1?'step':'false')});
 $('message').textContent='';window.scrollTo(0,0);
}
function choices(id,items,key){
 $(id).replaceChildren();
 for(const item of items){const label=el('label'),box=el('input');box.type='checkbox';box.checked=true;box.value=item[key];label.append(box,item.name);$(id).append(label)}
}
function changeStage(){choices('entries',stage()?.entries||[],'id');choices('tables',stage()?.tables||[],'number')}
for(const s of stages)$('stage').add(new Option(s.name,s.id));
$('stage').onchange=changeStage;changeStage();
function paintDays(){
 $('days').replaceChildren();
 for(const d of [...days].sort()){const b=el('button',d+' ×');b.onclick=()=>{days.delete(d);paintDays()};$('days').append(b)}
}
function addDate(){if($('date').value){if(personal)days.clear();days.add($('date').value);$('date').value='';paintDays()}}
$('addDate').onclick=addDate;
async function request(data,blob=false){
 const response=await fetch(location.pathname,{method:'POST',headers:{'X-CSRFToken':csrf},body:data});
 if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.error||'请求失败，请重试')}
 return blob?response.blob():response.json();
}
async function run(fn,output=$('message')){
 if(busy)return;busy=true;main.inert=true;
 try{await fn()}catch(e){output.textContent=e.message}finally{main.inert=false;busy=false}
}
$('prepare').onclick=()=>run(async()=>{
 addDate();const s=stage(),times=[...new Set($('times').value.trim().split(/[\s,，、]+/))];
 const ids=chosen('entries'),tables=chosen('tables');
 if(!s||ids.length<4||!days.size||!tables.length||!times.every(t=>/^([01]\d|2[0-3]):[0-5]\d$/.test(t)))throw Error('请选择至少四名参赛方、比赛日、比赛用桌，并填写 HH:MM 格式的时间。');
 const data=new FormData();data.set('ajax','1');data.set('mode','template');data.set('stage',s.id);
 for(const [k,list] of Object.entries({entries:ids,tables,days:[...days],times}))for(const v of list)data.append(k,v);
 workbook=await request(data,true);
 $('file-name').textContent=main.querySelector('small').textContent.split(' / ')[0]+' · '+s.name+'排程.xlsx';
 $('file-size').textContent='Excel 文件 · '+Math.ceil(workbook.size/1024)+' KB';
 scope={stage:s.id,entries:ids,tables};
 $('prompt').value=['请填写附件的「赛程」表，保留表头、比赛日、时间和桌名，返回可下载的 .xlsx 文件。',main.querySelector('small').textContent.split(' / ')[0]+'，阶段：'+s.name,'比赛日：'+[...days].sort().join('、')+'；开赛时间：'+times.join('、'),
 personal?'根据「本轮排名」顺序每四人一桌，每名选手恰好出战一次，使用赛事参考中的编号与姓名。':'参赛队伍：'+s.entries.filter(p=>ids.includes(p.id)).map(p=>p.name).join('、'),
 '每桌四个不同参赛方，同一时段不能重复出战。'+(s.fixed?'四列依次对应东南西北。':''),
 checks().length?'尽量满足：'+checks().join('、')+'的安排均衡。':'',$('notes').value.trim()].filter(Boolean).join('\n');
 go(2);
});
$('copy').onclick=async()=>{try{await navigator.clipboard.writeText($('prompt').value);$('message').textContent='提示词已复制'}catch{$('prompt').select();$('message').textContent='已选中提示词，请复制'}};
$('download').onclick=()=>{const a=el('a'),url=URL.createObjectURL(workbook);a.href=url;a.download=$('file-name').textContent;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
$('uploadBack').onclick=()=>go(workbook?2:1);
for(const b of document.querySelectorAll('[data-go]'))b.onclick=()=>{if(b.closest('section')===panes[0]){scope=null;workbook=null}go(Number(b.dataset.go))};
$('upload').onsubmit=e=>{e.preventDefault();run(async()=>{const data=new FormData(e.target);data.set('ajax','1');if(scope)data.set('scope',JSON.stringify(scope));preview=await request(data);render();go(4)})};
function select(values,current){const s=el('select');for(const v of values)s.add(new Option(v,v));if(current)s.value=current;return s}
function dialog(title,fields,change){
 $('dialogTitle').textContent=title;$('fields').replaceChildren(...fields);$('editError').textContent='';$('edit').showModal();
 $('apply').onclick=()=>run(async()=>{
 const rows=preview.rows.map(r=>[...r]);change(rows);const data=new FormData();data.set('ajax','1');data.set('mode','edit');if(scope)data.set('scope',JSON.stringify(scope));data.set('revision',preview.revision);data.set('rows',JSON.stringify(rows));
 preview=await request(data);$('edit').close();render();
 },$('editError'));
}
function label(name,input){const l=el('label',name+' ');l.append(input);return l}
function editRow(i){
 const row=preview.rows[i],s=stages.find(s=>s.name===row[0]);
 const inputs=row.slice(4).map(n=>select(s.entries.map(p=>p.name),n));
 dialog(row.slice(1,4).join(' · '),inputs.map((v,j)=>label(s.fixed?'东南西北'[j]:'席位 '+(j+1),v)),rows=>{rows[i].splice(4,4,...inputs.map(v=>v.value))});
}
$('swap').onclick=()=>{
 const ds=[...new Set(preview.rows.map(r=>r[1]))].sort(),a=select(ds,ds[0]),b=select(ds,ds[1]);
 dialog('交换两个比赛日的全部赛程',[label('比赛日',a),label('与',b)],rows=>{if(a.value===b.value)throw Error('请选择两个不同日期');for(const r of rows){if(r[1]===a.value)r[1]=b.value;else if(r[1]===b.value)r[1]=a.value}});
};
function render(){
 const ds=[...new Set(preview.rows.map(r=>r[1]))].sort();let warning=false;
 $('audit').replaceChildren();$('preview').replaceChildren();
 for(const group of preview.stats){
 if(preview.stats.length>1)$('audit').append(el('h3',group.stage));
 for(const item of group.audit.filter(a=>checks().includes(a.label))){
 const d=el('details');d.className='audit '+(item.warning?'warn':'good');warning||=item.warning;
 const summary=el('summary'),icon=el('span',item.warning?'!':'✓'),link=el('span',item.warning?'查看差异 ›':'查看明细 ›');
 icon.className='audit-icon';icon.setAttribute('aria-hidden','true');link.className='audit-link';
 summary.append(icon,el('strong',item.label+' · '+(item.warning?'有差异':'一致')),link);
 d.append(summary,el('p',item.result));
 for(const line of item.details)d.append(el('div',line));$('audit').append(d)}}
 if(personal)$('audit').append(el('p','本轮名单已核对，每名选手出战一次。'));
 if(warning)$('audit').append(el('small','次数差异不影响导入。'));
 for(const day of ds){const panel=el('details');panel.className='day';panel.open=day===ds[0];panel.append(el('summary',day));
 const wrap=el('div');wrap.className='scroll';const table=el('table'),head=table.createTHead().insertRow();
 const fixed=preview.rows.filter(r=>r[1]===day).every(r=>stages.find(s=>s.name===r[0])?.fixed);
 for(const title of ['阶段','时间','桌名',...(fixed?[...'东南西北']:['席位一','席位二','席位三','席位四']),'操作'])head.append(el('th',title));
 const body=table.createTBody();preview.rows.forEach((r,i)=>{if(r[1]!==day)return;const tr=body.insertRow();for(const v of [r[0],...r.slice(2)])tr.insertCell().textContent=v;const b=el('button','微调');b.onclick=()=>editRow(i);tr.insertCell().append(b)});
 wrap.append(table);panel.append(wrap);$('preview').append(panel)}
 $('swap').hidden=ds.length<2;$('warning').hidden=!warning;
 $('summary').textContent=[main.querySelector('small').textContent.split(' / ')[0],[...new Set(preview.rows.map(r=>r[0]))].join('、'),ds[0]+(ds.length>1?' 至 '+ds.at(-1):''),ds.length+' 个比赛日',preview.rows.length+' 个半庄'].join(' · ');
 $('confirm').textContent='确认导入 '+preview.rows.length+' 个半庄';
}
$('confirm').onclick=()=>run(async()=>{
 const body={action:personal?'pairing-commit':'schedule-excel',revision:preview.revision,token:preview.token};
 if(personal)body.tables=preview.tables;
 const response=await fetch('/api/events/'+main.dataset.event+'/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(body)});
 if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.error||'导入失败，请重新预览')}
 location.assign('/manage/?event='+main.dataset.event+'&page=schedule');
});
if(preview){render();go(4)}else if($('message').textContent.trim()){const msg=$('message').textContent;go(3);$('message').textContent=msg}else go(1);
})();
