"""Render human-readable report sections; no archive or executor dependency."""
from datetime import datetime, timedelta, timezone
import re

BJT = timezone(timedelta(hours=8))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


TITLES = {'global': '全球跨资产 Radar', 'commodities': '商品 Radar', 'free': 'Free Report｜开放研究'}
INTERNAL = re.compile(r'run_id|information_cutoff|registry_commit|registry_version|'
                      r'prompt_sha256|数据仓\s*commit|研究状态\s*[:：]\s*complete|'
                      r'初筛完成|条件维持|实体未补齐|旧参数保留', re.I)


def action_text(report):
    return '\n'.join(f"{key}. {report['actions'][key]}" for key in 'ABCD')


def render_report(report):
    """Preserve prose; free research has no required chapters or action section."""
    day = timestamp(report['information_cutoff_utc']).astimezone(BJT)
    lines = [f"# {TITLES[report['domain']]}", '',
             f"研究时间：{day:%Y年%m月%d日 %H:%M}（北京时间）", '']
    if report['domain'] == 'free':
        require(report['markdown'].strip(), 'Empty free report')
        lines.extend([report['markdown'], ''])
    else:
        for section in report['sections']:
            lines.extend([f"## {section['number']}. {section['title']}", '', section['markdown'], ''])
    result = '\n'.join(lines) + '\n'
    require(not INTERNAL.search(result), 'Internal status or metadata leaked into report prose')
    if report['domain'] != 'free':
        require(report['sections'][-1]['markdown'].strip() == action_text(report),
                'Final section must equal canonical A/B/C/D actions; do not append duplicate actions')
    return result.encode('utf-8')
