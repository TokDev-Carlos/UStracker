#!/bin/bash
# UStracker — gera o instalador Windows a partir do instalador anterior (Runtime, .NET, WebView2) + o código deste repositório.
# Uso: tools/build_installer.sh <instalador_anterior.exe> <pasta_de_trabalho>   (precisa de 7z e makensis no PATH ou em Z7/MAKENSIS)
# Saída: <pasta>/UStracker_install_x64.exe + .sha256. Para se faltar qualquer arquivo do programa anterior.
set -euo pipefail
PREV="$1"; WORK="$2"; REPO="$(cd "$(dirname "$0")/.." && pwd)"
Z7="${Z7:-7z}"; MAKENSIS="${MAKENSIS:-makensis}"
VERSION="$(tr -d '[:space:]' < "$REPO/version.md")"
rm -rf "$WORK/x" "$WORK/src"; mkdir -p "$WORK/x" "$WORK/src"
"$Z7" x -y -bd -o"$WORK/x" "$PREV" >/dev/null
# 1) base = programa anterior (sem o código do UStracker, telas e documentos)
(cd "$WORK/x" && cp -a $(ls -A | grep -v '^\$PLUGINSDIR$') "$WORK/src/")
rm -rf "$WORK/src/Runtime/Lib/site-packages/ustracker" "$WORK/src/frontend" "$WORK/src/Docs"
find "$WORK/src" -name __pycache__ -prune -exec rm -rf {} +
# 2) código novo por cima (MESCLA: nunca apaga Runtime)
PYTHONPATH="$REPO/src:${PYTHONPATH:-}" python3 - "$REPO" "$WORK/src" <<'EOF'
import shutil, sys, tempfile
from pathlib import Path
repo, dst = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / 'tools'))
import publish_update as p
with tempfile.TemporaryDirectory() as t:
    shutil.copytree(p.stage(repo, Path(t) / 'prog'), dst, dirs_exist_ok=True)
EOF
cp "$REPO/release/LEIA-ME.txt" "$WORK/src/LEIA-ME.txt"; cp "$REPO"/release/Docs/*.md "$WORK/src/Docs/"
# 3) conferência: tudo o que existia no anterior (fora código/telas/docs) continua existindo
missing=$(comm -23 <(cd "$WORK/x" && find . -type f | grep -v -e '^./\$PLUGINSDIR' -e '/site-packages/ustracker/' -e '^./frontend/' -e '^./Docs/' -e __pycache__ | sort) \
                   <(cd "$WORK/src" && find . -type f | sort))
if [ -n "$missing" ]; then echo "ERRO: faltam arquivos do programa anterior:"; echo "$missing" | head -20; exit 3; fi
grep -q "\"version\": \"$VERSION\"" "$WORK/src/VERSION.json" || { echo "ERRO: VERSION.json não é $VERSION"; exit 4; }
# 4) instalador (endereço da nuvem sem a chave da empresa; ícone do UStracker)
python3 -c "import json,sys; b=json.load(open(sys.argv[1])); assert 'company_key' not in b" "$WORK/src/Trust/placa-bootstrap.json"
cd "$REPO/release/installer"
"$MAKENSIS" -V2 -INPUTCHARSET UTF8 -DSRC="$WORK/src" -DVERSION="$VERSION" \
  "-DWV2=$WORK/x/\$PLUGINSDIR/MicrosoftEdgeWebView2RuntimeInstallerX64.exe" \
  -DPLACA="$WORK/src/Trust/placa-bootstrap.json" -DICON="$REPO/host/Bootstrap/Assets/UStracker.ico" \
  -DOUT="$WORK/UStracker_install_x64.exe" UStracker.nsi
cd "$WORK" && sha256sum UStracker_install_x64.exe | tee UStracker_install_x64.exe.sha256
echo "arquivos: $(cd "$WORK/src" && find . -type f | wc -l)"
