/* Per-half-game resource workspace. Existing revision-checked commands remain authoritative. */
const resourceUI={eventId:null,date:'',dirty:false,busy:false,closed:false};
async function resourceCanLeave(){
 if(page!=='resources'&&!resourceUI.dirty&&!resourceUI.busy)return true;
 if(resourceUI.busy){notice('正在保存，请稍候');return false}
 if(resourceUI.dirty){
  const discard=await new Promise(resolve=>{
   const box=document.createElement('dialog');box.className='resource-discard-dialog';
   box.innerHTML='<h2>修改尚未保存</h2><p>离开后，本场未保存的修改将丢失。</p><div class="resource-live-actions"><button type="button" class="secondary" data-stay>继续编辑</button><button type="button" class="danger" data-discard>放弃修改</button></div>';
   document.body.append(box);let accepted=false;
   box.addEventListener('close',()=>{box.remove();resolve(accepted)});
   box.querySelector('[data-stay]').onclick=()=>box.close();
   box.querySelector('[data-discard]').onclick=()=>{accepted=true;box.close()};
   box.showModal();box.querySelector('[data-stay]').focus();
  });
  if(!discard)return false;
 }
 resourceUI.dirty=false;return true;
}
window.addEventListener('beforeunload',e=>{if(resourceUI.dirty||resourceUI.busy){e.preventDefault();e.returnValue=''}});
document.addEventListener('click',async e=>{
 const target=e.target.closest('a,[data-page]');
 if(!target||target.closest('.resource-workspace')||(!resourceUI.dirty&&!resourceUI.busy))return;
 e.preventDefault();e.stopImmediatePropagation();
 if(await resourceCanLeave())target.click();
},true);
function resourceMatches(){return [...(event.document.matches||[])].filter(m=>m.state!=='cancelled').sort((a,b)=>a.date.localeCompare(b.date)||Number(a.number)-Number(b.number)||String(a.time).localeCompare(String(b.time))||a.id.localeCompare(b.id))}
function resourceNames(m){return (m.seats||m.players||[]).map(s=>event.kind==='team'?team(s.teamId):player(s.playerId||s.id)).join(' / ')}
function resourceData(m){return event.document.matchResources?.[m.id]||m.resources||{}}
function resources(){
 const matches=resourceMatches(),days=[...new Set(matches.map(m=>m.date))].sort(),today=scheduleToday();
 if(resourceUI.eventId!==event.id){resourceUI.eventId=event.id;resourceUI.date='';resourceUI.closed=window.matchMedia('(max-width:900px)').matches&&!resourceMatchId;resourceUI.dirty=false}
 const selected=matches.find(m=>m.id===resourceMatchId);
 if(selected&&!resourceUI.date)resourceUI.date=selected.date;
 if(!days.includes(resourceUI.date))resourceUI.date=days.includes(today)?today:days.find(d=>d>today)||days.at(-1)||'';
 const rows=matches.filter(m=>m.date===resourceUI.date),tables=[...new Set(rows.map(m=>m.number))];
 if(!rows.some(m=>m.id===resourceMatchId))resourceMatchId=rows[0]?.id||null;
 const index=days.indexOf(resourceUI.date),missing=rows.filter(m=>!resourceData(m).commentators?.length).length;
 $('#content').innerHTML=`<h1>对局资料</h1><div class="resource-toolbar"><div class="resource-date-nav"><button type="button" id="resource-prev" class="secondary" aria-label="上一个比赛日" ${index<=0?'disabled':''}>‹</button><label><span class="sr-only-resource">比赛日</span><select id="resource-date">${days.map(d=>`<option ${d===resourceUI.date?'selected':''}>${esc(d)}</option>`).join('')}</select></label><button type="button" id="resource-next" class="secondary" aria-label="下一个比赛日" ${index>=days.length-1?'disabled':''}>›</button><button type="button" id="resource-today" class="secondary">今天</button></div><small>${rows.length} 场对局${missing?` · 待安排解说 <b>${missing}</b> 场`:''}</small></div><div class="resource-workspace"><div class="resource-directory">${tables.map(number=>{const live=event.document.tableLive?.[resourceUI.date]?.[String(number)];return `<section class="resource-table"><div class="resource-table-head"><h2>${esc(tableLabel(number))}桌</h2>${can('matchday-live')?`<button type="button" class="secondary resource-text-button" data-resource-live="${esc(number)}">${live?'直播间已配置 · 编辑':'设置直播间'}</button>`:''}</div>${rows.filter(m=>m.number===number).map(m=>{const data=resourceData(m);return `<article class="resource-match ${m.id===resourceMatchId&&!resourceUI.closed?'selected':''}" data-resource-row="${esc(m.id)}" data-resource-open="${esc(m.id)}" role="button" tabindex="0" aria-controls="resource-editor" aria-pressed="${m.id===resourceMatchId&&!resourceUI.closed}" aria-label="${esc(tableLabel(m.number))}桌 ${esc(m.time)} ${esc(resourceNames(m))}"><div class="resource-match-time"><strong>${esc(m.time||'时间待定')}</strong><small>${m.state==='published'?'已完赛':'待赛 / 未完成'}</small></div><div class="resource-match-copy"><strong>${esc(resourceNames(m))}</strong><p class="${data.commentators?.length?'':'resource-pending'}">${data.commentators?.length?'解说：'+esc(data.commentators.join('、')):'未安排解说'}</p><small>${data.videos?.length||data.records?.length?`回放 ${data.videos?.length||0} · 牌谱 ${data.records?.length||0}`:m.state==='published'?'暂无赛后资料':'赛后资料待补充'}</small></div><span class="resource-row-indicator" aria-hidden="true">${m.id===resourceMatchId&&!resourceUI.closed?'已选中':'›'}</span></article>`}).join('')}</section>`}).join('')||'<div class="card">暂无可查看的对局</div>'}</div><section id="resource-editor" aria-label="本场资料"></section></div>`;
 const changeDate=async date=>{if(!await resourceCanLeave()){$('#resource-date').value=resourceUI.date;return}resourceUI.date=date;resourceMatchId=null;resourceUI.closed=window.matchMedia('(max-width:900px)').matches;resources()};
 $('#resource-date').onchange=e=>changeDate(e.target.value);
 $('#resource-prev').onclick=()=>changeDate(days[index-1]);$('#resource-next').onclick=()=>changeDate(days[index+1]);
 $('#resource-today').onclick=async()=>{await changeDate(days.includes(today)?today:days.find(d=>d>today)||days.at(-1)||'');if(!days.includes(today))notice('今天没有赛程，已定位最近比赛日')};
 document.querySelectorAll('[data-resource-open]').forEach(row=>{
 const select=async()=>{
  if(resourceMatchId===row.dataset.resourceOpen&&!resourceUI.closed)return;
  if(!await resourceCanLeave())return;
  resourceMatchId=row.dataset.resourceOpen;resourceUI.closed=false;resources();
  if(window.matchMedia('(max-width:900px)').matches)$('#resource-editor h2')?.focus();
  else document.querySelector('[data-resource-open="'+CSS.escape(resourceMatchId)+'"]')?.focus({preventScroll:true});
 };
 row.onclick=select;
 row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select()}};
});
 document.querySelectorAll('[data-resource-live]').forEach(b=>b.onclick=()=>resourceLive(b.dataset.resourceLive));
 if(resourceMatchId&&!resourceUI.closed)resourceEditor(rows.find(m=>m.id===resourceMatchId),rows);else $('#resource-editor').hidden=true;
}
function resourceEditor(m,rows){
 if(!m)return;
 const editor=$('#resource-editor'),data=resourceData(m),writable=can('match-resources');
 const draft={commentators:[...(data.commentators||[])],videos:(data.videos||[]).map(x=>({...x})),records:(data.records||[]).map(x=>({...x}))};
 const recent=[...new Set(resourceMatches().slice().reverse().flatMap(m=>resourceData(m).commentators||[]))].slice(0,8);
 const previous=rows.filter(x=>x.number===m.number).filter(x=>String(x.time)<String(m.time)).at(-1);
 editor.hidden=false;editor.className='resource-editor-panel';
 editor.innerHTML=`<div class="resource-editor-head"><div><h2 tabindex="-1">本场资料</h2><p>${esc(m.date)} · ${esc(tableLabel(m.number))}桌 · ${esc(m.time)}</p><small>${esc(resourceNames(m))}</small></div><button type="button" class="secondary" id="resource-close" aria-label="关闭本场资料">×</button></div><form id="resource-form"><fieldset ${writable?'':'disabled'}><section class="resource-section"><h3>本场解说</h3><div id="resource-commentator-tags"></div><div class="resource-add-person"><input id="resource-person" aria-label="解说姓名" placeholder="输入姓名，回车添加" maxlength="120"><button type="button" class="secondary" id="resource-add-person">添加</button></div><div class="resource-recent"><small>最近使用</small>${recent.map(n=>`<button type="button" class="secondary" data-resource-person="${esc(n)}">${esc(n)}</button>`).join('')||'<small>暂无</small>'}</div>${previous&&resourceData(previous).commentators?.length?'<button type="button" class="secondary resource-text-button" id="resource-copy">沿用上一半庄</button>':''}</section>${[['videos','视频回放'],['records','牌谱']].map(([key,title])=>`<section class="resource-section"><div class="resource-section-heading"><h3>${title}</h3><button type="button" class="secondary resource-text-button" data-add-link="${key}">＋ 添加</button></div><div data-resource-links="${key}"></div></section>`).join('')}</fieldset><p id="resource-error" role="alert"></p>${writable?'<div class="resource-savebar"><span id="resource-save-state">资料已同步</span><div><button type="button" class="secondary" id="resource-cancel">取消</button><button type="submit" class="primary">保存资料</button></div><button type="submit" class="secondary resource-text-button" name="next" value="1">保存并编辑下一场 →</button></div>':'<p class="resource-readonly">当前为只读状态</p>'}</form>`;
 const dirty=()=>{resourceUI.dirty=true;const state=$('#resource-save-state');if(state)state.textContent='有未保存的修改'};
 const error=text=>$('#resource-error').textContent=text;
 const renderPeople=()=>{const host=$('#resource-commentator-tags');host.innerHTML=draft.commentators.map((n,i)=>`<span class="resource-person-tag">${esc(n)}${writable?`<button type="button" class="secondary" data-remove-person="${i}" aria-label="移除${esc(n)}">×</button>`:''}</span>`).join('');host.querySelectorAll('[data-remove-person]').forEach(b=>b.onclick=()=>{draft.commentators.splice(Number(b.dataset.removePerson),1);dirty();renderPeople()})};
 const addPeople=value=>{const names=value.split(/[,，、\n]/).map(n=>n.trim()).filter(Boolean),combined=[...new Set([...draft.commentators,...names])];if(combined.length>10){error('最多添加10位解说');return false}draft.commentators=combined;error('');renderPeople();if(names.length)dirty();return true};
 $('#resource-add-person').onclick=()=>{if(addPeople($('#resource-person').value))$('#resource-person').value=''};
 $('#resource-person').onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing){e.preventDefault();$('#resource-add-person').click()}};
 document.querySelectorAll('[data-resource-person]').forEach(b=>b.onclick=()=>addPeople(b.dataset.resourcePerson));
 if($('#resource-copy'))$('#resource-copy').onclick=()=>addPeople(resourceData(previous).commentators.join('、'));
 function links(key){const host=editor.querySelector(`[data-resource-links="${key}"]`);host.innerHTML=draft[key].map((link,i)=>`<div class="resource-link"><div><input aria-label="${key==='videos'?'回放':'牌谱'}标题" placeholder="标题（选填）" value="${esc(link.title||'')}" maxlength="120" data-link-title="${i}"><button type="button" class="secondary" data-remove-link="${i}" aria-label="删除此链接">×</button></div><input type="url" required maxlength="2000" aria-label="${key==='videos'?'回放':'牌谱'}网址" placeholder="粘贴完整网址 https://…" value="${esc(link.url||'')}" data-link-url="${i}"></div>`).join('')||'<p class="resource-empty">暂未添加</p>';
 host.querySelectorAll('[data-link-title]').forEach(input=>input.oninput=()=>{draft[key][Number(input.dataset.linkTitle)].title=input.value;dirty()});host.querySelectorAll('[data-link-url]').forEach(input=>input.oninput=()=>{draft[key][Number(input.dataset.linkUrl)].url=input.value;dirty()});host.querySelectorAll('[data-remove-link]').forEach(b=>b.onclick=()=>{draft[key].splice(Number(b.dataset.removeLink),1);dirty();links(key)});
 }
 editor.querySelectorAll('[data-add-link]').forEach(b=>b.onclick=()=>{const key=b.dataset.addLink;if(draft[key].length>=20){error('每类最多20条链接');return}draft[key].push({title:'',url:''});dirty();links(key);editor.querySelector(`[data-resource-links="${key}"] .resource-link:last-child [data-link-url]`).focus()});
 renderPeople();links('videos');links('records');
 $('#resource-form').addEventListener('input',dirty);
 const close=async()=>{if(!await resourceCanLeave())return;resourceUI.closed=true;resources();document.querySelector(`[data-resource-open="${CSS.escape(m.id)}"]`)?.focus()};$('#resource-close').onclick=close;if($('#resource-cancel'))$('#resource-cancel').onclick=close;
 $('#resource-form').onsubmit=async e=>{e.preventDefault();if(!writable||resourceUI.busy)return;if(!addPeople($('#resource-person').value))return;
 for(const key of ['videos','records'])for(const link of draft[key]){link.url=link.url.trim();try{const u=new URL(link.url);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw Error()}catch(_){error('请填写完整的 HTTP 或 HTTPS 网址');return}}
 const next=e.submitter?.name==='next',nextMatch=rows[rows.findIndex(x=>x.id===m.id)+1];
 resourceUI.busy=true;editor.querySelectorAll('button,input').forEach(n=>n.disabled=true);error('');
 try{await api('/api/events/'+event.id+'/',{action:'match-resources',revision:event.revision,id:m.id,...draft});resourceUI.dirty=false;if(next&&nextMatch){resourceMatchId=nextMatch.id;if(page==='schedule')workspaceUI.matchId=nextMatch.id;}await load(event.id);notice(next&&!nextMatch?'资料已保存，已是当天最后一场':'资料已保存')}
 catch(err){error(err.message);editor.querySelectorAll('button,input').forEach(n=>n.disabled=false)}finally{resourceUI.busy=false}
 };
}
async function resourceLive(number){
 if(!await resourceCanLeave())return;
 resources();
 const date=resourceUI.date,dialog=document.createElement('dialog');dialog.className='resource-live-dialog';dialog.innerHTML=`<h2>${esc(date)} · ${esc(tableLabel(number))}桌</h2><form><label>B站直播间<input type="url" name="url" maxlength="2000" placeholder="https://live.bilibili.com/…" value="${esc(event.document.tableLive?.[date]?.[number]||'')}"></label><small>留空保存可移除直播入口</small><p role="alert"></p><div class="resource-live-actions"><button type="button" class="secondary">取消</button><button type="submit" class="primary">保存直播</button></div></form>`;document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.querySelector('[type=button]').onclick=()=>dialog.close();dialog.addEventListener('cancel',e=>{if(resourceUI.busy)e.preventDefault()});dialog.showModal();
 dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();resourceUI.busy=true;dialog.querySelectorAll('button').forEach(n=>n.disabled=true);try{await command('matchday-live',{date,table:number,url:dialog.querySelector('input').value.trim()});dialog.close()}catch(err){dialog.querySelector('[role=alert]').textContent=err.message;dialog.querySelectorAll('button').forEach(n=>n.disabled=false)}finally{resourceUI.busy=false}};
}
