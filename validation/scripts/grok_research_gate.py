"""Grok research acceptance and rendering; no model, network or publication calls.

Checks submitted evidence and calculations, not the truth of source content or
investment judgment. The publishing program re-runs this against real files.
"""
from pathlib import Path, PurePosixPath
import math
import re
from urllib.parse import urlparse

VERSION = 'grok_research_gate_v1'


def check_research(report, required_scopes, evidence_root=None):
    # Lazy imports allow the generated validator to call this extension.
    from grok_radar_validation import require, unique, timestamp, sha256
    evidence = report.get('research_evidence', {})
    require(evidence.get('version') == VERSION, 'Missing current Grok research evidence')
    universe = evidence.get('universe', [])
    require(len(universe) == len(set(universe)) and set(required_scopes) <= set(universe),
            'Research universe omits baseline or repeats scopes')
    rows = unique(report['coverage'], 'scope')
    require(set(rows) == set(universe), 'Coverage must match baseline plus discovered universe')
    searches = unique(evidence.get('searches', []), 'search_id')
    require(searches, 'Missing actual retrieval records')
    files = {}
    for search in searches.values():
        require(search['status'] in ('read', 'unavailable'), 'Unperformed retrieval cannot count as research')
        require(search['scopes'] and set(search['scopes']) <= set(universe), 'Retrieval scopes invalid')
        parsed = urlparse(search['source_url'])
        require(parsed.scheme in ('https', 'http') and parsed.netloc, 'Retrieval needs a public source URL')
        require('china-stock-engine' not in search['source_url'].lower(), 'Paused source forbidden')
        for source in report['data_versions'].values():
            if source['repository'].lower() in search['source_url'].lower():
                require(source['commit'] and source['commit'] in search['source_url'], 'Engine retrieval URL must pin its input commit')
        require(timestamp(search['accessed_at']) <= timestamp(report['generated_at_utc']), 'Retrieval after report generation')
        path = PurePosixPath(search['artifact'])
        require(not path.is_absolute() and path.parts and path.parts[0] == 'evidence' and
                all(p not in ('.', '..') and ':' not in p for p in path.parts) and '\\' not in search['artifact'], 'Unsafe evidence path')
        require(re.fullmatch('[0-9a-f]{64}', search['sha256']), 'Invalid evidence SHA-256')
        require(search['artifact'] not in files or files[search['artifact']] == search['sha256'], 'Conflicting evidence hash')
        files[search['artifact']] = search['sha256']
        require(isinstance(search['result'], str) and search['result'].strip(), 'Missing retrieval outcome')
        if evidence_root is not None:
            base = Path(evidence_root).resolve()
            target = (base / search['artifact']).resolve()
            require(target.is_relative_to(base), 'Evidence escapes package')
            require(target.is_file() and sha256(target.read_bytes()) == search['sha256'], 'Missing/corrupt source snapshot: ' + search['artifact'])

    facts = unique(report['facts'], 'fact_id')
    for fact in facts.values():
        ids = fact.get('search_ids', [])
        require(ids and set(ids) <= searches.keys(), 'Fact lacks retrieval evidence: ' + fact['fact_id'])
        require(all(searches[s]['status'] == 'read' for s in ids), 'Unavailable source cannot support a fact')
        require(fact['known_at'] is not None and timestamp(fact['known_at']) <= timestamp(report['information_cutoff_utc']),
                'Undated or post-cutoff fact cannot support research')

    def refs(item, label, allow_na=False):
        status = item.get('status')
        require(status in ('analyzed', 'data_missing', 'not_applicable'), 'Unfinished research: ' + label)
        fids, sids = item.get('fact_ids', []), item.get('search_ids', [])
        require(set(fids) <= facts.keys() and set(sids) <= searches.keys(), 'Dangling evidence: ' + label)
        if status == 'analyzed':
            require(fids and sids, 'Analyzed item needs facts and retrievals: ' + label)
            require(set(sids) >= {s for f in fids for s in facts[f]['search_ids']}, 'Item omits fact retrievals: ' + label)
        elif status == 'data_missing':
            require(sids and item.get('limitations'), 'Missing data needs actual attempts and limits: ' + label)
        else:
            require(item.get('limitations'), 'Not applicable requires justification: ' + label)
        return status

    for scope, row in rows.items():
        refs(row, scope)
        require(row['analysis'].strip(), 'Missing scope analysis')
        require(any(scope in searches[s]['scopes'] for s in row['search_ids']), 'No scoped search: ' + scope)
    for section in report['sections']:
        text = section['markdown'].strip()
        require(text and not re.search(r'\.\.\.|…|\bTODO\b|\bplaceholder\b|需从分片进一步提取', text, re.I), 'Outline/placeholder section')
        require(not re.search(r'(?m)^\s*[ABCD][.、．]\s*', text), 'Actions belong only in structured actions; would render twice')
        assessment = section.get('assessment', {})
        refs(assessment, 'section ' + str(section['number']))
        for key in ('analysis', 'counterevidence', 'conclusion'):
            require(isinstance(assessment.get(key), str) and assessment[key].strip(), 'Missing section ' + key)
        # Core dashboards must contain actual observations; no all-missing report
        # can become a successful complete pair simply by declaring limitations.
        if section['number'] == (2 if report['domain'] == 'global' else 3):
            require(assessment['status'] == 'analyzed', 'Core dashboard is incomplete')

    calculations = unique(evidence.get('calculations', []), 'calculation_id')
    computed = {}
    for calc in calculations.values():
        inputs = calc['inputs']
        require(inputs, 'Calculation lacks inputs')
        values = []
        for item in inputs:
            require(('fact_id' in item) != ('calculation_id' in item), 'Ambiguous calculation input')
            if 'fact_id' in item:
                require(item['fact_id'] in facts, 'Calculation lacks input facts')
                values.append(facts[item['fact_id']].get(item.get('field', 'value')))
            else:
                require(item['calculation_id'] in computed, 'Calculation dependency missing, forward or cyclic')
                values.append(computed[item['calculation_id']])
        require(all(type(v) in (int, float) and math.isfinite(v) for v in values), 'Calculation inputs must be finite fact values')
        op = calc['operation']
        require(op in ('sum', 'product', 'difference', 'ratio', 'percent_change'), 'Unsupported calculation; add an audited operation')
        require(op in ('sum', 'product') or len(values) == 2, 'Calculation needs two inputs')
        require(op not in ('ratio', 'percent_change') or values[1] != 0, 'Zero calculation denominator')
        result = (sum(values) if op == 'sum' else math.prod(values) if op == 'product' else values[0] - values[1] if op == 'difference' else
                  values[0] / values[1] if op == 'ratio' else (values[0] / values[1] - 1) * 100)
        require(type(calc['result']) in (int, float) and math.isfinite(calc['result']) and
                math.isclose(result, calc['result'], rel_tol=1e-7, abs_tol=1e-7), 'Calculation result mismatch')
        require(calc.get('unit') and calc.get('purpose'), 'Calculation unit/purpose required')
        computed[calc['calculation_id']] = result
    for candidate in report['candidates']:
        for key in ('pricing_gap', 'counterevidence', 'catalyst', 'invalidation', 'risk_budget', 'execution_plan'):
            require(isinstance(candidate.get(key), str) and candidate[key].strip(), 'Incomplete candidate: ' + key)
        require(set(candidate.get('calculation_ids', [])) <= calculations.keys(), 'Candidate calculation missing')
        scores = candidate.get('scores')
        if scores is None:
            require(candidate.get('unscored_reason'), 'Unscored candidate needs reason')
        else:
            caps = {'logic': 25, 'odds': 25, 'catalyst': 20, 'price_vol': 15, 'crowding': 15}
            require(all(type(scores.get(k)) in (int, float) and 0 <= scores[k] <= cap for k, cap in caps.items()), 'Score cap/type invalid')
            require(scores.get('total') == sum(scores[k] for k in caps), 'Score total mismatch')
            require(set(candidate.get('score_reasons', {})) == set(caps) and
                    all(isinstance(v, str) and v.strip() for v in candidate['score_reasons'].values()), 'Missing score reasons')
    require(not report['candidates'] or calculations or evidence.get('calculation_gap'), 'Record calculations or a specific input gap')
    return {'gate_version': VERSION, 'evidence_files': files, 'scopes': len(rows),
            'investment_truth': 'requires_source_and_research_review'}


def render_research(report):
    """Include sources, scope records and calculation inputs; actions exactly once."""
    lines = [f"# {report['domain']} Radar", '']
    for key in ('run_id', 'information_cutoff_utc', 'generated_at_utc', 'registry_commit', 'archive_repository', 'prompt_sha256'):
        lines.extend([f'{key}: {report[key]}'])
    lines.append('')
    for section in report['sections']:
        a = section['assessment']
        lines.extend([f"## {section['number']}. {section['title']}", '', section['markdown'], '',
                      '分析：' + a['analysis'], '反证/替代解释：' + a['counterevidence'], '结论：' + a['conclusion'],
                      '事实引用：' + ', '.join(a['fact_ids']), '限制：' + '；'.join(a['limitations']), ''])
    lines.extend(f"{k}. {report['actions'][k]}" for k in 'ABCD')
    lines.extend(['', '## 事实与来源', ''])
    searches = {s['search_id']: s for s in report['research_evidence']['searches']}
    for f in report['facts']:
        lines.extend([f"- **{f['fact_id']}**：{f['statement']}",
                      f"  观测：{f['observed_at']}；已知：{f['known_at']}；限制：{'；'.join(f['limitations'])}"])
        for sid in f['search_ids']:
            s = searches[sid]
            lines.append(f"  [{sid}]({s['source_url']})；读取：{s['accessed_at']}；证据：{s['artifact']}；SHA-256：{s['sha256']}")
    lines.extend(['', '## 覆盖与缺口', ''])
    for row in report['coverage']:
        lines.append(f"- {row['scope']} [{row['status']}]：{row['analysis']}；事实：{', '.join(row['fact_ids'])}；限制：{'；'.join(row['limitations'])}")
    lines.extend(['', '## 计算记录', ''])
    for c in report['research_evidence']['calculations']:
        lines.append(f"- {c['calculation_id']}：{c['operation']}({c['inputs']}) = {c['result']} {c['unit']}；{c['purpose']}")
    if not report['research_evidence']['calculations']:
        lines.append(report['research_evidence'].get('calculation_gap', '本批无适用计算；见候选与限制。'))
    return ('\n'.join(lines) + '\n').encode('utf-8')
