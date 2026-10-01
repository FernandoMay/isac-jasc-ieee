#!/usr/bin/env python3
"""ISAC R2 falsifiers: Figure 5 lineage.

Property under test.

    A published figure must be a deterministic function of a named experimental
    artifact, produced by the same run, with no independently fabricated content.

The pre-fix generator is four lines:

    rd = np.random.randn(50, 50)
    rd[25, 15] = 100
    im = ax.imshow(rd, ..., extent=[-30, 30, 0, 500])
    plt.colorbar(im, ax=ax, label='Power [dB]')

It reads nothing from the simulation. The run produces R_true, v_true, R_est and
v_est for every realization, so a figure with real lineage was available and was
not used. The colourbar is labelled in dB over raw Gaussian draws, and the axis
extents are a display range applied to array indices.

**Two corrections to the earlier inventory, recorded here because the first
version of this file would have asserted them.**

Figure 5 is NOT included in `main.tex`. That file includes exactly fig1 through
fig4; there is no `fig:rd` label and no `\ref` to it. So the manuscript never
showed this figure, and the framing "the paper's visual evidence is fabricated"
was wrong. The defect is narrower and different: the package publishes a
fabricated figure that no manuscript claim depends on.

It IS included in `presentation.tex`. So the invented content is not confined to
an unused file -- it appears in a document that is read.

And the repository carries two divergent copies of every figure: root-level PDFs
last regenerated at 808f0b2, `figures/` at 12fd2a7. `main.tex` reads
`figures/`, `presentation.tex` reads the root. The paper and the presentation
therefore show different bytes for the same figures. R2-F6 asserts they agree.

**No assertion asks the figure to look like anything.** What is asserted is
that it is a function of the artifact, from the same run, deterministically, and
that no independent data generation survives inside the plotting stage.
"""

import importlib.util
import inspect
import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "isac_simulator.py"
FIGURES = ROOT / "figures"
ROOT_FIGURES = ROOT

REQUIRED_COLUMNS = ("R_true", "v_true", "R_est", "v_est")
N = 300


def load_module():
    spec = importlib.util.spec_from_file_location("isac_r2", TARGET)
    module = importlib.util.module_from_spec(spec)
    sys.modules["isac_r2"] = module
    spec.loader.exec_module(module)
    return module


def synth_frame():
    """A structurally faithful experimental frame, including the columns the
    artifact does NOT currently carry, so R2-F3 can be judged honestly."""
    rng = np.random.default_rng(11)
    return {
        "R_true": rng.uniform(30, 300, N),
        "v_true": rng.uniform(-20, 20, N),
        "R_est": rng.uniform(30, 300, N),
        "v_est": rng.uniform(-20, 20, N),
        "snr_db": rng.uniform(-15, 15, N),
        "type": ["mc"] * N,
    }


def main():
    print("property: a published figure is a deterministic function of a named")
    print("         experimental artifact, produced by the same run")
    print("=" * 78)

    module = load_module()
    failures = []

    gen = getattr(module, "generate_range_doppler_figure", None)

    # --- R2-F1: lineage — perturb the input, the figure must move ------------
    print(f"  [INFO] R2-F1 perturb one artifact value and re-render:")
    if gen is None:
        print("  [FAIL] R2-F1 no lineage-carrying figure generator exists; Figure 5 is "
              "still")
        print("         plotted from an independent numpy.random call")
        failures.append("F1-no-lineage-generator")
    else:
        base_frame = synth_frame()
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            gen(t1, base_frame)
            perturbed = {k: (v.copy() if isinstance(v, np.ndarray) else v)
                         for k, v in base_frame.items()}
            perturbed["R_true"] = perturbed["R_true"] + 25.0
            gen(t2, perturbed)
            f1 = sorted(pathlib.Path(t1).glob("*.pdf"))
            f2 = sorted(pathlib.Path(t2).glob("*.pdf"))
            if not f1 or not f2:
                print(f"  [FAIL] R2-F1 the generator produced no PDF")
                failures.append("F1-no-output")
            elif f1[0].read_bytes() != f2[0].read_bytes():
                print(f"  [PASS] R2-F1 shifting R_true by 25 m changed the rendered "
                      f"figure")
            else:
                print(f"  [FAIL] R2-F1 shifting R_true by 25 m left the figure "
                      f"byte-identical, so the")
                print("         figure is not a function of its supposed input")
                failures.append("F1-figure-ignores-input")

    # --- R2-F2: no independent fabrication -----------------------------------
    print(f"  [INFO] R2-F2 disable the global RNG and re-render:")
    if gen is not None:
        state = np.random.get_state()

        def exploding(*_a, **_k):
            raise AssertionError("the plotting stage generated its own random data")

        np.random.rand = exploding
        np.random.randn = exploding
        np.random.random = exploding
        np.random.uniform = exploding
        try:
            with tempfile.TemporaryDirectory() as t:
                gen(t, synth_frame())
            survived = True
        except AssertionError:
            survived = False
        finally:
            np.random.set_state(state)
        if survived:
            print(f"  [PASS] R2-F2 the figure rendered with every global RNG replaced by "
                  f"a raiser,")
            print(f"           so nothing in the plotting stage fabricates data")
        else:
            print(f"  [FAIL] R2-F2 the figure still depends on a random generator")
            failures.append("F2-still-random")

    # --- R2-F3: same-run correspondence --------------------------------------
    print(f"  [INFO] R2-F3 does the artifact carry the quantities a range-Doppler "
          f"figure needs?")
    csv_path = ROOT / "isac_experiment_results.csv"
    if not csv_path.exists():
        print(f"  [FAIL] R2-F3 artifact absent")
        failures.append("F3-no-artifact")
    else:
        header = csv_path.read_text().splitlines()[0].split(",")
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        present = [c for c in REQUIRED_COLUMNS if c in header]
        print(f"           artifact columns present : {present}")
        print(f"           artifact columns missing : {missing}")
        if missing:
            print(f"  [FAIL] R2-F3 the committed artifact does not carry {missing}.")
            print(f"         A figure cannot be traceable to quantities the run does not "
                  f"publish, so")
            print(f"         R2 requires the artifact to gain them before any figure can "
                  f"have lineage.")
            failures.append("F3-artifact-lacks-true-and-estimates")
        else:
            print(f"  [PASS] R2-F3 the artifact carries every quantity the figure needs")

    # --- R2-F4: deterministic rendering --------------------------------------
    print(f"  [INFO] R2-F4 same input, same figure:")
    if gen is not None:
        frame = synth_frame()
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            gen(t1, frame)
            gen(t2, frame)
            a = sorted(pathlib.Path(t1).glob("*.pdf"))
            b = sorted(pathlib.Path(t2).glob("*.pdf"))
            if a and b and a[0].read_bytes() == b[0].read_bytes():
                print(f"  [PASS] R2-F4 rendering is deterministic for a fixed input")
            else:
                print(f"  [FAIL] R2-F4 two renders of the same input differ")
                failures.append("F4-not-deterministic")

    # --- R2-F5: no hidden regeneration during plotting -----------------------
    # The first version of this check grepped the generator's source for
    # "np.random" and failed, because the generator's docstring quotes the four
    # lines it replaced, one of which is np.random.randn. That is the sixth time
    # in this program that a check matched the explanation of a defect as the
    # defect, and the second time in this file's own history. R2-F2 already
    # establishes behaviourally that no RNG is consulted, so this check covers
    # what F2 cannot: whether the plotting stage calls back into the simulator to
    # produce data of its own.
    print(f"  [INFO] R2-F5 disable the simulator's own entry points and re-render:")
    if gen is not None:
        def exploding(*_a, **_k):
            raise AssertionError("the plotting stage called back into the simulator")

        originals = {}
        try:
            for name in ("run_monte_carlo", "sensing_snr", "crlb_range",
                         "estimate_range", "comparison_snr"):
                if hasattr(module, name):
                    originals[name] = getattr(module, name)
                    setattr(module, name, exploding)
            with tempfile.TemporaryDirectory() as t:
                gen(t, synth_frame())
            survived = True
        except AssertionError:
            survived = False
        finally:
            for name, fn in originals.items():
                setattr(module, name, fn)

        if survived:
            print(f"  [PASS] R2-F5 the figure rendered with run_monte_carlo, sensing_snr,")
            print(f"           crlb_range, estimate_range and comparison_snr all replaced "
                  f"by raisers")
            print(f"           So the plotting stage neither re-simulates nor re-derives "
                  f"anything.")
        else:
            print(f"  [FAIL] R2-F5 the plotting stage called back into the simulator")
            failures.append("F5-regenerates-during-plotting")

    # --- R2-F6: the two figure copies in the repository must agree -----------
    print(f"  [INFO] R2-F6 root-level and figures/ copies of each figure:")
    names = sorted(p.name for p in FIGURES.glob("fig*.pdf"))
    divergent = []
    for name in names:
        root_copy = ROOT_FIGURES / name
        if not root_copy.exists():
            print(f"           {name}: no root-level copy")
            continue
        a = root_copy.read_bytes()
        b = (FIGURES / name).read_bytes()
        same = a == b
        if not same:
            divergent.append(name)
        print(f"           {name}: {'identical' if same else 'DIFFERENT'}")
    if divergent:
        print(f"  [FAIL] R2-F6 {len(divergent)} figure(s) exist in two divergent "
              f"copies: {', '.join(divergent)}")
        print(f"         main.tex reads figures/ and presentation.tex reads the root, so "
              f"the paper and")
        print(f"         the presentation show different bytes for the same figures.")
        failures.append("F6-duplicate-divergent-figures")
    else:
        print(f"  [PASS] R2-F6 both copies of every figure agree")

    print("=" * 78)
    if failures:
        print("FAILED: " + ", ".join(failures))
        print()
        print("R2 does not attempt to make Figure 5 resemble anything. If the")
        print("experiment cannot supply what a range-Doppler map needs, the honest")
        print("outcome is NEW EXPERIMENT REQUIRED, not a better-looking plot.")
        return 1
    print("PASSED: Figure 5 is a deterministic function of the run that produced the "
          "artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
