# ISAC-JASC: Integrated Sensing and Communication for Sustainable Development

**IEEE Paper — Monte Carlo Simulation Framework**

## Overview

ISAC-JASC explores Integrated Sensing and Communication as a predictive learning primitive for sustainable development, targeting agricultural monitoring (Feed the Future) and financial inclusion (GreenRemit) applications.

## Package Structure

```
isac_ieee_package/
├── main.tex                    # IEEE paper (8 sections)
├── references.bib              # 25 references with DOIs
├── isac_simulator.py           # Monte Carlo simulation engine
├── compile.ps1 / compile.sh    # Build scripts
├── README.md                   # This file
└── figures/                    # Generated results
    ├── fig1_sensing_comm_tradeoff.pdf
    ├── fig2_crlb_analysis.pdf
    ├── fig3_spectral_efficiency.pdf
    ├── fig4_application_scenarios.pdf
    └── fig5_range_doppler_map.pdf
```

## Quick Start

```bash
# 1. Install dependencies
pip install numpy scipy matplotlib pandas

# 2. Run Monte Carlo simulation
python isac_simulator.py 200 20

# 3. Compile paper (Windows)
.\compile.ps1 -sim

# 4. Or compile manually
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

## Key Results

| Metric | Low SNR (-15dB) | Mid SNR (0dB) | High SNR (+15dB) |
|--------|:-:|:-:|:-:|
| Sensing PE | 0.350 | 0.045 | 0.008 |
| Comm. BER | 0.45 | 0.008 | 3e-4 |
| SE [bps/Hz] | 0.80 | 3.50 | 5.50 |

## Repository

[https://github.com/FernandoMay/isac-ieee-paper](https://github.com/FernandoMay/isac-jasc-ieee)
