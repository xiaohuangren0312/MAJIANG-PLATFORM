const H=require('../v3/roster-model');
const fs=require('node:fs'),path=require('node:path');
function projectPublic(tournaments){
 return {demo:true,updatedAt:'2026-09-05T18:00:00+08:00',tournaments:tournaments.filter(t=>t.visibility==='public').map(t=>{
  const visibleStages=t.stages.filter(s=>s.visibility==='public');
  const stageIds=new Set(visibleStages.map(s=>s.id));
  // Only final published results enter public statistics. Draft results never leave this boundary.
  const eligible=t.matches.filter(m=>m.status==='published'&&m.visibility==='public'&&stageIds.has(m.stageId)).map(m=>({...m,penalties:m.penalties.filter(e=>e.status!=='pending'),yakuman:m.yakuman.filter(e=>e.status!=='pending')}));
  const source={...t,matches:eligible,carries:t.carries.filter(c=>c.visibility==='public')};
  const teams=t.teams.map(team=>({id:team.id,name:team.name,color:team.color||'#196346'}));
  const players=t.players.map(p=>({id:p.id,name:p.name,teamId:p.teamId||null,bio:p.publicBio||'用每一场认真对局，书写自己的赛季。'}));
  const result=eligible.map(m=>({id:m.id,stageId:m.stageId,date:m.date,table:m.table,number:m.number,ruleName:m.rules.name,ruleVersion:m.rules.version,
   seats:H.scoreMatch(m,source).map((s,i)=>({playerId:s.playerId,teamId:s.teamId||null,score:m.seats[i].score,rank:s.rank,tied:s.tied,base:s.base,penalty:s.personalPenalty,points:s.net,teamPoints:s.teamNet})),
   penalties:m.penalties.map(p=>({playerId:p.playerId,amount:p.amount,scope:p.scope,explanation:p.publicExplanation||'赛事规则积分调整'})),
   yakuman:m.yakuman.map(y=>({playerId:y.playerId,types:y.types,multiplier:y.multiplier,round:y.round,method:y.method||'自摸'}))}));
  const schedule=t.matches.filter(m=>m.scheduleVisibility==='public'&&stageIds.has(m.stageId)).map(m=>({id:m.id,stageId:m.stageId,date:m.date,time:m.publicTime||'14:00',table:m.table,number:m.number,lineupPublished:result.some(r=>r.id===m.id)||m.lineupVisibility==="public",players:m.seats.map(s=>({playerId:(result.some(r=>r.id===m.id)||m.lineupVisibility==="public")?s.playerId:null,teamId:s.teamId||null})),state:result.some(r=>r.id===m.id)?'completed':m.scheduleState==='cancelled'?'cancelled':'scheduled',resultId:result.some(r=>r.id===m.id)?m.id:null}));
  const statistics={};
  ['all',...stageIds].forEach(stage=>{statistics[stage]={};['raw','competitive'].forEach(metric=>{statistics[stage][metric]={};['team','player'].forEach(kind=>{
   statistics[stage][metric][kind]=H.statistics(source,stage,kind,metric).map(r=>({id:r.id,name:r.name,base:r.base,penalty:r.penalty,carry:r.carry,total:r.total,raw:r.raw,games:r.games,rank:r.rank,places:r.places,avgRank:r.avgRank,topRate:r.topRate,topTwo:r.topTwo,avoidLast:r.avoidLast,best:r.best,avgPoints:r.avgPoints,yakuman:r.yakuman,last:r.last,history:r.scoreHistory}));
  })})});
  return {id:t.id,name:t.name,type:t.type,season:'2026',venue:'欢雀楼 · 主赛场',currentStage:visibleStages[0]?.id,stages:visibleStages.map(s=>({id:s.id,name:s.name})),teams,players,results:result,schedule,statistics,rules:{name:t.rules.name,start:t.rules.start,returnPoints:t.rules.returnPoints,bonuses:t.rules.bonuses,description:'阶段带入独立列示；原始累计不重复计算带入分。'}};
 })};
}
function demo(){
 const ts=H.seed();ts.forEach((t,i)=>{t.visibility='public';t.name=i?'欢雀楼个人公开赛':'欢雀楼秋季团体联赛';t.stages[0].name=i?'预选赛':'常规赛';t.stages[1].name='决赛';t.stages.forEach(s=>s.visibility='public');t.teams.forEach((team,k)=>team.color=['#21654a','#c4503d','#526c9a','#785d88'][k]);t.matches.forEach(m=>{m.visibility='public';m.scheduleVisibility='public';m.publicTime=m.number%2?'14:00':'16:00'});const upcoming=H.newMatch(t);upcoming.date='2026-09-12';upcoming.scheduleVisibility='public';upcoming.publicTime='14:00';upcoming.visibility='private';upcoming.penalties.push({playerId:t.players[0].id,amount:990,scope:'personal',reason:'INTERNAL_ONLY_DRAFT_NOTE'});const next=H.newMatch(t);next.date='2026-09-12';next.publicTime='16:00';next.scheduleVisibility='public';next.visibility='private';});
 const hidden=H.makeTournament('private-event','PRIVATE_EVENT_SHOULD_NOT_LEAK','team');hidden.visibility='private';ts.push(hidden);return ts;
}
if(require.main===module){const output=path.join(__dirname,'site','data.json');fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(projectPublic(demo()),null,2));console.log('Public demo data generated: '+output)}
module.exports={projectPublic,demo};
