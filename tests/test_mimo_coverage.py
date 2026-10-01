#!/usr/bin/env python3
"""ISAC MIMO coverage falsifier.

Property under test.

    A claim resting on a capability the package does not contain cannot be
    adjudicated from that package. This test establishes whether the capability
    is present.

The manuscript claims, at main.tex L278:

    "With MIMO extensions (4x4 spatial multiplexing), the achievable SE scales
     to >10 bps/Hz."

Present status, to be established here rather than assumed: no antenna count in
the parameters, no spatial-stream count, no channel matrix, no MIMO signal model,
no 4x4 parameterisation, and no artifact column that could carry such a result.

**This is a coverage question, not a truth question.** "The package contains no
4x4 experiment" is not "the claim is false". The disposition is NOT VERIFIED /
NEW EXPERIMENT REQUIRED -- NO PACKAGE COVERAGE, and the distinction matters: an
audit that recorded the claim as contradicted would be asserting that the paper
claims something untrue, when the correct statement is that the package cannot
speak to it either way.

No experiment is written to rescue the claim. Inventing a 4x4 model during an
audit would produce a number with no evidentiary standing and would contaminate
the package with a configuration the manuscript's own method section never
specified.

Behavioural where behaviour can carry it, and structural only where it cannot:
a dataclass's fields are read, a function's call signature is inspected, and the
artifact's header is read. Nothing here greps for the word "MIMO" in prose,
because a docstring mentioning it would be indistinguishable from an
implementation.
"""

import csv
import importlib.util
import inspect
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "isac_simulator.py"
ARTIFACT = ROOT / "isac_experiment_results.csv"

ANTENNA_TERMS = ("n_ant", "n_antenna", "n_tx_ant", "n_rx_ant", "ntx", "nrx",
                  "n_spatial_stream", "n_streams", "mimo", "mimo_order")
MATRIX_TERMS = ("H", "channel_matrix", "h_matrix", "spatial_covariance",
                "R_h", "svd", "eigen")


def load_module():
    spec = importlib.util.spec_from_file_location("isac_mimo", TARGET)
    module = importlib.util.module_from_spec(spec)
    sys.modules["isac_mimo"] = module
    spec.loader.exec_module(module)
    return module


def main():
    print("property: the MIMO claim's required capability is either present in")
    print("         the package or recorded as absent coverage")
    print("=" * 78)

    module = load_module()
    failures = []

    # --- C1: antenna / stream configuration in the parameters --------------
    fields = set()
    params_type = getattr(module, "ISACParams", None)
    if params_type is None:
        print("  [FAIL] C1 ISACParams is absent; the package exposes no parameter type")
        failures.append("C1-no-params-type")
    else:
        fields = {f.name.lower() for f in
                  __import__("dataclasses").fields(params_type)}
        antenna = sorted(t for t in ANTENNA_TERMS
                         if any(t in f for f in fields))
        print(f"  [INFO] C1 ISACParams fields: {len(fields)}")
        print(f"           {', '.join(sorted(fields))}")
        if antenna:
            print(f"  [FAIL] C1 antenna/stream parameter(s) present: {antenna}")
            failures.append("C1-antenna-params-present")
        else:
            print(f"  [PASS] C1 no antenna count and no spatial-stream count in the "
                  f"parameters")

    # --- C2: the channel model signature ------------------------------------
    comm = getattr(module, "comm_sinr", None)
    if comm is None:
        print(f"  [FAIL] C2 comm_sinr absent")
        failures.append("C2-no-comm-model")
    else:
        sig = inspect.signature(comm)
        print(f"  [INFO] C2 comm_sinr{sig}")
        takes_matrix = any(t in sig.parameters for t in MATRIX_TERMS)
        takes_count = any(t in sig.parameters for t in ANTENNA_TERMS)
        if takes_matrix or takes_count:
            print(f"  [FAIL] C2 the channel model accepts a matrix or an antenna count, "
                  f"so spatial")
            print(f"         multiplexing could be expressed through it")
            failures.append("C2-channel-model-supports-spatial")
        else:
            print(f"  [PASS] C2 the channel model returns a scalar SINR from range alone; "
                  f"it has no")
            print(f"           channel matrix and no antenna-count argument, so 4x4 is "
                  f"not expressible")

    # --- C3: the SE function cannot receive a matrix ------------------------
    se_fn = getattr(module, "spectral_efficiency", None)
    if se_fn is None:
        print(f"  [FAIL] C3 spectral_efficiency absent")
        failures.append("C3-no-se-function")
    else:
        src = inspect.getsource(se_fn)
        body = "\n".join(ln for ln in src.splitlines()
                         if not ln.strip().startswith(('#', '"""', "'''")))
        scalar = "sinr_lin < 1e-30" in body or "sinr_lin <=" in body
        if scalar and not any(t in body for t in MATRIX_TERMS):
            print(f"  [PASS] C3 spectral_efficiency takes a scalar SINR; a channel "
                  f"matrix could not")
            print(f"           be passed, so MIMO multiplexing has no path to SE")
        else:
            print(f"  [FAIL] C3 spectral_efficiency's body does not look scalar-only; a "
                  f"spatial")
            print(f"         channel may be representable")
            failures.append("C3-se-not-scalar")

    # --- C4: the artifact carries no MIMO output ----------------------------
    if not ARTIFACT.exists():
        print(f"  [FAIL] C4 artifact absent")
        failures.append("C4-no-artifact")
    else:
        header = ARTIFACT.read_text().splitlines()[0].lower()
        print(f"  [INFO] C4 artifact columns: {header}")
        cols = [c.strip() for c in header.split(",")]
        mimo_cols = [c for c in cols
                     if any(t in c for t in ANTENNA_TERMS + MATRIX_TERMS)]
        if mimo_cols:
            print(f"  [FAIL] C4 artifact carries MIMO-related column(s): {mimo_cols}")
            failures.append("C4-mimo-columns")
        else:
            print(f"  [PASS] C4 no artifact column can carry a spatial-multiplexing "
                  f"result")

    # --- C5: the disposition is coverage, not truth -------------------------
    print(f"  [INFO] C5 adjudication:")
    print(f"           main.tex L278 claims '>10 bps/Hz' with 4x4 spatial multiplexing.")
    print(f"           C1-C4 establish that the package contains no 4x4 configuration,")
    print(f"           no channel matrix, no path from a matrix to SE, and no artifact")
    print(f"           column that could hold such a result.")
    print(f"           Disposition: NOT VERIFIED / NEW EXPERIMENT REQUIRED -- NO PACKAGE")
    print(f"           COVERAGE. Not CONTRADICTED: the package cannot speak to the claim")
    print(f"           in either direction, and recording it as false would assert")
    print(f"           something the evidence does not support.")
    print(f"           No 4x4 experiment is written to rescue the claim. Inventing one")
    print(f"           during an audit would produce a number with no evidentiary")
    print(f"           standing.")

    print("=" * 78)
    if failures:
        print("FAILED: " + ", ".join(failures))
        print()
        print("Coverage is present, so the claim is adjudicable and must be adjudicated")
        print("against evidence rather than filed as out of scope.")
        return 1
    print("PASSED: MIMO coverage is absent and recorded as such, not as a refutation")
    return 0


if __name__ == "__main__":
    sys.exit(main())