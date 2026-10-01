property: a validation introduces evidence independent of the
         construction it validates
==============================================================================
  [INFO] F1 intervention: scale the reference bound by 4 and
         re-measure the estimator's dispersion against it.
         mean error/bound at 1x bound : 0.801254  (sd 0.614870)
         mean error/bound at 4x bound : 0.801254  (sd 0.614870)
  [FAIL] F1 the estimator's error is a fixed multiple of the reference bound.
         The ratio is unchanged when the bound is scaled by 4 (0.8013 -> 0.8013),
         which is only possible if the error is drawn from the bound. Detected by
         intervention, not by reading the source.
         Consequence: the CRLB comparison in this package is not evidence of
         anything. The bound is an input to the measurement it is used to judge.
  [INFO] F2 positive control, independent generator: 0.449374 -> 0.112344 under the same scaling
  [PASS] F2 the instrument can distinguish an independent construction; its error
           responded to the intervention while the package's did not.
           A test that cannot pass anything would be indistinguishable from one that
           fails everything.
  [INFO] F3 can this package express an error that violates its own bound?
         max error/bound, package construction  : 4.400178
         max error/bound, independent generator: 2.465785
  [PASS] F3 a violation is expressible and was observed
  [INFO] F4 valid independent case (error well inside the bound):
  [PASS] F4 an independent estimator inside the bound is not flagged (ratio 0.4494)
==============================================================================
FAILED: F1-estimator-draws-from-bound

I1 is deliberately untouched. The artifact holds 550 sweep rows and
10,000 mc rows that do not overlap at the same nominal SNR, and the
paper does not say which population its >4 bps/Hz claim refers to.
That is an internal correspondence question, not a stale number.
