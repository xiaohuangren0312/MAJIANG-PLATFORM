function can(action){return !!event?.actions?.includes(action)}
function enforcePermissions(){
 const map={'stage-form':'stage','team-form':'team','player-form':'player','rule-form':'rule','match-form':'match','lineup-form':'lineup','score-form':event.document.matches.find(m=>m.id===opened)?.state==='published'?'correct':'score'};
 Object.entries(map).forEach(([id,action])=>{if(!can(action))document.querySelectorAll('#'+id+' input,#'+id+' select,#'+id+' textarea,#'+id+' button').forEach(el=>el.disabled=true)});
 [['#publish','publish'],['#cancel','cancel'],['#visibility','visibility']].forEach(([selector,action])=>{if($(selector)&&!can(action))$(selector).disabled=true});
 document.querySelectorAll('[data-edit-team]').forEach(el=>el.disabled=!can('team-update'));document.querySelectorAll('[data-edit-player]').forEach(el=>el.disabled=!can('player-update'));
 let role=$('#current-role');if(!role){role=document.createElement('p');role.id='current-role';$('#nav').before(role)}role.textContent='当前角色：'+({superadmin:'总管理员',admin:'子赛事管理员'}[event.role]||'未授权');
}
async function access(){
 const eventId=event.id;
 $('#content').innerHTML=`<h1>账号与赛事授权</h1><p>总管理员管理全部赛事；子赛事管理员只管理指定赛事；普通账号只查看公开赛事。</p><div class="card"><h2>${esc(event.name)} 的管理员</h2><div id="access-members">正在读取…</div></div><div class="card"><h2>分配子赛事管理员</h2><form id="grant-form"><label>已有账号用户名<input name="username" required maxlength="120" autocomplete="off"></label><label>授权操作<select name="role"><option value="admin">授予本赛事完整管理权限</option><option value="revoke">撤回本赛事管理权限</option></select></label><label>备注（选填）<input name="reason" maxlength="120"></label><button>保存授权</button></form><p>同一账号可以管理多个获授权赛事。撤回全部赛事权限后恢复为普通账号；账号不能自行扩大权限。</p></div><div class="card"><h2>创建普通账号</h2><p>新账号默认没有管理权限，可按需授予指定赛事。</p><form id="account-form"><label>用户名<input name="username" required maxlength="120" autocomplete="off"></label><label>初始密码（默认1234@qwer；自定义至少12位）<input name="password" type="password" value="1234@qwer" required autocomplete="new-password"></label><button>创建账号</button></form></div>`;
 form('grant-form',f=>command('grant',Object.fromEntries(f)));
 form('account-form',async f=>{const r=await api('/api/accounts/',Object.fromEntries(f));$('#account-form').reset();notice('已创建普通账号 '+r.username)});
 try{const data=await api('/api/events/'+eventId+'/access/');if(event?.id!==eventId||page!=='access')return;$('#access-members').innerHTML=`<div class="table-scroll"><table><thead><tr><th>账号</th><th>身份</th><th>状态</th></tr></thead><tbody>${data.members.map(u=>`<tr><td>${esc(u.username)}</td><td>${u.platformAdmin?'总管理员':'子赛事管理员'}</td><td>${u.active?'启用':'停用'}</td></tr>`).join('')}</tbody></table></div>`}catch(e){notice(e.message)}
}
