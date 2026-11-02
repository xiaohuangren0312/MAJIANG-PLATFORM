/* Shared management interactions: no automatic retries or business writes. */
function workspaceTaskMatches(m,key,today){
 if(m.state!=='draft')return false;
 const stage=event.document.stages.find(s=>s.id===m.stageId);if(stage?.locked||m.readOnly)return false;
 if(key==='today')return m.date===today;
 if(key==='overdue')return m.date<today;
 const end=new Date(today+'T00:00:00+08:00');end.setDate(end.getDate()+6);
 const until=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(end);
 return key==='comment'&&m.date>=today&&m.date<=until&&!resourceData(m).commentators?.length;
}
const workspaceTaskLabels={today:'今日待录分 / 发布',overdue:'逾期待录分 / 发布',comment:'近 7 日待安排解说'};
function workspaceTodoMarkup(matches,today){return Object.entries(workspaceTaskLabels).map(([key,label])=>{const n=matches.filter(m=>workspaceTaskMatches(m,key,today)).length;return `<div class="workspace-todo task-${key}"><strong>${n}</strong><span>${label}<small>${key==='today'?today:key==='overdue'?'今天之前的未完成对局':'含今天，按每半庄安排'}</small></span><button class="secondary" data-task="${key}" ${n?'':'disabled'}>${key==='comment'?'安排解说':'查看对局'} →</button></div>`}).join('')+'<p class="task-footnote">未来未开赛场次不计入录分待办</p>'}
function bindWorkspaceTodos(){document.querySelectorAll('[data-task]').forEach(b=>b.onclick=()=>{scheduleFilter={date:'',query:'',state:'draft',task:b.dataset.task};workspaceUI.scheduleVisited=true;workspaceUI.matchId=null;workspaceUI.tab=b.dataset.task==='comment'?'resources':'detail';workspaceGo('schedule');if(b.dataset.task==='comment'){workspaceUI.tab='resources';workspaceMatch(workspaceVisibleMatches())}})}
function workspaceFilterChips(){const host=$('#workspace-filter-chips');if(!host)return;const f=scheduleFilter;host.innerHTML=[f.task?['task',workspaceTaskLabels[f.task]]:null,f.date?['date',f.date]:null,f.state!=='all'?['state',f.state==='draft'?'待赛 / 未完成':f.state==='published'?'已完赛':'已取消']:null].filter(Boolean).map(([key,label])=>`<button type="button" class="filter-chip" data-clear-filter="${key}">${esc(label)} <span aria-hidden="true">×</span><span class="sr-only-resource">移除此筛选</span></button>`).join('');host.querySelectorAll('button').forEach(b=>b.onclick=async()=>{if(!await resourceCanLeave())return;const k=b.dataset.clearFilter;scheduleFilter[k]=k==='state'?'all':'';schedule()})}
function workspaceCompactFilters(){const toolbar=$('.schedule-toolbar');if(!toolbar||toolbar.dataset.compact)return;toolbar.dataset.compact='1';const query=$('#schedule-query'),search=query.closest('label'),reset=toolbar.querySelector(':scope>button'),filters=document.createElement('details');filters.className='workspace-filter-menu';filters.innerHTML='<summary>筛选</summary><div class="workspace-filter-popover"></div>';const body=filters.lastElementChild;[$('#schedule-day'),$('#match-state')].forEach(el=>body.append(el.closest('label')));toolbar.append(filters);if(reset){reset.className='secondary';toolbar.append(reset)}const refresh=document.createElement('button');refresh.type='button';refresh.className='secondary';refresh.textContent='刷新';refresh.onclick=async()=>{if(!await resourceCanLeave())return;try{await load(event.id);notice('赛程已刷新')}catch(e){notice(e.message,true)}};toolbar.append(refresh);search.firstChild.textContent='';query.setAttribute('aria-label','搜索队伍、选手');const chips=document.createElement('div');chips.id='workspace-filter-chips';toolbar.after(chips);workspaceFilterChips()}
function workspaceContextBar(){
 if(document.querySelector('.workspace-contextbar')||page!=='resources'||!workspaceUI.returnContext||workspaceUI.returnContext.eventId!==event.id)return;
 const m=event.document.matches.find(m=>m.id===resourceMatchId),bar=document.createElement('div');bar.className='workspace-contextbar';bar.innerHTML=`<button class="secondary" type="button">← 返回${workspaceUI.returnContext.opened?'比分录入':'赛程'}</button><span>${esc(event.name)}${m?' / '+esc(m.date)+' / '+esc(tableName(m.number))+' / '+esc(m.time):''}</span>`;$('#content>h1')?.after(bar);if(!bar.isConnected)$('#content').prepend(bar);bar.querySelector('button').onclick=async()=>{if(!await resourceCanLeave())return;const ctx=workspaceUI.returnContext;workspaceUI.returnContext=null;page=ctx.page;opened=ctx.opened;render();requestAnimationFrame(()=>window.scrollTo(0,ctx.scroll))};
}
function workspaceDraftSnapshot(){const people=[...document.querySelectorAll('#resource-commentator-tags .resource-person-tag')].map(x=>x.textContent.replace(/×$/,'').trim());return [...(people.length?[{label:'已填写解说',value:people.join('、')}]:[]),... [...document.querySelectorAll('#content input,#content select,#content textarea')].filter(el=>!['password','file','hidden'].includes(el.type)&&el.type!=='checkbox'&&el.type!=='radio').map(el=>({label:el.getAttribute('aria-label')||el.closest('label')?.childNodes[0]?.textContent?.trim()||el.name||'输入',value:el.tagName==='SELECT'?el.selectedOptions[0]?.textContent:el.value})).filter(x=>x.value)]}
async function workspaceConflict(url,body,data){
 if(document.querySelector('.workspace-conflict'))return;
 const snapshot=workspaceDraftSnapshot(),dialog=document.createElement('dialog');dialog.className='workspace-conflict';dialog.setAttribute('aria-label','数据已更新');const meta=data.conflict||{};
 dialog.innerHTML=`<div class="conflict-title"><span>!</span><div><h2>这份资料已被更新</h2><p>你的输入已保留，请先核对变动。</p></div></div><div class="conflict-meta">${esc(meta.actor||'其他操作人员')}${meta.at?' · '+esc(new Date(meta.at).toLocaleString('zh-CN')):''}${meta.action?' · '+esc(meta.action):''}</div><div class="conflict-fields"><h3>更新内容</h3><p>${esc((meta.fields||[]).join('、')||'赛事数据发生变化')}</p></div><details><summary>查看我的当前输入</summary><dl class="conflict-inputs">${snapshot.map(x=>`<dt>${esc(x.label)}</dt><dd>${esc(x.value)}</dd>`).join('')}</dl></details><p class="conflict-hint">载入最新版后，原输入会保留在核对面板中，不会自动提交。</p><div class="actions"><button type="button" class="secondary" data-stay>返回编辑</button><button type="button" class="primary" data-latest>载入最新版并核对</button></div>`;
 document.body.append(dialog);dialog.onclose=()=>dialog.remove();dialog.querySelector('[data-stay]').onclick=()=>dialog.close();dialog.querySelector('[data-latest]').onclick=async()=>{const id=event.id;dialog.querySelector('[data-latest]').disabled=true;try{const latest=await api('/api/events/'+id+'/');if(event.id!==id)return;event=latest;if(event.managementDocument){event.document=event.managementDocument;delete event.managementDocument}workspaceUI.dirty=false;resourceUI.dirty=false;render();workspaceUI.retainedInput={eventId:id,items:snapshot};workspaceRetainedPanel();dialog.close()}catch(e){notice(e.message,true);dialog.querySelector('[data-latest]').disabled=false}};dialog.showModal();
}

function workspaceUndoRemoval(host,row,label){const next=row.nextSibling;row.remove();let note=host.querySelector('.workspace-undo');if(note)note.remove();note=document.createElement('div');note.className='workspace-undo';note.setAttribute('role','status');note.innerHTML='<span>'+esc(label)+'已移除，尚未保存</span><button type="button" class="secondary">撤销移除</button>';host.append(note);note.querySelector('button').onclick=()=>{host.insertBefore(row,next?.isConnected?next:note);note.remove();workspaceUI.dirty=true};}

function workspaceRetainedPanel(){const saved=workspaceUI.retainedInput;if(!saved||saved.eventId!==event?.id||document.querySelector('.workspace-retained-input'))return;const panel=document.createElement('details');panel.className='card workspace-retained-input';panel.open=true;panel.innerHTML='<summary>更新前的输入 · 请核对后重新填写</summary><dl class="conflict-inputs">'+saved.items.map(x=>`<dt>${esc(x.label)}</dt><dd>${esc(x.value)}</dd>`).join('')+'</dl><button type="button" class="secondary">核对完成，关闭</button>';panel.querySelector('button').onclick=()=>{workspaceUI.retainedInput=null;panel.remove()};$('#content').prepend(panel)}


// Keep navigation context in this tab only; never store scores or drafts.
document.addEventListener('click',e=>{
 const a=e.target.closest('a[href]');if(!a||e.defaultPrevented||!event||workspaceUI.dirty||workspaceUI.busy||resourceUI.dirty)return;
 const url=new URL(a.href,location.href);if(url.origin!==location.origin||url.pathname!=='/manage/posters/')return;
 const token=typeof crypto.randomUUID==='function'?crypto.randomUUID():Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');
 try{sessionStorage.setItem('hql-poster-return:'+token,JSON.stringify({at:Date.now(),eventId:event.id,page,opened,filter:scheduleFilter,matchId:workspaceUI.matchId,tab:workspaceUI.tab,scroll:window.scrollY}));url.searchParams.set('returnContext',token);a.href=url.href}catch(_){}
});
function workspaceRestorePosterContext(){
 const url=new URL(location.href),token=url.searchParams.get('returnContext');if(!token||!event)return;
 url.searchParams.delete('returnContext');history.replaceState(null,'',url);
 try{const key='hql-poster-return:'+token,ctx=JSON.parse(sessionStorage.getItem(key)||'null');sessionStorage.removeItem(key);
 if(!ctx||ctx.eventId!==event.id||Date.now()-ctx.at>7200000||!Object.hasOwn(pages,ctx.page))return;
 workspaceContext();page=ctx.page;opened=event.document.matches.some(m=>m.id===ctx.opened)?ctx.opened:null;
 scheduleFilter={date:String(ctx.filter?.date||''),query:String(ctx.filter?.query||''),state:['all','draft','published','cancelled'].includes(ctx.filter?.state)?ctx.filter.state:'all',task:Object.hasOwn(workspaceTaskLabels,ctx.filter?.task)?ctx.filter.task:''};
 workspaceUI.scheduleVisited=true;workspaceUI.matchId=ctx.matchId;workspaceUI.tab=['detail','resources','poster'].includes(ctx.tab)?ctx.tab:'detail';
 requestAnimationFrame(()=>window.scrollTo(0,Math.max(0,Number(ctx.scroll)||0)));
 }catch(_){}
}

const settingsDrafts=new WeakMap();
const settingsFormSelector='#rule-form,[data-stage-edit],#venue-settings-form,#event-tables-form';
function settingsValues(f){return [...f.elements].filter(x=>x.name&&!['submit','button','file','hidden'].includes(x.type)).map(x=>({name:x.name,value:x.value,checked:x.checked}));}
function settingsChanged(f){const s=settingsDrafts.get(f);return !!s&&JSON.stringify(settingsValues(f))!==JSON.stringify(s.values);}
function settingsAccept(f){const s=settingsDrafts.get(f);if(s){s.values=settingsValues(f);settingsStatus(f);}}
function settingsStatus(f){const s=settingsDrafts.get(f);if(!s)return;const changed=settingsChanged(f);s.note.hidden=!changed&&!s.busy;s.note.textContent=s.busy?'正在保存…':'有未保存的修改';s.note.dataset.busy=String(s.busy);}
function settingsTrack(){document.querySelectorAll(settingsFormSelector).forEach(f=>{if(settingsDrafts.has(f))return;const note=document.createElement('p');note.className='settings-draft-status';note.setAttribute('role','status');note.hidden=true;f.prepend(note);settingsDrafts.set(f,{values:settingsValues(f),note,busy:false});f.addEventListener('input',()=>settingsStatus(f));f.addEventListener('change',()=>settingsStatus(f));});}
async function settingsCanLeave(root=document,except=null){
 const forms=[...root.querySelectorAll(settingsFormSelector)].filter(f=>f!==except);
 if(forms.some(f=>settingsDrafts.get(f)?.busy)){notice('正在保存，请稍候');return false;}
 const changed=forms.filter(settingsChanged);if(!changed.length)return true;
 const accepted=await new Promise(resolve=>{const d=document.createElement('dialog');d.className='settings-discard-dialog';d.setAttribute('aria-label','修改尚未保存');d.innerHTML='<h2>修改尚未保存</h2><p>离开后，这些设置的修改将丢失。</p><div class="actions"><button type="button" class="secondary" data-stay>继续编辑</button><button type="button" class="danger" data-discard>放弃修改并离开</button></div>';let yes=false;d.onclose=()=>{d.remove();resolve(yes)};d.querySelector('[data-stay]').onclick=()=>d.close();d.querySelector('[data-discard]').onclick=()=>{yes=true;d.close()};document.body.append(d);d.showModal();});
 if(accepted)changed.forEach(f=>{for(const v of settingsDrafts.get(f).values){const el=[...f.elements].find(x=>x.name===v.name&&(!['checkbox','radio'].includes(x.type)||x.value===v.value));if(el){el.value=v.value;if(['checkbox','radio'].includes(el.type))el.checked=v.checked;}}settingsStatus(f);});return accepted;
}
async function settingsSave(f,handler){
 settingsTrack();const state=settingsDrafts.get(f);if(state?.busy)return;
 if(state&&!await settingsCanLeave(document,f))return;
 if(state){state.busy=true;settingsStatus(f);}
 try{await handler();settingsAccept(f);}finally{if(state){state.busy=false;settingsStatus(f);}}
}
document.addEventListener('click',async e=>{const a=e.target.closest('a,[data-page]');if(!a||a.target==='_blank'||![...document.querySelectorAll(settingsFormSelector)].some(f=>settingsChanged(f)||settingsDrafts.get(f)?.busy))return;e.preventDefault();e.stopImmediatePropagation();if(await settingsCanLeave())a.click();},true);
window.addEventListener('beforeunload',e=>{if([...document.querySelectorAll(settingsFormSelector)].some(f=>settingsChanged(f)||settingsDrafts.get(f)?.busy)){e.preventDefault();e.returnValue='';}});
