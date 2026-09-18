/* Shared presentation only: move existing controls without replacing handlers. */
(()=>{
 const isControl=n=>n.nodeType===1&&n.matches('button,a.button,a[download]');
 function arrange(){
  observer.disconnect();
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
 const observer=new MutationObserver(arrange);arrange();
})();
