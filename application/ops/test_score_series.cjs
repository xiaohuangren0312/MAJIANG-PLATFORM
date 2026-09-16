const assert=require('node:assert/strict');const {scoreSeries}=require('../static/trend-data.js');
const t={results:[{stageId:'s',date:'2026-01-01',number:1,seats:[{teamId:'a',playerId:'p',teamPoints:10,points:10}]},{stageId:'s',date:'2026-01-02',number:2,seats:[]}],statistics:{s:{competitive:{team:[{id:'a',carry:-5,total:15}]},raw:{team:[{id:'a',total:10}]}}},dailySummaries:[{stageId:'s',day:'2026-01-01',entries:[{teamId:'a',points:20}]}]};
let s=scoreSeries(t,'team','a','s','competitive');assert.equal(s.total,15);assert.equal(s.carry,-5);assert.equal(s.difference,0);assert.equal(s.points[1].played,false);assert.equal(s.points[1].total,15);
s=scoreSeries(t,'team','a','s','raw');assert.equal(s.carry,0);assert.equal(s.total,20);assert.equal(s.difference,-10);
t.dailySummaries[0].entries[0].points=null;s=scoreSeries(t,'team','a','s','competitive');assert.equal(s.total,null);assert.equal(s.difference,null);
assert.equal(scoreSeries(t,'team','a','all','competitive').competitive,false);console.log('Carry, summary override, idle date, discrepancy and unknown checks passed');
