function matchDetail(){
 const d=event.document,m=d.matches.find(x=>x.id===opened),locked=d.stages.find(s=>s.id===m.stageId).locked,readonly=locked||m.state==='cancelled'||m.readOnly||!can('score');
 if(readonly){resultView(m);return}
 $('#content').innerHTML=`<button class="secondary" id="back">← 返回赛程</button><button class="secondary" id="match-resources-shortcut">补充解说 / 视频 / 牌谱</button><h1>${esc(m.date)} · ${tableLabel(m.number)}桌</h1><p>${esc(m.time)} · ${esc(m.rule.name)} v${m.rule.version} · ${locked?'阶段已锁定':m.state==='published'?'已发布，可更正':'等待发布'}</p><div class="card"><h2>出战名单</h2><form id="lineup-form"><div class="four">${m.seats.map((s,i)=>`<label>${['东','南','西','北'][i]} · ${event.kind==='team'?esc(team(s.teamId)):''}<select name="p${i}" ${readonly||m.state==='published'?'disabled':''}>${options([{id:'',name:'请选择'},...d.players.filter(p=>(m.state==='published'&&p.id===s.playerId)||(p.active&&(event.kind!=='team'||(p.bond?p.bondStages?.[m.stageId]:p.teamId)===s.teamId)))],s.playerId)}</select></label>`).join('')}</div>${!readonly&&m.state==='draft'?'<button>保存并公布出战名单</button>':''}</form></div><div class="card"><h2>战果录入</h2><form id="score-form"><fieldset ${readonly?'disabled':''}><div class="four">${m.seats.map((s,i)=>`<div class="seat"><h3>${esc(player(s.playerId))}</h3><label>终局点数<input name="score${i}" type="number" step="1" value="${s.score??m.rule.start}" required></label>${s.points!==undefined?`<p>已保存个人净分 ${pt(s.points)} PT${event.kind==='team'?`<br>队伍贡献 ${pt(s.teamPoints)} PT`:''}</p>`:''}</div>`).join('')}</div><h3>罚分记录</h3><div id="penalty-rows"></div>${!readonly?'<button type="button" class="secondary" id="add-penalty">＋ 添加罚分</button>':''}<h3>役满记录</h3><div id="yakuman-rows"></div>${!readonly?'<button type="button" class="secondary" id="add-yakuman">＋ 添加役满</button>':''}${m.state==='published'?'<label>备注（选填）<input name="correction" maxlength="120"></label>':''}${!readonly?`<hr><button>${m.state==='published'?'保存更正并重新发布':'保存战果并标记已完赛'}</button>`:''}</fieldset><p id="score-dirty" role="status"></p></form>${!readonly&&m.state==='draft'?`<hr><div class="actions"><button class="primary" id="publish" ${m.seats.every(s=>'score' in s)?'':'disabled'}>审核无误，发布赛果</button><button class="danger" id="cancel">取消本场</button></div>`:''}</div>`;
 matchMetadata(m);
 if(!readonly)pastePanel(m);
 organizeMatchEditor(m);
 click('#match-resources-shortcut',()=>openResources(m.id));
 const contestants=m.seats.filter(s=>s.playerId).map(s=>({id:s.playerId,name:player(s.playerId)}));
 function dirty(){if($('#publish'))$('#publish').disabled=true;$('#score-dirty').textContent='有未保存修改，请先保存成绩。'}
 function addRow(kind,value={},mark=true){
  const host=$('#'+kind+'-rows'),row=document.createElement('div');row.className='score-event';row.dataset.kind=kind;
  const select=`<label>选手<select data-field="playerId" required>${options([{id:'',name:'请选择'},...contestants],value.playerId||'')}</select></label>`;
  row.innerHTML=kind==='penalty'?`<div class="grid">${select}<label>罚分（PT）<input data-field="amount" type="number" step="0.1" min="0.1" max="10000" value="${value.amount===undefined?'':pt(value.amount)}" required></label><label>影响范围<select data-field="scope">${options(event.kind==='team'?[{id:'both',name:'个人及队伍'},{id:'personal',name:'仅个人'},{id:'team',name:'仅队伍'}]:[{id:'personal',name:'仅个人'}],value.scope||(event.kind==='team'?'both':'personal'))}</select></label><label>罚分备注（选填）<input data-field="explanation" value="${esc(value.explanation||'')}" maxlength="120"></label></div>`:`<div class="grid">${select}<label>役满役种（逗号分隔）<input data-field="types" value="${esc(value.types?.join(',')||'')}" required placeholder="例如大三元、字一色"></label><label>局次<input data-field="round" value="${esc(value.round||'')}" maxlength="120" required placeholder="例如南二局一本场"></label><label>倍数<input data-field="multiplier" type="number" min="1" max="10" value="${value.multiplier||1}" required></label><label>和牌方式<select data-field="method">${options([{id:'自摸',name:'自摸'},{id:'荣和',name:'荣和'}],value.method||'自摸')}</select></label></div>`;
  if(!readonly){const button=document.createElement('button');button.type='button';button.className='danger';button.textContent='移除此条'+(kind==='penalty'?'罚分':'役满');button.onclick=()=>{row.remove();dirty()};row.append(button)}
  host.append(row);if(mark)dirty();
 }
 m.penalties.forEach(p=>addRow('penalty',p,false));m.yakuman.forEach(y=>addRow('yakuman',y,false));
 click('#add-penalty',()=>addRow('penalty'));click('#add-yakuman',()=>addRow('yakuman'));
 $('#score-form').oninput=dirty;$('#lineup-form').oninput=dirty;
 click('#back',()=>{opened=null;render()});
 form('lineup-form',f=>command('lineup',{id:m.id,seats:m.seats.map((s,i)=>({teamId:s.teamId,playerId:f.get('p'+i)}))}));
 function records(kind){return [...document.querySelectorAll('#'+kind+'-rows .score-event')].map(row=>{const item={};row.querySelectorAll('[data-field]').forEach(el=>item[el.dataset.field]=el.value);if(kind==='penalty')item.amount=Math.round(Number(item.amount)*10);else{item.multiplier=Number(item.multiplier);item.types=item.types.split(/[,，、]/).map(x=>x.trim()).filter(Boolean)}return item})}
 form('score-form',f=>command('save-result',{id:m.id,scores:[0,1,2,3].map(i=>Number(f.get('score'+i))),penalties:records('penalty'),yakuman:records('yakuman'),reason:f.get('correction')||''}));
 click('#publish',()=>command('publish',{id:m.id}));click('#cancel',()=>{if(confirm('确认取消本场对局？'))return command('cancel',{id:m.id})});
}

function pastePanel(m){
 const panel=document.createElement('section');panel.className='card';panel.innerHTML=`<h2>Excel表格粘贴录入</h2><p>上排姓名，下排点数或PT。</p><form id="paste-form"><label>数值类型<select name="mode"><option value="scores">终局点棒（支持省略两位）</option><option value="pt">得点PT（无罚分ML规则）</option></select></label><label>粘贴表格<textarea name="text" rows="4" required placeholder="选手甲&#9;选手乙&#9;选手丙&#9;选手丁&#10;400&#9;300&#9;200&#9;100"></textarea></label><button>解析并预览</button></form><div id="paste-preview"></div>`;$('#score-form').closest('.card').before(panel);
 let token=null,revision=null;const clear=()=>{token=null;$('#paste-preview').innerHTML=''};$('#paste-form').oninput=clear;
 form('paste-form',async f=>{revision=event.revision;const r=await api('/api/events/'+event.id+'/',{action:'paste-preview',revision,id:m.id,...Object.fromEntries(f)});token=r.token;$('#paste-preview').innerHTML=`<h3>核对预览</h3><p>${r.preview.candidates.length>1?'请选择实际结果':'校验通过'}</p>${r.preview.candidates.map((c,i)=>`<div class="card"><label><input type="radio" name="paste-candidate" value="${i}" ${r.preview.candidates.length===1?'checked':''}>候选 ${i+1}</label><div class="table-scroll"><table><tr><th>选手</th><th>终局点棒</th><th>顺位</th><th>净分PT</th></tr>${c.seats.map((s,j)=>`<tr><td>${esc(r.preview.names[j])}</td><td>${s.score.toLocaleString()}</td><td>${s.rank}</td><td class="${s.points<0?'negative':'positive'}">${pt(s.points)}</td></tr>`).join('')}</table></div></div>`).join('')}<button class="primary" id="paste-save" type="button">确认保存战果</button>`;click('#paste-save',async()=>{const selected=$('input[name="paste-candidate"]:checked');if(!token||!selected)throw Error('请先选择预览结果');await api('/api/events/'+event.id+'/',{action:'paste-commit',revision,token,candidate:Number(selected.value)});await load(event.id);notice('表格战果已保存，对应赛程已完赛')})});
}

function resultView(m){
 const d=event.document,value=n=>n==null?'未知':pt(n);
 $('#content').innerHTML=`<button class="secondary" id="back">← 返回赛程</button><h1>${esc(m.date||'日期未知')} · ${tableLabel(m.number)}桌</h1><p>${esc(m.time)} · ${esc(d.stages.find(s=>s.id===m.stageId)?.name)} · ${{published:'已完赛',draft:'待赛',cancelled:'已取消'}[m.state]}</p><section class="card"><h2>对局成绩</h2><div class="table-scroll"><table><thead><tr><th>队伍</th><th>选手</th><th>终局点数</th><th>顺位</th><th>个人PT</th><th>队伍PT</th></tr></thead><tbody>${m.seats.map(s=>`<tr><td>${esc(s.teamId?team(s.teamId):'未知')}</td><td>${esc(s.playerId?player(s.playerId):'未知')}</td><td>${esc(s.score??'未知')}</td><td>${esc(s.rank??'未知')}</td><td class="${s.points<0?'negative':'positive'}">${value(s.points)}</td><td class="${s.teamPoints<0?'negative':'positive'}">${value(s.teamPoints)}</td></tr>`).join('')}</tbody></table></div>${m.penalties.length?`<h3>罚分</h3>${m.penalties.map(x=>`<p>${esc(player(x.playerId))} · ${value(x.amount)} PT</p>`).join('')}`:''}${m.yakuman.length?`<h3>役满</h3>${m.yakuman.map(x=>`<p>${esc(player(x.playerId))} · ${esc((x.types||[]).join('、'))}</p>`).join('')}`:''}<button class="secondary" id="view-resources">解说与资料</button></section>`;
 click('#back',()=>{opened=null;render()});click('#view-resources',()=>openResources(m.id));matchMetadata(m);
}

function matchMetadata(m){
 const locked=event.document.stages.find(s=>s.id===m.stageId)?.locked;
 if(can('match-update')&&!locked){
  const panel=document.createElement('section');panel.className='card';panel.innerHTML=`<h2>赛程设置</h2><form id="match-meta-form"><div class="grid"><label>日期<input name="date" type="date" value="${esc(m.date)}" required></label><label>时间<input name="time" type="time" value="${esc(m.time)}" required></label><label>桌号<select name="number">${Array.from({length:26},(_,i)=>`<option value="${i+1}" ${m.number===i+1?'selected':''}>${tableLabel(i+1)}桌</option>`).join('')}</select></label></div><div class="actions"><button>保存赛程</button><button class="danger" type="button" id="delete-match">删除本场</button></div></form>`;$('#content').append(panel);
  form('match-meta-form',f=>command('match-update',{id:m.id,...Object.fromEntries(f),number:Number(f.get('number'))}));
  click('#delete-match',async()=>{if(!confirm('删除本场赛程及战果？排行榜会重新计算。'))return;await api('/api/events/'+event.id+'/',{action:'match-delete',revision:event.revision,id:m.id});opened=null;await load(event.id);notice('本场已删除')});
 }
}

function organizeMatchEditor(m){
 const content=$('#content');
 const manual=$('#score-form').closest('.card'),paste=$('#paste-form')?.closest('.card');
 manual.classList.add('manual-score-panel');
 if(paste){
  const switcher=document.createElement('div');switcher.className='score-mode-switch';switcher.setAttribute('role','group');switcher.setAttribute('aria-label','录入方式');
  switcher.innerHTML='<button type="button" class="primary" aria-pressed="true" data-score-mode="manual">手动录分</button><button type="button" class="secondary" aria-pressed="false" data-score-mode="paste">Excel 粘贴</button>';
  paste.before(switcher);paste.hidden=true;
  switcher.querySelectorAll('button').forEach(b=>b.onclick=()=>{const usePaste=b.dataset.scoreMode==='paste';paste.hidden=!usePaste;manual.hidden=usePaste;switcher.querySelectorAll('button').forEach(x=>{const active=x===b;x.classList.toggle('primary',active);x.classList.toggle('secondary',!active);x.setAttribute('aria-pressed',String(active))})});
 }
 for(const [kind,title,entries] of [['penalty','罚分',m.penalties],['yakuman','役满',m.yakuman]]){
  const host=$('#'+kind+'-rows'),heading=host.previousElementSibling,add=host.nextElementSibling;
  const details=document.createElement('details');details.className='score-extra';details.open=entries.length>0;
  const summary=document.createElement('summary');summary.textContent=title+(entries.length?' · '+entries.length+' 条':'');heading.before(details);heading.remove();details.append(summary,host);if(add?.tagName==='BUTTON')details.append(add);
 }
 const meta=$('#match-meta-form')?.closest('.card');if(meta){const details=document.createElement('details');details.className='card match-settings';meta.before(details);const summary=document.createElement('summary');summary.textContent='赛程设置';details.append(summary);meta.querySelector('h2')?.remove();meta.classList.remove('card');details.append(meta)}
}
