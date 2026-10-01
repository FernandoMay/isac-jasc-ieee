property: the estimator is independent of the bound, the comparison uses one SNR
         state, and invalid inputs are rejected rather than clamped
==============================================================================
  [INFO] R1-F1 scale the reference bound by 4 and re-measure the estimator.
  [FAIL] R1-F1 no independent estimator exists; the package still draws the
         estimator's error from crlb_range
  [INFO] R1-F2 reproducibility of the independent estimator:
  [INFO] R1-F3 does the package define a single comparison SNR?
  [FAIL] R1-F3 no comparison_snr exists. The pre-fix code evaluated the error at
         the noisy measured SNR and the reference at the clean set SNR, so the ratio
         compared two different states. A single named state must be defined and used
         by both sides.
  [INFO] R1-F4 what happens when the bound is asked for snr <= 0:
  [FAIL] R1-F4 the package declares no rejection type. Pre-fix, crlb_range guarded its
         divisor with max(snr_lin, 1e-30), which converts a negative physical SNR into a
         near-zero positive one and returns a finite bound of order 1e15. An invalid
         input must not produce an apparently valid statistic.
  [INFO] R1-F5 a valid scenario still produces a finite, finite-valued estimate:
  [INFO] R1-F6 two runs from the same seed agree:
  [INFO] R1-F7 does the estimator import or call the bound?
==============================================================================
FAILED: F1-no-independent-estimator, F3-no-comparison-point, F4-no-rejection-type

No ratio is targeted. R1a repairs what the manuscript says the estimator
is -- a delay estimator on the OFDM waveform of eq. (rx_sensing) -- and
leaves the bound as a reference computed afterwards from the same state.
