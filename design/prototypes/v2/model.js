(function(root){
  const S=typeof module!=='undefined'?require('./scoring.js'):root.Scoring;
  const clone=x=>JSON.parse(JSON.stringify(x));
  const templates={
    ml:{...S.defaults,id:'ml',name:'M.LEAGUE · 基础计分',kyotaku:'distributed',ready:true},
    npm:{...S.defaults,id:'npm',name:'日本职业麻将协会 · 基础计分',kyotaku:'retained',ready:true},
    saiko:{...S.defaults,start:30000,returnPoints:30000,bonuses:[30,10,-10,-30],id:'saiko',name:'最高位战普通 · 参考草稿',kyotaku:'unverified',ready:false},
    renmei:{...S.defaults,start:30000,returnPoints:30000,bonuses:null,id:'renmei',name:'日本职业麻将联盟 · 待配置',kyotaku:'unverified',ready:false}
  };
  const types=['大三元','四暗刻','国士无双','小四喜','大四喜','字一色','清老头','绿一色','四杠子','九莲宝灯','天和','地和'];
  function scoreMatch(match,tournament){
    const r=match.rules;
    if(!r.ready)throw Error('此参考模板尚未完整配置，请在规则页另存为已核对的自定义版本后用于新对局');
    if(match.tournamentId!==tournament.id)throw Error('赛事不匹配');
    const ids=match.seats.map(s=>s.playerId);
    if(new Set(ids).size!==4||ids.some(id=>!tournament.players.some(p=>p.id===id)))throw Error('四名选手须不同且属于本赛事');
    if(!tournament.stages.some(s=>s.id===match.stageId))throw Error('阶段不属于本赛事');
    if(tournament.type==='team'&&match.seats.some(s=>!tournament.teams.some(team=>team.id===s.teamId)))throw Error('队伍不属于本赛事');
    const deposit=match.deposit??0;
    if(!Number.isSafeInteger(deposit)||deposit<0||deposit%1000)throw Error('剩余供托须为非负 1000 点整数倍');
    if(r.kyotaku==='distributed'&&deposit!==0)throw Error('本规则要求先分配终局供托，再录入最终点数');
    const scored=S.calculate(match.seats.map(s=>s.score),{...r,expectedTotal:r.start*4-deposit});
    const penalties=match.penalties||[];
    penalties.forEach(p=>{
      if(!ids.includes(p.playerId)||!Number.isSafeInteger(p.amount)||p.amount<=0||!p.reason.trim())throw Error('罚分需要有效选手、正数扣分和原因');
      if(!['personal','team','both'].includes(p.scope)||tournament.type==='individual'&&p.scope!=='personal')throw Error('处罚影响范围与赛事类型不符');
    });
    (match.yakuman||[]).forEach(y=>{if(!ids.includes(y.playerId)||!Array.isArray(y.types)||!y.types.length||new Set(y.types).size!==y.types.length||y.types.some(v=>!types.includes(v))||!Number.isInteger(y.multiplier)||y.multiplier<1||!y.round.trim())throw Error('役满需填写有效选手、局和役种/倍数');});
    return scored.map((s,i)=>{
      const player=tournament.players.find(p=>p.id===ids[i]);
      const mine=penalties.filter(p=>p.playerId===player.id);
      const personalPenalty=mine.filter(p=>p.scope!=='team').reduce((n,p)=>n-p.amount,0);
      const teamPenalty=mine.filter(p=>p.scope!=='personal').reduce((n,p)=>n-p.amount,0);
      return {...s,playerId:player.id,teamId:match.seats[i].teamId??player.teamId,base:s.pointsTenths,personalPenalty,teamPenalty,net:s.pointsTenths+personalPenalty,teamNet:s.pointsTenths+teamPenalty};
    });
  }
  // Value in 0.1 pt units; ratio is rational. Avoid binary decimal rounding.
  function transform(value,numerator,denominator,mode){
    if(![value,numerator,denominator].every(Number.isSafeInteger)||numerator<0||denominator<=0)throw Error('比例须为非负整数分子和正整数分母');
    const n=value*numerator;
    if(!Number.isSafeInteger(n))throw Error('结算数值超出范围');
    const x=n/denominator;
    if(mode==='ceil')return Math.ceil(x);
    if(mode==='floor')return Math.floor(x);
    if(mode==='trunc')return Math.trunc(x);
    if(mode==='halfAway')return Math.sign(n)*Math.floor((Math.abs(n)*2+denominator)/(denominator*2));
    throw Error('舍入方式无效');
  }
  function leaderboard(t,stage,kind,metric='raw'){
    if(kind==='team'&&t.type!=='team')return [];
    const list=kind==='team'?t.teams:t.players;
    const rows=list.map(x=>({id:x.id,name:x.name,base:0,penalty:0,carry:0,games:0,yakuman:0}));
    const index=Object.fromEntries(rows.map(x=>[x.id,x]));
    t.matches.filter(m=>m.status==='published'&&(stage==='all'||m.stageId===stage)).forEach(m=>{
      const ss=scoreMatch(m,t);
      const seen=new Set();
      ss.forEach(s=>{const row=index[kind==='team'?s.teamId:s.playerId];if(!row)return;row.base+=s.base;row.penalty+=kind==='team'?s.teamPenalty:s.personalPenalty;if(!seen.has(row.id)){row.games++;seen.add(row.id)}});
      (m.yakuman||[]).forEach(y=>{const s=ss.find(s=>s.playerId===y.playerId);const row=index[kind==='team'?s.teamId:s.playerId];if(row)row.yakuman++;});
    });
    if(stage!=='all'&&metric==='competitive')t.carries.filter(c=>c.targetStage===stage&&c.kind===kind).forEach(c=>{if(index[c.id])index[c.id].carry+=c.value});
    rows.forEach(r=>{r.raw=r.base+r.penalty;r.total=r.raw+r.carry});
    rows.sort((a,b)=>b.total-a.total||a.name.localeCompare(b.name));
    rows.forEach((r,i)=>{r.rank=i&&r.total===rows[i-1].total?rows[i-1].rank:i+1});
    return rows;
  }
  function settlementPreview(t,sourceStage,targetStage,kind,options){
    const source=t.stages.find(s=>s.id===sourceStage),target=t.stages.find(s=>s.id===targetStage);
    if(!source||!target||t.stages.indexOf(target)!==t.stages.indexOf(source)+1)throw Error('请选择相邻的源阶段和下一阶段');
    if(source.locked)throw Error('源阶段已经结算锁定');
    if(t.matches.some(m=>m.stageId===sourceStage&&!['published','cancelled'].includes(m.status)))throw Error('本阶段还有未发布对局，不能结算');
    if(!t.matches.some(m=>m.stageId===sourceStage&&m.status==='published'))throw Error('本阶段没有已发布对局');
    if(t.matches.some(m=>m.stageId===targetStage&&m.status!=='cancelled')||t.carries.some(c=>c.targetStage===targetStage))throw Error('目标阶段已经开始或已有带入记录');
    if(kind==='team'&&t.type!=='team')throw Error('个人赛不能结算队伍分');
    const rows=leaderboard(t,sourceStage,kind,'competitive').map(r=>{
      const compress=options.penalties==='full'?r.total-r.penalty:r.total;
      const kept=options.penalties==='full'?r.penalty:0;
      const suggested=transform(compress,options.numerator,options.denominator,options.rounding)+kept;
      return {...r,theoretical:compress*options.numerator/options.denominator+kept,suggested,final:suggested,reason:'',advance:true};
    });
    return {tournamentId:t.id,sourceRevision:t.revision,sourceStage,targetStage,kind,options:clone(options),rows};
  }
  function commitSettlement(t,plan){
    if(plan.tournamentId!==t.id||plan.sourceRevision!==t.revision)throw Error('来源成绩或赛事已变化，请重新生成预览');
    const fresh=settlementPreview(t,plan.sourceStage,plan.targetStage,plan.kind,plan.options);
    if(plan.rows.length!==fresh.rows.length||new Set(plan.rows.map(r=>r.id)).size!==fresh.rows.length)throw Error('预览对象不完整');
    plan.rows.forEach(r=>{const old=fresh.rows.find(x=>x.id===r.id);if(!old||r.suggested!==old.suggested||!Number.isSafeInteger(r.final)||r.final!==r.suggested&&!r.reason.trim())throw Error('人工调整必须为有效分值并填写原因')});
    if(!plan.rows.some(r=>r.advance))throw Error('至少选择一个晋级对象');
    const entries=plan.rows.filter(r=>r.advance).map(r=>({targetStage:plan.targetStage,kind:plan.kind,id:r.id,value:r.final}));
    t.carries.push(...entries);t.settlements.push(clone(plan));t.stages.find(s=>s.id===plan.sourceStage).locked=true;t.revision++;
  }
  function makeTournament(id,name,type,template='ml'){
    const teams=type==='team'?['青岚','赤羽','白夜','玄武'].map((name,i)=>({id:id+'-t'+i,name})):[];
    return {id,name,type,template,rules:clone(templates[template]),teams,players:['林澈','秋山','夏川','白石'].map((name,i)=>({id:id+'-p'+i,name,teamId:teams[i]?.id})),stages:[{id:'r',name:'预赛',locked:false},{id:'s',name:'决赛',locked:false}],matches:[],carries:[],settlements:[],revision:1};
  }
  function newMatch(t,stageId='r'){
    const stage=t.stages.find(s=>s.id===stageId);
    if(!stage||stage.locked)throw Error('该阶段不存在或已锁定');
    const expected=t.rules.start*4;
    const scores=[41600,30000,20000,expected-91600];
    const match={id:t.id+'-m'+(t.matches.length+1),tournamentId:t.id,stageId,date:'2026-09-06',table:'A',number:t.matches.length+1,status:'draft',rules:clone(t.rules),deposit:0,seats:t.players.slice(0,4).map((p,i)=>({playerId:p.id,teamId:p.teamId,score:scores[i]})),penalties:[],yakuman:[]};
    t.matches.push(match);t.revision++;return match;
  }
  function publish(t,m){if(m.status==='published')throw Error('此对局已经发布');if(t.stages.find(s=>s.id===m.stageId)?.locked)throw Error('阶段已锁定');scoreMatch(m,t);m.status='published';t.revision++}
  function seed(){const a=makeTournament('t1','欢雀楼秋季团体联赛','team','ml'),b=makeTournament('t2','欢雀楼个人公开赛','individual','npm');
    [a,b].forEach((t,ti)=>{for(let n=0;n<3;n++){const m=newMatch(t);m.date='2026-09-0'+(3+n);m.table=n%2?'B':'A';const scores=n===0?[35000,30000,22000,13000]:n===1?[20000,45000,30000,5000]:[32000,28000,24000,16000];m.seats.forEach((s,i)=>s.score=scores[(i+ti)%4]);if(n===1)m.penalties.push({playerId:t.players[1].id,amount:200,scope:t.type==='team'?'both':'personal',reason:'迟到（演示裁定）'});if(n===0)m.yakuman.push({playerId:t.players[0].id,types:['大三元'],multiplier:1,round:'南2局',method:'自摸'});publish(t,m)}});return [a,b]}
  const api={templates,types,scoreMatch,transform,leaderboard,settlementPreview,commitSettlement,makeTournament,newMatch,publish,seed,clone};
  if(typeof module!=='undefined')module.exports=api;root.HQL=api;
})(typeof globalThis!=='undefined'?globalThis:this);
