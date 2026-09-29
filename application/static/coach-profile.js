(()=>{
const $=s=>document.querySelector(s),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let current=null,seq=0,busy=false;
const csrf=()=>document.cookie.split('; ').find(s=>s.startsWith('csrftoken='))?.split('=')[1]||'';
function notice(text,error=false){$('#message').textContent=text;$('#message').classList.toggle('error',error)}
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
  const type=file.type==='image/png'?'image/png':'image/jpeg';
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,type,.88));
  if(!blob||blob.size>5*1024*1024)throw Error('压缩后图片仍超过5MB，请选择较小的图片');
  return new File([blob],type==='image/png'?'upload.png':'upload.jpg',{type});
 }finally{URL.revokeObjectURL(url)}
}
async function load(){const n=++seq,id=$('#profile-event').value;current=null;if(!id){$('#profile-content').textContent='暂无可编辑的队伍资料';return}const data=await request('/api/coach/profile/'+id+'/');if(n!==seq)return;current=data;render()}
function render(){const group=(title,kind,rows)=>rows.length?`<h2 style="margin:24px 0 14px">${title}</h2><div class="profile-grid">${rows.map(r=>`<article class="card"><div class="profile-heading">${r.imageUrl||kind!=='team'?`<img class="profile-image" src="${esc(r.imageUrl||'/assets/player-default.png')}" alt="${esc(r.name)}">`:`<span class="profile-image roster-placeholder" style="display:grid;place-items:center;${kind==='team'?'background:'+esc(r.color)+';color:white':''}">${kind==='team'?esc(r.name.slice(0,2)):'头像'}</span>`}<h2>${esc(r.name)}${r.bond?' · 羁绊':''}</h2></div><form data-profile="${kind}" data-id="${esc(r.id)}">${kind==='team'?`<label>队伍名称<input name="name" value="${esc(r.name)}" maxlength="120" required></label><label>代表色<input name="color" type="color" value="${esc(r.color)}"></label>`:''}<label>${kind==='team'?'队伍简介':'选手简介'}<textarea name="bio" maxlength="500" rows="3">${esc(r.bio)}</textarea></label><button>保存资料</button></form><form class="profile-upload" data-image="${kind}" data-id="${esc(r.id)}"><label>${kind==='team'?'队标':'头像'} · PNG / JPEG / WebP，大图自动压缩<input name="image" type="file" accept="image/png,image/jpeg,image/webp" required></label><button>上传${kind==='team'?'队标':'头像'}</button></form></article>`).join('')}</div>`:'';$('#profile-content').innerHTML=group('队伍','team',current.teams)+group('选手','player',current.players)||'<p>暂无可编辑资料</p>';
 document.querySelectorAll('[data-profile],[data-image]').forEach(f=>f.onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;const id=current.id,revision=current.revision,position=scrollY;$('#profile-event').disabled=true;document.querySelectorAll('#profile-content button').forEach(b=>b.disabled=true);try{const data=new FormData(f);if(f.dataset.image){notice('正在处理并上传图片…');data.set('image',await prepareImage(data.get('image')));data.set('kind',f.dataset.image);data.set('entityId',f.dataset.id);data.set('revision',revision);await request('/api/events/'+id+'/image/',data)}else await request('/api/coach/profile/'+id+'/',{...Object.fromEntries(data),revision,kind:f.dataset.profile,entityId:f.dataset.id});await load();scrollTo(0,position);notice('已保存')}catch(error){notice(error.message,true)}finally{busy=false;$('#profile-event').disabled=false;document.querySelectorAll('#profile-content button').forEach(b=>b.disabled=false)}})
}
$('#profile-event').onchange=()=>load().catch(e=>notice(e.message,true));request('/api/coach/profile/').then(async data=>{$('#profile-event').innerHTML=data.events.map(e=>`<option value="${esc(e.id)}">${esc(e.name)}</option>`).join('');await load()}).catch(e=>notice(e.message,true));
})();
