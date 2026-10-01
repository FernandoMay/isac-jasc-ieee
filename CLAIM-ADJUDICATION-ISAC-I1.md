# ISAC — I1 claim adjudication: population correspondence

**Date:** 2026-09-30
**Evidence state:** R1 `12fd2a7`, R2 `30c5794`, I6 `a3113d7`. Branch `fix/isac-audit-sweep`.
**Package and manuscript:** not modified by this document.
**Companions:** `CLAIM-INVENTORY-ISAC.md`, `CLAIM-ADJUDICATION-ISAC-I6.md`.

---

## 0. The question, stated correctly

The abstract asserts `SE > 4 bps/Hz` at SNR above −5 dB. The package's figures show values at or below 2.93. Before asking whether `>4` is true, the question is:

> **What population and what experimental configuration does each SE claim intend to rest on?**

The answer is that the artifact contains two experiments sharing one column name.

---

## 1. The finding

`snr_db` is not the same quantity in the two populations. It is a **control parameter** in one and an **output** in the other.

```
sweep    snr_lin_set = 10**(snr_set/10)                    snr_set ∈ {-15…15}
         sinr = snr_lin_set × lognormal(0, 0.2)
         snr_db is WHAT YOU SET

mc       snr_lin = sensing_snr(params, R_true, rcs)        R_true, rcs random
         sinr    = comm_sinr(params, R_true)               ← depends on range ONLY
         snr_db = 10·log10(snr_lin)                        snr_db is WHAT YOU GOT
```

`comm_sinr` never reads `snr_lin` or `rcs`. Within the Monte Carlo population, **SE is a function of range, and `snr_db` is a passive bystander column** that happens to correlate with range because sensing SNR also depends on range.

| | sweep | mc |
|---|---|---|
| what sets SE | the swept control `snr_set` | `comm_sinr(R_true)` only |
| `rcs` enters SE | no | **no** |
| `snr_db` role | control (x-axis of Fig. 3) | output |
| SE range | 0.0168 – 2.9903 | 3.58 – 7.38 |
| fraction with SE > 4 | **0.0000** | 0.8426 |

**The two populations do not overlap, and they are not two samples of one experiment.** Any partition on `snr_db` — including the abstract's "at SNR above −5 dB" — selects on different things in each.

---

## 2. What the −5 dB filter actually selects

```
all mc rows              n=10000   SE [3.58, 7.38]  mean 4.90
mc rows with snr_db >= -5  n=1155   SE [5.76, 7.38]  mean 6.61
SE > 4 among snr_db >= -5 :  1.0000
SE > 4 among ALL mc       :  0.8426
```

Within the filtered subset:

```
corr(SE, snr_db)  = +0.7946
corr(SE, R_true)  = -0.9738
corr(snr_db, R_true) = -0.8051
```

SE is almost perfectly determined by range, and `snr_db` is a weaker proxy for range. The filter selects on `rcs` — which contributes to `snr_db` and **not at all** to SE — and the surviving realizations happen to be short-range ones.

**The Monte Carlo population never experiences a low SINR.** Its worst case is `R = 300 m → 21.6 dB SINR → SE ≈ 3.9`. So a threshold of 4 bps/Hz sits below the population's floor, and the claim is satisfied for every member of the filtered subset — which is a statement about the population's construction, not about a regime the experiment probed.

The paper's own description of the population, at `main.tex:305`, is that Monte Carlo values are computed "with random target positions (`R ~ U[30,300]`), velocities, and radar cross sections". That is an accurate description of how the rows were produced. It is not a description of a swept SNR condition.

---

## 3. Adjudication matrix

| ID | claim | evidence required | disposition | basis |
|---|---|---|---|---|
| **I1-C1** | abstract: `SE > 4 bps/Hz` at SNR > −5 dB, agricultural scenarios | an identified population and scenario | **NEW EXPERIMENT REQUIRED / NOT IDENTIFIED** | satisfied only by the `mc` population, whose SE floor is 3.58 and whose `snr_db` is an output rather than a condition. There is no agricultural scenario dimension in the artifact at all |
| **I1-C2** | prose: SE reaches 2.65 bps/Hz at SINR +15 dB | the sweep curve | **SUPPORTED** | the sweep curve maximum computes to **2.6445**. This is the one SE claim that names a quantity its population actually contains |
| **I1-C3** | Figure 3's plotted values | the population actually plotted | **ADJUDICATED — plotted population is `sweep`** | Figure 3 plots `grp['se'].mean()` over `df_sweep`, i.e. the population with SE ≤ 2.99. Its y-limit is `max(se_v) × 1.2 = 3.17` |
| **I1-C4** | is `mc` the same physical experiment as `sweep`? | identical model, differing only in realization count | **CONTRADICTED** | the two feed `spectral_efficiency` structurally different arguments: a swept control versus `comm_sinr(R_true)`, which ignores both `snr_lin` and `rcs`. This is not a sampling difference |
| **I1-C5** | is the MC's effective advantage declared anywhere? | a statement in paper, code or artifact | **CONTRADICTED** | `comm_sinr` is documented only as "Communication SINR [linear] with simplified path loss". Neither the manuscript nor the artifact states that the Monte Carlo population carries a different effective link than the sweep |
| **I1-C6** | does any claim requiring `> 4` share a model with the rest of the paper? | experimental correspondence | **NOT IDENTIFIED** | the paper presents one experiment. The artifact contains two, under one column name, and no text distinguishes them |

---

## 4. The two threshold lines Figure 3 cannot show

Carried forward from the inventory, now with the population question settled:

```
Figure 3 y-limit  = max(sweep SE) × 1.2 = 3.1734
threshold line at y = 4.0    OUTSIDE the plotted range
threshold line at y = 8.0    OUTSIDE the plotted range
```

The figure labelled "Agri. 4 bps/Hz" and "Finance 8 bps/Hz" cannot display either threshold. And Figure 4, which supplies the scenario evidence, takes two arbitrary points from that same sweep curve:

```
Agriculture bar = se_v[len//3] = 0.1652 bps/Hz   against a 4.0 target
Finance bar     = se_v[len//2] = 0.5381 bps/Hz   against an 8.0 target
```

Both bars fall below the line drawn beside them. This is unchanged by anything in this document and does not depend on the `mc` population at all — the figures never plot it.

---

## 5. What is settled, and what is not

**Settled.** `sweep` and `mc` are different experiments. Figure 3 and Figure 4 plot `sweep`. The prose claim of 2.65 bps/Hz is faithful to `sweep`. The abstract's `> 4` is reachable only from `mc`, whose SE floor is 3.58 and whose `snr_db` is an output.

**Not settled, and deliberately so.** Whether `SE > 4` is achievable *in the regime the paper describes*. The package has no experiment that sweeps SNR for the Monte Carlo population, and no agricultural or financial configuration. Establishing it would require either a declared second experiment or a swept MC population — neither of which exists.

**Not adjudicated here.** The `> 10 bps/Hz` claim for 4×4 MIMO. There is no MIMO configuration, parameter or column anywhere in the package. That is a coverage question and is kept separate, as agreed.

---

## 6. Frozen

I1 is adjudicated. No package code and no manuscript claim is edited by this document.

The disposition pattern matches I6: the instrument was sound enough to ask the question, and the answers are about correspondence rather than about a number being wrong. `> 4` is not recorded as contradicted — it is recorded as resting on a population the paper does not describe, whose defining column means something different there.