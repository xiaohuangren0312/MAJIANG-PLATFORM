/* Shared presentation only: move existing controls without replacing handlers. */
(()=>{
 const isControl=n=>n.nodeType===1&&n.matches('button,a.button,a[download]');
 function arrange(){
  observer.disconnect();
  layout();
  polish();
  document.querySelectorAll('main button,dialog button,main a[download],dialog a[download]').forEach(b=>{
   b.classList.add('ui-button');
   if(!b.matches('.primary,.secondary,.danger'))b.classList.add(b.tagName==='BUTTON'&&b.form&&b.type==='submit'?'primary':'secondary');
  });
  document.querySelectorAll('main form,dialog form,main fieldset,dialog fieldset,main td,main #content,dialog').forEach(parent=>{
   const children=[...parent.childNodes];let run=[];
   const flush=()=>{
    if(!run.length)return;
    const footer=parent.matches('form,fieldset,dialog')&&run.some(b=>b.tagName==='BUTTON'&&b.form&&b.type==='submit'),table=parent.matches('td');
    if(run.length<2&&!footer){run=[];return}
    const group=document.createElement('div');group.className=footer?'form-actions':table?'row-actions':'page-actions';
    run[0].before(group);
    const ordered=run;
    ordered.forEach(b=>group.append(b));run=[];
   };
   children.forEach(n=>{if(isControl(n))run.push(n);else if(n.nodeType===3&&!n.textContent.trim()){}else flush()});flush();
  });
  document.querySelectorAll('form > .actions,dialog .actions').forEach(group=>{
   group.classList.add('form-actions');
  });
  observer.observe(document.body,{childList:true,subtree:true});
 }
 function fold(card,title){
  if(!card||card.closest('details.layout-fold'))return;
  const details=document.createElement('details');details.className='card layout-fold';
  const summary=document.createElement('summary');summary.textContent=title;
  card.before(details);details.append(summary);card.classList.remove('card');card.classList.add('fold-body');details.append(card);
 }
 function layout(){
  const content=document.querySelector('#content');if(!content)return;
  const teamForm=document.querySelector('#team-form');
  if(teamForm&&!content.querySelector('.team-directory')){
   const list=teamForm.nextElementSibling;
   if(list&&list.querySelector('.roster-team')){
    const panel=document.createElement('section');panel.className='card team-directory';
    const title=document.createElement('h2');title.textContent='参赛队伍';panel.append(title,list);list.classList.add('team-directory-grid');
    teamForm.closest('.grid').after(panel);
   }
  }
  fold(teamForm?.closest('.card'),'添加队伍');
  fold(document.querySelector('#player-form')?.closest('.card'),'选手报名');
  fold(document.querySelector('#bond-form')?.closest('.card'),'登记羁绊选手');
  fold(document.querySelector('#match-form')?.closest('.card'),'安排赛程 / 直接录分');
  content.querySelectorAll('.fold-body>h2').forEach(h=>h.hidden=true);
  const members=document.querySelector('#access-members');
  if(members&&!content.querySelector('.access-layout')){
   const layout=document.createElement('div');layout.className='access-layout';
   const directory=document.createElement('section');directory.className='access-directory';
   const actions=document.createElement('aside');actions.className='access-actions';actions.setAttribute('aria-label','账号操作');
   members.closest('.card').before(layout);layout.append(directory,actions);
   [members,document.querySelector('#coach-accounts')].filter(Boolean).forEach(n=>directory.append(n.closest('.card')));
   [document.querySelector('#grant-form'),document.querySelector('#account-form')].filter(Boolean).forEach(n=>actions.append(n.closest('.card')));
   if(!actions.children.length){actions.remove();layout.classList.add('access-readonly')}
  }
  fold(document.querySelector('#grant-form')?.closest('.card'),'分配赛事管理员');
  fold(document.querySelector('#account-form')?.closest('.card'),'创建账号');
  content.querySelectorAll('.access-actions .fold-body>h2').forEach(h=>h.hidden=true);
  document.querySelectorAll('#coach-accounts .roster-team').forEach(row=>{
   row.classList.add('coach-account-row');if(row.querySelector('.roster-row-actions'))return;
   const buttons=[...row.children].filter(n=>n.tagName==='BUTTON');if(buttons.length){const group=document.createElement('div');group.className='roster-row-actions';row.append(group);buttons.forEach(b=>group.append(b))}
  });
 }

 function polish(){
  const content=document.querySelector('#content');
  if(!content)return;
  const heading=content.querySelector(':scope>h1');
  if(heading&&!heading.closest('.admin-page-heading')){
   const hero=document.createElement('div');hero.className='admin-page-heading';
   const context=document.createElement('small');context.textContent=document.querySelector('#events option:checked')?.textContent||'赛事管理';
   heading.before(hero);hero.append(context,heading);
  }
  const hero=content.querySelector('.admin-page-heading');
  if(hero&&!hero.querySelector('.admin-page-actions')){const tools=document.createElement('div');tools.className='admin-page-actions';hero.append(tools)}
  function toolPanel(node,title){
   if(!node||node.closest('.admin-tool-panel,.operation-drawer'))return;
   const card=node.closest('.layout-fold')||node.closest('.card');if(!card)return;
   const panel=document.createElement('details');panel.className='admin-tool-panel';
   const summary=document.createElement('summary');summary.textContent=title;panel.append(summary);
   (hero?.querySelector('.admin-page-actions')||content).append(panel);
   if(card.matches('details')){[...card.children].filter(n=>n.tagName!=='SUMMARY').forEach(n=>panel.append(n));card.remove()}
   else panel.append(card);
   const close=document.createElement('button');close.type='button';close.className='admin-panel-close';close.textContent='关闭 ×';close.setAttribute('aria-label','关闭'+title);close.onclick=()=>{panel.open=false;summary.focus()};panel.lastElementChild.prepend(close);
  }
  toolPanel(document.querySelector('#matchday-live-form'),'桌次直播');
  toolPanel(document.querySelector('#match-form'),'＋ 安排赛程');
  toolPanel(document.querySelector('#team-form'),'＋ 添加队伍');
  toolPanel(document.querySelector('#player-form'),'＋ 选手报名');
  toolPanel(document.querySelector('#bond-form'),'羁绊选手');
  document.querySelectorAll('.manage-fixture-actions').forEach(actions=>{
   if(actions.querySelector('.fixture-more'))return;
   const extras=[...actions.querySelectorAll('button[data-resource-match],button[data-random-seats]')];
   if(!extras.length)return;
   const more=document.createElement('details');more.className='fixture-more';const summary=document.createElement('summary');summary.textContent='更多';more.append(summary,...extras);actions.append(more);
  });
  if(content.dataset.layoutPage==='overview'){
   const counts=content.querySelector(':scope>.grid');const title=content.querySelector('.overview-heading');
   if(counts&&title&&!counts.classList.contains('overview-metrics')){counts.classList.add('overview-metrics');title.after(counts)}
   const stage=content.querySelector('[data-stage-edit]')?.closest('.card');if(stage)stage.classList.add('stage-directory');
  }
  const search=content.querySelector('#roster-search');if(search)search.closest('.card').classList.add('roster-directory');
  if(content.querySelector('#score-form')){
   content.classList.add('score-workspace');
   content.querySelectorAll('#score-form .four>.seat').forEach((seat,i)=>{if(!seat.querySelector('.score-wind')){const wind=document.createElement('span');wind.className='score-wind';wind.textContent='东南西北'[i];seat.prepend(wind)}});
  }else content.classList.remove('score-workspace');
 }
 document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.admin-tool-panel[open],.fixture-more[open]').forEach(p=>{p.open=false;p.querySelector('summary').focus()})});
 document.addEventListener('click',e=>document.querySelectorAll('.admin-tool-panel[open],.fixture-more[open]').forEach(p=>{if(!p.contains(e.target))p.open=false}));
 const observer=new MutationObserver(arrange);arrange();
})();

/* Full-height editors reuse live forms and their permission/validation handlers. */
(()=>{
 const style=document.createElement('style');style.textContent=`
 .management-page dialog.operation-drawer{position:fixed;inset:0 0 0 auto;margin:0;border:0;border-left:1px solid #d7cdbd;border-radius:0;padding:0;width:min(560px,100vw);max-width:100vw;height:100dvh;max-height:100dvh;background:#fffdf8;color:#27382e;box-shadow:-12px 0 48px #18291e25;overflow:hidden}
 .management-page dialog.operation-drawer[open]{display:flex;flex-direction:column}
 .operation-drawer::backdrop{background:#17271e66}
 .operation-drawer .operation-head{display:flex;align-items:center;justify-content:space-between;flex:none;padding:22px 24px;border-bottom:1px solid #e4dccf;background:#f5f2e9}
 .management-page .operation-head h2{margin:0;font-size:22px;color:#27382e}.operation-head button{font-size:24px;border:0;background:transparent;padding:4px 10px}
 .operation-drawer .operation-body{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;padding:24px}
 .operation-drawer .operation-body>.card,.operation-drawer .operation-body>.fold-body{border:0;box-shadow:none;padding:0;margin:0;background:transparent}
 .operation-drawer .operation-body>details>summary,.operation-drawer .operation-body>section>h2,.operation-drawer .operation-body .admin-panel-close{display:none}
 .operation-drawer .operation-body .grid{grid-template-columns:1fr;gap:16px}.operation-drawer label{display:block;margin-bottom:18px}.operation-drawer input:not([type=checkbox]):not([type=radio]),.operation-drawer select,.operation-drawer textarea{width:100%;min-width:0;box-sizing:border-box}
 .operation-drawer .operation-footer{flex:none;padding:16px 24px;border-top:1px solid #e4dccf;background:#fffdf8;display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;padding-bottom:max(16px,env(safe-area-inset-bottom))}
 .operation-drawer .operation-feedback{padding:0 24px;color:#a73629;flex:none}.operation-drawer .operation-feedback:not(:empty){padding-top:12px;padding-bottom:12px;background:#fff0df}
 .operation-drawer [data-operation-source]{display:none!important}.operation-drawer .workspace-savebar{display:none}.operation-drawer .workspace-impact{font-size:13px;line-height:1.6}.operation-drawer .operation-discard{background:#fff0df;padding:14px 24px;border-top:1px solid #e2c59b;flex:none}.operation-discard p{margin:0 0 12px}
 body.operation-open{overflow:hidden!important}.workspace-access:not(:has(#workspace-account-editor:not([hidden]))){grid-template-columns:1fr}
 @media(max-width:600px){.management-page dialog.operation-drawer{width:100vw}.operation-drawer .operation-head,.operation-drawer .operation-body{padding:18px}.operation-drawer .operation-footer{padding-left:18px;padding-right:18px}.operation-footer button{flex:1;min-height:44px}.operation-drawer input,.operation-drawer select,.operation-drawer textarea{font-size:16px}}

 .management-page dialog.operation-wide{width:min(740px,100vw)}
 .operation-wide .operation-body .grid{grid-template-columns:repeat(2,minmax(0,1fr))}
 .operation-wide .operation-body .four{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
 .operation-drawer .form-actions:has(>[data-operation-source]):not(:has(>button:not([data-operation-source]))){display:none}
 .management-page .table-settings-dialog[open]{display:flex;flex-direction:column;padding:0;overflow:hidden;max-height:min(760px,90dvh)}
 .table-settings-dialog>.overview-hub-title{padding:20px 24px;margin:0;border-bottom:1px solid #ded6c9;flex:none}
 .table-settings-dialog #event-tables-form{display:flex;flex-direction:column;min-height:0;flex:1;padding:0 24px}
 .table-settings-dialog .table-scroll{overflow:auto;min-height:0;max-height:calc(90dvh - 210px);flex:1}.table-settings-dialog thead{position:sticky;top:0;background:#f3f0e7;z-index:1}
 .table-settings-dialog .actions{flex:none;margin:0;padding:16px 0;background:#fffdf8}
 .management-page #create-event{padding:24px;width:min(480px,calc(100vw - 36px))}.creation-head{display:flex;align-items:center;justify-content:space-between}.creation-head h2{margin:0}.creation-head button{font-size:24px;background:transparent;border:0}.inline-discard{background:#fff0df;border:1px solid #e6cfab;padding:14px;border-radius:6px;margin:12px 0}.inline-discard p{margin:0 0 12px}
 @media(max-width:600px){.operation-wide .operation-body .grid,.operation-wide .operation-body .four{grid-template-columns:1fr}.management-page .table-settings-dialog{width:100vw;max-width:100vw;max-height:100dvh;height:100dvh;border-radius:0}}
 `;document.head.append(style);
 let active=null;
 const values=node=>[...node.querySelectorAll('input,select,textarea')].map(el=>[el,el.value,el.checked]);
 function openDrawer(node,title,{restoreHidden=false}={}){
  if(active){active.pending=()=>openDrawer(node,title,{restoreHidden});active.requestClose();return;}
  const parent=node.parentNode,next=node.nextSibling,oldHidden=node.hidden,oldOpen=node.open,trigger=document.activeElement;
  const snapshot=values(node),anchor=document.createComment('drawer-origin');parent.insertBefore(anchor,node);
  const d=document.createElement('dialog');d.className='operation-drawer';if(node.querySelector('#match-form'))d.classList.add('operation-wide');d.setAttribute('aria-label',title);
  const head=document.createElement('header');head.className='operation-head';const h=document.createElement('h2');h.textContent=title;const x=document.createElement('button');x.type='button';x.textContent='×';x.setAttribute('aria-label','关闭'+title);head.append(h,x);if(node._returnPanel){const back=document.createElement('button');back.type='button';back.textContent='← 返回赛事 Logo';back.style.fontSize='14px';back.onclick=()=>openDrawer(node._returnPanel,'更换赛事 Logo',{restoreHidden:true});head.prepend(back);}
  const body=document.createElement('div');body.className='operation-body';const feedback=document.createElement('div');feedback.className='operation-feedback';feedback.setAttribute('role','alert');const footer=document.createElement('footer');footer.className='operation-footer';
  const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';cancel.textContent='取消';footer.append(cancel);
  node.hidden=false;if(node.tagName==='DETAILS')node.open=true;body.append(node);
  const section=(before,title)=>{if(!before||before.classList.contains('drawer-section-title')||before.previousElementSibling?.classList.contains('drawer-section-title'))return;const h=document.createElement('h3');h.className='drawer-section-title';h.textContent=title;before.before(h)};
  const venue=node.querySelector('#venue-settings-form');if(venue){section(venue.firstElementChild,'基本信息');const image=venue.querySelector('img');if(image&&!image.closest('.drawer-image-setting')){const label=image.nextElementSibling;const box=document.createElement('div');box.className='drawer-image-setting';image.before(box);box.append(image,label);}}
  const match=node.querySelector('#match-form');if(match){section(match.querySelector('.grid'),'比赛安排');section(match.querySelector('.four'),'参赛队伍与风位');section(match.querySelector('[name=commentators]')?.closest('label'),'解说安排');}

  if(node.querySelector('#match-meta-form')){const match=event?.document?.matches.find(m=>m.id===opened);if(match){const context=document.createElement('section');context.className='operation-match-context';const label=document.createElement('h3');label.textContent='对阵信息';context.append(label);match.seats.forEach((seat,i)=>{const row=document.createElement('p');row.textContent='东南西北'[i]+' · '+(seat.teamId?team(seat.teamId)+' · ':'')+(seat.playerId?player(seat.playerId):'名单待公布');context.append(row)});body.append(context)}}
  d.append(head,body,feedback,footer);document.body.append(d);
  let busy=0;const wrapped=[];node.querySelectorAll("form").forEach(f=>{const original=f.onsubmit;if(!original)return;wrapped.push([f,original]);f.onsubmit=async function(e){if(busy){e.preventDefault();return}busy++;try{return await original.call(this,e)}finally{busy--}}});const proxies=[];
  node.querySelectorAll('button').forEach(b=>{
   if(b.matches('[data-close-account],.admin-panel-close')||b.textContent.trim()==='关闭')return;
   if(b.id==='delete-match'){if(b.closest('.operation-danger'))return;const more=document.createElement('details');more.className='operation-danger';const label=document.createElement('summary');label.textContent='更多操作';b.before(more);more.append(label,b);return;}if(!(b.type==='submit'&&b.form)&&b.id!=='create-and-score')return;
   b.dataset.operationSource='1';const proxy=document.createElement('button');proxy.type='button';proxy.className=b.className|| (b.id==='delete-match'?'danger':'primary');proxy.textContent=b.textContent;proxy.disabled=b.disabled;proxy.onclick=()=>b.click();footer.append(proxy);proxies.push([b,proxy]);
  });
  const sync=()=>proxies.forEach(([b,p])=>{if(p.disabled!==b.disabled)p.disabled=b.disabled;if(p.textContent!==b.textContent)p.textContent=b.textContent});const obs=new MutationObserver(sync);obs.observe(node,{attributes:true,subtree:true,childList:true,characterData:true});
  const message=document.querySelector('#message');const msgObs=new MutationObserver(()=>{feedback.textContent=message.textContent});if(message)msgObs.observe(message,{childList:true,subtree:true,characterData:true});
  const cleanup=()=>{obs.disconnect();msgObs.disconnect();wrapped.forEach(([f,handler])=>f.onsubmit=handler);node.querySelectorAll('[data-operation-source]').forEach(b=>delete b.dataset.operationSource);delete node._returnPanel;if(anchor.isConnected){anchor.replaceWith(node);node.hidden=restoreHidden||oldHidden;if(node.tagName==='DETAILS')node.open=oldOpen;}d.remove();document.body.classList.remove('operation-open');const pending=active?.pending;active=null;if(trigger?.isConnected)trigger.focus();if(pending)pending()};
  const changed=()=>node.querySelector('#matchday-live-form')?(()=>{const f=node.querySelector('form');return f.elements.url.value!==(event.document.tableLive?.[f.elements.date.value]?.[f.elements.table.value]||'')})():snapshot.some(([el,v,c])=>el.value!==v||el.checked!==c);
  const close=()=>{if(busy){feedback.textContent='正在保存，请稍候';return;}if(!changed()){d.close();return;}if(d.querySelector('.operation-discard'))return;const warning=document.createElement('div');warning.className='operation-discard';warning.innerHTML='<p>修改尚未保存，是否放弃？</p><button type="button" class="secondary">继续编辑</button> <button type="button" class="danger">放弃修改</button>';warning.children[1].onclick=()=>{active.pending=null;warning.remove()};warning.children[2].onclick=()=>{snapshot.forEach(([el,v,c])=>{if(el.type!=='file')el.value=v;else el.value='';el.checked=c});d.close()};footer.before(warning)};
  x.onclick=cancel.onclick=close;d.addEventListener('cancel',e=>{e.preventDefault();close()});d.addEventListener('close',cleanup,{once:true});
  active={d,anchor,requestClose:close,close:()=>d.close()};document.body.classList.add('operation-open');d.showModal();
 }
 window.openOperationDrawer=openDrawer;
 // Keep original event handlers; only relocate the existing controls.
 const previousOverview=window.overviewEditPanel;
 if(typeof overviewEditPanel==='function')overviewEditPanel=function(panel,title){if(title==='管理阶段')return previousOverview(panel,title);if(panel)openDrawer(panel,title,{restoreHidden:true})};
 function convert(){
  if(active&&!active.anchor.isConnected)active.close();
  document.querySelectorAll('.admin-tool-panel').forEach(panel=>{
   if(panel.dataset.operationBound||!panel.querySelector('#team-form,#player-form,#bond-form,#matchday-live-form,#match-form'))return;
   panel.dataset.operationBound='1';const summary=panel.querySelector('summary'),body=panel.lastElementChild;
   summary.addEventListener('click',e=>{e.preventDefault();panel.open=false;openDrawer(body,summary.textContent.replace(/^＋\s*/,''))});
  });
  const f=document.querySelector('#match-meta-form');if(f&&!f.closest('.operation-drawer')&&!f.dataset.operationBound){
   f.dataset.operationBound='1';const container=f.closest('.match-settings')||f.closest('.card');const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent='编辑本场赛程';container.before(button);container.hidden=true;button.onclick=()=>openDrawer(container,'编辑赛程',{restoreHidden:true});
  }
  const account=document.querySelector('#workspace-account-editor');if(account&&!account.hidden&&!account.closest('.operation-drawer'))openDrawer(account,account.querySelector('h2')?.textContent||'账号授权',{restoreHidden:true});
 }
 const observer=new MutationObserver(()=>{observer.disconnect();convert();observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']})});observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});convert();
})();

/* Short confirmations stay in the current editing surface. */
window.inlineDiscard=function(root,proceed){
 if(root.querySelector('.inline-discard'))return;
 const note=document.createElement('div');note.className='inline-discard';note.setAttribute('role','alert');note.innerHTML='<p>修改尚未保存，是否放弃？</p><button type="button" class="secondary">继续编辑</button> <button type="button" class="danger">放弃修改</button>';
 note.children[1].onclick=()=>note.remove();note.children[2].onclick=()=>{note.remove();proceed()};root.append(note);note.scrollIntoView({block:'nearest'});
};
window.confirmBusinessDelete=function(title,detail){return new Promise(resolve=>{
 const d=document.createElement('dialog');d.setAttribute('aria-label',title);const h=document.createElement('h2');h.textContent=title;const p=document.createElement('p');p.textContent=detail;const cancel=document.createElement('button');cancel.type='button';cancel.textContent='取消';cancel.className='secondary';const remove=document.createElement('button');remove.type='button';remove.textContent='确认删除';remove.className='danger';let accepted=false;cancel.onclick=()=>d.close();remove.onclick=()=>{accepted=true;d.close()};d.append(h,p,cancel,remove);document.body.append(d);d.onclose=()=>{d.remove();resolve(accepted)};d.showModal();cancel.focus();
})};
window.openCreationDialog=function(){
 const d=document.querySelector('#create-event'),f=d.querySelector('form');
 if(!d.dataset.enhanced){d.dataset.enhanced='1';const head=document.createElement('div');head.className='creation-head';const h=f.querySelector('h2');const close=document.createElement('button');close.type='button';close.textContent='×';close.setAttribute('aria-label','关闭新建赛事');head.append(h,close);f.prepend(head);const actions=document.createElement('div');actions.className='creation-actions';const submit=[...f.querySelectorAll('button')].find(b=>b.type==='submit');actions.append(document.querySelector('#close-create'),submit);f.append(actions);d._close=()=>{if(f.querySelector('button:not([type]),button[type=submit]')?.disabled)return;const dirty=[...f.elements].some(el=>el.name&&!['submit','button'].includes(el.type)&&(el.type==='checkbox'?el.checked!==el.defaultChecked:el.value!==el.dataset.initial));if(dirty)inlineDiscard(f,()=>{f.reset();d.close()});else d.close()};close.onclick=()=>d._close();document.querySelector('#close-create').onclick=()=>d._close();d.addEventListener('cancel',e=>{e.preventDefault();d._close()})}
 [...f.elements].forEach(el=>el.dataset.initial=el.value);d.showModal();
};
