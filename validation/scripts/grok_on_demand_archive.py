"""Offline Grok run-index merge and latest ordering. Does not publish or read GitHub."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from grok_radar_validation import json_bytes, parse_json, require, sha256, timestamp, unique, validate_schema

ROOT = Path(__file__).resolve().parents[1]
REPO = 'farfromexact/Global-Cross-Asset-Radar-Grok'


def schema(name):
    return parse_json((ROOT / f'schemas/grok_on_demand/{name}.schema.json').read_bytes())


def check_preserved(before, after):
    validate_schema(before, schema('runs'))
    validate_schema(after, schema('runs'))
    left, right = unique(before['runs'], 'run_id'), unique(after['runs'], 'run_id')
    require(left.keys() <= right.keys(), 'Historical run entries lost')
    require(all(value == right[key] for key, value in left.items()), 'Historical run entry changed')
    require({k: v for k, v in before.items() if k != 'runs'} ==
            {k: v for k, v in after.items() if k != 'runs'}, 'Index metadata changed')


def merge_index(before, manifest_raw, manifest_path, latest=None, now=None):
    now = now or datetime.now(timezone.utc)
    validate_schema(before, schema('runs'))
    manifest = parse_json(manifest_raw)
    validate_schema(manifest, schema('run_manifest'))
    require(before['archive_repository'] == manifest['archive_repository'] == REPO, 'Wrong archive repository')
    require(before['archive_mode'] == manifest['archive_mode'] == 'production', 'Production archive required')
    require(manifest['batch_status'] == 'complete' and manifest['archive_status'] == 'verified', 'Incomplete batch cannot enter success index')
    cutoff, started, completed = (timestamp(manifest[k]) for k in
                                   ('information_cutoff_utc', 'started_at_utc', 'completed_at_utc'))
    require(cutoff <= started <= completed <= now, 'Invalid batch chronology')
    day = started.astimezone(timezone(timedelta(hours=8))).strftime('%Y/%m/%d')
    prefix = f"reports/{day}/{manifest['run_id']}"
    require(manifest_path == prefix + '/run_manifest.json', 'Wrong batch manifest path')
    for domain in ('global', 'commodities'):
        item = manifest['reports'][domain]
        require(started <= timestamp(item['generated_at_utc']) <= completed, 'Invalid report chronology')
        for key, ext in (('markdown', 'md'), ('json', 'json')):
            require(item[key]['path'] == f'{prefix}/{domain}.{ext}', 'Wrong domain report path')
    entry = {k: manifest[k] for k in ('run_id', 'information_cutoff_utc', 'started_at_utc', 'completed_at_utc', 'batch_status')}
    entry['manifest'] = {'path': manifest_path, 'sha256': sha256(manifest_raw)}
    rows = unique(before['runs'], 'run_id')
    if entry['run_id'] in rows:
        require(rows[entry['run_id']] == entry, 'Same run_id has different immutable content')
    merged = deepcopy(before)
    if entry['run_id'] not in rows:
        merged['runs'].append(entry)
    check_preserved(before, merged)

    def order(item):
        return (timestamp(item['information_cutoff_utc']), timestamp(item['started_at_utc']), item['run_id'])
    update_latest = all(order(entry) >= order(row) for row in merged['runs'])
    if latest is not None:
        validate_schema(latest, schema('latest'))
        require(latest['archive_repository'] == REPO and latest['archive_mode'] == 'production', 'Wrong latest target')
        require(latest['run_id'] in rows, 'Latest is absent from the baseline index; reread coherent state')
        existing = rows[latest['run_id']]
        require(latest['manifest'] == existing['manifest'] and
                all(latest[k] == existing[k] for k in ('information_cutoff_utc', 'started_at_utc')),
                'Latest/index identity mismatch')
        update_latest = update_latest and order(entry) >= order(latest)
    return merged, {'scope': 'local_merge_only', 'run_count': len(merged['runs']),
                    'update_latest': update_latest, 'remote_readback': 'not_verified_by_this_tool',
                    'ci_validation_status': 'pending_or_unverified'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--before', help='Full actual current manifests/runs.json')
    group.add_argument('--initialize-empty', action='store_true', help='Only after confirmed remote absence, never on a read error')
    parser.add_argument('--manifest-file', required=True, help='Actual readback of the complete run_manifest')
    parser.add_argument('--manifest-path', required=True)
    parser.add_argument('--latest', help='Actual current latest/run.json, if present')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        before = parse_json(Path(args.before).read_bytes()) if args.before else {
            'schema_version': 'radar_runs_v1', 'archive_mode': 'production', 'archive_repository': REPO, 'runs': []}
        latest = parse_json(Path(args.latest).read_bytes()) if args.latest else None
        merged, result = merge_index(before, Path(args.manifest_file).read_bytes(), args.manifest_path, latest)
        with Path(args.output).open('xb') as stream:
            stream.write(json_bytes(merged))
        require(Path(args.output).read_bytes() == json_bytes(merged), 'Local index readback differs')
        print(json_bytes(result).decode('utf-8'), end='')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, 'FAILED: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
