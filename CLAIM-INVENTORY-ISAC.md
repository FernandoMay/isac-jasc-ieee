# ISAC — claim inventory and lineage reconstruction

**Date:** 2026-09-30
**Baseline:** `bb6f9e3` ("Update GitHub repository link in README"), working tree clean at clone.
**Branch:** `fix/isac-audit-sweep`, created **before the first commit**. Destination is a gate property here, not a Git habit learned afterwards.
**Status:** no code modified, no artifact regenerated, no manuscript edited. Reconstruction only.
**Artifact under audit:** `isac_experiment_results.csv` — 10,550 rows, columns `snr_db, pe, ber, se, sinr_db, crlb_R, crlb_v, type`.

---

## 0. Destination gate (new, from LEO)

```
branch at clone   master
branch created    fix/isac-audit-sweep   ← before any commit
tree              CLEAN
```

LEO published to `master` by mistake at the end of its sweep. That failure is a
gate omission, not a slip: ten release-gate checks were run and none asked which
branch the push would land on. Here the branch exists before there is anything to
commit.

---

## 1. Claim inventory

| # | claim | loc | type | published | artifact evidence |
|---|---|---|---|---|---|
| **I1** | "spectral efficiency **> 4 bps/Hz** at SNR above −5 dB in agricultural scenarios" | L70 (abstract) | threshold crossing, scenario-conditioned | >4 | **depends entirely on which `type` rows are read — see §4** |
| **I2** | "SE reaches 2.65 bps/Hz at SINR = +15 dB" | L278 | measurement | 2.65 | **2.6445** from the `sweep` rows — faithful |
| **I3** | "With MIMO extensions (4×4), achievable SE scales to **> 10 bps/Hz**" | L278 | extrapolation | >10 | **no MIMO in the artifact; not modelled at all** |
| **I4** | "prediction error < 0.05" | L70, L305 | threshold crossing | <0.05 | present in `pe`; condition not yet adjudicated |
| **I5** | "financial inclusion applications require SNR > 0 dB for comparable performance" | L70 | comparative, scenario-conditioned | >0 | **no scenario dimension exists in the artifact** |
| **I6** | CRLB is "derived for joint parameter estimation, establishing theoretical performance limits" | L70 | derivation + validation | — | **circular — see §2** |
| **I7** | Figure 5 "Range-Doppler Map (OFDM-ISAC)" with axes Velocity [m/s] and Range [m], colourbar Power [dB] | L~300 | visual evidence of sensing capability | — | **fabricated — see §3** |
| **I8** | Figure 4 "SE by Scenario", Agriculture bar against a 4 bps/Hz target, Finance bar against 8 bps/Hz | fig4 | scenario evidence | — | **the two bars are two points on one curve — see §5** |

### Internal document inconsistency, recorded separately

Monte Carlo realization count is stated three ways in one document:

```
L70  abstract   "across 200 independent Monte Carlo realizations"
L256 body      "N_MC = 10,000 Monte Carlo realizations"
L305 body      "N_MC = 10,000 independent Monte Carlo trials"
tab:params     "Monte Carlo realizations & 200"
code           run_monte_carlo(params, n_mc: int = 2000)   default 2000
artifact       550 sweep + 10000 mc rows → run with n_mc=10000
```

Six statements, four different values. The code's default (2000) matches none of
the paper's three.

---

## 2. Estimator lineage — the validation is circular

The generation of measurements, verbatim:

```python
R_est = R_true + np.random.randn() * crlb_range(params, snr_meas)
v_est = v_true + np.random.randn() * crlb_velocity(params, snr_meas)
...
'crlb_R': crlb_range(params, snr_lin),
'crlb_v': crlb_velocity(params, snr_lin),
```

The estimator's error is **drawn from the bound**. Its standard deviation is
therefore the bound by construction, and no configuration of the sensing model
and no replacement of the CRLB derivation could change the outcome, because the
outcome is an input to the comparison.

Verified numerically at `snr_lin = 1.0`:

```
crlb_range              1.060660
std of estimator error  0.648590     over 20,000 realizations
ratio                   0.611496
```

The ratio is below 1 only because the CRLB is itself evaluated at a *noisy* SNR,
which randomises the multiplier downward. The estimator cannot exceed the bound
for any seed, which is the definition of a construction that cannot fail.

**Consequently the CRLB comparison in this package is not evidence of anything.**
The paper's claim I6 is not merely unsupported — the instrument cannot fail, so
it cannot support a claim in either direction.

The same holds for the `sweep` rows' prediction error, which is even more
direct: `pe_val = min(1.0, abs(np.random.randn()) * crlb_r / 100)` — a random
draw scaled by the bound, with no estimator involved at all.

---

## 3. Figure lineage — Figure 5 has no lineage

```python
rd = np.random.randn(50, 50)
rd[25, 15] = 100
im = ax.imshow(rd, aspect='auto', cmap='viridis', extent=[-30, 30, 0, 500])
ax.set_xlabel('Velocity [m/s]'); ax.set_ylabel('Range [m]')
ax.set_title('Range-Doppler Map (OFDM-ISAC)')
plt.colorbar(im, ax=ax, label='Power [dB]')
```

Trace, link by link:

| link | status |
|---|---|
| paper Figure 5 | exists |
| figure generator | `isac_simulator.py:310-320` |
| input data | `np.random.randn(50, 50)`, one cell overwritten with 100 |
| simulation output | **none. The function never reads `df`, `R_true`, `v_true`, `R_est` or `v_est`** |
| axis mapping | `extent=[-30, 30, 0, 500]` is a display range applied to array indices; index 0–49 maps to 0–500 m and 0–50 maps to −30…30 m/s by convention only |
| colourbar | labelled "Power [dB]"; the values are raw Gaussian draws, not dB, not power |

The aggravating fact: the simulation **does** produce `R_true`, `v_true`,
`R_est` and `v_est` for every Monte Carlo realization. A genuine range–velocity
scatter, or a histogram of estimates against truth, was available from the same
run and was not used. The figure is not a degraded rendering of a real result;
it is unrelated to the run that produced the artifact beside it.

This is the case the audit anticipated: **a deterministically reproducible
figure can be deterministically invented.** Regenerating it reproduces the noise
exactly and proves nothing about sensing capability.

---

## 4. What "SE > 4 bps/Hz" depends on

The artifact holds two row populations under one file, and they disagree about
the claim.

```
type = 'sweep'   550 rows    11 distinct snr_db     SE at snr >= -5 dB:  0.191 –  2.925
type = 'mc'   10,000 rows    10,000 distinct snr_db SE at snr >= -5 dB:  5.794 –  7.387
```

At the same nominal SNR the two populations do not overlap. The `mc` rows reach
`sinr_db` up to 41.6 while the `sweep` rows sit at their set point, so the two
populations are computed under different effective SINR definitions — the
Monte Carlo path applies a processing gain the sweep path does not.

Therefore:

- claim **I1** is satisfied by the `mc` rows and **not** by the `sweep` rows;
- claim **I2** (2.65 bps/Hz) is reproduced **exactly** from the `sweep` rows —
  the computed curve maximum is **2.6445**;
- the paper's figures plot the **`sweep`** rows.

**The abstract's claim and the paper's own figures are computed from different
populations of the same artifact.** That is not yet an adjudication of I1. It is
the finding that I1 cannot be adjudicated until the paper states which
population it refers to — and that I1 and I2, as written, cannot both be true of
the same experimental condition.

I3 (>10 bps/Hz with 4×4 MIMO) has **no counterpart in the artifact**: no MIMO
configuration, no parameter, no column. It is an extrapolation about a system the
package does not model.

---

## 5. Figure 4 — the scenario evidence, traced

```python
se_at = [se_v[len(se_v)//3], se_v[len(se_v)//2]]
a1.bar(x, se_at, ...)
a1.axhline(y=4.0, ..., label='Agri. Target')
a1.axhline(y=8.0, ..., label='Finance Target')
a1.set_xticklabels(['Agriculture\n(Feed the Future)', 'Finance\n(GreenRemit)'])
```

`se_v` is the single spectral-efficiency curve plotted in Figure 3. The two
"scenarios" are **two arbitrary points on that one curve**, at one-third and one-
half of its length. No agricultural configuration and no financial configuration
is simulated anywhere; the artifact has no scenario column.

Computed from the artifact:

```
SE curve (sweep rows)        max 2.6445 bps/Hz
Agriculture bar              0.1652 bps/Hz   against a 4.0 target   -> does not reach it
Finance bar                  0.5381 bps/Hz   against an 8.0 target  -> does not reach it
```

Both bars fall short of the target drawn beside them by factors of 24 and 15.

And in Figure 3, whose y-limit is `max(se_v) * 1.2 = 3.17`:

```
threshold line at y = 4.0    OUTSIDE the plotted range
threshold line at y = 8.0    OUTSIDE the plotted range
```

The paper's own SE figure **cannot display either application threshold** it
claims are crossed. The lines are drawn off-axis.

---

## 6. Status before any repair

| row | status |
|---|---|
| I1 SE > 4 bps/Hz | **not adjudicable as written** — depends on an unstated row population; contradicted by the population the figures plot |
| I2 SE 2.65 bps/Hz @ +15 dB | **faithful** to the `sweep` curve (2.6445) |
| I3 > 10 bps/Hz MIMO | **not modelled** — no counterpart in the package |
| I4 PE < 0.05 | not yet adjudicated |
| I5 Finance needs SNR > 0 | **no scenario dimension exists** |
| I6 CRLB establishes performance limits | **circular — the instrument cannot fail** |
| I7 Figure 5 Range-Doppler | **fabricated, no lineage to any simulation output** |
| I8 Figure 4 SE by Scenario | **two points on one curve, both below their targets** |

No repair has been designed. The falsifiers come next, beginning with the one
ISAC contributes that LEO did not need:

> **A validation must introduce evidence independent of the construction it
> validates.**

No file has been modified. No claim has been edited.
