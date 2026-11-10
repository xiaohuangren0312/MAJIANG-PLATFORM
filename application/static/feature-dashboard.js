// Routes use the same controls as the management pages. Opening a card never submits a form.
function destination(target, selector, openPanel=false) {
    return () => {
        opened=null;
        preview=null;
        page=target;
        render();
        if (!selector) return;
        requestAnimationFrame(() => {
            if (page!==target) return;
            const control=document.querySelector(selector);
            if (!control) { notice('当前赛事没有可打开的操作',true); return; }
            if (openPanel) {
                const trigger=control.closest('.admin-tool-panel')?.querySelector('summary');
                if (trigger) { trigger.click(); return; }
            }
            if (control.matches('button') && !control.disabled) control.click();
            else { control.scrollIntoView({block:'center'}); control.focus(); }
        });
    };
}

function matchPicker(state) {
    return () => {
        workspaceContext();
        workspaceUI.scheduleVisited=true;
        workspaceUI.tab='detail';
        workspaceUI.matchId=null;
        scheduleFilter={date:'',query:'',state};
        destination('schedule')();
    };
}

function chooseMatch(matches) {
    return () => {
        const dialog=document.createElement('dialog');
        dialog.className='feature-match-picker';
        dialog.setAttribute('aria-label','选择对局');
        dialog.innerHTML='<h2>选择对局</h2><label>日期 <select></select></label><div class="feature-match-list"></div><button type="button" class="secondary">关闭</button>';
        const date=dialog.querySelector('select'),list=dialog.querySelector('.feature-match-list');
        const dates=[...new Set(matches.map(m=>m.date))].sort();
        dates.forEach(d=>date.add(new Option(d,d)));
        date.value=dates.find(d=>d>=scheduleToday())||dates.at(-1)||'';
        function drawMatches(){
            list.replaceChildren();
            for(const m of matches.filter(m=>m.date===date.value).sort((a,b)=>a.time.localeCompare(b.time)||a.number-b.number)){
                const button=document.createElement('button');
                button.type='button';button.className='secondary';
                const seats=m.seats.map(s=>event.kind==='team'?team(s.teamId):player(s.playerId));
                button.textContent=m.time+' · '+tableName(m.number)+'　'+seats.join(' / ');
                button.onclick=()=>{dialog.close();workspaceGo('schedule',m.id)};
                list.append(button);
            }
            if(!matches.length)list.textContent='暂无符合条件的对局。';
        }
        date.onchange=drawMatches;drawMatches();
        dialog.querySelector(':scope > button').onclick=()=>dialog.close();
        dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
    };
}

function catalog() {
    const cards=[];
    let group='赛程与战果';
    function add(title, description, keywords, action, allowed=true, status='') {
        if (allowed) cards.push({group,title,description,keywords,action,status});
    }
    if (event) {
        const url='/manage/events/'+encodeURIComponent(event.id)+'/batch-schedule/';
        const teamEvent=event.kind==='team';
        const doc=event.document;
        const openStages=doc.stages.filter(s=>!s.locked);
        const pending=doc.matches.filter(m=>m.state==='draft' && openStages.some(s=>s.id===m.stageId));
        const roundPending=openStages.length===1 && pending.length;
        add('安排单场赛程','选择时间、桌次和参赛名单','排赛程 手动安排 新建比赛',destination('schedule','#match-form',true),can('match'));
        add('批量排程','按多个比赛日生成整批赛程','排赛程 自动安排 多日 分桌',url,can('batch-schedule'));
        add('高高碰批量排程','按本轮排名预览全部桌次','排赛程 自动安排 个人赛 分桌',url,can('pairing-preview'),roundPending?'本阶段还有 '+pending.length+' 桌待完成':'');
        add('录入比分','选择待赛对局，录分或发布赛果','录分 成绩 粘贴比分 名单 罚分 役满 发布',chooseMatch(pending),can('score'),pending.length?'':'暂无待录分对局');
        add('更正赛果','选择已发布的对局并核对比分','更正成绩 修正 改分',chooseMatch(doc.matches.filter(m=>m.state==='published'&&!m.readOnly&&openStages.some(s=>s.id===m.stageId))),can('correct'));
        add('编辑对局','调整赛程、名单或取消待赛对局','修改比赛时间 桌号 取消 删除对局',chooseMatch(pending),can('match-update')||can('cancel'));
        add('桌次直播','设置各比赛日的直播地址','直播间 链接',destination('schedule','#matchday-live-form',true),can('matchday-live'));
        add('赛程战果','查看比赛日、桌次和对局详情','赛果 成绩 查分 随机座位 修改赛程 撤销 取消 删除对局 更正',matchPicker('all'));
        add('对局资料',can('match-resources')?'维护解说、视频和牌谱':'查看解说、视频和牌谱','录像 回放 解说员',destination('resources'));
        add('海报中心','生成出战海报或比赛战报','导出 图片 每日战报','/manage/posters/?event='+encodeURIComponent(event.id));
        add('每日战报','按比赛日导出战果海报','海报 导出 图片 日报','/manage/posters/?type=daily&event='+encodeURIComponent(event.id));
        group='队伍与选手';
        add('队伍管理','查看本赛事队伍及队员','队徽 队色 队标 名单 队伍资料',destination('roster'),teamEvent);
        add('添加队伍','登记新队伍','建队 新建队伍',destination('roster','#team-form',true),teamEvent&&can('team'));
        add('选手名册','按编号或姓名查找选手','队员 名单 选手资料 头像 编辑 删除',destination('roster','#roster-search'));
        add('选手报名','登记参赛选手','新增选手 注册',destination('roster','#player-form',true),can('player'));
        add('羁绊选手','登记选手的阶段所属队伍','报名 借调',destination('roster','#bond-form',true),teamEvent&&can('bond-player'));
        add('教练管理','查看和调整本赛事的教练授权','教练账号 绑定队伍 停用',destination('access'),can('coach-manage'));
        group='规则与阶段';
        add('计分规则','管理规则版本及模板','积分 PT 起始点 返点 顺位分 规则库',destination('rules'),can('rule'));
        add('阶段管理','设置阶段名称、晋级名次及用桌','阶段设置 晋级名单',destination('overview',openStages.length?'[data-edit-stage-tables="'+CSS.escape(openStages[0].id)+'"]':'.stage-table-directory'),can('stage-update')||can('stage'));
        add('管理桌名','设置桌次名称和启用状态','赛事桌次 桌号 黑八 蓝八',destination('overview','#manage-event-tables'),can('tables-update'));
        add('阶段结算','核对排名、晋级和带入分','结算预览 晋级名单',destination('settle'),can('settlement-preview'));
        group='赛事与权限';
        add('赛事概览','查看阶段进度和待办事项','状态 概况 工作台',destination('overview'));
        add('赛事公开设置','查看并调整公开状态','可见性 隐藏 公开赛事',()=>{destination('overview')();document.querySelector('#visibility')?.focus()},can('visibility'));
        add('赛事 Logo','上传赛事标志或恢复默认','标识 更换图片',destination('overview','#overview-change-logo'),can('event-logo'));
        add('赛事归档','查看最终排名与归档操作','结束比赛 修订 重开',destination('lifecycle'),can('archive-preview')||can('archive-reopen')||event.archived||event.completed);
        if(doc.archive||doc.archiveRevision||doc.completion)
            add('导出归档战果','下载赛事归档工作簿','Excel 导出 历史成绩','/api/events/'+encodeURIComponent(event.id)+'/archive.xlsx');
        add('清理测试赛事','预览本赛事的清理范围','测试赛 删除',destination('lifecycle','#cleanup-preview'),can('cleanup-preview'));
        add('创建账号','为本赛事创建可授权的账号','教练账号 新用户',destination('access','#workspace-create-account'),can('coach-manage'));
        add('分配赛事管理员','分配或撤回赛事管理权限','赛事授权 授权账号',destination('access','#workspace-grant'),can('grant'));
        add('查看观众端','打开赛事公开页面','公众端 排名','/#home?event='+encodeURIComponent(event.id),event.public);
    }
    group='场馆与协作';
    if (!document.querySelector('#new-event').hidden)
        add('新建赛事','建立个人赛或团体赛','创建比赛',()=>document.querySelector('#new-event').click());
    if (event && document.querySelector('#venue-settings-form'))
        add('场馆设置','编辑场馆名称与默认 Logo','场馆标志 宣传语',destination('overview','#overview-edit-venue'));
    for(const [path,title,desc,keys] of [
        ['/draft/','组队选人','进入选人大会','选秀 竞拍'],
        ['/coach/lineups/','出战名单','管理已授权队伍的出战安排','教练排班 上场名单'],
        ['/coach/profile/','队伍资料','维护已授权队伍的展示资料','教练 队色 简介'],
        ['/manage/history-backfill/','历史补录','打开历史赛季补录工作区','历史核对 补成绩']
    ]) {
        const link=document.querySelector('.workspace-links a[href="'+path+'"], #overview-tools a[href="'+path+'"]');
        if (path.startsWith('/coach/')) {
            if (event?.coachTools) add(title,desc,keys,path+'?event='+encodeURIComponent(event.id));
        } else if (link) add(title,desc,keys,link.href);
    }
    return cards;
}

export function showDashboard(host) {
    const cards=catalog();
    host.className='feature-dashboard';
    host.innerHTML='<section class="feature-head"><small></small><h1>功能总览</h1><label><span aria-hidden="true">⌕</span><input type="search" aria-label="搜索功能" placeholder="搜索功能，例如：排赛程、录分、海报"></label></section><p class="feature-count" role="status"></p><div class="feature-groups"></div>';
    host.querySelector('small').textContent=event?event.name+'　/　'+(event.kind==='team'?'团体赛':'个人赛'):'场馆管理';
    const search=host.querySelector('input');
    function draw() {
        const query=search.value.trim().toLocaleLowerCase();
        const found=cards.filter(c=>[c.group,c.title,c.description,c.keywords].join(' ').toLocaleLowerCase().includes(query));
        host.querySelector('.feature-count').textContent=query?'找到 '+found.length+' 项功能':'';
        const groups=host.querySelector('.feature-groups');
        groups.replaceChildren();
        if(!found.length){groups.textContent=query?'没有匹配的功能，请更换关键词。':'当前没有可用功能。';return}
        for(const group of new Set(found.map(c=>c.group))){
            const section=document.createElement('section'),heading=document.createElement('h2'),grid=document.createElement('div');
            heading.textContent=group;grid.className='feature-grid';section.append(heading,grid);groups.append(section);
            for(const card of found.filter(c=>c.group===group)){
                const link=typeof card.action==='string';
                const tile=document.createElement(link?'a':'button');
                if(link)tile.href=card.action;else {tile.type='button';tile.onclick=card.action}
                tile.className='feature-tile';
                const title=document.createElement('strong'),detail=document.createElement('small');
                title.textContent=card.title;detail.textContent=card.description;const symbol=document.createElement('span');
                symbol.className='feature-icon';symbol.setAttribute('aria-hidden','true');
                const paths={'赛程与战果':'M3 6h18v15H3z M3 10h18 M7 3v5 M17 3v5','队伍与选手':'M4 21v-2c0-5 12-5 12 0v2 M10 12a4 4 0 1 0 0-8 4 4 0 1 0 0 8 M17 13q5 1 5 6','规则与阶段':'M5 3h10l4 4v14H5z M8 11h8 M8 15h6'};
                const path=paths[group]||'M3 4h7v7H3z M14 4h7v7h-7z M3 15h7v6H3z M14 15h7v6h-7z';
                symbol.innerHTML='<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="'+path+'"/></svg>';
                tile.append(symbol,title,detail);
                if(card.status){const status=document.createElement('em');status.textContent=card.status;tile.append(status)}
                grid.append(tile);
            }
        }
    }
    search.oninput=draw;draw();
}
