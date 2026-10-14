(()=>{
const $=s=>document.querySelector(s),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let current=null,seq=0,busy=false,editor=null,edited=false;
const csrf=()=>document.cookie.split('; ').find(s=>s.startsWith((window.HQL_BRAND?.csrfCookie||'csrftoken')+'='))?.split('=')[1]||'';
function notice(text,error=false){if(editor){const status=editor.querySelector('[data-editor-status]');status.textContent=text;status.classList.toggle('error',error)}$('#message').textContent=text;$('#message').classList.toggle('error',error)}
async function request(url,body){const multipart=body instanceof FormData;const r=await fetch(url,{cache:'no-store',...(body?{method:'POST',headers:{'X-CSRFToken':csrf(),...(!multipart?{'Content-Type':'application/json'}:{})},body:multipart?body:JSON.stringify(body)}:{})});if(r.status===401){location.href='/login/?next=/coach/profile/';throw Error('请先登录')}if(r.status===413)throw Error('图片过大，请选择较小的图片后重试');let data;try{data=await r.json()}catch(_){throw Error(r.status===403?'登录状态已变化，请刷新页面后重试':'服务暂时无法处理上传，请稍后重试')}if(!r.ok)throw Error(data.error||'操作失败');return data}
async function prepareImage(file){
 if(!(file instanceof File)||!file.size)throw Error('请先选择图片');
 if(file.size>30*1024*1024)throw Error('原图超过30MB，请选择较小的图片');
 const url=URL.createObjectURL(file);
 try{
  const image=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('图片无法读取，请选择JPEG、PNG或WebP格式'));im.src=url});
  const scale=Math.min(1,1024/Math.max(image.naturalWidth,image.naturalHeight));
  if(!image.naturalWidth||!image.naturalHeight)throw Error('图片尺寸无效，请换一张图片');
  const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
  const ctx=canvas.getContext('2d');if(!ctx)throw Error('浏览器无法处理图片，请换一张较小的图片');
  ctx.drawImage(image,0,0,canvas.width,canvas.height);
  const type=['image/png','image/webp'].includes(file.type)?'image/png':'image/jpeg';
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,type,.88));
  if(!blob||blob.size>5*1024*1024)throw Error('压缩后图片仍超过5MB，请选择较小的图片');
  return new File([blob],type==='image/png'?'upload.png':'upload.jpg',{type});
 }finally{URL.revokeObjectURL(url)}
}

async function editLogo(source,saved,kind='team'){
 const caption=kind==='team'?'队标':'头像';
 const local=source instanceof Blob,url=local?URL.createObjectURL(source):source;
 try{
  const image=await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('无法读取队标原图，请重新上传'));im.src=url});
  const base=Math.min(image.naturalWidth,image.naturalHeight);let zoom=saved?base/saved.size:1,x=saved?.x??(image.naturalWidth-base)/2,y=saved?.y??(image.naturalHeight-base)/2,shape=saved?.shape||(kind==='team'?'rounded':'circle');
  const dialog=document.createElement('dialog');dialog.className='logo-editor';dialog.setAttribute('aria-labelledby','logo-editor-title');
  dialog.innerHTML='<div class="logo-editor-heading"><h2 id="logo-editor-title">调整队标</h2><button type="button" data-cancel aria-label="关闭裁剪">×</button></div><p>拖动定位 · 双指缩放</p><div class="logo-preview-stage"><canvas width="512" height="512" tabindex="0" aria-label="队标裁剪预览，可用方向键移动图片"></canvas></div><div class="logo-zoom"><button type="button" data-zoom-out aria-label="缩小队标">−</button><input type="range" min="0.25" max="5" step="0.01" aria-label="队标缩放"><button type="button" data-zoom-in aria-label="放大队标">＋</button><output aria-live="polite"></output></div><fieldset><legend>显示形状</legend><label><input type="radio" name="logo-shape" value="square"><span class="logo-shape-icon square" aria-hidden="true"></span><span>方形</span></label><label><input type="radio" name="logo-shape" value="rounded"><span class="logo-shape-icon rounded" aria-hidden="true"></span><span>圆角</span></label><label><input type="radio" name="logo-shape" value="circle"><span class="logo-shape-icon circle" aria-hidden="true"></span><span>圆形</span></label></fieldset><div class="logo-editor-actions"><button type="button" data-reset>居中重置</button><button type="button" data-cancel>取消</button><button type="button" class="primary" data-save>保存队标</button></div>';
  dialog.innerHTML=dialog.innerHTML.replaceAll('队标',caption);
  document.body.append(dialog);const canvas=dialog.querySelector('canvas'),ctx=canvas.getContext('2d'),slider=dialog.querySelector('[type=range]');
  slider.value=zoom;dialog.querySelector('[value="'+shape+'"]').checked=true;
  function draw(){const size=base/zoom;x=Math.max(-size,Math.min(image.naturalWidth,x));y=Math.max(-size,Math.min(image.naturalHeight,y));canvas.style.borderRadius=shape==='circle'?'50%':shape==='rounded'?'15.625%':'0';dialog.querySelector('output').textContent=Math.round(zoom*100)+'%';ctx.clearRect(0,0,512,512);ctx.save();ctx.beginPath();if(shape==='circle')ctx.arc(256,256,256,0,Math.PI*2);else if(shape==='rounded')ctx.roundRect(0,0,512,512,80);else ctx.rect(0,0,512,512);ctx.clip();ctx.drawImage(image,x,y,size,size,0,0,512,512);ctx.restore()}
  function setZoom(value){const old=base/zoom;zoom=Math.max(.25,Math.min(5,value));slider.value=zoom;x+=(old-base/zoom)/2;y+=(old-base/zoom)/2;draw()}
  slider.oninput=()=>setZoom(Number(slider.value));dialog.querySelector('[data-zoom-out]').onclick=()=>setZoom(zoom/1.2);dialog.querySelector('[data-zoom-in]').onclick=()=>setZoom(zoom*1.2);
  dialog.querySelectorAll('[name=logo-shape]').forEach(r=>r.onchange=()=>{shape=r.value;draw()});
  const pointers=new Map();let gesture=null;
  function measure(){const pts=[...pointers.values()];return pts.length>1?{x:(pts[0].x+pts[1].x)/2,y:(pts[0].y+pts[1].y)/2,d:Math.hypot(pts[0].x-pts[1].x,pts[0].y-pts[1].y)}:{...pts[0],d:0}}
  canvas.onpointerdown=e=>{pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});canvas.setPointerCapture(e.pointerId);gesture=measure()};
  canvas.onpointermove=e=>{if(!pointers.has(e.pointerId))return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const next=measure();if(gesture.d&&next.d)setZoom(zoom*next.d/gesture.d);const ratio=base/zoom/canvas.getBoundingClientRect().width;x-=(next.x-gesture.x)*ratio;y-=(next.y-gesture.y)*ratio;gesture=next;draw()};
  canvas.onpointerup=canvas.onpointercancel=canvas.onlostpointercapture=e=>{pointers.delete(e.pointerId);gesture=pointers.size?measure():null};
  canvas.onwheel=e=>{e.preventDefault();setZoom(zoom*(e.deltaY<0?1.1:1/1.1))};
  canvas.onkeydown=e=>{const delta=base/zoom/40;if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();x+=e.key==='ArrowLeft'?delta:e.key==='ArrowRight'?-delta:0;y+=e.key==='ArrowUp'?delta:e.key==='ArrowDown'?-delta:0;draw()};
  dialog.querySelector('[data-reset]').onclick=()=>{zoom=1;slider.value=1;x=(image.naturalWidth-base)/2;y=(image.naturalHeight-base)/2;draw()};
  return await new Promise(resolve=>{const done=value=>{dialog.close();dialog.remove();resolve(value)};dialog.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=()=>done(null));dialog.oncancel=e=>{e.preventDefault();done(null)};dialog.querySelector('[data-save]').onclick=()=>done({x,y,size:base/zoom,shape});dialog.showModal();draw()});
 }finally{if(local)URL.revokeObjectURL(url)}
}
addEventListener('beforeunload',e=>{if(edited||busy){e.preventDefault();e.returnValue=''}});
function closeEditor(force=false){if(!editor)return true;if(!force&&(busy||(edited&&!confirm('资料尚未保存，放弃修改？'))))return false;const panel=editor,card=panel._card;if(!force)panel.querySelectorAll('form').forEach(f=>f.reset());panel.close();card.append(panel.querySelector('.profile-fields'));card.querySelector('.profile-fields').hidden=true;panel.remove();editor=null;edited=false;card.querySelector('[data-edit-profile]')?.focus();return true}
function openEditor(card){if(!closeEditor())return;editor=document.createElement('dialog');editor.className='profile-editor';editor._card=card;editor.setAttribute('aria-labelledby','profile-editor-title');editor.innerHTML='<div class="profile-editor-head"><div><small>资料编辑</small><h2 id="profile-editor-title">'+esc(card.querySelector('h2').textContent)+'</h2></div><button type="button" data-close aria-label="关闭资料编辑">×</button></div><p data-editor-status role="status">修改后保存即可更新公开资料</p>';const fields=card.querySelector('.profile-fields');fields.hidden=false;editor.append(fields);document.body.append(editor);editor.querySelector('[data-close]').onclick=()=>closeEditor();editor.oncancel=e=>{e.preventDefault();closeEditor()};editor.addEventListener('input',()=>{edited=true;editor.querySelector('[data-editor-status]').textContent='有未保存的修改'});editor.showModal()}
async function load(){const n=++seq,id=$('#profile-event').value;current=null;if(!id){$('#profile-content').textContent='暂无可编辑的队伍资料';return}const data=await request('/api/coach/profile/'+id+'/');if(n!==seq)return;current=data;render()}
function render(){window.dispatchEvent(new CustomEvent('coach-profile-ready',{detail:current}));const group=(title,kind,rows)=>rows.length?`<h2 style="margin:24px 0 14px">${title}</h2><div class="profile-grid">${rows.map(r=>`<article class="card profile-summary"><div class="profile-heading">${r.imageUrl||kind!=='team'?`<img class="profile-image ${r.imageUrl?'custom-picture':''}" src="${esc(r.imageUrl||'/assets/player-default.png')}" alt="${esc(r.name)}">`:`<span class="profile-image roster-placeholder" style="display:grid;place-items:center;${kind==='team'?'background:'+esc(r.color)+';color:white':''}">${kind==='team'?esc(r.name.slice(0,2)):'头像'}</span>`}<h2>${esc(r.name)}${r.bond?' · 羁绊':''}</h2></div><p class="profile-bio">${esc(r.bio||"尚未填写简介")}</p><button type="button" data-edit-profile>编辑资料 <span aria-hidden="true">→</span></button><div class="profile-fields" hidden><form data-profile="${kind}" data-id="${esc(r.id)}">${kind==='team'?`<label>队伍名称<input name="name" value="${esc(r.name)}" maxlength="120" required></label><label>代表色<input name="color" type="color" value="${esc(r.color)}"></label>`:''}<label>${kind==='team'?'队伍简介':'选手简介'}<textarea name="bio" maxlength="500" rows="3">${esc(r.bio)}</textarea></label><button>保存资料</button></form><form class="profile-upload" data-image="${kind}" data-id="${esc(r.id)}"><label>${kind==='team'?'队标':'头像'} · PNG / JPEG / WebP，大图自动压缩<input name="image" type="file" accept="image/png,image/jpeg,image/webp" required></label><button>裁剪并上传${kind==='team'?'队标':'头像'}</button>${r.imageUrl?`<button type="button" data-recrop>调整${kind==='team'?'队标':'头像'}</button>`:''}</form></div></article>`).join('')}</div>`:'';$('#profile-content').innerHTML=group('队伍','team',current.teams)+group('选手','player',current.players)||'<p>暂无可编辑资料</p>';

 const team=current.teams[0];
 if(team){$('#team-name').textContent=team.name;$('#team-emblem').innerHTML=`<img src="${esc(team.imageUrl||'/assets/player-default.png')}" alt="${esc(team.name)}队标">`;$('#team-bio').textContent=team.bio||'';const teamCard=$('[data-profile="team"]')?.closest('article');if(teamCard){teamCard.hidden=true;$('#edit-team').onclick=()=>openEditor(teamCard)}}
 $('#edit-team').hidden=!team;
 $('#member-count').textContent=String(current.players.length).padStart(2,'0');
 document.querySelectorAll('#profile-content>h2').forEach(n=>n.hidden=true);
 document.querySelectorAll('.profile-summary').forEach(card=>{const b=card.querySelector('[data-edit-profile]');b.setAttribute('aria-label','编辑'+card.querySelector('h2').textContent+'资料');b.innerHTML='✎';const bio=card.querySelector('.profile-bio');if(bio.textContent==='尚未填写简介')bio.hidden=true});
 if(window.currentCoachEvent!==current.id){window.currentCoachEvent=current.id;window.dispatchEvent(new Event('coach-event-change'))}
 async function save(f,reuse=false){
  if(busy)return;if(f.dataset.image){const form=editor?.querySelector('[data-profile]');if(form&&[...form.elements].some(el=>el.name&&el.value!==el.defaultValue)){notice('请先保存资料，再调整图片。',true);return}}busy=true;const id=current.id,revision=current.revision,position=scrollY;
  $('#profile-event').disabled=true;document.querySelectorAll('#profile-content button,.profile-editor button').forEach(b=>b.disabled=true);
  try{
   const data=new FormData(f);
   if(f.dataset.image){
    {
     const row=current[f.dataset.image==='team'?'teams':'players'].find(r=>r.id===f.dataset.id),file=reuse?null:await prepareImage(data.get('image'));
     const crop=await editLogo(file||row.imageSourceUrl||row.imageUrl,reuse?row.imageCrop:null,f.dataset.image);
     if(!crop)return;
     if(reuse){data.delete('image');data.set('reuseSource','1')}else data.set('image',file);
     data.set('crop',JSON.stringify(crop));
    }
    notice('正在保存图片…');data.set('kind',f.dataset.image);data.set('entityId',f.dataset.id);data.set('revision',revision);
    await request('/api/events/'+id+'/image/',data);
   }else await request('/api/coach/profile/'+id+'/',{...Object.fromEntries(data),revision,kind:f.dataset.profile,entityId:f.dataset.id});
   closeEditor(true);await load();scrollTo(0,position);notice('已保存');
  }catch(error){notice(error.message,true)}finally{busy=false;$('#profile-event').disabled=false;document.querySelectorAll('#profile-content button,.profile-editor button').forEach(b=>b.disabled=false)}
 }
 document.querySelectorAll('[data-edit-profile]').forEach(b=>b.onclick=()=>openEditor(b.closest('article')));
 document.querySelectorAll('[data-profile],[data-image]').forEach(f=>{f.onsubmit=e=>{e.preventDefault();save(f)};const b=f.querySelector('[data-recrop]');if(b)b.onclick=()=>save(f,true)});

}
$('#profile-event').onchange=()=>{if(window.coachLineupCanLeave&&!window.coachLineupCanLeave()){$('#profile-event').value=current?.id||'';return}load().catch(e=>notice(e.message,true))};request('/api/coach/profile/').then(async data=>{$('#profile-event').innerHTML=data.events.map(e=>`<option value="${esc(e.id)}">${esc(e.name)}</option>`).join('');const requested=new URLSearchParams(location.search).get('event');if(data.events.some(e=>e.id===requested))$('#profile-event').value=requested;await load()}).catch(e=>notice(e.message,true));
})();
