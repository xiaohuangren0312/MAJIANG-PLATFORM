function can(action){return !!event?.actions?.includes(action)}
function enforcePermissions(){
 const map={'stage-form':'stage','team-form':'team','player-form':'player','rule-form':'rule','match-form':'match','lineup-form':'lineup','score-form':event.document.matches.find(m=>m.id===opened)?.state==='published'?'correct':'score'};
 Object.entries(map).forEach(([id,action])=>{if(!can(action))document.querySelectorAll('#'+id+' input,#'+id+' select,#'+id+' textarea,#'+id+' button').forEach(el=>el.disabled=true)});
 [['#publish','publish'],['#cancel','cancel'],['#visibility','visibility']].forEach(([selector,action])=>{if($(selector)&&!can(action))$(selector).disabled=true});
 document.querySelectorAll('[data-edit-team]').forEach(el=>el.disabled=!can('team-update'));document.querySelectorAll('[data-edit-player]').forEach(el=>el.disabled=!can('player-update'));
 let role=$('#current-role');if(!role){role=document.createElement('p');role.id='current-role';$('#nav').before(role)}role.textContent='当前角色：'+({superadmin:'总管理员',admin:'赛事管理员'}[event.role]||'未授权');
}
async function access(){
 const eventId=event.id,superadmin=event.role==='superadmin';
 $('#content').innerHTML=`<h1>账号与赛事授权</h1><div class="card"><h2>赛事管理员</h2><div id="access-members">正在读取…</div></div>${superadmin?`<div class="card"><h2>分配赛事管理员</h2><form id="grant-form"><label>已有账号用户名<input name="username" required maxlength="120"></label><label>授权操作<select name="role"><option value="admin">授予本赛事管理权限</option><option value="revoke">撤回本赛事管理权限</option></select></label><button>保存授权</button></form></div>`:''}${can('coach-manage')||superadmin?`<div class="card"><h2>创建账号</h2><form id="account-form"><label>账号身份<select name="role"><option value="coach">本赛事教练</option>${superadmin?'<option value="admin">本赛事管理员</option><option value="viewer">观众</option>':''}</select></label>${event.kind==='team'?`<label>教练所属队伍<select name="teamId"><option value="">暂不绑定</option>${options(event.document.teams)}</select></label>`:''}<label>用户名<input name="username" required maxlength="120" autocomplete="off"></label><label>初始密码<input name="password" type="password" value="1234@qwer" required autocomplete="new-password"></label><button>创建账号</button></form></div>`:''}<div class="card"><h2>本赛事教练账号</h2><div id="coach-accounts">正在读取…</div></div>`;
 form('grant-form',f=>command('grant',Object.fromEntries(f)));
 form('account-form',async f=>{const result=await api('/api/accounts/',{...Object.fromEntries(f),eventId:event.id,revision:event.revision});await load(eventId);notice('已创建账号 '+result.username)});
 try{
  const data=await api('/api/events/'+eventId+'/access/');if(event?.id!==eventId||page!=='access')return;
  $('#access-members').innerHTML=data.members.map(u=>`<p>${esc(u.username)} · ${u.platformAdmin?'总管理员':'赛事管理员'}</p>`).join('')||'<p>暂无赛事管理员</p>';
  $('#coach-accounts').innerHTML=data.coaches.map(u=>`<div class="roster-team"><span>${esc(u.username)} · ${u.active?'启用':'已停用'}</span>${event.kind==='team'?`<label>所属队伍<select data-coach-team="${esc(u.userId)}" ${can('coach-manage')?'':'disabled'}><option value="">未绑定</option>${event.document.teams.map(t=>`<option value="${esc(t.id)}" ${t.id===u.teamId?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label>`:''}<button class="${u.active?'danger':'secondary'}" data-coach="${esc(u.userId)}" data-active="${u.active?'false':'true'}" ${can('coach-manage')?'':'disabled'}>${u.active?'停用':'恢复'}</button><button class="danger" data-remove-coach="${esc(u.userId)}" ${can('coach-manage')?'':'disabled'}>移除</button></div>`).join('')||'<p>暂无教练账号</p>';
  document.querySelectorAll('[data-coach-team]').forEach(el=>el.onchange=async()=>{try{await command('coach-manage',{userId:el.dataset.coachTeam,teamId:el.value})}catch(e){notice(e.message,true)}});
  document.querySelectorAll('[data-coach]').forEach(b=>b.onclick=async()=>{try{await command('coach-manage',{userId:b.dataset.coach,active:b.dataset.active==='true'})}catch(e){notice(e.message,true)}});
  document.querySelectorAll('[data-remove-coach]').forEach(b=>b.onclick=async()=>{if(!confirm('移除本赛事的教练授权？'))return;try{await command('coach-manage',{userId:b.dataset.removeCoach,remove:true})}catch(e){notice(e.message,true)}});
 }catch(e){notice(e.message,true)}
}
