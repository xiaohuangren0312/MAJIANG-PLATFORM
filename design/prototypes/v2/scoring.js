(function (root) {
  const defaults = { start: 25000, returnPoints: 30000, bonuses: [50, 10, -10, -30], tie: 'split', version: 1 };
  function calculate(scores, rules = defaults) {
    if (scores.length !== 4 || scores.some(x => !Number.isFinite(x) || !Number.isInteger(x) || x % 100 !== 0)) throw new Error('请输入四个以 100 点为单位的最终点数');
    if (!Number.isInteger(rules.start) || rules.start <= 0 || rules.start % 100 || !Number.isInteger(rules.returnPoints) || rules.returnPoints <= 0 || rules.returnPoints % 100 || !Array.isArray(rules.bonuses) || rules.bonuses.length !== 4 || rules.bonuses.some(x => !Number.isFinite(x) || Math.abs(x * 10 - Math.round(x * 10)) > 1e-8) || !['split', 'seat'].includes(rules.tie)) throw new Error('请检查规则数值，顺位加分最多一位小数');
    if (scores.reduce((a, b) => a + b, 0) !== (rules.expectedTotal ?? rules.start * 4)) throw new Error('总点数应为 ' + ((rules.expectedTotal ?? rules.start * 4)).toLocaleString() + '，请先结算供托并核对点数');
    const order = scores.map((score, seat) => ({ score, seat })).sort((a,b) => b.score - a.score || a.seat - b.seat);
    const result = Array(4);
    for (let i = 0; i < 4;) {
      let end = i + 1;
      if (rules.tie === 'split') while (end < 4 && order[end].score === order[i].score) end++;
      const n = end - i;
      const total = rules.bonuses.slice(i, end).reduce((a,b) => a + Math.round(b * 10), 0);
      const share = Math.floor(total / n), remainder = total - share * n;
      for (let j = i; j < end; j++) {
        const r = order[j];
        const bonusTenths = share + (j - i < remainder ? 1 : 0);
        result[r.seat] = { rank: i + 1, tied: n > 1, bonusTenths, pointsTenths: (r.score - rules.returnPoints) / 100 + bonusTenths };
      }
      i = end;
    }
    return result;
  }
  const api = { defaults, calculate };
  if (typeof module !== 'undefined') module.exports = api;
  root.Scoring = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
