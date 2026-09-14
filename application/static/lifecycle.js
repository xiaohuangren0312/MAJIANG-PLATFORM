function qualificationChoices(stageId,played=false){
 const d=event.document,stage=d.stages.find(s=>s.id===stageId),incoming=d.settlements.find(c=>c.target===stageId),kind=event.kind==='team'?'team':'player';
 let items=(kind==='team'?d.teams:d.players).filter(x=>x.active);
 if(stage&&d.stages.indexOf(stage)>0)items=incoming?items.filter(x=>Object.hasOwn(incoming.rows,x.id)):[];
 if(played)items=items.filter(x=>d.matches.some(m=>m.stageId===stageId&&m.state==='published'&&m.seats.some(s=>s[kind+'Id']===x.id)));
 return items;
}
function bindQualificationChoices(){
 const select=$('#match-form [name="stageId"]');if(!select)return;
 const update=()=>{const items=qualificationChoices(select.value);for(let i=0;i<4;i++){const el=$('#match-form [name="seat'+i+'"]'),old=el.value;el.innerHTML='<option value="">请选择</option>'+options(items,old)}
 let hint=$('#qualification-hint');if(!hint){hint=document.createElement('p');hint.id='qualification-hint';select.closest('.grid').after(hint)}hint.textContent=items.length?'当前阶段可安排 '+items.length+' 个参赛对象':'请先结算上一阶段并确认晋级名单';};select.onchange=update;update();
}
function bindAdvancementChoices(){
 const select=$('#preview-form [name="source"]'),holder=$('#advancement-choices');if(!select||!holder)return;
 const update=()=>{const cutoff=event.document.stages.find(s=>s.id===select.value)?.advanceCount;if(cutoff){holder.textContent='按阶段竞技排名前 '+cutoff+' 名自动选择，名单将在结算预览中展示。';return}holder.innerHTML=qualificationChoices(select.value,true).map(x=>`<label><input type="checkbox" name="ids" value="${esc(x.id)}" checked>${esc(x.name)}</label>`).join('')||'<p>该阶段尚无可结转的已发布成绩。</p>';};select.onchange=update;update();
}
function standingsTable(p){return `<div class="table-scroll"><table><thead><tr><th>名次</th><th>${p.kind==='team'?'队伍':'选手'}</th><th>最终竞技分</th><th>阶段净分</th><th>带入分</th></tr></thead><tbody>${p.rows.map(r=>`<tr><td>${r.rank}</td><td>${esc(r.name)}</td><td>${pt(r.total)}</td><td>${pt(r.raw)}</td><td>${pt(r.carry)}</td></tr>`).join('')}</tbody></table></div>`}
function lifecycle(){
 const a=event.document.archive;
 $('#content').innerHTML=`<h1>结束与归档</h1><p>${esc(event.name)} · ${event.isTest?'测试赛事':'正式赛事'} · ${a?'已归档':'进行中'}</p>${a?`<div class="card"><h2>最终排名 · ${esc(a.standings.stageName)}</h2><p>归档时间：${esc(new Date(a.at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}))} · ${esc(a.actor)}</p><p>${esc(a.reason)}</p>${standingsTable(a.standings)}<p>比赛数据已锁定，公开展示仍可查看赛程、战果和排行。</p></div>`:`<div class="card"><p>完成各阶段结算并发布最后阶段成绩后，预览最终排名。确认归档将锁定全部比赛数据。</p><button id="archive-preview" ${can('archive-preview')?'':'disabled'}>预览最终排名</button><div id="archive-detail"></div></div>`}${can('cleanup-preview')?'<div class="card"><h2>清理测试赛事</h2><p>清理后从管理端与展示端移除本赛事。自动保留恢复备份和清理回执，其他赛事及账号不受影响。</p><button id="cleanup-preview">预览清理范围</button><div id="cleanup-detail"></div></div>':''}`;
 click('#archive-preview',async()=>{const id=event.id,revision=event.revision,r=await api('/api/events/'+id+'/',{action:'archive-preview',revision});if(event.id!==id||page!=='lifecycle')return;$('#archive-detail').innerHTML=`<h2>${esc(r.preview.stageName)} · 最终排名</h2>${standingsTable(r.preview)}<form id="archive-form"><label>备注（选填）<input name="reason" maxlength="120" value="比赛已结束，确认最终排名"></label><button>确认结束并归档</button></form>`;form('archive-form',async f=>{await api('/api/events/'+id+'/',{action:'archive-commit',revision,token:r.token,reason:f.get('reason')});await load(id);notice('比赛已归档，最终排名已固定')})});
 click('#cleanup-preview',async()=>{const id=event.id,revision=event.revision,r=await api('/api/events/'+id+'/',{action:'cleanup-preview',revision});if(event.id!==id||page!=='lifecycle')return;const c=r.preview.counts;$('#cleanup-detail').innerHTML=`<p>将清理：${esc(r.preview.name)}，${c.teams}支队伍、${c.players}名选手、${c.matches}场对局、${c.audits}条操作记录。${r.preview.public?'公开入口也会移除。':''}</p><form id="cleanup-form"><label>输入完整赛事名称<input name="confirmName" required autocomplete="off"></label><label>备注（选填）<input name="reason" maxlength="120" value="验收完成，清理测试数据"></label><button>确认清理测试赛事</button></form>`;form('cleanup-form',async f=>{await api('/api/events/'+id+'/',{action:'cleanup-commit',revision,token:r.token,...Object.fromEntries(f)});event=null;page='overview';opened=null;preview=null;await load();notice('测试赛事已清理，恢复备份与清理回执已保存')})});
}
