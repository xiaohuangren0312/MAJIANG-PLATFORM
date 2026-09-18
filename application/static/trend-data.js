function scoreTimeline(t,kind,id,stage='all'){
 const matches=t.results.filter(m=>stage==='all'||m.stageId===stage).slice().sort((a,b)=>(a.date||'').localeCompare(b.date||'')||(a.time||'').localeCompare(b.time||'')||a.number-b.number);
 if(kind==='player')return matches.filter(m=>m.seats.some(s=>s.playerId===id)).map((m,i)=>{const s=m.seats.find(s=>s.playerId===id);return {label:'第'+(i+1)+'半庄',date:m.date,delta:s.points??null,played:true}});
 const days=new Map();for(const m of matches){const key=m.date;let d=days.get(key);if(!d){d={label:key,parts:new Map()};days.set(key,d)}let part=d.parts.get(m.stageId);if(!part){part={delta:0,played:false,missing:false};d.parts.set(m.stageId,part)}for(const s of m.seats.filter(s=>s.teamId===id)){part.played=true;if(s.teamPoints==null)part.missing=true;else part.delta+=s.teamPoints}}
 for(const summary of t.dailySummaries||[]){if(stage!=='all'&&summary.stageId!==stage)continue;let day=days.get(summary.day);if(!day){day={label:summary.day,parts:new Map()};days.set(summary.day,day)}const entry=summary.entries.find(x=>x.teamId===id);if(entry)day.parts.set(summary.stageId,{delta:entry.points||0,played:true,missing:entry.points==null})}
 return [...days.values()].sort((a,b)=>a.label.localeCompare(b.label)).map(d=>({label:d.label,date:d.label,played:[...d.parts.values()].some(x=>x.played),delta:[...d.parts.values()].some(x=>x.missing)?null:[...d.parts.values()].reduce((n,x)=>n+x.delta,0)}));
}
if(typeof module!=='undefined')module.exports={scoreTimeline};

function rankMovements(t,kind,stage,rows){
 const matches=t.results.filter(m=>stage==='all'||m.stageId===stage).slice().sort((a,b)=>(a.date||'').localeCompare(b.date||'')||(a.time||'').localeCompare(b.time||'')||a.number-b.number);
 const deltas=new Map();let label='';
 if(kind==='team'){
  for(const row of rows){const last=scoreTimeline(t,kind,row.id,stage).at(-1);if(last){label=last.date;deltas.set(row.id,last.delta)}}
 }else{
  const last=matches.at(-1);if(!last)return {};
  label=last.date+' '+(last.time||'');
  const batch=matches.filter(m=>m.date===last.date&&(last.pairingRound?m.pairingRound===last.pairingRound&&m.stageId===last.stageId:last.time?m.time===last.time:m.id===last.id));
  for(const m of batch)for(const seat of m.seats){if(!seat.playerId)continue;const prior=deltas.has(seat.playerId)?deltas.get(seat.playerId):0;deltas.set(seat.playerId,seat.points==null||prior===null?null:prior+seat.points)}
 }
 if(!label||rows.some(r=>deltas.get(r.id)===null||!Number.isFinite(r.total)))return {};
 const before=rows.map(r=>({id:r.id,total:r.total-(deltas.get(r.id)||0)}));
 const rank=(list,id)=>1+list.filter(r=>r.total>list.find(x=>x.id===id).total).length;
 return Object.fromEntries(rows.map(r=>[r.id,{before:rank(before,r.id),after:rank(rows,r.id),change:rank(before,r.id)-rank(rows,r.id),label}]));
}
if(typeof module!=='undefined')module.exports={scoreTimeline,rankMovements};

// Qualification always uses the complete competitive board, independent of display filters.
function qualificationMap(t,kind,stage){
 const count=t.stages.find(s=>s.id===stage)?.advanceCount||0;
 if(!count||stage==='all'||(t.type==='team'?'team':'player')!==kind)return null;
 const rows=t.statistics[stage]?.competitive?.[kind]||[];
 if(!rows.length)return null;
 return {count,rows:Object.fromEntries(rows.map(r=>[r.id,{pending:!r.games,rank:1+rows.filter(x=>x.total>r.total).length,qualified:r.games>0&&1+rows.filter(x=>x.total>r.total).length<=count}]))};
}
if(typeof module!=='undefined')module.exports.qualificationMap=qualificationMap;

function scoreSeries(t,kind,id,stage='all',metric='raw'){
 const competitive=metric==='competitive'&&stage!=='all';
 const row=t.statistics[stage]?.[competitive?'competitive':'raw']?.[kind]?.find(r=>r.id===id);
 const carry=competitive?(row?.carry??0):0;
 let total=carry;
 const points=scoreTimeline(t,kind,id,stage).map(p=>{total=p.delta==null||total==null?null:total+p.delta;return {...p,total}});
 const expected=row?.total??null;
 return {points,carry,competitive,expected,total,difference:expected==null||total==null?null:expected-total};
}
if(typeof module!=='undefined')module.exports.scoreSeries=scoreSeries;

// Live standings use persisted stage settlement values; never recompute a ratio here.
function teamBoardContext(t,requested='live',requestedMetric){
 const ids=(t.stages||[]).map(s=>s.id);
 const current=ids.includes(t.currentStage)?t.currentStage:[...ids].reverse().find(id=>(t.statistics[id]?.competitive?.team||[]).length)||ids[0];
 const live=requested==='live'||requested==='all';
 const stage=live?current:requested;
 const metric='competitive';
 const rows=t.statistics[stage]?.[metric]?.team||[];
 const active=new Set(rows.map(r=>r.id)),earlier=ids.slice(0,ids.indexOf(stage)),eliminated=[];
 if(live)for(const team of t.teams||[]){
  if(active.has(team.id))continue;
  for(const id of [...earlier].reverse()){
   const row=t.statistics[id]?.competitive?.team?.find(r=>r.id===team.id);
   if(row){eliminated.push({...row,stageId:id,stageName:t.stages.find(s=>s.id===id).name});break;}
  }
 }
 const finished=Boolean(t.archived||(t.historical&&current===ids.at(-1)&&(t.schedule||[]).length&&(t.schedule||[]).every(m=>m.state==='completed'||m.state==='cancelled')));
 return {stage,metric,rows,live,eliminated,finished};
}
if(typeof module!=='undefined')module.exports.teamBoardContext=teamBoardContext;

function nextMatchDay(t,today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())){
 const schedule=t.schedule||[];
 if(t.archived||(t.historical&&schedule.length&&schedule.every(m=>['completed','cancelled'].includes(m.state))))return {state:'finished',matches:[]};
 const pending=schedule.filter(m=>m.state==='scheduled'&&m.date>=today).sort((a,b)=>a.date.localeCompare(b.date)||(a.time||'').localeCompare(b.time||''));
 if(!pending.length)return {state:'empty',matches:[]};
 const date=pending[0].date;
 return {state:date===today?'today':'next',date,matches:schedule.filter(m=>m.date===date&&m.state!=='cancelled').slice().sort((a,b)=>(a.time||'').localeCompare(b.time||'')||String(a.table||'').localeCompare(String(b.table||''))||(a.number||0)-(b.number||0))};
}
if(typeof module!=='undefined')module.exports.nextMatchDay=nextMatchDay;
