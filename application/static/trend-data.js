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
