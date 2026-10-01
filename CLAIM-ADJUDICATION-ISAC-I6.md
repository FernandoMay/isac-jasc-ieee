# ISAC — I6 claim adjudication

**Date:** 2026-09-30
**Evidence state:** R1 `12fd2a7`, R2 `30c5794`. Branch `fix/isac-audit-sweep`.
**Falsifiers:** R1-F 7/7 green, R2-F 6/6 green, I6-F red by documented supersession.
**Manuscript:** not edited.
**Companions:** `CLAIM-INVENTORY-ISAC.md` (lineage), `tests/test_validation_independence.py` (superseded, kept red).

---

## 0. Why R1 GREEN is not I6 GREEN

R1 removed defects in the instrument. That makes the claims testable. It does not make any of them true. R1a and R1b cleared the way to *ask*; the answers are below, and one of them is that the manuscript's CRLB analysis does not agree with itself.

---

## 1. Adjudication matrix

| ID | claim | what must be true | status | evidence |
|---|---|---|---|---|
| **I6-C1** | the implemented estimator corresponds to the declared sensing method | the estimator must be the mechanism eq. (rx_sensing) describes | **ADJUDICATED — CORRESPONDS** | `estimate_range` is a matched filter against the known OFDM symbol, reading the delay off the correlation peak and converting through τ = 2R/c. The manuscript describes Range-Doppler processing via 2D-FFT; the estimator is a 1D delay estimator, so it corresponds to eq. (delay_doppler) and eq. (rx_sensing) but **not** to the 2D-FFT receiver described at L210. See C7. |
| **I6-C2** | the estimation is independent of the CRLB | the estimator must not read the reference | **SUPPORTED** | ×4 scaling of the bound does not move the estimator (R1-F1); replacing `crlb_range` with a function that raises does not stop it producing all 20 estimates (R1-F7); the estimator's body contains no bound call |
| **I6-C3** | the reported CRLB corresponds to the estimator's observation model | the bound must be the correct limit for the model the estimator implements | **NEW EXPERIMENT REQUIRED / NOT IDENTIFIED** | see §2. Two independent obstacles, neither resolvable from the current artifacts |
| **I6-C4** | the error/CRLB comparison uses one physical state | both sides evaluated at the same SNR | **SUPPORTED** | `comparison_snr` names the state; both `estimate_range` and the reported `crlb_R` are evaluated at it, and `snr_cmp_lin` is published per realization |
| **I6-C5** | invalid SNR inputs are not silently converted into valid measurements | snr ≤ 0 must be rejected, not clamped | **SUPPORTED** | `InvalidSensingInput` replaces the `max(snr_lin, 1e-30)` guard; R1-F4 verifies rejection at −1.0 and 0.0 |
| **I6-C6** | the package's numbers confirm the declared theoretical accuracy | the artifact must show the estimator at the bound | **NOT VERIFIED** | see §3. The instrument is no longer designed to produce agreement with the bound, so this claim now requires evidence that does not exist in either population of the artifact |
| **I6-C7** | the receiver performs range-Doppler processing via 2D-FFT | a 2D delay-Doppler map must be computed | **NEW EXPERIMENT REQUIRED** | the package never computes one. The pre-fix Figure 5 was labelled "Range-Doppler Map" but plotted independent noise; the replacement is renamed because it is not one |

---

## 2. I6-C3: the manuscript's CRLB analysis disagrees with itself

Two equations in §Cramér-Rao Lower Bound Analysis, evaluated at the paper's own parameters (`N_sub` 256, `N_sym` 64, `B` 100 MHz, `f_c` 28 GHz, SNR 0.002031):

```
eq (crlb)   sigma_R^2 >= c / (2 B sqrt(2 SNR))
            -> sigma_R = 4.8515 m

eq (fisher) J = (2 SNR / (N_sub N_sym)) diag((2B/c)^2, ...)
            -> sigma_R^2 = 1/J_RR = 9.0769e+06
            -> sigma_R = 3012.80 m
```

**They differ by a factor of 621 in standard deviation.** eq (fisher) inverted carries `N_sub·N_sym` and `c²`; eq (crlb) carries neither. This is an internal document defect that exists independently of any code, so it cannot be adjudicated from the artifacts at all.

### And the code implements one of them under the other's name

`crlb_range()` returns `c / (2·B·√(2·SNR))` — **exactly the right-hand side of eq (crlb), which the paper labels σ_R², a variance.** The function is named as though it returns a standard deviation, the artifact column is `crlb_R`, and Figure 2's axis is labelled `CRLB_Range [m]`.

Pre-R1 the variance was used as a standard deviation: `R_est = R_true + randn() * crlb_range(...)`, so the realised error had the variance of the variance squared. Post-R1 the same quantity is reported and, in the figure's axis label, presented as a metre-valued standard deviation.

### The comparison, both readings

```
estimator dispersion                    0.9471 m
crlb_range() read as a VARIANCE        23.5375     ratio 0.0402
sqrt(crlb_range()) read as a STD        4.8515 m   ratio 0.1952
```

The estimator is below the bound under either reading, by 5× or 27×. **That is not a small discrepancy and it is not evidence that the bound is wrong.** An efficient unbiased estimator achieves the CRLB and cannot beat it, so a large gap in that direction indicates the two quantities are not the same kind of object, which is exactly what §2 establishes.

**Disposition: NEW EXPERIMENT REQUIRED / NOT IDENTIFIED.** Not CONTRADICTED: with two mutually inconsistent bounds in the manuscript and a code path that conflates a variance with a deviation, there is no single stated proposition for the artifact to contradict.

---

## 3. I6-C6: what the language claims versus what can be shown

`main.tex:267`:

> "Figure~\ref{fig:crlb} compares the empirical estimation errors with the theoretical CRLB. The range estimation standard deviation **approaches the CRLB** for SNR > 0 dB, confirming that the OFDM-ISAC receiver **achieves near-optimal performance** in the high-SNR regime."

Two independent problems.

**Figure 2 plots no empirical series.** Its entire drawing surface is two calls:

```
ax1.semilogy(snr_v, crlb_r, ..., label='CRLB_Range [m]')
ax2.semilogy(snr_v, crlb_v, ..., label='CRLB_Velocity [m/s]')
```

There is no error series, no `R_est`, no dispersion. A figure described as comparing empirical errors with a theoretical bound contains only the theoretical bound.

**The agreement the sentence reports was manufactured.** Pre-R1, `pe` was the bound divided by range, so any plot of empirical error against the bound reproduced the bound by construction. The instrument was designed to produce concordance. R1 removed that, which is the correct outcome: a falsifier is only useful if it can fail, and this one now can.

**Disposition: NOT VERIFIED.** Not CONTRADICTED — the claim is about the empirical estimator's position relative to a bound, and neither population of the artifact supplies an unbiased empirical standard deviation computed against a stated bound under stated assumptions.

The new instrument produces an inconvenient result. That is not a defect in the repair and must not be presented as one.

---

## 4. Superseded states, recorded

| ID | pre-R1 evidence | post-R1 | historical state |
|---|---|---|---|
| I6-C2 | error drawn from the bound | estimator independent, verified by two interventions | SUPERSEDED BY REPAIRED EVIDENCE |
| I6-C4 | error at `snr_meas`, reference at `snr_lin` | one named state, published as `snr_cmp_lin` | SUPERSEDED BY REPAIRED EVIDENCE |
| I6-C5 | `max(snr_lin, 1e-30)` silently clamped | `InvalidSensingInput` | SUPERSEDED BY REPAIRED EVIDENCE |
| I6-C3 | untestable — the instrument could not fail | testable, and unresolved | **was never testable** |
| I6-C6 | agreement by construction | agreement no longer available | **was never a measurement** |
| I6-C7 | figure labelled as a map, plotting noise | figure renamed, claim not adjudicated | claim never evidenced |

---

## 5. What each disposition requires

| disposition | claims | consequence |
|---|---|---|
| SUPPORTED | I6-C2, I6-C4, I6-C5 | retain; the wording already describes what the code does |
| ADJUDICATED — CORRESPONDS | I6-C1 | retain, with the 2D-FFT qualification stated (see I6-C7) |
| NEW EXPERIMENT REQUIRED | I6-C3, I6-C7 | rewrite to report non-identification; reserve the original assertions |
| NOT VERIFIED | I6-C6 | rewrite to report that the comparison the sentence asserts is not made |

**One claim in six survives as written.** The same shape as LEO's 1 of 21, arrived at by a different route: here the instrument was sound enough to *ask*, and the answers are that the manuscript's bound is internally inconsistent and that its validating figure contains no data.

---

## 6. Frozen

I6 is adjudicated. No manuscript claim is edited. I1 — the 550 sweep rows against 10,000 Monte Carlo rows that do not overlap at the same nominal SNR — remains open and is not addressed by this document.