"""Publish three Markdown reports from the manual Grok inbox. Standard library only.

The same file is deployed to the report repository. No model, scheduler, data
collector, or research-quality certification is involved.
"""
import argparse
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

REPOSITORY = 'farfromexact/Global-Cross-Asset-Radar-Grok'
REMOTE = 'https://github.com/' + REPOSITORY + '.git'
DOMAINS = ('global', 'commodities', 'free')
FORMAT = 'grok_text_archive_v2'
FORMAT_DOMAINS = {'grok_text_archive_v1': ('global', 'commodities'), FORMAT: DOMAINS}
BJT = timezone(timedelta(hours=8))
MARKER = re.compile(r'^<!-- radar:(global|commodities|free) -->\r?\n', re.M)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def utc(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(stamp.tzinfo is not None, 'Timestamp needs a timezone')
    return stamp.astimezone(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_submission(raw, domains=DOMAINS):
    require(len(raw) <= 4_000_000, 'Submission exceeds 4 MB')
    text = raw.decode('utf-8-sig')
    require('\x00' not in text, 'NUL byte in report')
    markers = list(MARKER.finditer(text))
    require([m.group(1) for m in markers] == list(domains),
            'Expected exactly ' + ', '.join(domains) + ' report markers in that order')
    require(not text[:markers[0].start()].strip(), 'Unexpected content before first report')
    reports = {}
    for i, match in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        body = text[match.end():end]
        require(body.strip(), 'Empty report: ' + match.group(1))
        reports[match.group(1)] = body
    return reports


def receipt_path(path):
    require(re.fullmatch(r'inbox/grok/[A-Za-z0-9][A-Za-z0-9._-]*\.md', path), 'Invalid inbox filename')
    return 'receipts/grok/' + PurePosixPath(path).stem + '.json'


class GitError(ValueError):
    pass


class GitStore:
    def __init__(self, directory, remote=REMOTE, branch='main'):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.branch = branch
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'user.name', 'Radar archive tool')
        self.git('config', 'user.email', 'radar-archive@users.noreply.github.com')
        self.git('remote', 'add', 'origin', remote)
        self.git('fetch', 'origin', branch)
        self.git('checkout', '-q', '-b', branch, 'FETCH_HEAD')

    def git(self, *args):
        env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
        token = env.get('RADAR_ARCHIVE_TOKEN')
        if token:
            count = int(env.get('GIT_CONFIG_COUNT', '0'))
            env.update({'GIT_CONFIG_COUNT': str(count + 1),
                        'GIT_CONFIG_KEY_' + str(count): 'http.https://github.com/.extraheader',
                        'GIT_CONFIG_VALUE_' + str(count): 'AUTHORIZATION: basic ' +
                            base64.b64encode(('x-access-token:' + token).encode()).decode()})
        result = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, timeout=120, env=env)
        if result.returncode:
            # Credential helpers can print secrets in stderr; do not echo it.
            raise GitError('Git operation failed: ' + args[0] + '; retry uses a fresh remote snapshot')
        return result.stdout

    def read(self, path):
        target = (self.root / path).resolve()
        require(target.is_relative_to(self.root.resolve()), 'Path outside archive')
        require(not (self.root / path).is_symlink(), 'Archive file must not be a symlink')
        return target.read_bytes() if target.is_file() else None

    def source(self, path):
        commit = self.git('log', '-1', '--format=%H', '--', path).decode().strip()
        require(re.fullmatch(r'[a-f0-9]{40}', commit), 'Missing submission commit')
        stamp = self.git('show', '-s', '--format=%cI', commit).decode().strip()
        return {'path': path, 'commit': commit, 'submitted_at_utc': iso(utc(stamp))}

    def commit(self, changes, message):
        for path, raw in changes.items():
            self.read(path)  # Validate the path before writing.
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        self.git('add', '--', *changes)
        if self.git('diff', '--cached', '--name-only').strip():
            self.git('commit', '-q', '-m', message)
            self.git('push', 'origin', 'HEAD:refs/heads/' + self.branch)
        commit = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('fetch', 'origin', self.branch)
        self.git('merge-base', '--is-ancestor', commit, 'FETCH_HEAD')
        for path, raw in changes.items():
            require(self.git('show', commit + ':' + path) == raw, 'Remote readback mismatch: ' + path)
        return commit


def read_json(store, path, default=None):
    raw = store.read(path)
    return json.loads(raw) if raw is not None else default


def archive_domains(manifest):
    domains = FORMAT_DOMAINS.get(manifest.get('archive_format'))
    require(domains is not None and set(manifest['reports']) == set(domains), 'Unknown archive format or report domains')
    return domains


def check_archived(store, manifest_ref):
    raw = store.read(manifest_ref['path'])
    require(raw is not None and digest(raw) == manifest_ref['sha256'], 'Archived manifest mismatch')
    manifest = json.loads(raw)
    domains = archive_domains(manifest)
    require(manifest['archive_status'] == 'verified', 'Archive is not complete')
    require(manifest['archive_repository'] == REPOSITORY, 'Wrong archive repository')
    base = 'reports/' + utc(manifest['submitted_at_utc']).astimezone(BJT).strftime('%Y/%m/%d/') + manifest['run_id']
    require(manifest_ref['path'] == base + '/run_manifest.json', 'Wrong immutable manifest path')
    for domain in domains:
        for kind in ('markdown', 'json'):
            ref = manifest['reports'][domain][kind]
            ext = 'md' if kind == 'markdown' else 'json'
            require(ref['path'] == base + '/' + domain + '.' + ext, 'Wrong report path')
            data = store.read(ref['path'])
            require(data is not None and digest(data) == ref['sha256'], 'Archived report mismatch: ' + ref['path'])
        content = read_json(store, manifest['reports'][domain]['json']['path'])
        require(content['schema_version'] == 'radar_text_report_v1' and content['domain'] == domain
                and content['archive_repository'] == REPOSITORY and content['run_id'] == manifest['run_id'],
                'JSON report identity mismatch')
        require(content['markdown'].encode('utf-8') == store.read(manifest['reports'][domain]['markdown']['path']),
                'JSON does not preserve the Markdown')
    return manifest


def order(record):
    # New entries are ordered by submission, not an invented research cutoff.
    stamp = record.get('submitted_at_utc') or record.get('started_at_utc')
    return utc(stamp), record['run_id']


def make_receipt(manifest, manifest_ref, source_hash):
    domains = archive_domains(manifest)
    return {'status': 'archived', 'archive_format': manifest['archive_format'], 'archive_repository': REPOSITORY, 'run_id': manifest['run_id'],
            'submission_sha256': source_hash, 'manifest': manifest_ref,
            'verification': 'six_report_files_read_back' if len(domains) == 3 else 'four_report_files_read_back',
            'research_quality': 'not_certified_by_archive_tool',
            'reports': {d: 'https://github.com/' + REPOSITORY + '/blob/main/' +
                        manifest['reports'][d]['markdown']['path'] for d in domains}}


def publish(store, path):
    receipt_name = receipt_path(path)
    raw = store.read(path)
    require(raw is not None, 'Submission not found')
    content_hash = digest(raw)
    before = read_json(store, 'manifests/runs.json',
                       {'schema_version': 'radar_runs_v2', 'archive_mode': 'production',
                        'archive_repository': REPOSITORY, 'runs': []})
    require(before.get('schema_version') in ('radar_runs_v1', 'radar_runs_v2') and
            before.get('archive_mode') == 'production' and before.get('archive_repository') == REPOSITORY
            and isinstance(before.get('runs'), list), 'Invalid run index')
    rows = before['runs']
    require(len({row['run_id'] for row in rows}) == len(rows), 'Duplicate run_id in existing index')
    withdrawn = read_json(store, 'manifests/withdrawn_runs.json', {'runs': []})
    withdrawn_ids = {row['run_id'] for row in withdrawn['runs']}
    require(not withdrawn_ids.intersection(row['run_id'] for row in rows), 'Withdrawn batch in success index')
    previous = read_json(store, receipt_name)
    if previous and previous.get('status') == 'archived':
        require(previous['submission_sha256'] == content_hash, 'Published inbox file changed; use a new filename')
        archived = check_archived(store, previous['manifest'])
        require(previous['run_id'] == archived['run_id'] and previous['archive_format'] == archived['archive_format']
                and previous['submission_sha256'] == archived['submission_sha256'], 'Receipt identity mismatch')
        parse_submission(raw, archive_domains(archived))
        require(any(row['run_id'] == previous['run_id'] and row['manifest'] == previous['manifest'] for row in rows),
                'Published receipt missing from run index')
        return previous
    # Archived v1 pairs are read-only above; every new submission needs all three.
    bodies = parse_submission(raw)
    for row in rows:
        if row.get('submission_sha256') == content_hash:
            manifest = check_archived(store, row['manifest'])
            receipt = make_receipt(manifest, row['manifest'], content_hash)
            store.commit({receipt_name: encode(receipt)}, 'Record identical Grok submission receipt')
            return receipt

    source = store.source(path)
    submitted = utc(source['submitted_at_utc'])
    require(submitted <= datetime.now(timezone.utc) + timedelta(minutes=5), 'Submission timestamp is in the future')
    run_id = submitted.astimezone(BJT).strftime('%Y%m%dT%H%M%S+0800_') + content_hash[:32]
    require(run_id not in withdrawn_ids, 'Withdrawn run_id cannot be republished')
    base = 'reports/' + submitted.astimezone(BJT).strftime('%Y/%m/%d/') + run_id
    manifest = {'archive_format': FORMAT, 'run_id': run_id, 'archive_mode': 'production',
                'archive_repository': REPOSITORY,
                'submitted_at_utc': source['submitted_at_utc'], 'source': source,
                'submission_sha256': content_hash, 'archive_status': 'prepared',
                'research_provenance': {'information_cutoff_utc': None, 'registry_commit': None,
                    'data_versions': None, 'note': 'Research dates and citations remain in the original Markdown; not inferred from upload time.'},
                'research_quality': 'not_certified_by_archive_tool', 'reports': {}}
    files = {}
    for domain, markdown in bodies.items():
        content = {'schema_version': 'radar_text_report_v1', 'domain': domain, 'run_id': run_id,
                   'archive_repository': REPOSITORY,
                   'submitted_at_utc': source['submitted_at_utc'], 'markdown': markdown,
                   'research_provenance': manifest['research_provenance']}
        files[domain + '.md'] = markdown.encode('utf-8')
        files[domain + '.json'] = encode(content)
        manifest['reports'][domain] = {kind: {'path': base + '/' + domain + '.' + ext,
            'sha256': digest(files[domain + '.' + ext])} for kind, ext in (('markdown', 'md'), ('json', 'json'))}
    stage = {base + '/' + name: data for name, data in files.items()}
    manifest_path = base + '/run_manifest.json'
    stage[manifest_path] = encode(manifest)
    for name, data in stage.items():
        existing = store.read(name)
        require(existing is None or existing == data, 'Immutable archive conflict: ' + name)
    store.commit(stage, 'Store Grok report bytes for archive readback')
    manifest.update(archive_status='verified', archived_at_utc=iso(datetime.now(timezone.utc)))
    manifest_raw = encode(manifest)
    manifest_ref = {'path': manifest_path, 'sha256': digest(manifest_raw)}
    entry = {key: manifest[key] for key in ('run_id', 'submitted_at_utc', 'archived_at_utc', 'submission_sha256')}
    entry.update(manifest=manifest_ref, batch_status='complete', archive_format=FORMAT)
    require(run_id not in {row['run_id'] for row in rows}, 'Conflicting run_id')
    index = {**before, 'schema_version': 'radar_runs_v2', 'runs': [*rows, entry]}
    latest = read_json(store, 'latest/run.json')
    if latest:
        require(any(row['run_id'] == latest['run_id'] and row['manifest'] == latest['manifest'] for row in rows),
                'Latest and index disagree; preserve them for repair')
    promote = all(order(entry) >= order(row) for row in rows)
    if latest:
        promote = promote and order(entry) >= order(latest)
    receipt = make_receipt(manifest, manifest_ref, content_hash)
    receipt['latest_promoted'] = promote
    changes = {manifest_path: manifest_raw, 'manifests/runs.json': encode(index), receipt_name: encode(receipt)}
    if promote:
        pointer = {'schema_version': 'radar_latest_v2', 'archive_mode': 'production',
                   'archive_repository': REPOSITORY,
                   'run_id': run_id, 'submitted_at_utc': source['submitted_at_utc'], 'manifest': manifest_ref,
                   'reports': {d: {kind: {**ref, 'path': 'latest/' + PurePosixPath(ref['path']).name}
                                  for kind, ref in refs.items()} for d, refs in manifest['reports'].items()}}
        changes.update({'latest/' + name: data for name, data in files.items()})
        changes['latest/run.json'] = encode(pointer)
        changes['status/on_demand_latest.json'] = encode({'status': 'archived', 'run_id': run_id,
            'archive_repository': REPOSITORY, 'archive_format': FORMAT,
            'research_quality': 'not_certified_by_archive_tool'})
    store.commit(changes, 'Publish verified Grok batch and preserve archive history')
    return receipt


def audit_archive(directory, legacy_checker):
    """Check the mixed archive; the preserved validator audits structured history."""
    store = object.__new__(GitStore)
    store.root = Path(directory).resolve()
    index = read_json(store, 'manifests/runs.json')
    require(index is not None and index['schema_version'] == 'radar_runs_v2'
            and index['archive_repository'] == REPOSITORY and index['archive_mode'] == 'production', 'Invalid text run index')
    rows = index['runs']
    require(len({r['run_id'] for r in rows}) == len(rows), 'Duplicate success index ID')
    withdrawn = read_json(store, 'manifests/withdrawn_runs.json', {'runs': []})['runs']
    require(not ({r['run_id'] for r in rows} & {r['run_id'] for r in withdrawn}), 'Withdrawn batch in success index')
    legacy, manifests = [], {}
    for row in rows:
        if row.get('archive_format') in FORMAT_DOMAINS:
            manifest = check_archived(store, row['manifest'])
            require(row['archive_format'] == manifest['archive_format'], 'Index format mismatch')
            require(row['batch_status'] == 'complete', 'Incomplete text batch')
            for key in ('run_id', 'submitted_at_utc', 'archived_at_utc', 'submission_sha256'):
                require(row[key] == manifest[key], 'Index identity mismatch: ' + key)
            submission = store.read(manifest['source']['path'])
            require(submission is not None and digest(submission) == manifest['submission_sha256'], 'Submission changed or missing')
            bodies = parse_submission(submission, archive_domains(manifest))
            for domain, body in bodies.items():
                require(body.encode('utf-8') == store.read(manifest['reports'][domain]['markdown']['path']),
                        'Archived prose differs from submission')
            receipt = read_json(store, receipt_path(manifest['source']['path']))
            expected_receipt = make_receipt(manifest, row['manifest'], row['submission_sha256'])
            require(receipt is not None and all(receipt.get(key) == value for key, value in expected_receipt.items()),
                    'Missing or inconsistent archive receipt')
        else:
            require('archive_format' not in row, 'Unknown archive format')
            legacy.append(row)
            manifest = read_json(store, row['manifest']['path'])
        manifests[row['run_id']] = manifest
    legacy_checker({**index, 'schema_version': 'radar_runs_v1', 'runs': legacy})
    latest = read_json(store, 'latest/run.json')
    if rows:
        newest = max(rows, key=order)
        manifest = manifests[newest['run_id']]
        domains = archive_domains(manifest) if 'archive_format' in manifest else ('global', 'commodities')
        require(latest is not None and latest['run_id'] == newest['run_id'] and latest['manifest'] == newest['manifest']
                and latest['archive_repository'] == REPOSITORY and set(latest['reports']) == set(domains), 'Latest and index disagree')
        for domain in domains:
            for kind, ext in (('markdown', 'md'), ('json', 'json')):
                ref = latest['reports'][domain][kind]
                original = manifest['reports'][domain][kind]
                require(ref['path'] == 'latest/' + domain + '.' + ext and ref['sha256'] == original['sha256'], 'Latest reference mismatch')
                data = store.read(ref['path'])
                require(data is not None and digest(data) == ref['sha256'], 'Latest byte mismatch')
    else:
        require(latest is None and all(store.read('latest/' + d + '.' + ext) is None for d in DOMAINS for ext in ('md', 'json')),
                'Empty index must not advertise latest')
    return {'status': 'passed', 'text_batches': len(rows) - len(legacy), 'legacy_batches': len(legacy),
            'withdrawn_batches': len(withdrawn), 'research_quality': 'not_certified_by_archive_tool'}


def process_inbox(store):
    paths = store.git('ls-files', 'inbox/grok/*.md').decode('utf-8').splitlines()
    errors, receipts = [], []
    # Scan all pending files so a superseded queued workflow cannot lose a submission.
    for path in sorted(paths, key=lambda p: (store.source(p)['submitted_at_utc'], p)):
        try:
            receipts.append(publish(store, path))
        except GitError:
            raise
        except (ValueError, KeyError, UnicodeError) as exc:
            failure = {'status': 'failed', 'submission': path, 'error': str(exc)}
            errors.append(failure)
            try:
                target = receipt_path(path)
            except ValueError:
                continue  # An invalid filename must not starve other submissions.
            store.commit({target: encode(failure)}, 'Record Grok submission failure without publishing reports')
    return {'receipts': receipts, 'errors': errors}


def smoke_test():
    """Exercise actual Git writes/readback against a disposable local bare remote."""
    with tempfile.TemporaryDirectory(prefix='radar-archive-test-') as directory:
        root = Path(directory).resolve()
        require(root.is_relative_to(Path(tempfile.gettempdir()).resolve()), 'Unexpected temporary test path')
        remote, seed = root / 'remote.git', root / 'seed'
        def git(*args):
            subprocess.run(['git', *map(str, args)], check=True, capture_output=True)
        git('init', '--bare', remote)
        git('init', '-b', 'main', seed)
        git('-C', seed, 'config', 'user.name', 'Archive synthetic test')
        git('-C', seed, 'config', 'user.email', 'test@example.invalid')
        source = seed / 'inbox/grok/synthetic.md'
        source.parent.mkdir(parents=True)
        source.write_bytes(''.join('<!-- radar:' + d + ' -->\n# Synthetic ' + d + '\nOffline test only.\n'
                                  for d in DOMAINS).encode())
        git('-C', seed, 'add', '--', 'inbox/grok/synthetic.md')
        git('-C', seed, 'commit', '-m', 'Synthetic inbox only')
        git('-C', seed, 'remote', 'add', 'origin', remote)
        git('-C', seed, 'push', 'origin', 'main')
        store = GitStore(root / 'publisher', str(remote))
        first = process_inbox(store)
        require(not first['errors'], 'Synthetic publication failed')
        require(first['receipts'][0]['verification'] == 'six_report_files_read_back', 'Incomplete three-report receipt')
        again = GitStore(root / 'retry', str(remote))
        second = process_inbox(again)
        require(first == second, 'Retry changed the receipt')
        require(len(read_json(again, 'manifests/runs.json')['runs']) == 1, 'Retry duplicated batch')
        pointer = read_json(again, 'latest/run.json')
        require(set(pointer['reports']) == set(DOMAINS), 'Missing latest report')
        for refs in pointer['reports'].values():
            for ref in refs.values():
                require(digest(again.read(ref['path'])) == ref['sha256'], 'Latest readback mismatch')
    return {'test': 'passed', 'scope': 'disposable_local_git_remote', 'production_reports_written': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', type=Path, help='Parse a submission locally, without publishing')
    parser.add_argument('--publish-inbox', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(smoke_test()))
        return 0
    if args.check:
        reports = parse_submission(args.check.read_bytes())
        print(json.dumps({'valid': True, 'characters': {d: len(t) for d, t in reports.items()}}, ensure_ascii=False))
        return 0
    require(args.publish_inbox, 'Choose --check FILE or --publish-inbox')
    for attempt in range(3):
        try:
            with tempfile.TemporaryDirectory(prefix='radar-publish-') as directory:
                require(Path(directory).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()),
                        'Unexpected temporary publisher path')
                result = process_inbox(GitStore(directory))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result['errors'] else 0
        except GitError:
            if attempt == 2:
                raise


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        raise SystemExit('Archive failed: ' + str(exc))
