function scoreTimeline(t,kind,id,stage='all'){
 const matches=t.results.filter(m=>stage==='all'||m.stageId===stage).slice().sort((a,b)=>(a.date||'').localeCompare(b.date||'')||(a.time||'').localeCompare(b.time||'')||a.number-b.number);
 if(kind==='player')return matches.filter(m=>m.seats.some(s=>s.playerId===id)).map((m,i)=>{const s=m.seats.find(s=>s.playerId===id);return {label:'第'+(i+1)+'半庄',date:m.date,delta:s.points??null,played:true}});
 const days=new Map();for(const m of matches){const key=m.date;let d=days.get(key);if(!d){d={label:key,parts:new Map()};days.set(key,d)}let part=d.parts.get(m.stageId);if(!part){part={delta:0,played:false,missing:false};d.parts.set(m.stageId,part)}for(const s of m.seats.filter(s=>s.teamId===id)){part.played=true;if(s.teamPoints==null)part.missing=true;else part.delta+=s.teamPoints}}
 for(const summary of t.dailySummaries||[]){if(stage!=='all'&&summary.stageId!==stage)continue;let day=days.get(summary.day);if(!day){day={label:summary.day,parts:new Map()};days.set(summary.day,day)}const entry=summary.entries.find(x=>x.teamId===id);if(entry)day.parts.set(summary.stageId,{delta:entry.points||0,played:true,missing:entry.points==null})}
 return [...days.values()].sort((a,b)=>a.label.localeCompare(b.label)).map(d=>({label:d.label,date:d.label,played:[...d.parts.values()].some(x=>x.played),delta:[...d.parts.values()].some(x=>x.missing)?null:[...d.parts.values()].reduce((n,x)=>n+x.delta,0)}));
}
if(typeof module!=='undefined')module.exports={scoreTimeline};
