const assert=require('node:assert/strict');
const {qualificationMap:q}=require('../static/trend-data.js');
const t={type:'personal',stages:[{id:'regular',advanceCount:2}],statistics:{regular:{competitive:{player:[{id:'a',total:100,games:1},{id:'b',total:50,games:1},{id:'c',total:50,games:1},{id:'d',total:0,games:0}]}}}};
assert.deepEqual(Object.values(q(t,'player','regular').rows).map(r=>r.qualified),[true,true,true,false]);
assert.equal(q(t,'team','regular'),null);assert.equal(q(t,'player','all'),null);assert.equal(q({...t,type:'team'},'player','regular'),null);
assert.equal(q({...t,stages:[{id:'regular',advanceCount:0}]},'player','regular'),null);
console.log('Qualification tie, no-games, event-kind and unset-cutoff checks passed');
