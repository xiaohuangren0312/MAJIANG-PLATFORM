(function(root){
 const H=typeof module!=='undefined'?require('./model'):root.HQL;
 const originalMake=H.makeTournament,originalNew=H.newMatch;
 const clean=value=>String(value??'').trim();
 function audit(t,action,id){t.revision++;(t.rosterAudit??=[]).push({action,id,revision:t.revision})}
 H.makeEmptyTournament=(...args)=>{const t=originalMake(...args);t.players=[];t.teams=[];return t};
 H.saveTeam=(t,data,id)=>{
  if(t.type!=='team')throw Error('个人赛不需要建立队伍');
  const name=clean(data.name),short=clean(data.short),color=data.color||'#155e49';
  if(!name||name.length>60||short.length>12||!/^#[0-9a-f]{6}$/i.test(color))throw Error('请填写有效队名、简称和颜色');
  if(t.teams.some(x=>x.id!==id&&x.name===name))throw Error('本赛事已存在同名队伍');
  let team=id?t.teams.find(x=>x.id===id):null;if(id&&!team)throw Error('队伍不属于此赛事');
  if(!team){team={id:t.id+'-team-'+(t.teams.length+1)};t.teams.push(team)}
  Object.assign(team,{name,short,color,active:data.active!==false});audit(t,id?'更新队伍':'创建队伍',team.id);return team;
 };
 H.savePlayer=(t,data,id)=>{
  const name=clean(data.name),number=clean(data.number),teamId=t.type==='team'?(data.teamId||undefined):undefined;
  if(!name||name.length>40||!number||number.length>20)throw Error('请填写选手姓名和赛事报名编号');
  if(t.players.some(p=>p.id!==id&&p.number===number))throw Error('本赛事报名编号已使用；同名选手请用不同编号');
  if(teamId&&!t.teams.some(v=>v.id===teamId))throw Error('队伍不属于此赛事');
  let p=id?t.players.find(p=>p.id===id):null;if(id&&!p)throw Error('选手不属于此赛事');
  if(!p){p={id:t.id+'-player-'+(t.players.length+1)};t.players.push(p)}
  const oldTeam=p.teamId;
  Object.assign(p,{name,number,teamId,active:data.active!==false});
  if(oldTeam!==teamId)(t.membershipHistory??=[]).push({playerId:p.id,from:oldTeam,to:teamId,revision:t.revision+1});
  audit(t,id?'更新报名':'新增报名',p.id);return p;
 };
 H.eligiblePlayers=t=>t.players.filter(p=>p.active!==false&&(t.type==='individual'||t.teams.some(team=>team.id===p.teamId&&team.active!==false)));
 H.newMatch=(t,stage)=>{
  const eligible=H.eligiblePlayers(t);if(eligible.length<4)throw Error('至少需要四名可出场选手；团体赛还需先为选手分配有效队伍');
  const m=originalNew(t,stage);m.seats=eligible.slice(0,4).map((p,i)=>({...m.seats[i],playerId:p.id,teamId:p.teamId}));return m;
 };
 H.setLineup=(t,m,ids)=>{
  if(m.tournamentId!==t.id||m.status!=='draft'||t.stages.find(s=>s.id===m.stageId)?.locked)throw Error('只能调整当前赛事未锁定的草稿阵容');
  if(ids.length!==4||new Set(ids).size!==4)throw Error('四个座次必须选择四名不同选手');
  const eligible=H.eligiblePlayers(t);if(ids.some(id=>!eligible.some(p=>p.id===id)))throw Error('选手未报名、已停用或尚未分配有效队伍');
  const oldIds=m.seats.map(s=>s.playerId);
  if([...m.penalties,...m.yakuman].some(e=>!ids.includes(e.playerId)))throw Error('被换下选手仍有罚分或役满事件，请先处理草稿事件');
  const sameSet=ids.every(id=>oldIds.includes(id));
  m.seats=ids.map((id,i)=>{const p=eligible.find(p=>p.id===id);const previous=sameSet?m.seats.find(s=>s.playerId===id):null;return {playerId:id,teamId:p.teamId,score:previous?previous.score:m.rules.start}});
  if(!sameSet)m.deposit=0;
  t.revision++;return {resetScores:!sameSet};
 };
 H.statistics=(t,stage,kind,metric='raw')=>{
  const rows=H.leaderboard(t,stage,kind,metric),map=Object.fromEntries(rows.map(r=>[r.id,r]));
  rows.forEach(r=>Object.assign(r,{places:[0,0,0,0],rankSum:0,appearances:0,best:null,last:0,scoreHistory:[]}));
  const matches=t.matches.filter(m=>m.status==='published'&&(stage==='all'||m.stageId===stage)).sort((a,b)=>a.date.localeCompare(b.date)||a.number-b.number);
  matches.forEach(m=>{const scores=H.scoreMatch(m,t);const increments={};scores.forEach((s,i)=>{
   const r=map[kind==='team'?s.teamId:s.playerId];if(!r)return;
   const n=s.tied?scores.filter(v=>v.rank===s.rank).length:1;
   for(let pos=s.rank-1;pos<s.rank-1+n;pos++)r.places[pos]+=1/n;
   r.rankSum+=s.rank+(n-1)/2;r.appearances++;r.best=r.best===null?m.seats[i].score:Math.max(r.best,m.seats[i].score);
   increments[r.id]=(increments[r.id]||0)+(kind==='team'?s.teamNet:s.net);
  });Object.entries(increments).forEach(([id,value])=>{map[id].last=value;map[id].scoreHistory.push(value)})});
  rows.forEach(r=>{const n=r.appearances;r.avgRank=n?r.rankSum/n:null;r.topRate=n?r.places[0]/n:null;r.topTwo=n?(r.places[0]+r.places[1])/n:null;r.avoidLast=n?1-r.places[3]/n:null;r.avgPoints=n?r.raw/n:null});return rows;
 };
 H.teamContributions=(t,teamId,stage)=>{
  if(!t.teams.some(team=>team.id===teamId))throw Error('队伍不属于此赛事');
  const map={};
  t.players.filter(p=>p.teamId===teamId).forEach(p=>map[p.id]={id:p.id,name:p.name,games:0,base:0,penalty:0,total:0,current:true});
  t.matches.filter(m=>m.status==='published'&&(stage==='all'||m.stageId===stage)).forEach(m=>H.scoreMatch(m,t).filter(s=>s.teamId===teamId).forEach(s=>{const p=t.players.find(p=>p.id===s.playerId),r=map[p.id]??={id:p.id,name:p.name,games:0,base:0,penalty:0,total:0,current:p.teamId===teamId};r.games++;r.base+=s.base;r.penalty+=s.teamPenalty;r.total+=s.teamNet}));
  return Object.values(map).sort((a,b)=>b.total-a.total);
 };
 if(typeof module!=='undefined')module.exports=H;
})(typeof globalThis!=='undefined'?globalThis:this);
