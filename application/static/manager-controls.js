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
   if(!node||node.closest('.admin-tool-panel'))return;
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
