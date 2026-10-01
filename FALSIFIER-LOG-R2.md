property: a published figure is a deterministic function of a named
         experimental artifact, produced by the same run
==============================================================================
  [INFO] R2-F1 perturb one artifact value and re-render:
  [FAIL] R2-F1 no lineage-carrying figure generator exists; Figure 5 is still
         plotted from an independent numpy.random call
  [INFO] R2-F2 disable the global RNG and re-render:
  [INFO] R2-F3 does the artifact carry the quantities a range-Doppler figure needs?
           artifact columns present : []
           artifact columns missing : ['R_true', 'v_true', 'R_est', 'v_est']
  [FAIL] R2-F3 the committed artifact does not carry ['R_true', 'v_true', 'R_est', 'v_est'].
         A figure cannot be traceable to quantities the run does not publish, so
         R2 requires the artifact to gain them before any figure can have lineage.
  [INFO] R2-F4 same input, same figure:
  [INFO] R2-F5 does the figure stage call back into the simulator?
  [INFO] R2-F6 root-level and figures/ copies of each figure:
           fig1_sensing_comm_tradeoff.pdf: DIFFERENT
           fig2_crlb_analysis.pdf: DIFFERENT
           fig3_spectral_efficiency.pdf: DIFFERENT
           fig4_application_scenarios.pdf: DIFFERENT
           fig5_range_doppler_map.pdf: DIFFERENT
  [FAIL] R2-F6 5 figure(s) exist in two divergent copies: fig1_sensing_comm_tradeoff.pdf, fig2_crlb_analysis.pdf, fig3_spectral_efficiency.pdf, fig4_application_scenarios.pdf, fig5_range_doppler_map.pdf
         main.tex reads figures/ and presentation.tex reads the root, so the paper and
         the presentation show different bytes for the same figures.
==============================================================================
FAILED: F1-no-lineage-generator, F3-artifact-lacks-true-and-estimates, F6-duplicate-divergent-figures

R2 does not attempt to make Figure 5 resemble anything. If the
experiment cannot supply what a range-Doppler map needs, the honest
outcome is NEW EXPERIMENT REQUIRED, not a better-looking plot.
