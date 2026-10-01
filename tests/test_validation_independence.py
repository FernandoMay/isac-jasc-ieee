"""ISAC I6-F falsifier: validation independence.  -- SUPERSEDED by R1-F1..F7.

STATUS: superseded, and still RED by design. Read this before trusting it.

This file's `package_estimator` is a closure written by the audit that replicates
the pre-fix construction:

    R_true + randn() * crlb_range(params, snr_meas)

It therefore verifies that closure, not the package's estimation path. After row
R1 repaired the package, this file continued to report RED because the code it
examines is the audit's own copy of the defect, which R1 did not and should not
have touched.

That is a real limitation and it is the same one the methodology section warns
about: an integrity check cannot establish correspondence if its inputs are an
unaudited transcription of the claim being checked. I6-F checked a transcription.
It is kept, red, because it is the evidence that the instrument can fail for the
right property BEFORE a repair is evaluated with it -- which is the boundary LEO
established and which R1 respected.

The assertions that actually test the package are in
tests/test_estimator_independence.py, which calls module.estimate_range directly
and passes R1-F1 through R1-F7. R1-F1 scales the bound 4x and requires the
estimator not to move; R1-F7 replaces the bound with a function that raises and
requires the estimator to survive.

Nothing here is deleted. A falsifier that was red before a repair and remains red
afterwards, for a reason that is in its own source, is a record, not a bug.



import importlib.util
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "isac_simulator.py"

SCALE = 4.0
N_REALIZATIONS = 20000
SEED = 20260930


def load_module():
    spec = importlib.util.spec_from_file_location("isac_i6f", TARGET)
    module = importlib.util.module_from_spec(spec)
    sys.modules["isac_i6f"] = module
    spec.loader.exec_module(module)
    return module


def measure_error_dispersion(error_source, params, snr_lin, n=N_REALIZATIONS, seed=SEED):
    """Dispersion of the estimator error relative to the bound, under one
    generator. `error_source(params, snr_meas, R_true)` returns R_est."""
    np.random.seed(seed)
    ratios = []
    for _ in range(n):
        R_true = 100.0
        snr_meas = snr_lin * (1 + np.random.randn() * 0.15)
        R_est = error_source(params, snr_meas, R_true)
        bound = module_bound(params, snr_lin)
        if bound > 0:
            ratios.append(abs(R_est - R_true) / bound)
    return float(np.mean(ratios)), float(np.std(ratios))


# The bound is looked up through a single indirection so that scaling it is a
# genuine intervention on the reference, not a local edit inside the probe.
_MODULE = {"m": None}


def module_bound(params, snr_lin):
    return _MODULE["m"].crlb_range(params, snr_lin)


def scaled_bound_factory(m, factor):
    """Return (bound_fn) that reports the package bound multiplied by factor."""
    original = m.crlb_range

    def scaled(params, snr_lin):
        return original(params, snr_lin) * factor

    return scaled, original


def main():
    print("property: a validation introduces evidence independent of the")
    print("         construction it validates")
    print("=" * 78)

    module = load_module()
    _MODULE["m"] = module
    params = module.ISACParams()
    snr_lin = 10 ** (0 / 10)
    failures = []

    # The package's own estimator, as a callable.
    def package_estimator(p, snr_meas, R_true):
        return R_true + np.random.randn() * module.crlb_range(p, snr_meas)

    # An independent estimator: its error process does not read the bound.
    def independent_estimator(p, snr_meas, R_true):
        _ = snr_meas          # the noise level is deliberately not consulted
        return R_true + np.random.randn() * 0.6

    # --- F1: the package's construction is circular -------------------------
    print(f"  [INFO] F1 intervention: scale the reference bound by {SCALE:g} and")
    print(f"         re-measure the estimator's dispersion against it.")
    base_ratio, base_sd = measure_error_dispersion(package_estimator, params, snr_lin)

    scaled, original = scaled_bound_factory(module, SCALE)
    module.crlb_range = scaled
    try:
        scaled_ratio, scaled_sd = measure_error_dispersion(package_estimator, params, snr_lin)
    finally:
        module.crlb_range = original

    print(f"         mean error/bound at 1x bound : {base_ratio:.6f}  (sd {base_sd:.6f})")
    print(f"         mean error/bound at {SCALE:g}x bound : {scaled_ratio:.6f}  "
          f"(sd {scaled_sd:.6f})")

    # Circularity signature: the error is a fixed multiple of whatever the bound
    # says, so scaling the bound scales the error and the ratio holds still.
    ratio_preserved = abs(scaled_ratio - base_ratio) < 0.02
    if ratio_preserved:
        print(f"  [FAIL] F1 the estimator's error is a fixed multiple of the reference "
              f"bound.")
        print(f"         The ratio is unchanged when the bound is scaled by {SCALE:g} "
              f"({base_ratio:.4f} -> {scaled_ratio:.4f}),")
        print(f"         which is only possible if the error is drawn from the bound. "
              f"Detected by")
        print(f"         intervention, not by reading the source.")
        print(f"         Consequence: the CRLB comparison in this package is not "
              f"evidence of")
        print(f"         anything. The bound is an input to the measurement it is used "
              f"to judge.")
        failures.append("F1-estimator-draws-from-bound")
    else:
        print(f"  [PASS] F1 the estimator's error does not track the reference bound")

    # --- F2: positive control — an independent generator must pass -----------
    ind_base, _ = measure_error_dispersion(independent_estimator, params, snr_lin)
    module.crlb_range = scaled
    try:
        ind_scaled, _ = measure_error_dispersion(independent_estimator, params, snr_lin)
    finally:
        module.crlb_range = original

    ind_moved = abs(ind_scaled - ind_base) > 0.02
    print(f"  [INFO] F2 positive control, independent generator: "
          f"{ind_base:.6f} -> {ind_scaled:.6f} under the same scaling")
    if ind_moved:
        print(f"  [PASS] F2 the instrument can distinguish an independent construction; "
              f"its error")
        print(f"           responded to the intervention while the package's did not.")
        print(f"           A test that cannot pass anything would be indistinguishable "
              f"from one that")
        print(f"           fails everything.")
    else:
        print(f"  [FAIL] F2 the instrument cannot distinguish an independent "
              f"construction from")
        print(f"         the circular one. F1 would then be reporting the instrument's "
              f"blindness,")
        print(f"         not the package's defect.")
        failures.append("F2-instrument-blind")

    # --- F3a: can the package express a violation at all? -------------------
    # The original F3 asked this and reported PASS. It passed for the wrong
    # reason -- the ratio exceeded 1 through the F3b argument mismatch rather
    # than through any property of the construction -- so it was not evidence of
    # anything and has been split rather than kept.
    #
    # F3a asks the narrow question: evaluated like-for-like, can this
    # construction register a bound violation, and can it register a pass? A
    # pipeline that can do neither is a statement about its generator, not about
    # the estimator.
    print(f"  [INFO] F3a evaluated like-for-like, can a violation and a pass both be")
    print(f"          expressed?")
    np.random.seed(SEED)
    bound_lfl = module.crlb_range(params, snr_lin)
    like_for_like = []
    for _ in range(N_REALIZATIONS):
        R_true = 100.0
        snr_meas = snr_lin * (1 + np.random.randn() * 0.15)
        # error drawn from the bound at the SAME argument the reference uses
        R_est = R_true + np.random.randn() * module.crlb_range(params, snr_lin)
        like_for_like.append(abs(R_est - R_true) / bound_lfl)
    lfl = np.array(like_for_like)
    violation_frac = float((lfl > 1.0).mean())
    print(f"          fraction of realizations violating the bound: {violation_frac:.4f}")
    print(f"          max ratio {lfl.max():.4f}")
    if 0.0 < violation_frac < 1.0:
        print(f"  [PASS] F3a both outcomes are expressible: {violation_frac:.4f} of "
              f"realizations exceed the")
        print(f"           bound and the rest do not, so the construction can register "
              f"either verdict.")
    else:
        print(f"  [FAIL] F3a the construction can only ever produce one verdict "
              f"({violation_frac:.4f} violating)")
        failures.append("F3a-single-verdict-only")

    # Positive control: an independent source must also express both.
    np.random.seed(SEED)
    ind_lfl = []
    for _ in range(N_REALIZATIONS):
        R_true = 100.0
        ind_lfl.append(abs(independent_estimator(params, snr_lin, R_true) - R_true)
                       / bound_lfl)
    ind_lfl = np.array(ind_lfl)
    ind_violation = float((ind_lfl > 1.0).mean())
    print(f"  [INFO] F3a independent source violates in {ind_violation:.4f} of "
          f"realizations")
    if 0.0 < ind_violation < 1.0:
        print(f"  [PASS] F3a the independent source expresses both verdicts too, so "
              f"the probe")
        print(f"           discriminates rather than always agreeing.")
    else:
        print(f"  [FAIL] F3a the independent source collapsed to a single verdict")
        failures.append("F3a-control-single-verdict")

    # --- F3b: is the reference evaluated at the same point as the error? -----
    # The second defect, discovered because the original F3 passed unexpectedly.
    # The package generates the error with crlb_range(params, snr_meas) at the
    # NOISY measured SNR, while the artifact reports crlb_range(params, snr_lin)
    # at the CLEAN set SNR. Those are two different points, so the published
    # comparison is not like-for-like.
    #
    # Detected by intervention rather than by argument inspection: perturb ONLY
    # the dispersion of the measured-SNR noise and leave the reference untouched.
    # If the estimator's error responds, the error was produced at the noisy
    # point, and the clean-SNR reference is measuring something else.
    print(f"  [INFO] F3b perturb only the measured-SNR noise and watch the error:")
    # The base SNR is raised and the noise scales kept modest on purpose. The
    # first version of this probe used 0 dB with noise scales 0.15 and 0.30 and
    # reported an error dispersion of 1.4e13, which looked like a dramatic
    # demonstration and was in fact a third defect contaminating the second.
    # crlb_range guards its divisor with max(snr_lin, 1e-30), which converts a
    # NEGATIVE measured SNR into a near-zero positive one instead of rejecting
    # it, so the bound becomes astronomically large and dominates the statistic.
    # At 0 dB a 0.30 noise scale drives snr_meas negative often enough to trigger
    # that. Running the mismatch at a base SNR where snr_meas stays positive
    # separates the two signals.
    base_snr_lin = 10 ** (10 / 10)
    def error_std_at_noise_scale(noise_scale, seed=SEED, n=8000, base=base_snr_lin):
        np.random.seed(seed)
        vals = []
        for _ in range(n):
            R_true = 100.0
            snr_meas = base * (1 + np.random.randn() * noise_scale)
            R_est = R_true + np.random.randn() * module.crlb_range(params, snr_meas)
            vals.append(abs(R_est - R_true))
        return float(np.std(vals))

    print(f"          base SNR +10 dB, noise scales chosen so snr_meas stays positive")
    pkg_lo = error_std_at_noise_scale(0.10)
    pkg_hi = error_std_at_noise_scale(0.20)
    moved = abs(pkg_hi - pkg_lo) > 1e-6

    np.random.seed(SEED)
    ind_lo = float(np.std([abs(independent_estimator(params, snr_lin, 100.0) - 100.0)
                           for _ in range(8000)]))

    print(f"          package error sd at noise 0.10 : {pkg_lo:.6f}")
    print(f"          package error sd at noise 0.20 : {pkg_hi:.6f}")
    print(f"          independent error sd            : {ind_lo:.6f}  (unaffected by noise)")

    if moved:
        print(f"  [FAIL] F3b the estimator's error is produced at the noisy measured "
              f"SNR, while the")
        print(f"           reference the artifact reports is evaluated at the clean set "
              f"SNR. Perturbing")
        print(f"           only the measured-SNR noise moved the error "
              f"({pkg_lo:.6f} -> {pkg_hi:.6f}), so")
        print(f"           the two quantities are not being compared at the same point.")
        print(f"           This is a SECOND defect, independent of F1's circularity: even")
        print(f"           a correct reference would be miscompared here. The original "
              f"F3 passed for")
        print(f"           this reason, which is why it had to be split.")
        failures.append("F3b-reference-evaluated-at-different-point")
    else:
        print(f"  [PASS] F3b the error and the reference are evaluated at the same point")

    # --- F4: the valid independent case must not be flagged -----------------
    print(f"  [INFO] F4 valid independent case (error well inside the bound):")
    np.random.seed(SEED)
    valid_ratio, _ = measure_error_dispersion(independent_estimator, params, snr_lin)
    flagged = valid_ratio > 1.0
    if not flagged:
        print(f"  [PASS] F4 an independent estimator inside the bound is not flagged "
              f"(ratio {valid_ratio:.4f})")
    else:
        print(f"  [FAIL] F4 a valid independent case was flagged (ratio "
              f"{valid_ratio:.4f}); the test would")
        print(f"         reject sound measurements and is therefore unusable as a gate")
        failures.append("F4-valid-case-false-positive")

    print("=" * 78)
    if failures:
        print("FAILED: " + ", ".join(failures))
        print()
        print("I1 is deliberately untouched. The artifact holds 550 sweep rows and")
        print("10,000 mc rows that do not overlap at the same nominal SNR, and the")
        print("paper does not say which population its >4 bps/Hz claim refers to.")
        print("That is an internal correspondence question, not a stale number.")
        return 1
    print("PASSED: the validation introduces independent evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())


import importlib.util
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "isac_simulator.py"

SCALE = 4.0
N_REALIZATIONS = 20000
SEED = 20260930


def load_module():
    spec = importlib.util.spec_from_file_location("isac_i6f", TARGET)
    module = importlib.util.module_from_spec(spec)
    sys.modules["isac_i6f"] = module
    spec.loader.exec_module(module)
    return module


def measure_error_dispersion(error_source, params, snr_lin, n=N_REALIZATIONS, seed=SEED):
    """Dispersion of the estimator error relative to the bound, under one
    generator. `error_source(params, snr_meas, R_true)` returns R_est."""
    np.random.seed(seed)
    ratios = []
    for _ in range(n):
        R_true = 100.0
        snr_meas = snr_lin * (1 + np.random.randn() * 0.15)
        R_est = error_source(params, snr_meas, R_true)
        bound = module_bound(params, snr_lin)
        if bound > 0:
            ratios.append(abs(R_est - R_true) / bound)
    return float(np.mean(ratios)), float(np.std(ratios))


# The bound is looked up through a single indirection so that scaling it is a
# genuine intervention on the reference, not a local edit inside the probe.
_MODULE = {"m": None}


def module_bound(params, snr_lin):
    return _MODULE["m"].crlb_range(params, snr_lin)


def scaled_bound_factory(m, factor):
    """Return (bound_fn) that reports the package bound multiplied by factor."""
    original = m.crlb_range

    def scaled(params, snr_lin):
        return original(params, snr_lin) * factor

    return scaled, original


def main():
    print("property: a validation introduces evidence independent of the")
    print("         construction it validates")
    print("=" * 78)

    module = load_module()
    _MODULE["m"] = module
    params = module.ISACParams()
    snr_lin = 10 ** (0 / 10)
    failures = []

    # The package's own estimator, as a callable.
    def package_estimator(p, snr_meas, R_true):
        return R_true + np.random.randn() * module.crlb_range(p, snr_meas)

    # An independent estimator: its error process does not read the bound.
    def independent_estimator(p, snr_meas, R_true):
        _ = snr_meas          # the noise level is deliberately not consulted
        return R_true + np.random.randn() * 0.6

    # --- F1: the package's construction is circular -------------------------
    print(f"  [INFO] F1 intervention: scale the reference bound by {SCALE:g} and")
    print(f"         re-measure the estimator's dispersion against it.")
    base_ratio, base_sd = measure_error_dispersion(package_estimator, params, snr_lin)

    scaled, original = scaled_bound_factory(module, SCALE)
    module.crlb_range = scaled
    try:
        scaled_ratio, scaled_sd = measure_error_dispersion(package_estimator, params, snr_lin)
    finally:
        module.crlb_range = original

    print(f"         mean error/bound at 1x bound : {base_ratio:.6f}  (sd {base_sd:.6f})")
    print(f"         mean error/bound at {SCALE:g}x bound : {scaled_ratio:.6f}  "
          f"(sd {scaled_sd:.6f})")

    # Circularity signature: the error is a fixed multiple of whatever the bound
    # says, so scaling the bound scales the error and the ratio holds still.
    ratio_preserved = abs(scaled_ratio - base_ratio) < 0.02
    if ratio_preserved:
        print(f"  [FAIL] F1 the estimator's error is a fixed multiple of the reference "
              f"bound.")
        print(f"         The ratio is unchanged when the bound is scaled by {SCALE:g} "
              f"({base_ratio:.4f} -> {scaled_ratio:.4f}),")
        print(f"         which is only possible if the error is drawn from the bound. "
              f"Detected by")
        print(f"         intervention, not by reading the source.")
        print(f"         Consequence: the CRLB comparison in this package is not "
              f"evidence of")
        print(f"         anything. The bound is an input to the measurement it is used "
              f"to judge.")
        failures.append("F1-estimator-draws-from-bound")
    else:
        print(f"  [PASS] F1 the estimator's error does not track the reference bound")

    # --- F2: positive control — an independent generator must pass -----------
    ind_base, _ = measure_error_dispersion(independent_estimator, params, snr_lin)
    module.crlb_range = scaled
    try:
        ind_scaled, _ = measure_error_dispersion(independent_estimator, params, snr_lin)
    finally:
        module.crlb_range = original

    ind_moved = abs(ind_scaled - ind_base) > 0.02
    print(f"  [INFO] F2 positive control, independent generator: "
          f"{ind_base:.6f} -> {ind_scaled:.6f} under the same scaling")
    if ind_moved:
        print(f"  [PASS] F2 the instrument can distinguish an independent construction; "
              f"its error")
        print(f"           responded to the intervention while the package's did not.")
        print(f"           A test that cannot pass anything would be indistinguishable "
              f"from one that")
        print(f"           fails everything.")
    else:
        print(f"  [FAIL] F2 the instrument cannot distinguish an independent "
              f"construction from")
        print(f"         the circular one. F1 would then be reporting the instrument's "
              f"blindness,")
        print(f"         not the package's defect.")
        failures.append("F2-instrument-blind")

    # --- F3a: can the package express a violation at all? -------------------
    # The original F3 asked this and reported PASS. It passed for the wrong
    # reason -- the ratio exceeded 1 through the F3b argument mismatch rather
    # than through any property of the construction -- so it was not evidence of
    # anything and has been split rather than kept.
    #
    # F3a asks the narrow question: evaluated like-for-like, can this
    # construction register a bound violation, and can it register a pass? A
    # pipeline that can do neither is a statement about its generator, not about
    # the estimator.
    print(f"  [INFO] F3a evaluated like-for-like, can a violation and a pass both be")
    print(f"          expressed?")
    np.random.seed(SEED)
    bound_lfl = module.crlb_range(params, snr_lin)
    like_for_like = []
    for _ in range(N_REALIZATIONS):
        R_true = 100.0
        snr_meas = snr_lin * (1 + np.random.randn() * 0.15)
        # error drawn from the bound at the SAME argument the reference uses
        R_est = R_true + np.random.randn() * module.crlb_range(params, snr_lin)
        like_for_like.append(abs(R_est - R_true) / bound_lfl)
    lfl = np.array(like_for_like)
    violation_frac = float((lfl > 1.0).mean())
    print(f"          fraction of realizations violating the bound: {violation_frac:.4f}")
    print(f"          max ratio {lfl.max():.4f}")
    if 0.0 < violation_frac < 1.0:
        print(f"  [PASS] F3a both outcomes are expressible: {violation_frac:.4f} of "
              f"realizations exceed the")
        print(f"           bound and the rest do not, so the construction can register "
              f"either verdict.")
    else:
        print(f"  [FAIL] F3a the construction can only ever produce one verdict "
              f"({violation_frac:.4f} violating)")
        failures.append("F3a-single-verdict-only")

    # Positive control: an independent source must also express both.
    np.random.seed(SEED)
    ind_lfl = []
    for _ in range(N_REALIZATIONS):
        R_true = 100.0
        ind_lfl.append(abs(independent_estimator(params, snr_lin, R_true) - R_true)
                       / bound_lfl)
    ind_lfl = np.array(ind_lfl)
    ind_violation = float((ind_lfl > 1.0).mean())
    print(f"  [INFO] F3a independent source violates in {ind_violation:.4f} of "
          f"realizations")
    if 0.0 < ind_violation < 1.0:
        print(f"  [PASS] F3a the independent source expresses both verdicts too, so "
              f"the probe")
        print(f"           discriminates rather than always agreeing.")
    else:
        print(f"  [FAIL] F3a the independent source collapsed to a single verdict")
        failures.append("F3a-control-single-verdict")

    # --- F3b: is the reference evaluated at the same point as the error? -----
    # The second defect, discovered because the original F3 passed unexpectedly.
    # The package generates the error with crlb_range(params, snr_meas) at the
    # NOISY measured SNR, while the artifact reports crlb_range(params, snr_lin)
    # at the CLEAN set SNR. Those are two different points, so the published
    # comparison is not like-for-like.
    #
    # Detected by intervention rather than by argument inspection: perturb ONLY
    # the dispersion of the measured-SNR noise and leave the reference untouched.
    # If the estimator's error responds, the error was produced at the noisy
    # point, and the clean-SNR reference is measuring something else.
    print(f"  [INFO] F3b perturb only the measured-SNR noise and watch the error:")
    # The base SNR is raised and the noise scales kept modest on purpose. The
    # first version of this probe used 0 dB with noise scales 0.15 and 0.30 and
    # reported an error dispersion of 1.4e13, which looked like a dramatic
    # demonstration and was in fact a third defect contaminating the second.
    # crlb_range guards its divisor with max(snr_lin, 1e-30), which converts a
    # NEGATIVE measured SNR into a near-zero positive one instead of rejecting
    # it, so the bound becomes astronomically large and dominates the statistic.
    # At 0 dB a 0.30 noise scale drives snr_meas negative often enough to trigger
    # that. Running the mismatch at a base SNR where snr_meas stays positive
    # separates the two signals.
    base_snr_lin = 10 ** (10 / 10)
    def error_std_at_noise_scale(noise_scale, seed=SEED, n=8000, base=base_snr_lin):
        np.random.seed(seed)
        vals = []
        for _ in range(n):
            R_true = 100.0
            snr_meas = base * (1 + np.random.randn() * noise_scale)
            R_est = R_true + np.random.randn() * module.crlb_range(params, snr_meas)
            vals.append(abs(R_est - R_true))
        return float(np.std(vals))

    print(f"          base SNR +10 dB, noise scales chosen so snr_meas stays positive")
    pkg_lo = error_std_at_noise_scale(0.10)
    pkg_hi = error_std_at_noise_scale(0.20)
    moved = abs(pkg_hi - pkg_lo) > 1e-6

    np.random.seed(SEED)
    ind_lo = float(np.std([abs(independent_estimator(params, snr_lin, 100.0) - 100.0)
                           for _ in range(8000)]))

    print(f"          package error sd at noise 0.10 : {pkg_lo:.6f}")
    print(f"          package error sd at noise 0.20 : {pkg_hi:.6f}")
    print(f"          independent error sd            : {ind_lo:.6f}  (unaffected by noise)")

    if moved:
        print(f"  [FAIL] F3b the estimator's error is produced at the noisy measured "
              f"SNR, while the")
        print(f"           reference the artifact reports is evaluated at the clean set "
              f"SNR. Perturbing")
        print(f"           only the measured-SNR noise moved the error "
              f"({pkg_lo:.6f} -> {pkg_hi:.6f}), so")
        print(f"           the two quantities are not being compared at the same point.")
        print(f"           This is a SECOND defect, independent of F1's circularity: even")
        print(f"           a correct reference would be miscompared here. The original "
              f"F3 passed for")
        print(f"           this reason, which is why it had to be split.")
        failures.append("F3b-reference-evaluated-at-different-point")
    else:
        print(f"  [PASS] F3b the error and the reference are evaluated at the same point")

    # --- F4: the valid independent case must not be flagged -----------------
    print(f"  [INFO] F4 valid independent case (error well inside the bound):")
    np.random.seed(SEED)
    valid_ratio, _ = measure_error_dispersion(independent_estimator, params, snr_lin)
    flagged = valid_ratio > 1.0
    if not flagged:
        print(f"  [PASS] F4 an independent estimator inside the bound is not flagged "
              f"(ratio {valid_ratio:.4f})")
    else:
        print(f"  [FAIL] F4 a valid independent case was flagged (ratio "
              f"{valid_ratio:.4f}); the test would")
        print(f"         reject sound measurements and is therefore unusable as a gate")
        failures.append("F4-valid-case-false-positive")

    print("=" * 78)
    if failures:
        print("FAILED: " + ", ".join(failures))
        print()
        print("I1 is deliberately untouched. The artifact holds 550 sweep rows and")
        print("10,000 mc rows that do not overlap at the same nominal SNR, and the")
        print("paper does not say which population its >4 bps/Hz claim refers to.")
        print("That is an internal correspondence question, not a stale number.")
        return 1
    print("PASSED: the validation introduces independent evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
