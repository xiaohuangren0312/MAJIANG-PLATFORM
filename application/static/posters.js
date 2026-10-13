(()=>{
'use strict';
if(new URLSearchParams(location.search).get('type')==='daily')return;
const context=new URLSearchParams(location.search);

const $=id=>document.getElementById(id),canvas=$('poster-canvas'),download=$('poster-download');
let data=null,match=null,generation=0,ready=false,busy=false;
const images=new Map(),fallback='/assets/player-default.png';
const font='"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif';
const serif='"Noto Serif CJK SC","Songti SC","SimSun",serif';
const template=()=>document.querySelector('[name="poster-template"]:checked').value;
const table=v=>/^\d+$/.test(String(v))&&+v>=1&&+v<=26?String.fromCharCode(64+(+v)):String(v);
function notice(t){$('poster-status').textContent=t}
function options(node,items){node.replaceChildren(...items.map(([value,label])=>new Option(label,value)))}
async function api(url){
 const r=await fetch(url,{cache:'no-store',credentials:'same-origin'});
 let body;try{body=await r.json()}catch{throw Error('无法读取数据，请重新登录后重试')}
 if(!r.ok)throw Error(body.error||'加载失败');return body;
}
function image(url){
 const u=new URL(url,location.origin);if(u.origin!==location.origin)throw Error('头像地址不属于本站');
 if(!images.has(u.href))images.set(u.href,new Promise((resolve,reject)=>{
 const im=new Image();const timer=setTimeout(()=>{images.delete(u.href);reject(Error('图片加载超时'))},15000);
 im.onload=()=>{clearTimeout(timer);resolve(im)};im.onerror=()=>{clearTimeout(timer);images.delete(u.href);reject(Error('图片加载失败'))};im.src=u.href;
 }));return images.get(u.href);
}
function clear(){ready=false;download.disabled=true;canvas.hidden=true}
function chooseDay(preferred){
 const days=[...new Set(data.matches.map(m=>m.date))];
 options($('poster-day'),days.map(d=>[d,d]));
 const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date());
 $('poster-day').value=days.includes(preferred)?preferred:(days.find(d=>d>=today)||days.at(-1)||'');
 chooseMatch(context.get('match'));context.delete('match');
}
function chooseMatch(preferred){
 const rows=data.matches.filter(m=>m.date===$('poster-day').value);
 options($('poster-match'),rows.map(m=>[m.id,`${m.time} · ${table(m.table)}桌 · 第${m.game}半庄 · ${m.stageName}`]));
 if(rows.some(m=>m.id===preferred))$('poster-match').value=preferred;
 syncTabs();draw();
}
async function load(){
 const token=++generation;clear();data=null;match=null;$('poster-warning').hidden=true;
 const id=$('poster-event').value,day=context.get('date')||$('poster-day').value,mid=$('poster-match').value;context.delete('date');
 options($('poster-day'),[]);options($('poster-match'),[]);
 if(!id){notice('暂无可管理的赛事');return}
 notice('正在读取名单…');
 try{const value=await api('/api/posters/'+id+'/');if(token!==generation)return;data=value;chooseDay(day);if(value.matches.some(m=>m.id===mid&&m.date===$('poster-day').value)){$('poster-match').value=mid;draw()}}
 catch(e){if(token===generation)notice(e.message)}
}
function text(c,value,x,y,size,max,color='#20251f',family=font,align='center',weight=600){
 c.fillStyle=color;c.textAlign=align;c.textBaseline='middle';
 let s=size;c.font=`${weight} ${s}px ${family}`;
 while(c.measureText(String(value)).width>max&&s>12){s--;c.font=`${weight} ${s}px ${family}`}
 c.fillText(String(value),x,y);
}
function line(c,x,y,x2,y2,color='#d8d0c2',width=1){c.strokeStyle=color;c.lineWidth=width;c.beginPath();c.moveTo(x,y);c.lineTo(x2,y2);c.stroke()}
function portrait(c,im,x,y,w,round=false){
 c.save();c.beginPath();if(round)c.arc(x+w/2,y+w/2,w/2,0,Math.PI*2);else c.rect(x,y,w,w);c.clip();
 c.fillStyle='#faf7ef';c.fillRect(x,y,w,w);
 // Contain the exact uploaded artwork; never redraw or stretch it.
 const scale=Math.min(w/im.width,w/im.height),iw=im.width*scale,ih=im.height*scale;
 c.drawImage(im,x+(w-iw)/2,y+(w-ih)/2,iw,ih);c.restore();
}
function seatBadge(c,wind,x,y,r){
 c.save();c.shadowColor='rgba(35,30,20,.18)';c.shadowBlur=5;c.shadowOffsetY=2;
 c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fillStyle='#faf7ee';c.fill();
 c.shadowColor='transparent';c.strokeStyle='#a34b34';c.lineWidth=1.8;c.stroke();
 text(c,wind||'待定',x,y+1,wind?r*1.22:r*.68,r*1.65,'#20251f',serif,'center',600);c.restore();
}
function contain(c,im,x,y,w,h){const s=Math.min(w/im.width,h/im.height);c.drawImage(im,x+(w-im.width*s)/2,y+(h-im.height*s)/2,im.width*s,im.height*s)}
function title(c,name,x,y,max,size,color='#20251f',align='center'){
 const parts=String(name).match(/^(.*?)\s*(S\d+)$/i);
 if(!parts){text(c,name,x,y,size,max,color,serif,align,800);return}
 let n=size;
 const width=()=>{c.font='800 '+n+'px '+serif;const a=c.measureText(parts[1]).width;c.font='800 '+Math.round(n*1.48)+'px '+font;return [a,c.measureText(parts[2]).width]};
 let widths=width();while(widths[0]+widths[1]+22>max&&n>16){n--;widths=width()}
 const left=x-(widths[0]+widths[1]+22)/2;
 text(c,parts[1],left,y,n,widths[0]+2,color,serif,'left',800);
 text(c,parts[2],left+widths[0]+22,y,Math.round(n*1.48),widths[1]+2,'#a23829',font,'left',800);
}
function caption(m){return `${m.stageName} · ${table(m.table)}桌 · 第${m.game}半庄`}
function commentaryLines(c,width){
 c.font=`400 24px ${font}`;
 const value=match.commentators?.length?'解说：'+match.commentators.join(' · '):'解说待定';
 const lines=[];let line='';
 for(const char of value){if(line&&c.measureText(line+char).width>width){lines.push(line);line=''}line+=char}
 if(line)lines.push(line);return lines;
}
function commentary(c,width,x,y,color){commentaryLines(c,width).forEach((line,i)=>text(c,line,x,y+i*32,24,width,color,font,'center',400))}
function ink(c,avatars,logo,landscape){
 c.fillStyle='#faf7ee';c.fillRect(0,0,1200,c.canvas.height);
 if(landscape){c.save();c.globalAlpha=.4;c.drawImage(landscape,0,1070,1200,430);c.restore()}
 contain(c,logo,475,40,250,100);
 title(c,data.name,600,220,1060,68);
 line(c,180,280,1020,280,'#a83e2d',2);
 text(c,match.date.replaceAll('-','.'),600,328,30,950,'#635d53',serif);
 c.fillStyle='#9f3d2e';c.fillRect(330,375,540,64);
 text(c,caption(match),600,408,27,505,'#fffaf0');
 line(c,600,485,600,1315);line(c,165,920,1035,920);
 match.players.forEach((p,i)=>{
 const x=i%2?810:390,y=i<2?475:950;
 portrait(c,avatars[i],x-145,y,290);
 seatBadge(c,p.wind,x+123,y+266,29);
 text(c,p.name,x,y+339,50,390);
 line(c,x-20,y+375,x+20,y+375,'#aa3d2a',3);
 text(c,p.teamName,x,y+408,26,380,'#696254',font,'center',400);
 });
 line(c,220,1392,980,1392);commentary(c,980,600,1436,'#635d53');
}
function teamPalette(value){
 const raw=/^#[0-9a-f]{6}$/i.test(value)?value:'#315369';
 let rgb=[1,3,5].map(n=>parseInt(raw.slice(n,n+2),16));
 // Preserve team hue; reduce only excessively bright colors for white lettering.
 const light=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];
 if(light>155)rgb=rgb.map(v=>v*155/light);
 const mix=(target,amount)=>'#'+rgb.map(v=>Math.round(v+(target-v)*amount).toString(16).padStart(2,'0')).join('');
 return [mix(0,.12),mix(255,.1),mix(0,.4)];
}
function brushTexture(c,texture,x,y,w,h,flip=false,opacity=.85){
 c.save();c.beginPath();c.rect(x,y,w,h);c.clip();
 c.globalCompositeOperation='soft-light';c.globalAlpha=opacity;
 c.filter='invert(1)';
 c.translate(x+w/2,y+h/2);if(flip)c.rotate(Math.PI);
 const scale=Math.max(w/texture.width,h/texture.height);
 c.drawImage(texture,-texture.width*scale/2,-texture.height*scale/2,texture.width*scale,texture.height*scale);
 c.restore();
}
function versus(c,avatars,logo,landscape,texture){
 c.fillStyle='#faf7ee';c.fillRect(0,0,1800,c.canvas.height);

 contain(c,logo,30,15,245,130);
 title(c,data.name,850,76,1080,62);
 text(c,match.date.replaceAll('-','.'),1610,77,34,310);
 line(c,0,158,1800,158,'#a73a2a',5);
 match.players.forEach((p,i)=>{
 const x=i*450,[top,middle,bottom]=teamPalette(p.color);
 const wash=c.createLinearGradient(x,161,x+450,1056);
 wash.addColorStop(0,top);wash.addColorStop(.5,middle);wash.addColorStop(1,top);
 c.fillStyle=wash;c.fillRect(x,161,450,895);
 c.fillStyle=bottom;c.fillRect(x,810,450,245);
 brushTexture(c,texture,x,161,450,895,i%2===1);
 text(c,p.teamName,x+225,243,39,405,'#fffdf5');
 line(c,x+194,289,x+256,289,'#fff5df',3);
 portrait(c,avatars[i],x+43,365,364,true);
 seatBadge(c,p.wind,x+354,676,33);
 text(c,p.name,x+225,925,84,404,'#fffdf5');
 if(i)line(c,x,160,x,1055,'#faf7ee',3);
 });
 c.fillStyle='#202723';c.fillRect(0,1058,1800,c.canvas.height-1058);
 brushTexture(c,texture,0,1058,1800,142,false,.5);
 line(c,0,1057,1800,1057,'#ae4435',4);
 text(c,caption(match),900,1107,46,1440,'#fffaf0');
 commentary(c,1640,900,1170,'#eee1c5');
}

async function draw(){
 syncTabs();
 const token=++generation;clear();match=data?.matches.find(m=>m.id===$('poster-match').value)||null;
 $('poster-warning').hidden=true;
 if(!match){notice('该比赛日暂无场次');return}
 if(!match.complete){notice('出战名单未齐，请先设置四位选手后再生成。');return}
 const current=match,mode=template();notice('正在生成预览…');
 if(current.private){$('poster-warning').hidden=false;$('poster-warning').textContent='本场包含尚未公开的出战名单。下载后请勿提前发布。'}
 try{
 let failed=0;
 const avatars=await Promise.all(current.players.map(async p=>{try{return await image(p.imageUrl)}catch(e){if(p.imageUrl===fallback)throw e;failed++;return image(fallback)}}));
 const [logo,landscape,texture]=await Promise.all([image('/brand/logo'),image('/assets/matchday-landscape.png').catch(()=>null),mode==='versus'?image('/assets/poster-drybrush.png'):Promise.resolve(null)]);
 if(token!==generation)return;
 const out=document.createElement('canvas');out.width=mode==='ink'?1200:1800;out.height=mode==='ink'?1500:1200;
 const c=out.getContext('2d');out.height+=Math.max(0,commentaryLines(c,mode==='ink'?980:1640).length-1)*32;c.imageSmoothingQuality='high';(mode==='ink'?ink:versus)(c,avatars,logo,landscape,texture);
 canvas.width=out.width;canvas.height=out.height;canvas.getContext('2d').drawImage(out,0,0);canvas.hidden=false;
 ready=true;download.disabled=busy;
 const defaults=current.players.filter(p=>p.imageUrl===fallback).length;
 notice(failed?`${failed} 张头像加载失败，已使用默认头像；可刷新重试。`:`预览已生成${defaults?' · '+defaults+' 位选手使用默认头像':''}`);
 }catch(e){if(token===generation)notice(e.message+'，请刷新重试')}
}
function syncTabs(){for(const type of ['lineup','daily']){const a=document.getElementById('tab-'+type);a.href='?'+new URLSearchParams({type,event:$('poster-event').value,date:$('poster-day').value,match:$('poster-match').value});a.setAttribute('aria-current',type==='lineup'?'page':'false')}}
$('poster-event').onchange=load;
$('poster-day').onchange=()=>chooseMatch();
$('poster-match').onchange=draw;
document.querySelectorAll('[name="poster-template"]').forEach(r=>r.onchange=draw);
$('poster-refresh').onclick=()=>{images.clear();load()};
download.onclick=async()=>{
 if(!ready||!match||busy)return;
 busy=true;download.disabled=true;
 const token=generation,id=data.id,mid=match.id,old=JSON.stringify({name:data.name,match});
 try{
 const latest=await api('/api/posters/'+id+'/');
 if(token!==generation)return;
 const updated=latest.matches.find(m=>m.id===mid);
 if(JSON.stringify({name:latest.name,match:updated})!==old){data=latest;chooseMatch(mid);notice('名单或赛事信息已更新，请核对新预览后再下载。');return}
 if(match.private&&!confirm('本场包含未公开名单。海报下载后请勿提前发布，是否继续下载？'))return;
 const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
 if(token!==generation)return;
 if(!blob)throw Error('图片导出失败');
 const url=URL.createObjectURL(blob),a=document.createElement('a');
 a.href=url;a.download=`${data.name}-${match.date}-${table(match.table)}桌-第${match.game}半庄-${template()==='ink'?'水墨':'对阵'}.png`.replace(/[<>:"/\\|?*]/g,'_');
 a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);notice('已生成 PNG；手机可在下载文件中保存图片。');
 }catch(e){notice(e.message)}finally{busy=false;download.disabled=!ready}
};
api('/api/posters/').then(value=>{
 options($('poster-event'),value.events.map(e=>[e.id,e.name]));if(value.events.some(e=>e.id===context.get('event')))$('poster-event').value=context.get('event');load();
}).catch(e=>{clear();notice(e.message)});
})();
