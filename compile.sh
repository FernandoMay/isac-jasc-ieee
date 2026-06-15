#!/usr/bin/env bash
set -euo pipefail
echo "=== ISAC-JASC IEEE Paper Build ==="

if [[ "${1:-}" == "-sim" ]]; then
  echo "[1] Running simulator..."
  python isac_simulator.py 200 20
else
  echo "[1] SKIP: Use '-sim' to re-run simulator"
fi

echo "[2] Checking LaTeX..."
command -v pdflatex >/dev/null || { echo "ERROR: pdflatex not found"; exit 1; }

[ -f IEEEtran.cls ] || (echo "[3] Downloading IEEEtran.cls..." && \
  wget -q https://mirrors.ctan.org/macros/latex/contrib/IEEEtran/IEEEtran.cls || \
  curl -sLO https://mirrors.ctan.org/macros/latex/contrib/IEEEtran/IEEEtran.cls)

echo "[4] Compiling..."
for f in main; do
  pdflatex -interaction=nonstopmode "$f.tex" >/dev/null 2>&1 || true
  bibtex "$f" >/dev/null 2>&1 || true
  pdflatex -interaction=nonstopmode "$f.tex" >/dev/null 2>&1 || true
  pdflatex -interaction=nonstopmode "$f.tex" >/dev/null 2>&1 || true
done
if [ -f main.pdf ]; then echo "SUCCESS: main.pdf ($(du -h main.pdf | cut -f1))"; else echo "ERROR"; exit 1; fi
echo "=== DONE ==="
