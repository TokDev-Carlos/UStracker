from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


class GuardError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except FileNotFoundError as exc:
        raise GuardError(f'Arquivo ausente: {path}') from exc
    except json.JSONDecodeError as exc:
        raise GuardError(f'JSON invalido: {path}: {exc}') from exc


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def normalize_increment_id(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    normalized = re.sub(r'[^A-Za-z0-9]+', '-', normalized).strip('-').lower()
    if not normalized:
        raise ValueError('Identificador de incremento vazio ou inseguro')
    return normalized


def _matches(path: str, patterns: Iterable[str]) -> bool:
    path = path.replace('\\', '/')
    return any(fnmatch.fnmatchcase(path, p.replace('\\', '/')) for p in patterns)


def check_diff_policy(changed_paths: list[str], policy: dict, changeset: dict) -> list[str]:
    violations: list[str] = []
    forbidden = policy.get('always_forbidden', [])
    globally_allowed = policy.get('always_allowed', [])
    scoped_allowed = changeset.get('allowed_paths', [])
    sensitive_allow = changeset.get('explicitly_allowed_sensitive_paths', [])

    for raw in changed_paths:
        path = raw.replace('\\', '/')
        is_forbidden = _matches(path, forbidden)
        is_sensitive_override = _matches(path, sensitive_allow)
        if is_forbidden and not is_sensitive_override:
            violations.append(f'forbidden:{path}')
            continue
        if _matches(path, globally_allowed) or _matches(path, scoped_allowed):
            continue
        violations.append(f'out-of-scope:{path}')
    return violations


def validate_schema_progress(schema_from: int, schema_to: int) -> list[str]:
    errors: list[str] = []
    if schema_to < schema_from:
        errors.append(f'schema-regression:{schema_from}->{schema_to}')
    if schema_to > schema_from + 1:
        errors.append(f'schema-skip:{schema_from}->{schema_to}')
    return errors


def snapshot_files(root: Path, excludes: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(p for p in root.rglob('*') if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if _matches(rel, excludes):
            continue
        result[rel] = sha256_file(path)
    return result


def verify_snapshot(root: Path, snapshot: dict[str, str], excludes: list[str]) -> dict[str, list[str]]:
    current = snapshot_files(root, excludes)
    expected_keys = set(snapshot)
    current_keys = set(current)
    return {
        'changed': sorted(k for k in expected_keys & current_keys if snapshot[k] != current[k]),
        'missing': sorted(expected_keys - current_keys),
        'unexpected': sorted(current_keys - expected_keys),
    }



SENSITIVE_TRACKED_PATTERNS = [
    'UserData/**', '*.db', '*.sqlite', '*.sqlite3', '.env', '.env.*', '*.pfx', '*.p12', '*.key',
    '**/*.pfx', '**/*.p12', '**/*.key'
]

PRIVATE_KEY_MARKERS = (
    b'-----BEGIN PRIVATE KEY-----',
    b'-----BEGIN RSA PRIVATE KEY-----',
    b'-----BEGIN EC PRIVATE KEY-----',
    b'-----BEGIN OPENSSH PRIVATE KEY-----',
)


def detect_forbidden_tracked_paths(paths: Iterable[str]) -> list[str]:
    findings: list[str] = []
    for raw in paths:
        path = raw.replace('\\', '/')
        if _matches(path, SENSITIVE_TRACKED_PATTERNS):
            findings.append(path)
    return sorted(set(findings))


def contains_private_key_marker(data: bytes) -> bool:
    stripped = data.lstrip()
    return any(stripped.startswith(marker) for marker in PRIVATE_KEY_MARKERS)


def scan_tracked_private_keys(repo: Path, paths: Iterable[str]) -> list[str]:
    findings: list[str] = []
    for raw in paths:
        path = raw.replace('\\', '/')
        full = repo / path
        if not full.is_file():
            continue
        try:
            if full.stat().st_size > 5 * 1024 * 1024:
                continue
            data = full.read_bytes()
        except OSError:
            continue
        if contains_private_key_marker(data):
            findings.append(path)
    return findings


def validate_changeset(data: dict) -> list[str]:
    errors: list[str] = []
    required = {
        'id': str,
        'baseline_version': str,
        'schema_from': int,
        'schema_to': int,
        'status': str,
        'user_approved_execution': bool,
        'allowed_paths': list,
        'explicitly_allowed_sensitive_paths': list,
        'acceptance_checks': list,
    }
    for key, typ in required.items():
        if key not in data:
            errors.append(f'missing:{key}')
        elif not isinstance(data[key], typ):
            errors.append(f'type:{key}:{typ.__name__}')
    if errors:
        return errors
    errors.extend(validate_schema_progress(data['schema_from'], data['schema_to']))
    if data['status'] not in {'PREPARED', 'APPROVED', 'IN_PROGRESS', 'VERIFIED', 'REJECTED'}:
        errors.append(f'invalid-status:{data["status"]}')
    if not data['allowed_paths']:
        errors.append('empty:allowed_paths')
    if not data['acceptance_checks']:
        errors.append('empty:acceptance_checks')
    return errors


def run_git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ['git', *args], cwd=repo, text=True, capture_output=True, encoding='utf-8', errors='replace'
    )
    if check and proc.returncode != 0:
        raise GuardError(f'git {" ".join(args)} falhou: {proc.stderr.strip()}')
    return proc.stdout.strip()


def repo_root(start: Path) -> Path:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'], cwd=start, text=True, capture_output=True,
        encoding='utf-8', errors='replace'
    )
    if proc.returncode != 0:
        raise GuardError('Diretorio nao esta em um repositorio Git')
    return Path(proc.stdout.strip()).resolve()


def changed_files(repo: Path, base_ref: str) -> list[str]:
    out = run_git(repo, 'diff', '--name-only', base_ref, '--')
    return [line.strip() for line in out.splitlines() if line.strip()]


def git_show_bytes(repo: Path, ref: str, path: str) -> bytes:
    proc = subprocess.run(['git', 'show', f'{ref}:{path}'], cwd=repo, capture_output=True)
    if proc.returncode != 0:
        raise GuardError(f'Nao foi possivel ler {path} em {ref}')
    return proc.stdout


def snapshot_git_ref(repo: Path, ref: str, excludes: list[str]) -> dict[str, str]:
    out = run_git(repo, 'ls-tree', '-r', '--name-only', ref)
    result: dict[str, str] = {}
    for path in sorted(line.strip() for line in out.splitlines() if line.strip()):
        if _matches(path, excludes):
            continue
        result[path] = sha256_bytes(git_show_bytes(repo, ref, path))
    return result


def ensure_not_install_root(repo: Path, install_root: str) -> list[str]:
    if not install_root:
        return []
    try:
        install = Path(install_root).resolve()
        if os.name == 'nt':
            if str(repo).casefold() == str(install).casefold():
                return ['workspace-is-active-install-root']
        elif repo == install:
            return ['workspace-is-active-install-root']
    except OSError:
        pass
    return []


def preflight(repo: Path, config: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(ensure_not_install_root(repo, config.get('active_install_root', '')))

    version = load_json(repo / 'VERSION.json')
    metadata = load_json(repo / 'HANDOFF_METADATA.json')
    if version.get('product') != config['product']:
        errors.append(f'product:{version.get("product")}')
    if version.get('version') != config['baseline_version']:
        errors.append(f'version:{version.get("version")}')
    if version.get('schema_version') != config['baseline_schema_version']:
        warnings.append(
            f'working-schema:{version.get("schema_version")} (baseline {config["baseline_schema_version"]})'
        )
    if metadata.get('baseline_version') != config['baseline_version']:
        errors.append('metadata-baseline-version-mismatch')
    if metadata.get('baseline_schema_version') != config['baseline_schema_version']:
        errors.append('metadata-baseline-schema-mismatch')
    if metadata.get('planned_schema_version') != config['planned_schema_version']:
        errors.append('metadata-planned-schema-mismatch')

    baseline_commit = run_git(repo, 'rev-parse', f'{config["baseline_tag"]}^{{}}')
    if baseline_commit != config['baseline_commit']:
        errors.append(f'baseline-tag-moved:{baseline_commit}')

    plan_path = repo / config['plan_path']
    plan_sha = sha256_file(plan_path)
    expected_plan_sha = metadata.get('included_plan_sha256', '').upper()
    if expected_plan_sha and plan_sha != expected_plan_sha:
        errors.append(f'plan-hash:{plan_sha}')

    expected_snapshot = load_json(repo / config['baseline_snapshot_path'])
    actual_snapshot = snapshot_git_ref(repo, config['baseline_tag'], config.get('snapshot_excludes', []))
    if expected_snapshot.get('files') != actual_snapshot:
        errors.append('baseline-snapshot-does-not-match-tag')

    tracked = [line for line in run_git(repo, 'ls-files').splitlines() if line]
    forbidden_tracked = detect_forbidden_tracked_paths(tracked)
    if forbidden_tracked:
        errors.extend(f'tracked-sensitive:{p}' for p in forbidden_tracked)
    private_keys = scan_tracked_private_keys(repo, tracked)
    if private_keys:
        errors.extend(f'tracked-private-key:{p}' for p in private_keys)

    status = run_git(repo, 'status', '--porcelain')
    if status:
        warnings.append('working-tree-has-uncommitted-changes')

    return {
        'status': 'PASS' if not errors else 'FAIL',
        'checked_at': utc_now(),
        'repo': str(repo),
        'head': run_git(repo, 'rev-parse', 'HEAD'),
        'branch': run_git(repo, 'branch', '--show-current'),
        'baseline_commit': baseline_commit,
        'errors': errors,
        'warnings': warnings,
    }


def create_checkpoint(repo: Path, config: dict, label: str, changeset_path: Path | None) -> dict:
    changeset = load_json(changeset_path) if changeset_path else None
    base_ref = changeset.get('base_commit') if changeset else config['engineering_base_commit']
    diff = changed_files(repo, base_ref)
    payload = {
        'label': label,
        'created_at': utc_now(),
        'head': run_git(repo, 'rev-parse', 'HEAD'),
        'branch': run_git(repo, 'branch', '--show-current'),
        'base_ref': base_ref,
        'changed_files': diff,
        'working_tree_status': run_git(repo, 'status', '--porcelain').splitlines(),
        'changeset_id': changeset.get('id') if changeset else None,
    }
    return payload


def candidate_gate(repo: Path, config: dict, policy: dict, changeset: dict, approval: dict) -> dict:
    errors = validate_changeset(changeset)
    if not approval.get('user_approved_execution', False):
        errors.append('execution-not-approved-by-user')
    if approval.get('approved_changeset_id') not in {None, changeset.get('id')}:
        errors.append('approval-changeset-mismatch')
    if changeset.get('status') != 'VERIFIED':
        errors.append(f'changeset-not-verified:{changeset.get("status")}')
    base = changeset.get('base_commit')
    if not base:
        errors.append('missing:base_commit')
        diff: list[str] = []
    else:
        diff = changed_files(repo, base)
        errors.extend(check_diff_policy(diff, policy, changeset))
    return {
        'status': 'PASS' if not errors else 'FAIL',
        'checked_at': utc_now(),
        'changeset_id': changeset.get('id'),
        'changed_files': diff,
        'errors': errors,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='UStracker engineering guardrails')
    p.add_argument('--repo', default='.', help='Repositorio UStracker')
    sub = p.add_subparsers(dest='command', required=True)

    pf = sub.add_parser('preflight')
    pf.add_argument('--config', default='engineering/config/project.json')
    pf.add_argument('--output')

    pol = sub.add_parser('policy')
    pol.add_argument('--config', default='engineering/config/project.json')
    pol.add_argument('--policy', default='engineering/config/path-policy.json')
    pol.add_argument('--changeset', required=True)
    pol.add_argument('--output')

    cp = sub.add_parser('checkpoint')
    cp.add_argument('--config', default='engineering/config/project.json')
    cp.add_argument('--label', required=True)
    cp.add_argument('--changeset')
    cp.add_argument('--output', required=True)

    cg = sub.add_parser('candidate-gate')
    cg.add_argument('--config', default='engineering/config/project.json')
    cg.add_argument('--policy', default='engineering/config/path-policy.json')
    cg.add_argument('--changeset', required=True)
    cg.add_argument('--approval', default='engineering/APPROVAL.json')
    cg.add_argument('--output')

    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo = repo_root(Path(args.repo).resolve())
    try:
        if args.command == 'preflight':
            config = load_json(repo / args.config)
            result = preflight(repo, config)
        elif args.command == 'policy':
            config = load_json(repo / args.config)
            policy = load_json(repo / args.policy)
            changeset = load_json(repo / args.changeset)
            errors = validate_changeset(changeset)
            base = changeset.get('base_commit') or config['engineering_base_commit']
            paths = changed_files(repo, base)
            errors.extend(check_diff_policy(paths, policy, changeset))
            result = {
                'status': 'PASS' if not errors else 'FAIL',
                'checked_at': utc_now(),
                'base_ref': base,
                'changed_files': paths,
                'errors': errors,
            }
        elif args.command == 'checkpoint':
            config = load_json(repo / args.config)
            cs = repo / args.changeset if args.changeset else None
            result = create_checkpoint(repo, config, args.label, cs)
        elif args.command == 'candidate-gate':
            config = load_json(repo / args.config)
            policy = load_json(repo / args.policy)
            changeset = load_json(repo / args.changeset)
            approval = load_json(repo / args.approval)
            result = candidate_gate(repo, config, policy, changeset, approval)
        else:
            raise GuardError(f'Comando desconhecido: {args.command}')
    except (GuardError, ValueError, KeyError) as exc:
        result = {'status': 'FAIL', 'checked_at': utc_now(), 'errors': [str(exc)]}

    output = getattr(args, 'output', None)
    if output:
        write_json(repo / output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('status') == 'PASS' or args.command == 'checkpoint' else 2


if __name__ == '__main__':
    raise SystemExit(main())
