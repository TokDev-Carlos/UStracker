"""Regenera visualizações e manifesto após revisão documental intencional."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REVISION = "PECSUS-1.2.1"
COMPLETE_SOURCES = [
    "00_LEIA_PRIMEIRO.md", "01_ESPECIFICACAO.md", "02_CONTRATOS.md",
    "03_EXECUCAO_LINEAR.md", "04_VERIFICACAO_E_ENTREGA.md",
    "05_OPERACAO_E_CONTINUIDADE.md", "FONTES_E_DECISOES.md",
    "MATRIZ_REQUISITOS.csv", "MATRIZ_ESCOPO_HISTORICO.csv", "CASOS_ACEITE.json",
    "PONTO_DE_PARADA.json", "SCRIPT_MESTRE_EXECUCAO_IA.txt",
]


def linear_text(root: Path) -> str:
    tasks = json.loads((root / "TAREFAS.json").read_text(encoding="utf-8"))
    parts = [
        "# UStracker V1 Implementation Plan — PECSUS 1.2.1\n",
        "> IA executora: usar fluxo disciplinado por tarefa; executar inline. Se Superpowers estiver disponível, usar executing-plans. Este arquivo é gerado de TAREFAS.json; não editar diretamente.\n",
        "**Goal:** criar e homologar UStracker 1.00.00.000 com evidência real.\n",
        "**Architecture:** monólito modular local Python/FastAPI/SQLCipher; Host WPF net48/WebView2; PUBLIC separado; uma escritora participante por dataset.\n",
        "**Tech Stack:** CPython 3.13.15 x64 embeddable, sqlcipher3 0.6.2, WPF .NET Framework 4.8 x64, Microsoft.Web.WebView2 1.0.4191.47, HTML/CSS/ES modules locais.\n",
        "**Spec:** 01_ESPECIFICACAO.md + 02_CONTRATOS.md + MATRIZ_ESCOPO_HISTORICO.csv.\n",
        "## Global Constraints\n",
        "Windows10 formal; Win11 compatibilidade adicional. Gates obrigatórios não são pulados. T01 antecede T02. PUBLIC nunca recebe dados privados. Dinheiro int cents/Decimal. Integrações futuras desativadas. Não executar scripts legados. Plano original imutável; Estado/ e Evidence/ pertencem à engenharia.\n",
    ]
    for task in tasks:
        parts.extend([
            f"\n---\n\n### {task['id']}: {task['title']}\n",
            f"**Depends on:** {', '.join(task['depends_on'] or task['prerequisites'])}\n",
            f"**Requirements:** {', '.join(task['requirements'])}\n",
            f"**Goal:** {task['objective']}\n",
            "**Files:**\n" + "\n".join(f"- Create/modify: `{p}`" for p in task['files']) + "\n",
            f"**Interfaces:** {task['interfaces']}\n",
        ])
        parts.extend(f"- [ ] **Step {i}:** {s}\n" for i, s in enumerate(task['steps'], 1))
        native = " --native --profile win10_22h2" if task['required_profile'] == 'win10_22h2' else ""
        parts.extend([
            f"\n**Acceptance cases:** {', '.join(task['acceptance_cases'])}\n",
            f"**Gate proof:** {task['proof']}\n",
            "**Required command pattern:**\n```powershell\n"
            f"& .\\.venv\\Scripts\\python.exe tools\\verify.py --task {task['id']}{native} --evidence-dir Evidence\n"
            f"if ($LASTEXITCODE -ne 0) {{ throw '{task['id']} gate failed' }}\n```\n",
            "**Checkpoint:** atualizar Estado/PONTO_DE_PARADA.json e Evidence/ na engenharia, mantendo semente e catálogo do plano imutáveis. Invalidar evidências afetadas por mudança; só avançar com casos obrigatórios PASS.\n",
        ])
    return "\n".join(parts)


def complete_text(root: Path) -> str:
    parts = ["PECSUS COMPLETO 1.2.1 — LEITURA AGREGADA, GERADA; FONTES CANÔNICAS NO PACOTE\n"]
    for name in COMPLETE_SOURCES:
        parts.append(f"\n{'=' * 72}\nARQUIVO: {name}\n{'=' * 72}\n")
        parts.append((root / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def manifest(root: Path) -> dict:
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink proibido: {path}")
        if not path.is_file() or path.name == "MANIFESTO_SHA256.json":
            continue
        data = path.read_bytes()
        entries.append({"path": path.relative_to(root).as_posix(), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return {"format": 2, "product": "UStracker", "plan_revision": REVISION,
            "scope": "Todos os arquivos do pacote, exceto este manifesto; evidência do produto fica fora desta raiz.", "files": entries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    (root / "03_EXECUCAO_LINEAR.md").write_text(linear_text(root), encoding="utf-8")
    (root / "PECSUS_COMPLETO_1_2_1.txt").write_text(complete_text(root), encoding="utf-8")
    (root / "MANIFESTO_SHA256.json").write_text(json.dumps(manifest(root), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Derivados e manifesto regenerados. Execute validar_plano.py. Isso não aprova casos do produto.")


if __name__ == "__main__":
    main()
