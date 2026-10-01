#!/usr/bin/env python3
"""ISAC R1 falsifiers: an independent estimator and a like-for-like comparison.

Row R1 repairs three instrumental properties. It does not attempt to make any
number look better, and no assertion here targets a ratio.

    R1a  the estimator's error must not be drawn from the reference bound
    R1b  the error and the reference must be evaluated at one defined SNR state
    R1c  a non-positive SNR must be rejected, not silently clamped

**The estimator under repair is meant to be a delay estimator.** The paper's
signal model is y(t) = A x(t - tau) e^{j 2 pi fd t} + n(t) with tau = 2R/c, so a
matched filter against the known OFDM symbol, reading the delay off the
correlation peak, is the mechanism the manuscript describes. That is what R1a
installs, in place of the current construction where the bound generates the
error. Substituting a different closed-form expression for the Gaussian draw
would have preserved the defect's shape while looking like a repair, and the
paper would still not be describing what the code does.

R1-F1 is the same intervention that exposed the defect, with the expectation
inverted. Scaling the bound by 4x moved the estimator's dispersion exactly
proportionally. After the repair, scaling the bound must move the bound and
leave the estimator alone, because the estimator never reads it.

**No ratio is a target.** After the repair the dispersion-to-bound ratio may be
0.62, or 1.37, or the model may turn out not to admit a direct comparison at
all. Calibrating a repair against an expected result is the same error this
program audits, and asserting ratio ~= 1 would manufacture a finding. What is
asserted is independence, a single comparison point, and explicit rejection.

F7 exists because R1a could be satisfied by a validator that simply does not
import the estimator, while the estimator still imports the validator's inputs.
The check follows the actual call path in both directions.
"""

import importlib.util
import inspect
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "isac_simulator.py"

SEED = 20260930
N = 4000
SCALE = 4.0
C_MPS = 3.0e8


def load_module():
    spec = importlib.util.spec_from_file_location("isac_r1", TARGET)
    module = importlib.util.module_from_spec(spec)
    sys.modules["isac_r1"] = module
    spec.loader.exec_module(module)
    return module


def main():
    print("property: the estimator is independent of the bound, the comparison "
          "uses one SNR")
    print("         state, and invalid inputs are rejected rather than clamped")
    print("=" * 78)

    module = load_module()
    params = module.ISACParams()
    failures = []

    estimator = getattr(module, "estimate_range", None)

    # --- R1-F1: the bound must not reach the estimator ----------------------
    print(f"  [INFO] R1-F1 scale the reference bound by {SCALE:g} and re-measure the "
          f"estimator.")
    if estimator is None:
        print("  [FAIL] R1-F1 no independent estimator exists; the package still draws "
              "the")
        print("         estimator's error from crlb_range")
        failures.append("F1-no-independent-estimator")
    else:
        def dispersion(seed, bound_scale=1.0):
            np.random.seed(seed)
            vals = []
            for _ in range(N):
                R_true = 150.0
                rcs = 1.0
                R_est = estimator(params, R_true, rcs)
                if R_est is None:
                    continue
                vals.append(abs(R_est - R_true))
            return float(np.std(vals)) if vals else float("nan")

        base = dispersion(SEED)
        original = module.crlb_range

        def scaled(p, snr):
            return original(p, snr) * bound_scale

        module.crlb_range = scaled
        try:
            after = dispersion(SEED)
        finally:
            module.crlb_range = original

        print(f"           estimator dispersion at 1x bound : {base:.6f} m")
        print(f"           estimator dispersion at {SCALE:g}x bound : {after:.6f} m")
        if abs(after - base) < 1e-9:
            print(f"  [PASS] R1-F1 scaling the bound by {SCALE:g} did not move the "
                  f"estimator at all")
        else:
            print(f"  [FAIL] R1-F1 scaling the bound by {SCALE:g} moved the estimator "
                  f"({base:.6f} -> {after:.6f} m)")
            print("           The estimator still reads the reference it is judged against.")
            failures.append("F1-estimator-still-reads-bound")

    # --- R1-F2: reproducible under a fixed scenario -------------------------
    print(f"  [INFO] R1-F2 reproducibility of the independent estimator:")
    if estimator is not None:
        np.random.seed(SEED)
        a = [estimator(params, 150.0, 1.0) for _ in range(50)]
        np.random.seed(SEED)
        b = [estimator(params, 150.0, 1.0) for _ in range(50)]
        if a == b:
            print(f"  [PASS] R1-F2 the same seed and scenario give identical estimates "
                  f"({a[0]:.4f} m)")
        else:
            print(f"  [FAIL] R1-F2 the same seed and scenario gave different estimates")
            failures.append("F2-not-reproducible")

    # --- R1-F3: one comparison point -----------------------------------------
    print(f"  [INFO] R1-F3 does the package define a single comparison SNR?")
    has_comparison = getattr(module, "comparison_snr", None)
    if has_comparison is None:
        print("  [FAIL] R1-F3 no comparison_snr exists. The pre-fix code evaluated the "
              "error at")
        print("         the noisy measured SNR and the reference at the clean set SNR, "
              "so the ratio")
        print("         compared two different states. A single named state must be "
              "defined and used")
        print("         by both sides.")
        failures.append("F3-no-comparison-point")
    else:
        np.random.seed(SEED)
        snr = has_comparison(params, 150.0, 1.0)
        print(f"  [PASS] R1-F3 comparison_snr is defined and returns {snr:.6f} "
              f"at R=150 m, rcs=1 m^2")
        src = inspect.getsource(module)
        if "comparison_snr(" in src and src.count("comparison_snr(") >= 3:
            print(f"           and it is called at {src.count('comparison_snr(')} sites, "
                  f"so both sides share it")
        else:
            print(f"  [FAIL] R1-F3 comparison_snr exists but is used at "
                  f"{src.count('comparison_snr(')} site(s); both sides must use it")
            failures.append("F3-comparison-point-unused")

    # --- R1-F4: non-positive SNR must be rejected ----------------------------
    print(f"  [INFO] R1-F4 what happens when the bound is asked for snr <= 0:")
    rejection = getattr(module, "InvalidSensingInput", None)
    if rejection is None:
        print("  [FAIL] R1-F4 the package declares no rejection type. Pre-fix, "
              "crlb_range guarded its")
        print("         divisor with max(snr_lin, 1e-30), which converts a negative "
              "physical SNR into a")
        print("         near-zero positive one and returns a finite bound of order 1e15. "
              "An invalid")
        print("         input must not produce an apparently valid statistic.")
        failures.append("F4-no-rejection-type")
    else:
        for probe in (-1.0, 0.0):
            try:
                value = module.crlb_range(params, probe)
                print(f"  [FAIL] R1-F4 snr={probe} returned a finite {value:.6e} "
                      f"instead of being rejected")
                failures.append(f"F4-accepted-{probe}")
            except rejection:
                print(f"  [PASS] R1-F4 snr={probe} is rejected explicitly")

    # --- R1-F5: the valid case still yields an interpretable statistic -------
    print(f"  [INFO] R1-F5 a valid scenario still produces a finite, finite-valued "
          f"estimate:")
    if estimator is not None:
        np.random.seed(SEED)
        vals = [estimator(params, 150.0, 1.0) for _ in range(200)]
        finite = [v for v in vals if v is not None and np.isfinite(v)]
        if len(finite) > 0:
            errs = np.array([abs(v - 150.0) for v in finite])
            print(f"  [PASS] R1-F5 {len(finite)}/200 estimates finite; "
                  f"mean |error| {errs.mean():.4f} m, "
                  f"dispersion {errs.std():.4f} m")
            print(f"           The statistic is interpretable. Its value relative to the "
                  f"bound is NOT a")
            print(f"           target of this repair and is deliberately unasserted.")
        else:
            print(f"  [FAIL] R1-F5 no finite estimate was produced for a valid scenario")
            failures.append("F5-no-finite-estimate")

    # --- R1-F6: replay determinism -------------------------------------------
    print(f"  [INFO] R1-F6 two runs from the same seed agree:")
    if estimator is not None:
        def run(seed):
            np.random.seed(seed)
            out = []
            for _ in range(200):
                R_est = estimator(params, 150.0, 1.0)
                out.append(None if R_est is None else round(float(R_est), 9))
            return out

        if run(SEED) == run(SEED):
            print(f"  [PASS] R1-F6 replay from the same seed reproduces the estimate "
                  f"sequence exactly")
        else:
            print(f"  [FAIL] R1-F6 replay from the same seed did not reproduce")
            failures.append("F6-replay-differs")

    # --- R1-F7: the estimator must not reach the bound at all ---------------
    # The first version of this check grepped the estimator's source for
    # "crlb_range" and failed, because the estimator's own docstring names the
    # construction it replaced. A check that matches the explanation of a defect
    # as the defect is the same false-green pattern this program has already
    # produced five times, and it would have failed here for the wrong reason.
    #
    # Behavioural instead: replace the reference bound with a function that
    # raises, and see whether the estimator still produces estimates. If the
    # estimator reads the bound, it cannot survive that.
    print(f"  [INFO] R1-F7 replace the reference bound with a function that raises:")
    if estimator is not None:
        original_bound = module.crlb_range

        def exploding_bound(p_, snr_):
            raise AssertionError('the estimator reached the reference bound')

        module.crlb_range = exploding_bound
        try:
            np.random.seed(SEED)
            survived = [estimator(params, 150.0, 1.0) for _ in range(20)]
            ok = all(v is not None for v in survived)
        except AssertionError:
            ok = False
        finally:
            module.crlb_range = original_bound

        if ok:
            print(f"  [PASS] R1-F7 the estimator produced all 20 estimates with the "
                  f"reference bound replaced")
            print(f"           by a function that raises. It does not read the bound at "
                  f"all, by")
            print(f"           construction rather than by inspection of the source.")
        else:
            print(f"  [FAIL] R1-F7 the estimator reached the reference bound")
            failures.append("F7-estimator-calls-bound")

    print("=" * 78)
    if failures:
        print("FAILED: " + ", ".join(failures))
        print()
        print("No ratio is targeted. R1a repairs what the manuscript says the estimator")
        print("is -- a delay estimator on the OFDM waveform of eq. (rx_sensing) -- and")
        print("leaves the bound as a reference computed afterwards from the same state.")
        return 1
    print("PASSED: the estimator is independent and the comparison is like-for-like")
    return 0


if __name__ == "__main__":
    sys.exit(main())
