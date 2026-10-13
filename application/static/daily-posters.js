(()=>{
'use strict';
const params=new URLSearchParams(location.search);if(params.get('type')!=='daily')return;
const $=id=>document.getElementById(id),preview=document.querySelector('.poster-preview'),download=$('poster-download');
$('poster-match-label').hidden=true;$('poster-templates').hidden=true;preview.classList.add('daily-preview');$('poster-refresh').textContent='刷新战报';
let data=null,generation=0,ready=false,busy=false;
const font='"Microsoft YaHei","PingFang SC",sans-serif',serif='KaiTi,"Songti SC",SimSun,serif';
const pt=(v,sign=false)=>Number.isFinite(v)?(sign&&v>0?'+':'')+(v/10).toFixed(1):'—';
function status(s){$('poster-status').textContent=s}
async function api(url){const r=await fetch(url,{cache:'no-store',credentials:'same-origin'});let value;try{value=await r.json()}catch{throw Error('加载失败，请重新登录后重试')}if(!r.ok)throw Error(value.error||'加载失败');return value}
function url(){return '/api/posters/'+$('poster-event').value+'/daily/?'+new URLSearchParams({date:$('poster-day').value})}
function sync(){for(const type of ['lineup','daily']){const a=$('tab-'+type);a.href='?'+new URLSearchParams({type,event:$('poster-event').value,date:$('poster-day').value});a.setAttribute('aria-current',type==='daily'?'page':'false')}}
async function draw(token){
 const snapshot=data;
 const result=await window.DailyPosterRenderer.render(snapshot);
 if(token!==generation)return;
 preview.replaceChildren(...result.canvases);ready=true;download.disabled=busy;
 status('预览已生成 · 共 '+result.canvases.length+' 张'+(result.missingImages?' · 部分队标加载失败，已使用文字标识':''));
}
async function load(){const token=++generation;ready=false;download.disabled=true;preview.replaceChildren();data=null;sync();if(!$('poster-event').value){status('暂无可管理赛事');return}status('正在生成战报…');try{const value=await api(url());if(token!==generation)return;data=value;const selected=value.date,days=[...new Set([...value.days,selected])].sort();$('poster-day').replaceChildren(...days.map(d=>new Option(d,d)));$('poster-day').value=selected;sync();if(!value.matches.length){status('该日暂无已发布战果');return}await draw(token)}catch(e){if(token===generation)status(e.message)}}
$('poster-event').onchange=()=>{$('poster-day').replaceChildren();load()};$('poster-day').onchange=load;$('poster-refresh').onclick=load;
download.onclick=async()=>{if(!ready||busy)return;busy=true;download.disabled=true;const token=generation;try{const latest=await api(url());if(token!==generation)return;if(JSON.stringify(latest)!==JSON.stringify(data)){await load();status('赛果已更新，请核对新预览后下载。');return}const canvases=[...preview.querySelectorAll('canvas')];for(let i=0;i<canvases.length;i++){const blob=await new Promise(resolve=>canvases[i].toBlob(resolve,'image/png'));if(token!==generation)return;if(!blob)throw Error('导出失败，请重试');const link=document.createElement('a'),u=URL.createObjectURL(blob);link.href=u;link.download=(data.name+'-'+data.date+'-当日战报-'+(i+1)+'.png').replace(/[<>:"/\\|?*]/g,'_');link.click();setTimeout(()=>URL.revokeObjectURL(u),60000)}status('已导出 '+canvases.length+' 张 PNG；如浏览器询问，请允许多文件下载。')}catch(e){status(e.message)}finally{busy=false;download.disabled=!ready}};
api('/api/posters/').then(value=>{$('poster-event').replaceChildren(...value.events.map(e=>new Option(e.name,e.id)));if(value.events.some(e=>e.id===params.get('event')))$('poster-event').value=params.get('event');if(params.get('date'))$('poster-day').append(new Option(params.get('date'),params.get('date')));load()}).catch(e=>status(e.message));
})();
