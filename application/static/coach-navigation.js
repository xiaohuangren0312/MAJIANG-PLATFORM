(()=>{
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths=['<path d="m3 10 9-7 9 7v11h-6v-7H9v7H3Z"/>','<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3h6v4H9zM9 12h6M9 16h6"/>','<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M8 14h2M14 14h2"/>','<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>'];
document.querySelectorAll('.coach-main-nav a').forEach((a,i)=>a.insertAdjacentHTML('afterbegin','<svg viewBox="0 0 24 24" aria-hidden="true">'+paths[i]+'</svg>'));
let current=null,mode='upcoming',publicPromise=null,version=0;
const query=id=>'?'+new URLSearchParams({event:id});
function links(id){document.querySelectorAll('.coach-main-nav a').forEach(a=>{a.href=new URL(a.href).pathname+query(id)})}
const eventSelect=document.querySelector('#lineup-event');eventSelect?.addEventListener('change',()=>queueMicrotask(()=>{if(eventSelect.value)links(eventSelect.value)}));
window.addEventListener('coach-event-selected',e=>links(e.detail));
const requested=new URLSearchParams(location.search).get('event');if(requested)links(requested);
async function renderSchedule(data){const host=document.querySelector('#coach-schedule-content');if(!host)return;const ticket=++version;host.hidden=false;host.className='coach-schedule-list';host.textContent='正在加载本队赛程…';
try{publicPromise??=fetch('/data.json').then(r=>{if(!r.ok)throw Error();return r.json()}).catch(e=>{publicPromise=null;throw e});const value=await publicPromise;if(ticket!==version)return;const event=value.tournaments.find(e=>e.id===data.id);const ids=new Set(data.teams.map(t=>t.id));const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());const matches=(event?.schedule||[]).filter(m=>m.players.some(p=>ids.has(p.teamId)));const results=(event?.results||[]).filter(m=>m.seats.some(s=>ids.has(s.teamId)));
const selected=mode==='upcoming'?matches.filter(m=>m.state==='scheduled'&&m.date>=today):results;selected.sort((a,b)=>(a.date.localeCompare(b.date)||(a.time||'').localeCompare(b.time||''))*(mode==='upcoming'?1:-1));
const days=[...new Set(selected.map(m=>m.date))];host.innerHTML='<div class="coach-schedule-tabs"><button type="button" data-view="upcoming" aria-pressed="'+(mode==='upcoming')+'">接下来的比赛</button><button type="button" data-view="results" aria-pressed="'+(mode==='results')+'">已结束</button></div>'+(!event?'<p>赛事尚未公开，可在出战名单中查看本队安排。</p>':days.length?days.map(day=>'<details class="card"'+(day===days[0]?' open':'')+'><summary><strong>'+esc(day)+'</strong><span>'+selected.filter(m=>m.date===day).length+' 半庄</span></summary>'+selected.filter(m=>m.date===day).map(m=>{const people=m.players||m.seats;const names=people.map(p=>event.teams.find(t=>t.id===p.teamId)?.name||'队伍待定').join(' / ');return '<div class="match-row"><strong>'+esc(m.time||'')+'</strong><span>'+esc(m.table||'')+'桌</span><span>'+esc(names)+'</span><a href="'+(mode==='upcoming'?'/coach/lineups/'+query(data.id)+'&date='+encodeURIComponent(day):'/#result?'+new URLSearchParams({event:data.id,id:m.id}))+'">'+(mode==='upcoming'?'安排出战':'查看战果与资料')+'</a></div>'}).join('')+'</details>').join(''):'<div class="card">'+(mode==='upcoming'?'暂无后续出战赛程':'暂无已发布战果')+'</div>');host.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{mode=b.dataset.view;renderSchedule(current)});
}catch(_){host.innerHTML='<p>赛程加载失败，请稍后重试。</p><button type="button">重新加载</button>';host.querySelector('button').onclick=()=>renderSchedule(current)}}

let lineup=null,homeVersion=0;
const calendar='<svg viewBox="0 0 24 24" aria-hidden="true">'+paths[2]+'</svg>';
function drawHome(){
 if(!current||!document.body.classList.contains('coach-home'))return;
 const host=document.querySelector('#coach-dashboard');if(!host)return;
 const data=lineup?.id===current.id?lineup:window.coachLineupSnapshot?.id===current.id?window.coachLineupSnapshot:null;
 const next=data?.nextMatchDay,rows=next?data.rows.filter(r=>r.date===next.date):[];
 const link='/coach/lineups/'+query(current.id)+(next?'&date='+encodeURIComponent(next.date):'');
 const pending=data?.rows.filter(r=>r.scheduled&&!r.published&&!r.locked&&r.playerId)||[];
 pending.sort((a,b)=>a.publishAt.localeCompare(b.publishAt));
 const dateText=v=>new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v));
 host.innerHTML='<div class="coach-dashboard-grid"><section class="coach-next-card"><h2>下一出战日</h2>'+(!data?'<p class="coach-empty">正在读取出战安排…</p>':next?'<div class="coach-next-date"><strong>'+esc(next.date.slice(5).replace('-','.'))+'</strong><span>'+esc(new Intl.DateTimeFormat('zh-CN',{weekday:'long'}).format(new Date(next.date+'T12:00:00+08:00')))+'</span><em>'+ (next.pending?'待安排':'已安排')+'</em></div><p class="coach-next-meta">'+esc(next.time)+' 首场　｜　'+esc(rows[0]?.stageName)+' · '+next.matches+' 半庄</p><div class="coach-next-bottom"><div class="coach-half-list">'+rows.map((r,i)=>'<div><span>第 '+(i+1)+' 半庄</span><time>'+esc(r.time)+'</time><small>'+esc(r.locked?'已锁定':r.published?'已公开':r.scheduled?'已预约':'未安排')+'</small></div>').join('')+'</div><a class="coach-action primary" href="'+link+'">'+(next.pending?'安排出战':'查看名单')+'</a></div>':'<div class="coach-empty">暂无后续出战赛程<small>赛程公布后将在这里提醒</small></div>')+'</section><section class="coach-release-card"><h2>发布安排</h2><div class="coach-release-content">'+calendar+'<strong>'+(pending.length?'已预约 '+pending.length+' 份名单':'暂无预约发布')+'</strong><p>'+(pending.length?'最近发布：'+esc(dateText(pending[0].publishAt)):'安排名单后可预约公开')+'</p><a class="coach-action" href="'+link+'">查看名单</a></div></section></div><section class="coach-recent-card"><div class="coach-form-heading"><h2>队员近况</h2><span>最近五场 · 左旧右新</span></div><div id="coach-recent-results" class="coach-empty">正在读取已发布战果…</div></section>';

 const ticket=++homeVersion,id=current.id,players=current.players.slice();
 publicPromise??=fetch('/data.json').then(r=>{if(!r.ok)throw Error();return r.json()}).catch(e=>{publicPromise=null;throw e});
 publicPromise.then(value=>{
 if(ticket!==homeVersion)return;
 const event=value.tournaments.find(e=>e.id===id),box=document.querySelector('#coach-recent-results');
 const results=(event?.results||[]).slice().sort((a,b)=>(b.date||'').localeCompare(a.date||'')||(b.time||'').localeCompare(a.time||'')||Number(b.number||0)-Number(a.number||0));
 box.className='coach-player-form';
 box.innerHTML=players.length?players.map(player=>{
 const recent=results.flatMap(match=>(match.seats||[]).filter(seat=>seat.playerId===player.id&&Number.isInteger(seat.rank)&&seat.rank>=1&&seat.rank<=4).map(seat=>({match,rank:seat.rank}))).slice(0,5).reverse();
 return '<div class="coach-form-player"><span class="coach-form-name">'+esc(player.name)+'</span><div class="coach-form-ranks">'+(recent.length?recent.map(({match,rank})=>'<a class="coach-rank rank-'+rank+'" href="/#result?'+new URLSearchParams({event:id,id:match.id})+'" aria-label="'+esc(player.name+'，'+match.date+' '+(match.time||'')+'，第'+rank+'位，查看战果')+'" title="'+esc(match.date+' '+(match.time||'')+' · 第'+rank+'位')+'">'+rank+'</a>').join(''):'<span class="coach-form-none">暂无战果</span>')+'</div></div>';
 }).join(''):'<span class="coach-form-none">暂无本队选手</span>';
 }).catch(()=>{if(ticket===homeVersion)document.querySelector('#coach-recent-results').textContent='战果暂时无法读取，请刷新重试'});

}
window.addEventListener('coach-lineups-ready',e=>{lineup=e.detail;drawHome()});
window.addEventListener('coach-profile-ready',e=>{current=e.detail;links(current.id);if(document.body.classList.contains('coach-schedule'))renderSchedule(current);drawHome()});
})();
