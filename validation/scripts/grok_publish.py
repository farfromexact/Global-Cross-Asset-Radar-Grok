"""Manual Grok-only publisher. Validate before writing; never publishes via a model.

Two commits: stage immutable reports/evidence as partial, fetch/read them back,
then atomically publish the verified manifest/index/latest. Normal fast-forward
pushes reject concurrent changes; at most two retries reread a fresh snapshot.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import subprocess
import tempfile

from grok_radar_validation import (require, parse_json, json_bytes, sha256, timestamp,
                                   validate_schema, validate_report, render_report, check_pair, check_archive)
from grok_research_gate import check_research, VERSION
from grok_on_demand_archive import merge_index, schema, REPO

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'https://github.com/farfromexact/Global-Cross-Asset-Radar-Grok.git'
REVIEW_KEYS = {'source_accuracy', 'coverage_and_discovery', 'counterevidence_and_pricing', 'calculations_and_risk'}


def prefix_for(manifest):
    day = timestamp(manifest['started_at_utc']).astimezone(timezone(timedelta(hours=8))).strftime('%Y/%m/%d')
    return f"reports/{day}/{manifest['run_id']}"


def validate_package(directory, registry_commit=None):
    directory = Path(directory).resolve()
    manifest = parse_json((directory / 'run_manifest.json').read_bytes())
    validate_schema(manifest, schema('run_manifest'))
    require(manifest['batch_status'] == 'complete' and manifest['archive_status'] == 'verified',
            'Package manifest must describe the proposed complete batch; it is not a publication receipt')
    require(manifest['archive_repository'] == REPO and manifest['archive_mode'] == 'production', 'Wrong archive target')
    if registry_commit is not None:
        require(manifest['registry_commit'] == registry_commit, 'Publisher must be the pinned Registry checkout')
    scopes = parse_json((ROOT / 'config/recovery_scopes.json').read_bytes())
    frozen, reports, artifacts = {}, {}, {}
    for domain in ('global', 'commodities'):
        raw = (directory / (domain + '.json')).read_bytes()
        report = parse_json(raw)
        require(report.get('domain') == domain, 'Wrong domain for report file: ' + domain)
        validate_report(report, manifest, schema('report'))
        if registry_commit is not None:
            for job, digest in manifest['prompt_sha256'].items():
                require(sha256((ROOT / 'compiled/grok_on_demand' / (job + '.md')).read_bytes()) == digest, 'Pinned prompt mismatch')
        result = check_research(report, scopes[domain], directory)
        for path, digest in result['evidence_files'].items():
            value = (directory / path).read_bytes()
            require(path not in artifacts or artifacts[path] == value, 'Conflicting shared snapshot')
            artifacts[path] = value
        md = (directory / (domain + '.md')).read_bytes()
        require(md == render_report(report), 'Markdown differs from the complete research rendering')
        frozen[domain + '.json'], frozen[domain + '.md'] = raw, md
        reports[domain] = report
    check_pair(reports['global'], reports['commodities'])
    review_raw = (directory / 'research_review.json').read_bytes()
    review = parse_json(review_raw)
    require(review['report_sha256'] == {d: sha256(frozen[d + '.json']) for d in reports}, 'Research review not bound to frozen reports')
    require(review.get('reviewer') and set(review['checks']) == REVIEW_KEYS, 'Missing research review areas')
    require(max(timestamp(r['generated_at_utc']) for r in reports.values()) <= timestamp(review['reviewed_at']) <=
            timestamp(manifest['completed_at_utc']) <= datetime.now(timezone.utc), 'Invalid research review/completion time')
    for check in review['checks'].values():
        require(check.get('status') == 'passed' and isinstance(check.get('evidence'), str) and check['evidence'].strip(),
                'Outstanding research review cannot publish')
    artifacts['research_review.json'] = review_raw
    prefix = prefix_for(manifest)
    raw = json_bytes(manifest)
    empty = {'schema_version': 'radar_runs_v1', 'archive_repository': REPO, 'archive_mode': 'production', 'runs': []}
    index, _ = merge_index(empty, raw, prefix + '/run_manifest.json')
    # Reuse archive identity/hash/previous-report checks before any remote write.
    local = {prefix + '/' + n: value for n, value in frozen.items()}
    local.update({prefix + '/run_manifest.json': raw, 'manifests/runs.json': json_bytes(index)})
    result = check_archive(manifest, frozen, local.__getitem__, {n: schema(n) for n in ('run_manifest', 'runs', 'latest')})
    require(result['batch'] == result['index'] == 'verified', 'Package cross-file validation failed: ' + str(result['errors']))
    return manifest, frozen, artifacts


class GitStore:
    """Dedicated temporary checkout: never resets or stages a user's worktree."""
    def __init__(self, root):
        self.root = Path(root)
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'user.name', 'Grok verified publisher')
        self.git('config', 'user.email', 'grok-publisher@users.noreply.github.com')
        self.git('remote', 'add', 'origin', TARGET)
        self.git('fetch', '--depth=1', 'origin', 'main')
        self.git('checkout', '-q', '-b', 'main', 'FETCH_HEAD')
        self.head = self.git('rev-parse', 'HEAD').decode().strip()

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, timeout=90)
        # Do not echo stderr: credential helpers/URLs may contain secrets.
        require(result.returncode == 0, 'Git operation failed: ' + args[0] + '; no force push attempted')
        return result.stdout

    def read(self, path):
        target = (self.root / path).resolve()
        require(target.is_relative_to(self.root.resolve()), 'Archive path escapes checkout')
        return target.read_bytes() if target.is_file() else None

    def commit(self, files, message):
        for path, raw in files.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        self.git('add', '--', *files)
        if self.git('diff', '--cached', '--name-only').strip():
            self.git('commit', '-q', '-m', message)
            self.git('push', 'origin', 'HEAD:refs/heads/main')
        commit = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('fetch', 'origin', 'main')
        # The pushed commit must remain an ancestor; a newer concurrent commit
        # is fine, but readback is tied to the immutable commit just pushed.
        self.git('merge-base', '--is-ancestor', commit, 'FETCH_HEAD')
        for path, raw in files.items():
            require(self.git('show', commit + ':' + path) == raw, 'Remote readback differs: ' + path)
        self.head = commit
        return commit


def publish_validated(manifest, reports, artifacts, store):
    """Called only after validate_package; no caller-provided status can skip it."""
    prefix = prefix_for(manifest)
    final_raw = json_bytes(manifest)
    immutable = {prefix + '/' + name: raw for name, raw in {**reports, **artifacts}.items()}
    for path, raw in immutable.items():
        previous = store.read(path)
        require(previous is None or previous == raw, 'Existing immutable batch differs: ' + path)
    withdrawal_raw = store.read('manifests/withdrawn_runs.json')
    if withdrawal_raw:
        withdrawn = parse_json(withdrawal_raw)
        require(manifest['run_id'] not in {r['run_id'] for r in withdrawn['runs']}, 'Withdrawn run_id cannot be republished')
    path = prefix + '/run_manifest.json'
    partial = deepcopy(manifest)
    partial.update(batch_status='partial', archive_status='partial')
    partial_raw = json_bytes(partial)
    existing = store.read(path)
    require(existing in (None, partial_raw, final_raw), 'Existing manifest conflicts; use a new run_id')
    stage = dict(immutable)
    stage[path] = final_raw if existing == final_raw else partial_raw
    source_commit = store.commit(stage, 'Stage validated Grok research for independent readback')
    # Store.commit performs fetch + immutable byte readback for every staged file.
    before_raw = store.read('manifests/runs.json')
    require(before_raw is not None, 'Success index must exist; initialize via reviewed repository setup')
    before = parse_json(before_raw)
    latest_raw = store.read('latest/run.json')
    latest = parse_json(latest_raw) if latest_raw else None
    merged, receipt = merge_index(before, final_raw, path, latest)
    changes = {path: final_raw, 'manifests/runs.json': json_bytes(merged)}
    acceptance_path = prefix + '/acceptance.json'
    acceptance = {'version': VERSION, 'run_id': manifest['run_id'], 'registry_commit': manifest['registry_commit'],
                  'source_readback_commit': source_commit, 'research_review_sha256': sha256(artifacts['research_review.json']),
                  'files': {name: sha256(raw) for name, raw in immutable.items()},
                  'scope': 'structural_evidence_and_calculation_checks_plus_declared_research_review',
                  'ci_validation_status': 'pending_or_unverified'}
    old_acceptance = store.read(acceptance_path)
    if old_acceptance:
        previous = parse_json(old_acceptance)
        require({k: v for k, v in previous.items() if k != 'source_readback_commit'} ==
                {k: v for k, v in acceptance.items() if k != 'source_readback_commit'}, 'Acceptance receipt changed')
        acceptance = previous
    changes[acceptance_path] = json_bytes(acceptance)
    if receipt['update_latest']:
        pointer = {k: manifest[k] for k in ('run_id', 'information_cutoff_utc', 'started_at_utc', 'archive_mode', 'archive_repository')}
        pointer.update(schema_version='radar_latest_v1', manifest={'path': path, 'sha256': sha256(final_raw)},
                       reports={d: {k: {'path': f'latest/{d}.{ext}', 'sha256': sha256(reports[d + '.' + ext])}
                                    for k, ext in [('markdown', 'md'), ('json', 'json')]} for d in ('global', 'commodities')})
        changes.update({'latest/' + n: raw for n, raw in reports.items()})
        changes['latest/run.json'] = json_bytes(pointer)
        changes['status/on_demand_latest.json'] = json_bytes({'status': 'verified', 'run_id': manifest['run_id'], 'archive_repository': REPO})
    commit = store.commit(changes, 'Publish independently checked Grok batch and coherent latest')
    return {'archive_commit': commit, 'run_id': manifest['run_id'], 'latest_promoted': receipt['update_latest'],
            'remote_readback': 'verified', 'ci_validation_status': 'pending_or_unverified'}


def audit_archive(directory):
    root = Path(directory)
    index = parse_json((root / 'manifests/runs.json').read_bytes())
    validate_schema(index, schema('runs'))
    require(len({r['run_id'] for r in index['runs']}) == len(index['runs']), 'Duplicate success index ID')
    withdrawn_path = root / 'manifests/withdrawn_runs.json'
    withdrawn = parse_json(withdrawn_path.read_bytes())['runs'] if withdrawn_path.exists() else []
    require(not ({r['run_id'] for r in index['runs']} & {r['run_id'] for r in withdrawn}), 'Withdrawn batch in success index')
    for row in index['runs']:
        path = row['manifest']['path']
        target = (root / path).resolve()
        require(target.is_relative_to(root.resolve()), 'Index path escapes archive')
        require(sha256(target.read_bytes()) == row['manifest']['sha256'], 'Indexed manifest hash mismatch')
        manifest, reports, artifacts = validate_package(target.parent)
        require(path == prefix_for(manifest) + '/run_manifest.json', 'Wrong index path')
        for key in ('run_id', 'information_cutoff_utc', 'started_at_utc', 'completed_at_utc', 'batch_status'):
            require(row[key] == manifest[key], 'Index identity mismatch')
        acceptance = parse_json((target.parent / 'acceptance.json').read_bytes())
        require(acceptance['version'] == VERSION and acceptance['run_id'] == manifest['run_id'] and
                acceptance['registry_commit'] == manifest['registry_commit'], 'Missing current acceptance')
        expected = {prefix_for(manifest) + '/' + n: sha256(raw) for n, raw in {**reports, **artifacts}.items()}
        require(acceptance['files'] == expected and acceptance['research_review_sha256'] == sha256(artifacts['research_review.json']), 'Acceptance hashes mismatch')
        require(re.fullmatch('[0-9a-f]{40}', acceptance['source_readback_commit']), 'Invalid readback commit')
        if (root / '.git').exists():
            source_commit = acceptance['source_readback_commit']
            def git(*args):
                result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=60)
                require(result.returncode == 0, 'Acceptance source commit is not verifiable: ' + args[0])
                return result.stdout
            git('merge-base', '--is-ancestor', source_commit, 'HEAD')
            for path, digest in expected.items():
                require(sha256(git('show', source_commit + ':' + path)) == digest, 'Acceptance source bytes differ')
    latest_path = root / 'latest/run.json'
    if index['runs']:
        newest = max(index['runs'], key=lambda r: (timestamp(r['information_cutoff_utc']), timestamp(r['started_at_utc']), r['run_id']))
        manifest, reports, _ = validate_package((root / newest['manifest']['path']).parent)
        result = check_archive(manifest, reports, lambda p: (root / p).read_bytes(), {n: schema(n) for n in ('run_manifest', 'runs', 'latest')})
        require(result['batch'] == result['index'] == result['latest'] == 'verified', str(result['errors']))
    else:
        require(not latest_path.exists() and not any((root / ('latest/' + d + '.' + ext)).exists()
                    for d in ('global', 'commodities') for ext in ('md', 'json')), 'Empty success index must not advertise latest')
    return {'success_batches': len(index['runs']), 'withdrawn_batches': len(withdrawn), 'status': 'passed',
            'scope': 'git_snapshot_and_acceptance_ancestry' if (root / '.git').exists() else 'local_snapshot_only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'publish', 'audit'])
    parser.add_argument('--package')
    parser.add_argument('--archive')
    args = parser.parse_args()
    try:
        if args.command == 'audit':
            require(args.archive, '--archive required')
            result = audit_archive(args.archive)
        else:
            require(args.package, '--package required')
            from grok_radar_checkpoint import registry_snapshot
            commit, _ = registry_snapshot(ROOT)
            manifest, reports, artifacts = validate_package(args.package, commit)
            result = {'status': 'local_package_passed', 'remote_readback': 'not_run', 'run_id': manifest['run_id']}
            if args.command == 'publish':
                for attempt in range(3):
                    try:
                        with tempfile.TemporaryDirectory(prefix='grok-publish-') as folder:
                            result = publish_validated(manifest, reports, artifacts, GitStore(folder))
                        break
                    except ValueError as exc:
                        if attempt == 2 or not str(exc).startswith('Git operation failed: push'):
                            raise
        print(json_bytes(result).decode(), end='')
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, 'FAILED: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
