/* Daily export uses published scores verbatim; rendering never recalculates PT. */
(()=>{
'use strict';
const W=1080,L=44,R=1036,INK='#263d30',MUTED='#778078',PAPER='#f4f2eb',RED='#b04533',GREEN='#526b60';
const sans='"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif',brush='KaiTi,"Songti SC",SimSun,serif';
const fmt=(v,sign=false)=>Number.isFinite(v)?(sign&&v>0?'+':'')+(v/10).toFixed(1):'—';
const color=v=>/^#[0-9a-f]{6}$/i.test(v||'')?v:'#758976';
function text(c,value,x,y,size,max,fill=INK,align='left',family=sans,weight=400){
 let str=String(value??''),s=size;c.textAlign=align;c.textBaseline='middle';c.fillStyle=fill;
 const set=()=>{c.font=`${weight} ${s}px ${family}`};set();
 while(c.measureText(str).width>max&&s>12){s--;set()}
 while(c.measureText(str).width>max&&str.length>1)str=str.slice(0,-2)+'…';
 c.fillText(str,x,y);
}
function rule(c,x,y,x2,y2,fill='#d7ded0'){c.strokeStyle=fill;c.lineWidth=1;c.beginPath();c.moveTo(x,y);c.lineTo(x2,y2);c.stroke()}
function contain(c,im,x,y,w,h){if(!im)return;const s=Math.min(w/im.width,h/im.height);c.drawImage(im,x+(w-im.width*s)/2,y+(h-im.height*s)/2,im.width*s,im.height*s)}
async function asset(src){if(!src)return null;const url=new URL(src,location.origin);if(url.origin!==location.origin)throw Error('图片必须来自本站');return new Promise((resolve,reject)=>{const im=new Image(),timer=setTimeout(()=>reject(Error('图片加载超时')),15000);im.onload=()=>{clearTimeout(timer);resolve(im)};im.onerror=()=>{clearTimeout(timer);reject(Error('图片加载失败'))};im.src=url.href})}
const tableKey=m=>`${m.stageId||''}:${m.table??''}`;
const compare=(a,b)=>String(a??'').localeCompare(String(b??''),'zh-CN',{numeric:true});
function orderedMatches(data){
 const stages=new Map(data.stages.map((s,i)=>[s.id,i]));
 return [...data.matches].sort((a,b)=>(stages.get(a.stageId)??0)-(stages.get(b.stageId)??0)||compare(a.stageId,b.stageId)||compare(a.table,b.table)||compare(a.time,b.time)||compare(a.id,b.id));
}
const cutoffBefore=(row,previous,stage)=>stage.advanceCount>0&&previous&&previous.rank<=stage.advanceCount&&row.rank>stage.advanceCount;
function commentaryLines(m){
 const names=m.commentators||[];if(!names.length)return [];
 // Reserve a conservative 56 characters per line at 14px.
 const lines=[];let value='解说：'+names.join(' · ');
 while(value.length){lines.push(value.slice(0,56));value=value.slice(56)}
 return lines;
}
const commentaryHeight=m=>commentaryLines(m||{}).length*22;
function paginate(data){
 const pages=[];let blocks=[],height=0;
 const flush=()=>{if(blocks.length)pages.push({blocks,height});blocks=[];height=0};
 const put=(type,rows,stage)=>{
  let block=null;
  for(let i=0;i<Math.max(rows.length,1);i++){
   const row=rows[i];
   const extra=type==='matches'?(block&&tableKey(block.rows.at(-1))!==tableKey(row)?16:0):(cutoffBefore(row,rows[i-1],stage)?28:0);
   const rowHeight=type==='matches'?128+commentaryHeight(row):70;
   if(height+(block?0:100)+rowHeight+extra>1740){flush();block=null}
   if(!block){block={type,rows:[],stage,cutoffAtStart:type==='ranking'&&!!cutoffBefore(row,rows[i-1],stage)};blocks.push(block);height+=100}
   const actualExtra=type==='matches'?(block.rows.length&&tableKey(block.rows.at(-1))!==tableKey(row)?16:0):extra;
   if(row)block.rows.push(row);height+=rowHeight+actualExtra;
  }
 };
 put('matches',orderedMatches(data));
 for(const stage of data.stages)put('ranking',stage.rows,{...stage,kind:data.kind});
 flush();return pages;
}
function heading(c,label,y,number,sub){text(c,number,L,y+23,22,40,RED,'left','Georgia',700);text(c,label,L+40,y+23,25,500,INK,'left',sans,700);text(c,sub,R,y+23,12,380,MUTED,'right');c.fillStyle=INK;c.fillRect(L,y+48,992,3)}
function matchRows(c,rows,y){
 c.fillStyle='#293f32';c.fillRect(L,y,992,46);text(c,'桌次 / 时间',L+50,y+23,12,95,'#c5cebe','center');
 for(let i=0;i<4;i++)text(c,'东南西北'[i],144+223*i+111.5,y+23,21,80,'#f9f7ed','center',brush,700);
 y+=46;
 rows.forEach((m,index)=>{
  if(index&&tableKey(rows[index-1])!==tableKey(m))y+=16;
  const byWind=new Map(m.seats.map(s=>[s.wind,s]));c.fillStyle='#fffdf8';c.fillRect(L,y,992,128);c.fillStyle='#f0f1e9';c.fillRect(L,y,100,128);
  const table=/^\d+$/.test(String(m.table))&&+m.table>=1&&+m.table<=26?String.fromCharCode(64+(+m.table)):m.table;
  text(c,table,L+12,y+49,28,54,INK,'left','Georgia',700);text(c,'桌',L+49,y+53,12,35,MUTED);text(c,m.time,L+12,y+78,16,80,GREEN,'left','Arial');
  for(let i=0;i<4;i++){
   const s=byWind.get('东南西北'[i]),x=144+i*223;
   if(i)rule(c,x,y+15,x,y+111,'#e5e7df');
   if(!s){text(c,'未记录',x+13,y+54,17,190,MUTED);continue}
   text(c,s.name,x+13,y+31,21,157,INK,'left',sans,650);text(c,s.rank?`${s.rank}位`:'—',x+210,y+31,12,32,s.rank===1?'#9d7133':'#7a827a','right');
   text(c,Number.isFinite(s.score)?s.score.toLocaleString('en-US'):'—',x+13,y+66,27,117,INK,'left','Arial');text(c,fmt(s.points,true),x+210,y+66,20,78,s.points>0?RED:GREEN,'right','Arial',700);
   const img=c.assets.get(s.teamImageUrl);if(img)contain(c,img,x+13,y+92,18,18);else{c.fillStyle=color(s.teamColor);c.fillRect(x+13,y+94,3,14)}
   text(c,s.team,x+(img?34:20),y+102,12,img?176:190,MUTED);
  }
  y+=128;const lines=commentaryLines(m);if(lines.length){c.fillStyle='#fffdf8';c.fillRect(L,y,992,lines.length*22);lines.forEach((value,i)=>text(c,value,157,y+10+i*22,14,865,MUTED));y+=lines.length*22}rule(c,L,y,R,y,'#e0e3db');
 });return y;
}
function rankings(c,rows,y,stage,cutoffAtStart=false){
 const cutoff=()=>{c.save();c.setLineDash([4,4]);rule(c,L,y+14,L+398,y+14,'#91a69a');rule(c,L+594,y+14,R,y+14,'#91a69a');c.restore();text(c,`晋级线 · 前 ${stage.advanceCount} 名`,L+496,y+14,13,185,GREEN,'center');y+=28};
 const team=stage.kind==='team',movementX=team?L+660:L+616;
 const cols=[L+14,L+178,movementX,L+836,R-14];
 if(team){text(c,'半庄',L+554,y+14,12,90,MUTED,'center');text(c,'已打 / 阶段总数',L+554,y+31,10,100,MUTED,'center')}
 text(c,'排名',cols[0],y+21,11,60,MUTED);text(c,stage.kind==='player'?'选手':'队伍',cols[1],y+21,11,230,MUTED);text(c,'升降',cols[2],y+21,11,70,MUTED,'center');text(c,'累计积分 PT',cols[3],y+21,11,150,MUTED,'right');text(c,'当日增减 PT',cols[4],y+21,11,125,MUTED,'right');y+=46;
 if(!rows.length){text(c,stage.notice||'暂无排名',L+16,y+32,18,960,MUTED);return y+70}
 rows.forEach((r,index)=>{
  if((index===0&&cutoffAtStart)||cutoffBefore(r,rows[index-1],stage))cutoff();
  const tint=color(r.color);c.fillStyle='#fffdfa';c.fillRect(L,y,992,65);const grad=c.createLinearGradient(L,y,R,y);grad.addColorStop(0,tint+'09');grad.addColorStop(1,tint+'00');c.fillStyle=grad;c.fillRect(L,y,992,65);c.fillStyle=tint;c.fillRect(L,y,4,65);
  text(c,r.rank,L+19,y+33,33,55,INK,'left','Arial',700);const img=c.assets.get(r.imageUrl);if(img)contain(c,img,L+100,y+9,66,45);else text(c,r.name.slice(0,2),L+132,y+33,20,64,tint,'center',brush,700);
  text(c,r.name,L+184,y+33,18,team?310:380,INK,'left',sans,700);
  if(team)text(c,`${Number.isInteger(r.playedGames)?r.playedGames:'—'} / ${Number.isInteger(r.stageGames)?r.stageGames:'—'}`,L+554,y+33,19,100,GREEN,'center','Arial');
  const movement=r.beforeRank-r.rank;text(c,movement>0?'▲ '+movement:movement<0?'▼ '+(-movement):'—',movementX,y+33,16,68,movement>0?RED:GREEN,'center','Arial',700);
  text(c,fmt(r.total),L+836,y+33,31,150,INK,'right','Arial',700);text(c,fmt(r.delta,true),R-14,y+33,22,122,r.delta>0?RED:GREEN,'right','Arial',700);y+=70;
 });return y;
}
async function render(data){
 if(data.matches.some(m=>m.seats.length!==4||new Set(m.seats.map(s=>s.wind)).size!==4||m.seats.some(s=>!['东','南','西','北'].includes(s.wind))))throw Error('部分战果缺少明确风位，无法按东南西北生成战报。请先核对原始记录。');
 const [logo,landscape]=await Promise.all([asset('/brand/logo'),asset('/assets/matchday-landscape.png')]);
 const urls=new Set([...data.matches.flatMap(m=>m.seats.map(s=>s.teamImageUrl)),...data.stages.flatMap(s=>s.rows.map(r=>r.imageUrl))].filter(Boolean));const assets=new Map();let missingImages=0;
 await Promise.all([...urls].map(async url=>{try{assets.set(url,await asset(url))}catch{missingImages++}}));
 const pages=paginate(data),canvases=pages.map((page,i)=>{
  const h=204+page.height+100,el=document.createElement('canvas');el.width=W*2;el.height=h*2;el.setAttribute('role','img');el.setAttribute('aria-label',`当日战报第${i+1}页`);const c=el.getContext('2d');c.scale(2,2);c.assets=assets;c.imageSmoothingQuality='high';c.fillStyle=PAPER;c.fillRect(0,0,W,h);
  c.save();c.globalAlpha=.22;contain(c,landscape,0,0,W,310);c.restore();contain(c,logo,L,28,126,47);text(c,data.name.replace(/\s*S\d+\s*$/i,''),192,51,21,575,INK,'left',brush);text(c,'DAILY MATCH REPORT',R,52,12,270,MUTED,'right','Arial');
  const season=data.name.match(/\bS\d+\b/i)?.[0];if(season)text(c,season,L,138,70,150,RED,'left','Georgia',700);text(c,'当日战报',season?176:L,138,57,520,INK,'left',brush,700);text(c,data.date.replaceAll('-','.'),R,123,29,270,INK,'right','Arial',700);text(c,`${data.matches.length} 场完赛`,R,158,12,270,MUTED,'right');
  let y=204;
  for(const block of page.blocks){
   const isMatch=block.type==='matches';heading(c,isMatch?'当日赛果':data.kind==='team'?'队伍排名':'个人排名',y,isMatch?'01':'02',isMatch?'每格：终局点数 / 本场 PT':block.stage.name+' · 当日结束排名');y+=54;
   y=isMatch?matchRows(c,block.rows,y):rankings(c,block.rows,y,block.stage,block.cutoffAtStart);
  }
  rule(c,L,y+22,R,y+22,'#b8c2af');text(c,[window.HQL_BRAND?.name,window.HQL_BRAND?.tagline].filter(Boolean).join(' · '),L,y+49,14,480,MUTED,'left',brush);text(c,`${location.host}${pages.length>1?' · '+(i+1)+' / '+pages.length:''}`,R,y+49,12,450,MUTED,'right','Arial');return el;
 });return {canvases,missingImages};
}
window.DailyPosterRenderer={render,paginate,orderedMatches};
})();
