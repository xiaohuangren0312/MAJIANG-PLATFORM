'use strict';
const config = JSON.parse(document.getElementById('batch-config').textContent);
const $ = id => document.getElementById(id);
const days = new Set();
let stage, draft = [], previewDates = [], filter = '', metric = 0, changed = false, busy = false, stale = false;
const labels = ['每队出战','两队同桌','每队分桌'];
const teamName = id => config.teams[id] || id;
const tableName = id => config.tables[id] || String(id);
const sum = values => values.reduce((a,b) => a+b,0);
const slot = r => r.day+' '+r.time;
function node(tag, text) {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    return n;
}
function button(text, action, cls='') {
    const n = node('button',text);
    n.type='button'; n.className=cls; n.onclick=action;
    return n;
}
function options(select, values, name, value) {
    select.replaceChildren(...values.map(v => new Option(name(v),String(v),false,v===value)));
}
function info(text) { $('message').textContent=text; }
function outdated() {
    changed=!!draft.length;
    if (changed) info('排程设置已修改，请重新生成预览。');
    $('save').disabled=true;
}
function paintDays() {
    $('days').replaceChildren(...[...days].sort().map(d => button(d+' ×',()=>{
        days.delete(d);paintDays();outdated();
    },'day')));
}
function initializeStage() {
    stage=config.stages.find(s=>s.id===$('stage').value);
    draft=[];previewDates=[];filter='';changed=false;
    $('tables').replaceChildren();
    for(const t of stage?.tables || []) {
        const label=node('label'), box=node('input');
        box.type='checkbox';box.checked=true;box.value=t;box.onchange=outdated;
        label.append(box,tableName(t));$('tables').append(label);
    }
    info(!stage?'没有可排程的开放阶段。':!stage.tables.length?'请先配置阶段用桌。':
         stage.teams.length<4?'本阶段至少需要四支启用且已获参赛资格的队伍。':'');
    $('generate').disabled=!stage || !stage.tables.length || stage.teams.length<4;
    render();
}
function stageMatches(){return config.matches.filter(m=>m.stage===stage?.id)}
function pairKey(a,b){return JSON.stringify(a<b?[a,b]:[b,a])}
function counts(rows) {
    const appearances=new Map(), pairs=new Map(), tables=new Map();
    const inc=(map,key)=>map.set(key,(map.get(key)||0)+1);
    function add(row){
        const teams=[...new Set(row.teams)];
        teams.forEach((t,i)=>{
            inc(appearances,t);inc(tables,JSON.stringify([t,row.table]));
            teams.slice(i+1).forEach(u=>inc(pairs,pairKey(t,u)));
        });
    }
    rows.forEach(add);
    return {appearances,pairs,tables,add};
}
function occupied(rows){
    const slots=new Map();
    for(const row of rows){
        const key=slot(row);
        if(!slots.has(key))slots.set(key,{teams:new Set(),tables:new Set()});
        const at=slots.get(key);at.tables.add(row.table);row.teams.forEach(t=>at.teams.add(t));
    }
    return slots;
}
function generate(){
    try{
        if(stale)return;
        const dates=[...days].sort(), start=$('start').value, n=$('rounds').valueAsNumber,
              gap=$('interval').valueAsNumber, tables=[...$('tables').querySelectorAll(':checked')].map(x=>Number(x.value));
        if(!dates.length||!tables.length||!start)throw Error('请选择比赛日、首场时间和用桌。');
        const [h,m]=start.split(':').map(Number);
        if(!Number.isInteger(n)||n<1||n>48||!Number.isInteger(gap)||gap<1||gap>1440||h*60+m+(n-1)*gap>=1440)
            throw Error('请核对时段数、间隔及当日结束时间。');
        if(dates.length*n*tables.length>500)throw Error('每批最多生成 500 场。');
        if(draft.length&&!confirm('替换当前整批草稿并重新生成预览？'))return;
        const weights=['appear','pair','spread'].map(id=>$(id).checked);
        const stats=counts(stageMatches()), taken=occupied(config.matches), rows=[];
        for(const day of dates)for(let j=0;j<n;j++){
            const minutes=h*60+m+j*gap;
            const time=[Math.floor(minutes/60),minutes%60].map(x=>String(x).padStart(2,'0')).join(':');
            const booked=taken.get(slot({day,time}));
            const free=tables.filter(t=>!booked?.tables.has(t));
            let pool=stage.teams.filter(t=>!booked?.teams.has(t));
            if(pool.length<4*free.length)throw Error(day+' '+time+' 可出战队伍不足，请减少同时用桌或更换时段。');
            for(const table of free){
                const teams=[];
                while(teams.length<4){
                    const cost=t=> (weights[0]?stats.appearances.get(t)||0:0)
                        +(weights[1]?sum(teams.map(u=>stats.pairs.get(pairKey(t,u))||0)):0)
                        +(weights[2]?stats.tables.get(JSON.stringify([t,table]))||0:0);
                    const scores=pool.map(t=>cost(t)+Math.random()*0.01);
                    const best=scores.indexOf(Math.min(...scores));
                    teams.push(pool.splice(best,1)[0]);
                }
                const row={day,time,table,teams};rows.push(row);stats.add(row);
            }
        }
        if(!rows.length)throw Error('所选日期和时段的桌次均已有赛程。');
        draft=rows;previewDates=dates;filter=rows[0].day;changed=false;
        info('');render();
    }catch(err){info(err.message)}
}
function choices(values,name,current,onchange,caption){
    const s=node('select');s.setAttribute('aria-label',caption);
    options(s,values,name,current);s.onchange=()=>onchange(s.value);
    return s;
}
function conflicts(){
    const slots=occupied(config.matches), errors=new Map();
    draft.forEach((r,i)=>{
        const key=slot(r);
        if(!slots.has(key))slots.set(key,{teams:new Set(),tables:new Set()});
        const used=slots.get(key);
        if(!r.time)errors.set(i,'请填写开赛时间');
        else if(used.tables.has(r.table))errors.set(i,'该时段桌次已占用');
        else if(new Set(r.teams).size!==4||r.teams.some(t=>used.teams.has(t)))errors.set(i,'该时段队伍重复出场');
        used.tables.add(r.table);r.teams.forEach(t=>used.teams.add(t));
    });
    return errors;
}
function statistics(){
    const rows=[...stageMatches(),...draft], stats=counts(rows);
    const teams=[...new Set([...(stage?.teams||[]),...rows.flatMap(r=>r.teams)])];
    const tables=[...new Set([...(stage?.tables||[]),...rows.map(r=>r.table)])];
    const data=[[],[],[]];
    teams.forEach((t,i)=>{
        data[0].push([teamName(t),stats.appearances.get(t)||0]);
        teams.slice(i+1).forEach(u=>data[1].push([teamName(t),teamName(u),stats.pairs.get(pairKey(t,u))||0]));
        data[2].push([teamName(t),...tables.map(n=>stats.tables.get(JSON.stringify([t,n]))||0)]);
    });
    function range(values){return values.length?Math.max(...values)-Math.min(...values):0}
    const differences=[range(data[0].map(r=>r[1])),range(data[1].map(r=>r[2])),
                       Math.max(0,...data[2].map(r=>range(r.slice(1))))];
    $('metrics').replaceChildren(...labels.map((label,i)=>{
        const b=button(label,()=>{metric=i;statistics()},metric===i?'on':'');
        const diff=differences[i],value=node('b',diff?'差 '+diff+' 次':'一致');
        if(diff)value.className='different';b.append(value);return b;
    }));
    const diff=differences[metric];
    $('warning').hidden=!diff;
    $('warning').textContent=['各队出战次数','各队组合的同桌次数','同一队在不同桌的出战次数'][metric]+'最多相差 '+diff+' 次，可按赛事安排保存。';
    const table=$('detail');table.replaceChildren();
    const head=table.createTHead().insertRow();
    for(const label of [['队伍','出战场数'],['队伍一','队伍二','同桌次数'],['队伍',...tables.map(tableName)]][metric])head.append(node('th',label));
    const body=table.createTBody();
    for(const values of data[metric]){const tr=body.insertRow();for(const v of values)tr.insertCell().textContent=v}
}
function render(){
    const errors=conflicts(),selectedDates=[...new Set(draft.map(r=>r.day))].sort();
    if(filter&&!selectedDates.includes(filter))filter='';
    $('generate').textContent=draft.length?'重新生成预览':'生成预览';
    $('total').textContent=selectedDates.length+' 个比赛日 · '+draft.length+' 场待保存';
    $('filters').replaceChildren(...(draft.length?['',...selectedDates]:[]).map(d=>button(d||'全部日期',()=>{filter=d;render()},d===filter?'on':'')));
    $('rows').replaceChildren();
    draft.forEach((r,i)=>{
        if(filter&&filter!==r.day)return;
        const tr=$('rows').insertRow();if(errors.has(i))tr.className='invalid';
        function edit(key,value){r[key]=value;render()}
        tr.insertCell().append(choices(previewDates,x=>x,r.day,v=>edit('day',v),'比赛日'));
        const time=node('input');time.type='time';time.setAttribute('aria-label','开赛时间');time.value=r.time;time.onchange=()=>edit('time',time.value);tr.insertCell().append(time);
        tr.insertCell().append(choices(stage.tables,tableName,r.table,v=>edit('table',Number(v)),'桌次'));
        r.teams.forEach((t,k)=>tr.insertCell().append(choices(stage.teams,teamName,t,v=>{r.teams[k]=v;render()},'队伍 '+(k+1))));
    });
    const first=errors.entries().next().value;
    $('status').textContent=first?'第 '+(first[0]+1)+' 场（'+draft[first[0]].day+' '+draft[first[0]].time+'）：'+first[1]:
        draft.length?'草稿尚未保存':'选择比赛日后生成预览';
    $('save').disabled=!draft.length||busy||changed||stale||!!first;
    statistics();
}
async function save(){
    if($('save').disabled)return;
    busy=true;document.querySelector('main').inert=true;$('save').disabled=true;info('正在保存…');
    try{
        const response=await fetch('/api/events/'+encodeURIComponent(config.id)+'/',{method:'POST',headers:{
            'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value
        },body:JSON.stringify({action:'batch-schedule',stageId:stage.id,revision:config.revision,rows:draft})});
        const result=await response.json();
        if(response.status===409){stale=true;throw Error('赛事已更新，当前草稿仍可查看。请刷新页面后重新生成。')}
        if(!response.ok)throw Error(result.error||'保存失败');
        const count=draft.length;
        config.matches.push(...draft.map(r=>({...r,stage:stage.id})));config.revision=result.revision;
        draft=[];filter='';info('已保存 '+count+' 场赛程。');
    }catch(err){info(err.message)}finally{busy=false;document.querySelector('main').inert=false;render()}
}
options($('stage'),config.stages.map(s=>s.id),id=>config.stages.find(s=>s.id===id).name,config.stages[0]?.id);
$('stage').onchange=()=>{if(draft.length&&!confirm('切换阶段会清除当前草稿，继续？')){$('stage').value=stage.id;return}initializeStage()};
$('day').value=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'});
$('add').onclick=()=>{if(!$('day').value){info('请选择比赛日。');return}if(!days.has($('day').value)){days.add($('day').value);paintDays();outdated()}};
for(const id of ['start','rounds','interval','appear','pair','spread'])$(id).onchange=outdated;
$('generate').onclick=generate;$('save').onclick=save;
window.addEventListener('beforeunload',e=>{if(draft.length){e.preventDefault();e.returnValue=''}});
initializeStage();
