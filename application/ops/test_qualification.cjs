const assert=require('node:assert/strict');
const {qualificationMap:q}=require('../static/trend-data.js');
const t={type:'personal',stages:[{id:'regular',advanceCount:2}],statistics:{regular:{competitive:{player:[{id:'a',total:100,games:1},{id:'b',total:50,games:1},{id:'c',total:50,games:1},{id:'d',total:0,games:0}]}}}};
assert.deepEqual(Object.values(q(t,'player','regular').rows).map(r=>r.qualified),[true,true,true,false]);
assert.equal(q(t,'team','regular'),null);assert.equal(q(t,'player','all'),null);assert.equal(q({...t,type:'team'},'player','regular'),null);
assert.equal(q({...t,stages:[{id:'regular',advanceCount:0}]},'player','regular'),null);
console.log('Qualification tie, no-games, event-kind and unset-cutoff checks passed');

assert.equal(q(t,'player','regular').rows.d.pending,true);
assert.equal(q(t,'player','regular').rows.a.pending,false);
const zero={...t,statistics:{regular:{competitive:{player:[{id:'a',total:0,games:0},{id:'b',total:0,games:0}]}}}};
assert(Object.values(q(zero,'player','regular').rows).every(r=>r.rank===1&&r.pending));

const s4={type:'team',stages:[{id:'regular',advanceCount:4}],statistics:{regular:{competitive:{team:[{id:'b',total:690,games:2},{id:'a',total:450,games:2},{id:'e',total:0,games:0},{id:'f',total:0,games:0},{id:'c',total:-100,games:2},{id:'d',total:-1040,games:2}]}}}};
const cut=q(s4,'team','regular');const entries=Object.values(cut.rows);assert.deepEqual(entries.map(r=>r.rank),[1,2,3,3,5,6]);assert.equal(entries.findIndex((r,i)=>i>0&&entries[i-1].rank<=cut.count&&r.rank>cut.count),4);
