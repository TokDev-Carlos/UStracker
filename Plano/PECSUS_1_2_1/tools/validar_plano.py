"""Validação documental read-only; exit 0 não significa homologação do produto."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from gerar_derivados import COMPLETE_SOURCES, REVISION, complete_text, linear_text


def read_json(path: Path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"JSON com chave duplicada {key}: {path.name}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)


def rows(root: Path, name: str):
    with (root / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def validate(root: Path) -> dict:
    errors = []
    def check(condition: bool, description: str) -> None:
        if not condition:
            errors.append(description)
    for path in root.rglob("*"):
        check(not path.is_symlink(), f"Symlink proibido: {path}")
        if path.is_file() and path.suffix == '.json':
            read_json(path)
        if path.is_file() and path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    tasks = read_json(root / 'TAREFAS.json')
    cases = read_json(root / 'CASOS_ACEITE.json')
    reqs = rows(root, 'MATRIZ_REQUISITOS.csv')
    history = rows(root, 'MATRIZ_ESCOPO_HISTORICO.csv')
    tid = {x['id'] for x in tasks}
    cid = {x['id'] for x in cases}
    rid = {x['requisito'] for x in reqs}
    hid = {x['id'] for x in history}
    check(len(tid) == len(tasks) == 18, 'Tarefas duplicadas ou total divergente')
    check(len(cid) == len(cases), 'IDs de caso duplicados')
    check(rid == {f'R{i:02d}' for i in range(1, 37)} and len(reqs) == 36, 'Requisitos divergentes')
    check(hid == {f'H{i:03d}' for i in range(1, 251)} and len(history) == 250, 'Histórico divergente')
    tmap = {t['id']: t for t in tasks}
    cmap = {c['id']: c for c in cases}
    check([t['id'] for t in tasks] == [f'T{i:02d}' for i in range(1, 19)], 'Ordem de tarefas divergente')
    for i, task in enumerate(tasks):
        name = task['id']
        expected = [] if i == 0 else [tasks[i - 1]['id']]
        check(task['depends_on'] == expected, f'{name}: dependência não linear/circular')
        check(set(task['requirements']) <= rid, f'{name}: requisito inexistente')
        owned = {c['id'] for c in cases if c['task'] == name}
        check(set(task['acceptance_cases']) == owned and len(task['acceptance_cases']) == len(owned), f'{name}: ownership de casos divergente')
        check(bool(task['files']) and bool(task['steps']) and bool(task['interfaces']), f'{name}: tarefa vazia')
        check(task['status'] == 'NAO_EXECUTADO', f'{name}: catálogo não é evidência')
        for step in task['steps']:
            check(not re.search(r'\b(TBD|TODO)\b', step), f'{name}: placeholder')
    for case in cases:
        check(case['task'] in tid and case['id'].startswith(case['task'] + '-C'), f"{case['id']}: task inválida")
        check(bool(case['input']) and bool(case['expected']), f"{case['id']}: caso vazio")
        check(case['status'] == 'NAO_EXECUTADO' and case['evidence'] == [], f"{case['id']}: catálogo misturado com resultados")
        check(isinstance(case['required'], bool), f"{case['id']}: required não booleano")
    check({c['id'] for c in cases if not c['required']} == {'T01-C05'}, 'Perfil de compatibilidade alterado')
    for task_id in ('T01', 'T16', 'T18'):
        check(tmap[task_id]['required_profile'] == 'win10_22h2', f'{task_id}: homologação deve usar Windows10')
    check(cmap['T01-C05'].get('profile') == 'windows11', 'Ensaio adicional deve usar Windows11')
    check('Windows 10 22H2' in cmap['T18-C06']['input'], 'T18 sem base Windows10')
    for req in reqs:
        expected = {t['id'] for t in tasks if req['requisito'] in t['requirements']}
        linked = set(filter(None, req['tarefas'].split('|')))
        check(linked == expected and bool(linked), f"{req['requisito']}: ownership de requisito divergente")
        expected_cases = {c for t in tasks if t['id'] in expected for c in t['acceptance_cases']}
        check(set(req['casos'].split('|')) == expected_cases, f"{req['requisito']}: casos divergentes")
    decisions = {'MANTER', 'SUBSTITUIR', 'RESOLVIDO', 'ADICIONAR', 'ADIAR', 'EXCLUIR'}
    for row in history:
        ts = set(filter(None, row['tasks'].split('|')))
        cs = set(filter(None, row['cases'].split('|')))
        check(row['decision'] in decisions, f"{row['id']}: decisão inválida")
        check(ts <= tid and cs <= cid, f"{row['id']}: referência inexistente")
        check(all(cmap[c]['task'] in ts for c in cs if c in cmap), f"{row['id']}: caso fora das tarefas associadas")
        if row['decision'] in {'ADIAR', 'EXCLUIR'}:
            check(bool(row['reason']) and bool(row['target_version']), f"{row['id']}: decisão sem motivo/versão")
        else:
            check(bool(ts) and bool(cs) and bool(row['canonical_resolution']), f"{row['id']}: item descoberto")
    spec = (root / '01_ESPECIFICACAO.md').read_text(encoding='utf-8')
    contract = (root / '02_CONTRATOS.md').read_text(encoding='utf-8')
    check(set(re.findall(r'\*\*(R\d{2}):\*\*', spec)) == rid, 'Especificação diverge de requisitos')
    for block in re.findall(r'```python\n(.*?)```', contract, re.S):
        ast.parse(block)
    required_tokens = ['uint32_be(total_chunks)', 'AuthStore não é revertido', 'credit_allocation_reversals',
                       'recurrence_id', 'financial_dimensions', 'VOID', 'ProcessStartInfo', 'UseShellExecute=false',
                       'nonce_prefix8', 'source_signature', 'WAITING', 'If-Match', 'shell_id']
    for token in required_tokens:
        check(token in contract, f'Contrato ausente: {token}')
    check('QUIESCED' in tmap['T15']['steps'][2] and 'então criar' in tmap['T15']['steps'][2], 'T15: freeze/backup desalinhado')
    check('uint32_be(total_chunks)' in tmap['T14']['steps'][0], 'T14: AAD desalinhado')
    check('T04' not in tmap['T03']['depends_on'], 'Ciclo Vault/T03')
    check('ProcessStartInfo.ArgumentList' not in json.dumps(tasks), 'Tarefa usa API .NET incompatível')
    check('net10.0-windows' not in json.dumps(tasks), 'Host target residual')
    check((root / '03_EXECUCAO_LINEAR.md').read_text(encoding='utf-8') == linear_text(root), 'Linear diverge de TAREFAS.json')
    check((root / 'PECSUS_COMPLETO_1_2_1.txt').read_text(encoding='utf-8') == complete_text(root), 'TXT agregado diverge das fontes')
    checkpoint = read_json(root / 'PONTO_DE_PARADA.json')
    check(checkpoint['plan_revision'] == REVISION and checkpoint['next_task'] == 'T01', 'Checkpoint inicial divergente')
    check(checkpoint['product_cases_status'] == 'NAO_EXECUTADO', 'Checkpoint afirma produto testado')
    manifest = read_json(root / 'MANIFESTO_SHA256.json')
    check(manifest['plan_revision'] == REVISION, 'Revisão de manifesto divergente')
    paths = [f['path'] for f in manifest['files']]
    check(len(paths) == len(set(paths)), 'Manifesto com path duplicado')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != root / 'MANIFESTO_SHA256.json'}
    check(actual == set(paths), 'Cobertura do manifesto divergente: arquivos faltantes/extras')
    for item in manifest['files']:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            errors.append('Path inseguro no manifesto')
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f'Arquivo ausente: {relative}')
            continue
        check(path.resolve().is_relative_to(root), f'Path fora de root: {relative}')
        data = path.read_bytes()
        check(len(data) == item['size'] and hashlib.sha256(data).hexdigest() == item['sha256'], f'Hash/tamanho divergente: {relative}')
    return {'ok': not errors, 'scope': 'DOCUMENTAL_ONLY', 'plan_revision': REVISION,
            'counts': {'requirements': len(reqs), 'tasks': len(tasks), 'cases': len(cases),
                       'required_cases': sum(c['required'] for c in cases), 'historical': len(history), 'manifest_files': len(paths)},
            'errors': errors, 'product_tests_executed': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = validate(args.root.resolve())
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as exc:
        result = {'ok': False, 'scope': 'DOCUMENTAL_ONLY', 'errors': [f'{type(exc).__name__}: {exc}'], 'product_tests_executed': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
