# =====================================================================
#  ISAC-JASC IEEE Paper - Full Build Pipeline (PowerShell)
#  Usage: .\compile.ps1 [-sim]
# =====================================================================

param([switch]$sim)

Write-Host "=== ISAC-JASC IEEE Paper Build Pipeline ===" -ForegroundColor Cyan

# Phase 1: Run Simulator
if ($sim) {
    Write-Host "[1/4] Running Monte Carlo simulation..." -ForegroundColor Yellow
    python isac_simulator.py 200 20
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Simulator failed" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "[1/4] SKIP: Use '-sim' to re-run simulator" -ForegroundColor DarkYellow
}

# Phase 2: Check LaTeX
Write-Host "[2/4] Checking LaTeX..." -ForegroundColor Yellow
$pdflatex = Get-Command pdflatex -ErrorAction SilentlyContinue
if (-not $pdflatex) {
    Write-Host "ERROR: pdflatex not found. Install MiKTeX:" -ForegroundColor Red
    Write-Host "  winget install MiKTeX.MiKTeX" -ForegroundColor Red
    exit 1
}
$miktexBin = Split-Path $pdflatex.Source -Parent

# Phase 3: Download IEEEtran if needed
if (-not (Test-Path "IEEEtran.cls")) {
    Write-Host "[3/4] Downloading IEEEtran.cls..." -ForegroundColor Yellow
    try { Invoke-WebRequest -Uri "https://mirrors.ctan.org/macros/latex/contrib/IEEEtran/IEEEtran.cls" -OutFile "IEEEtran.cls" -UseBasicParsing }
    catch { Write-Host "WARNING: Could not download IEEEtran.cls" -ForegroundColor Yellow }
} else { Write-Host "[3/4] IEEEtran.cls found" -ForegroundColor Green }

# Phase 4: Compile
Write-Host "[4/4] Compiling LaTeX (3 passes + bibtex)..." -ForegroundColor Yellow
$env:Path = "$miktexBin;$env:PATH"
foreach ($f in @("main")) {
    & "$miktexBin\pdflatex.exe" -interaction=nonstopmode "$f.tex" 2>&1 | Out-Null
    & "$miktexBin\bibtex.exe" "$f" 2>&1 | Out-Null
    & "$miktexBin\pdflatex.exe" -interaction=nonstopmode "$f.tex" 2>&1 | Out-Null
    & "$miktexBin\pdflatex.exe" -interaction=nonstopmode "$f.tex" 2>&1 | Out-Null
}
if (Test-Path "main.pdf") {
    $kb = [math]::Round((Get-Item "main.pdf").Length / 1024)
    Write-Host "SUCCESS: main.pdf ($kb KB)" -ForegroundColor Green
} else { Write-Host "ERROR: main.pdf not generated" -ForegroundColor Red; exit 1 }
Write-Host "=== DONE ===" -ForegroundColor Cyan
