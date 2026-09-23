"""Pure draft rules. Event roster is supplied through the adapter only."""
import copy
from league.domain import require, integer, find, Invalid

def configuration(document, kind, payload):
    require(kind == 'team', '只有团体赛可以组队选人')
    require(not document.get('archive') and not document.get('historySnapshot'), '已归档或历史赛事不能创建选人活动')
    previous = document.get('draft')
    require(not previous or previous.get('phase') == 'setup', '选人开始后不能覆盖配置')
    require(not any(m.get('state') != 'cancelled' for m in document.get('matches', [])), '请在安排比赛之前完成组队选人')
    rows = payload.get('teams')
    candidates = payload.get('candidates')
    require(isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows), '请配置参选队伍')
    require(isinstance(candidates, list) and candidates and all(isinstance(r, dict) for r in candidates), '请配置候选选手')
    step = integer(payload.get('bidStep', 1), '加价步长', 1, 1000000)
    teams, seen_teams, seen_users, seen_coaches = [], set(), set(), set()
    for row in rows:
        team = find(document['teams'], row.get('teamId'))
        require(team.get('active', True), '参选队伍已停用')
        user_id = integer(row.get('coachUserId'), '教练账号', 1)
        coach = find(document['players'], row.get('coachPlayerId'))
        require(coach.get('active', True) and not coach.get('bond'), '教练须为启用的正式选手')
        require(coach.get('teamId') in (None, '', team['id']), '教练已属于其他队伍')
        require(team['id'] not in seen_teams and user_id not in seen_users and coach['id'] not in seen_coaches, '队伍、教练账号或教练选手重复')
        budget = integer(row.get('budget', 30), '总预算', 0, 1000000)
        playing = row.get('coachPlaying', not coach.get('nonPlayingCoach', False))
        require(type(playing) is bool, '请选择教练是否参赛')
        price = integer(row.get('coachPrice', 0), '教练定价', 0, budget)
        require(playing or price == 0, '不参赛教练定价必须为0')
        capacity = integer(row.get('capacity', team.get('draftSettings', {}).get('capacity', 6)), '含教练人数上限', 2, 100)
        members = {p['id'] for p in document['players'] if p.get('teamId') == team['id'] and not p.get('bond')}
        members.add(coach['id'])
        require(len(members) <= capacity, '现有名单超过人数上限')
        teams.append(dict(teamId=team['id'], coachUserId=user_id, coachPlayerId=coach['id'], budget=budget, coachPrice=price, coachPlaying=playing, balance=budget-price, capacity=capacity))
        seen_teams.add(team['id']); seen_users.add(user_id); seen_coaches.add(coach['id'])
    pool, seen_players = [], set()
    for row in candidates:
        player = find(document['players'], row.get('playerId'))
        require(player.get('active', True) and not player.get('bond') and not player.get('nonPlayingCoach') and not player.get('teamId'), '候选必须为本赛事启用且未分队的正式选手')
        require(player['id'] not in seen_players and player['id'] not in seen_coaches, '候选重复或包含教练')
        description = row.get('description', player.get('bio', ''))
        require(isinstance(description, str) and len(description) <= 2000, '选手介绍最多2000字')
        pool.append(dict(playerId=player['id'], startPrice=integer(row.get('startPrice', 0), '起拍价', 0, 1000000), description=description.strip(), state='available'))
        seen_players.add(player['id'])
    updated = copy.deepcopy(document)
    updated['draft'] = dict(version=1, phase='setup', bidStep=step, teams=teams, candidates=pool, allocations=[], round=0)
    return updated


def allocate(document, team_id, player_id, method, price=0):
    draft = document['draft']
    team = next(r for r in draft['teams'] if r['teamId'] == team_id)
    player = find(document['players'], player_id)
    candidate = next((r for r in draft['candidates'] if r['playerId'] == player_id), None)
    require(not player.get('nonPlayingCoach') and candidate and candidate['state'] == ('third-pool' if method == 'third-round' else 'available') and not player.get('teamId') and player.get('active', True) and not player.get('bond'), '选手已归队或不可选')
    require(find(document['teams'], team_id).get('active', True), '队伍已停用')
    members = [p for p in document['players'] if p.get('teamId') == team_id and not p.get('bond')]
    require(len(members) < team['capacity'], '队伍人数已满')
    integer(price, '成交价', 0, team['balance'])
    team['balance'] -= price
    player['teamId'] = team_id
    candidate['state'] = 'allocated'
    draft['allocations'].append(dict(teamId=team_id, playerId=player_id, price=price, method=method))


def first_pick(document, action, payload, team_id=None):
    import secrets
    d = copy.deepcopy(document)
    require(not d.get('archive') and not d.get('historySnapshot'), '赛事不可修改')
    require(not any(m.get('state') != 'cancelled' for m in d.get('matches', [])), '选人期间不能已有比赛安排')
    draft = d.get('draft')
    require(draft is not None, '请先保存选人配置')
    phase = draft['phase']
    if action == 'start':
        require(phase == 'setup', '活动已开始')
        require(len(draft['candidates']) >= len(draft['teams']), '候选人数不足每队一选')
        for row in draft['teams']:
            coach = find(d['players'], row['coachPlayerId'])
            require(coach.get('active', True) and not coach.get('bond') and coach.get('teamId') in (None, '', row['teamId']), '教练归属已变化，请重新配置')
            require(find(d['teams'], row['teamId']).get('active', True), '队伍已停用')
            coach['teamId'] = row['teamId']
            if not row.get('coachPlaying', True): coach['nonPlayingCoach'] = True
            else: coach.pop('nonPlayingCoach', None)
            require(sum(p.get('teamId') == row['teamId'] and not p.get('bond') for p in d['players']) < row['capacity'], '队伍必须保留一选名额')
        for row in draft['candidates']:
            player = find(d['players'], row['playerId'])
            require(player.get('active', True) and not player.get('teamId') and not player.get('bond') and not player.get('nonPlayingCoach'), '候选归属已变化，请重新配置')
        draft.update(phase='nomination', round=1, pending=[r['teamId'] for r in draft['teams']], nominations={}, conflicts=[], reveals=[], rolls=[])
    elif action == 'nominate':
        require(phase == 'nomination' and team_id in draft['pending'], '当前队伍无需提交一选')
        pid = payload.get('playerId')
        require(any(r['playerId'] == pid and r['state'] == 'available' for r in draft['candidates']), '候选不可选')
        require(team_id not in draft['nominations'], '已提交，请等待管理员公布')
        draft['nominations'][team_id] = pid
    elif action == 'admin-nominate':
        target=payload.get('teamId');pid=payload.get('playerId')
        require(phase=='nomination' and target in draft['pending'], '该队伍当前无需提交一选')
        require(any(r['playerId']==pid and r['state']=='available' for r in draft['candidates']), '候选不可选')
        player=find(d['players'],pid)
        require(player.get('active',True) and not player.get('teamId') and not player.get('bond') and not player.get('nonPlayingCoach'), '候选归属或状态已变化')
        row=next(t for t in draft['teams'] if t['teamId']==target)
        require(not exclusion(d,row,0), '队伍已满员或不可参与选择')
        draft['nominations'][target]=pid
    elif action == 'reveal':
        require(phase == 'nomination' and set(draft['pending']) == set(draft['nominations']), '请等待全部教练提交')
        groups = {}
        for tid, pid in draft['nominations'].items(): groups.setdefault(pid, []).append(tid)
        draft['reveals'].append(dict(round=draft['round'], choices=copy.deepcopy(draft['nominations'])))
        draft['conflicts'] = []
        for pid, tids in groups.items():
            if len(tids) == 1: allocate(d, tids[0], pid, 'first-pick')
            else: draft['conflicts'].append(dict(playerId=pid, teams=tids))
        draft['phase'] = 'revealed'
    elif action == 'roll':
        require(phase == 'revealed', '请先公布一选')
        conflict = next((r for r in draft['conflicts'] if r['playerId'] == payload.get('playerId')), None)
        require(conflict is not None, '冲突已处理或不存在')
        values = {tid: secrets.randbelow(100)+1 for tid in conflict['teams']}
        winners = [tid for tid, v in values.items() if v == max(values.values())]
        draft['rolls'].append(dict(round=draft['round'], playerId=conflict['playerId'], values=values, winner=winners[0] if len(winners)==1 else None))
        if len(winners) == 1:
            allocate(d, winners[0], conflict['playerId'], 'first-roll')
            draft['conflicts'].remove(conflict)
        else: conflict['teams'] = winners
    elif action == 'continue':
        require(phase == 'revealed' and not draft['conflicts'], '请先处理全部冲突')
        won = {r['teamId'] for r in draft['allocations']}
        pending = [r['teamId'] for r in draft['teams'] if r['teamId'] not in won]
        draft.update(pending=pending, nominations={})
        if pending:
            draft['round'] += 1
            draft['phase'] = 'nomination'
        else: draft['phase'] = 'auction-ready' if any(r['state'] == 'available' for r in draft['candidates']) else ('third-ready' if any(r['state'] == 'third-pool' for r in draft['candidates']) else 'review-ready')
    else: raise Invalid('未知选人操作')
    return d




AUCTION_ACTIONS = {'draw', 'open-bidding', 'bid', 'pass', 'confirm-lot', 'next-lot', 'draw-third', 'assign-third', 'assign-second'}


def exclusion(document, row, minimum):
    if not find(document['teams'], row['teamId']).get('active', True): return '队伍已停用'
    count = sum(p.get('teamId') == row['teamId'] and not p.get('bond') for p in document['players'])
    if count >= row['capacity']: return '人数已满'
    if row['balance'] < minimum: return '余额不足'
    return None


def advance_turn(document, after=None):
    draft = document['draft']; lot = draft['lot']
    minimum = lot['price'] + draft['bidStep'] if lot['leader'] else lot['startPrice']
    lot['minimum'] = minimum
    eligible = []
    for row in draft['teams']:
        tid = row['teamId']
        if tid == lot['leader'] or tid in lot['passed']: continue
        reason = exclusion(document, row, minimum)
        if reason: lot['excluded'][tid] = reason
        else:
            lot['excluded'].pop(tid, None)
            eligible.append(tid)
    if not eligible:
        lot['turn'] = None
        lot['state'] = 'awaiting-confirm'
        return
    order = [r['teamId'] for r in draft['teams']]
    start = (order.index(after)+1) % len(order) if after in order else lot['firstIndex']
    lot['turn'] = next(order[(start+i)%len(order)] for i in range(len(order)) if order[(start+i)%len(order)] in eligible)


def auction(document, action, payload, team_id=None):
    import secrets
    from league.domain import uid
    d = copy.deepcopy(document)
    require(not d.get('archive') and not d.get('historySnapshot'), '赛事不可修改')
    require(not any(m.get('state') != 'cancelled' for m in d.get('matches', [])), '选人期间不能已有比赛安排')
    draft = d.get('draft'); require(draft is not None, '请先配置活动')
    if action in {'draw', 'draw-third'}:
        third = action == 'draw-third'
        require(draft['phase'] == ('third-ready' if third else 'auction-ready'), '请先完成上一环节或处理当前选手')
        pool = [r for r in draft['candidates'] if r['state'] == ('third-pool' if third else 'available')]
        require(pool, '当前候选池已处理完毕')
        # A stale roster must be corrected explicitly, never silently overwritten.
        for row in pool:
            player = find(d['players'], row['playerId'])
            require(player.get('active', True) and not player.get('teamId') and not player.get('bond') and not player.get('nonPlayingCoach'), '候选名单已变化，请先核对')
        chosen = secrets.choice(pool)
        count = len(draft.get('lots', []))
        draft['lot'] = dict(id=uid(), stage=3 if third else 2, playerId=chosen['playerId'], startPrice=chosen['startPrice'], price=None, leader=None, state='preview', passed=[], excluded={}, turn=None, firstIndex=count % len(draft['teams']), bids=[], minimum=chosen['startPrice'])
        draft['phase'] = 'auction'
        return d
    require(draft['phase'] == 'auction' and draft.get('lot'), '当前不在竞拍环节')
    lot = draft['lot']
    # Bind every response to this candidate, not just a possibly refreshed revision.
    require(payload.get('lotId') == lot['id'], '选手已切换，请刷新后操作')
    if action == 'open-bidding':
        require(lot['state'] == 'preview', '竞拍已经开始')
        lot['state'] = 'bidding'; advance_turn(d)
    elif action in {'bid', 'pass'}:
        require(lot['state'] == 'bidding', '当前不能出价或 PASS')
        require(team_id == lot['turn'] and team_id not in lot['passed'], '未轮到当前队伍或本阶段已经 PASS')
        if action == 'pass':
            lot['passed'].append(team_id)
            lot['bids'].append(dict(teamId=team_id, action='pass'))
        else:
            row = next(r for r in draft['teams'] if r['teamId'] == team_id)
            price = integer(payload.get('price'), '出价', lot['minimum'], 1000000)
            require(not exclusion(d, row, price), '队伍人数已满、已停用或余额不足')
            lot.update(price=price, leader=team_id)
            lot['bids'].append(dict(teamId=team_id, action='bid', price=price))
        advance_turn(d, team_id)
    elif action == 'confirm-lot':
        require(lot.get('stage', 2) == 2, '第三轮请由管理员选择队伍并确认分派')
        require(lot['state'] == 'awaiting-confirm', '请等待其他队伍响应')
        if lot['leader']:
            allocate(d, lot['leader'], lot['playerId'], 'auction', lot['price'])
            lot['outcome'] = 'sold'
        else:
            candidate = next(r for r in draft['candidates'] if r['playerId'] == lot['playerId'])
            require(candidate['state'] == 'available', '候选状态已变化')
            candidate['state'] = 'third-pool';lot['outcome'] = 'unsold'
        lot['state'] = 'settled'
        draft.setdefault('lots', []).append(copy.deepcopy(lot))
    elif action == 'assign-second':
        require(lot.get('stage', 2) == 2 and lot['state'] in {'preview','bidding','awaiting-confirm','settled'}, '当前选手不在第二阶段')
        target=payload.get('teamId')
        require(any(t['teamId']==target for t in draft['teams']), '接收队伍不属于本活动')
        price=integer(payload.get('price'), '分配金额', 0, 1000000)
        previous=dict(state=lot['state'],leader=lot.get('leader'),price=lot.get('price'),outcome=lot.get('outcome'),assignedTeam=lot.get('assignedTeam'),assignedPrice=lot.get('assignedPrice'))
        was_settled=lot['state']=='settled'
        if was_settled:
            require(draft.get('lots') and draft['lots'][-1]['id']==lot['id'], '成交记录已变化，请刷新核对')
            candidate=next(r for r in draft['candidates'] if r['playerId']==lot['playerId'])
            player=find(d['players'],lot['playerId'])
            if lot.get('outcome') in {'sold','assigned'}:
                require(draft['allocations'] and draft['allocations'][-1]['playerId']==lot['playerId'], '分配记录已变化，请先核对')
                allocation=draft['allocations'][-1]
                prior_team=lot.get('assignedTeam') if lot.get('outcome')=='assigned' else lot['leader']
                prior_price=lot.get('assignedPrice') if lot.get('outcome')=='assigned' else lot['price']
                require(allocation['teamId']==prior_team and allocation['price']==prior_price and player.get('teamId')==prior_team and candidate['state']=='allocated', '选手归属或成交记录已变化，请先核对')
                source=next(t for t in draft['teams'] if t['teamId']==prior_team)
                source['balance']+=allocation['price']
                require(source['balance']<=source['budget']-source['coachPrice'], '原队伍余额不一致')
                draft['allocations'].pop();player['teamId']=None
            else:
                require(lot.get('outcome')=='unsold' and candidate['state']=='third-pool' and not player.get('teamId'), '流拍记录已变化')
            candidate['state']='available'
        allocate(d,target,lot['playerId'],'admin-second',price)
        lot.setdefault('adminChanges',[]).append(dict(before=previous,teamId=target,price=price))
        lot.update(state='settled',outcome='assigned',assignedTeam=target,assignedPrice=price,turn=None)
        if was_settled:draft['lots'][-1]=copy.deepcopy(lot)
        else:draft.setdefault('lots',[]).append(copy.deepcopy(lot))
    elif action == 'assign-third':
        require(lot.get('stage', 2) == 3 and lot['state'] == 'awaiting-confirm', '请先完成第三轮竞价')
        target = payload.get('teamId')
        require(any(t['teamId'] == target for t in draft['teams']), '接收队伍不属于本活动')
        if lot['leader'] is not None:
            price = lot['price']
            require(type(payload.get('price')) is int and payload['price'] == price, '有有效出价时必须按最终竞拍价扣费')
        else: price = integer(payload.get('price'), '分派价格', 0, 1000000)
        allocate(d, target, lot['playerId'], 'third-round', price)
        lot.update(state='settled', outcome='assigned', assignedTeam=target, assignedPrice=price)
        draft.setdefault('lots', []).append(copy.deepcopy(lot))
    elif action == 'next-lot':
        require(lot['state'] == 'settled', '请先确认成交或流拍')
        draft.pop('lot')
        if lot.get('stage', 2) == 3:
            draft['phase'] = 'third-ready' if any(r['state'] == 'third-pool' for r in draft['candidates']) else 'review-ready'
        else:
            draft['phase'] = 'auction-ready' if any(r['state'] == 'available' for r in draft['candidates']) else ('third-ready' if any(r['state'] == 'third-pool' for r in draft['candidates']) else 'review-ready')
    else: raise Invalid('未知竞拍操作')
    return d
