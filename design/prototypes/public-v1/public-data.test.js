const assert=require('node:assert/strict'),{projectPublic,demo}=require('./build-public-data');
const source=demo(),data=projectPublic(source),serialized=JSON.stringify(data);
assert.equal(data.tournaments.length,2);
assert.ok(!serialized.includes('INTERNAL_ONLY_DRAFT_NOTE'));
assert.ok(!serialized.includes('PRIVATE_EVENT_SHOULD_NOT_LEAK'));
assert.ok(!serialized.includes('rosterAudit'));
for(const t of data.tournaments){assert.equal(t.results.length,3);assert.equal(t.schedule.length,5);assert.equal(t.schedule.filter(m=>m.state==='scheduled').length,2);assert.ok(t.schedule.filter(m=>m.state==='scheduled').every(m=>m.resultId===null&&!('seats' in m)&&!('score' in m)));assert.equal(t.statistics.all.raw.player.reduce((n,p)=>n+p.penalty,0),-200)}
for(const event of data.tournaments){
  for(const match of event.schedule){
    assert.equal(match.lineupPublished,!!match.resultId);
    if(!match.resultId)assert.ok(match.players.every(p=>p.playerId===null));
  }
}
const lineupSource=demo(),unpublished=data.tournaments[0].schedule.find(m=>!m.resultId);
const lineupMatch=lineupSource[0].matches.find(m=>m.id===unpublished.id);
assert.deepEqual(unpublished.players.map(p=>p.teamId),lineupMatch.seats.map(s=>s.teamId||null));
lineupMatch.lineupVisibility='public';
const announced=projectPublic(lineupSource).tournaments[0].schedule.find(m=>m.id===lineupMatch.id);
assert.equal(announced.lineupPublished,true);
assert.equal(announced.resultId,null);
assert.deepEqual(announced.players.map(p=>p.playerId),lineupMatch.seats.map(s=>s.playerId));
const t=source[0];t.matches[0].penalties.push({playerId:t.players[0].id,amount:500,scope:'personal',reason:'PENDING_NOTE',status:'pending'});
const after=projectPublic(source);assert.deepEqual(after.tournaments[0].statistics,data.tournaments[0].statistics);assert.ok(!JSON.stringify(after).includes('PENDING_NOTE'));
t.stages[0].visibility='private';const stageHidden=projectPublic(source).tournaments[0];assert.equal(stageHidden.results.length,0);assert.equal(stageHidden.schedule.length,0);
console.log('Public projection: private events, stages, drafts, notes and pending penalties excluded; published schedule remains visible.');
