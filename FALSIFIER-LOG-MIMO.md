property: the MIMO claim's required capability is either present in
         the package or recorded as absent coverage
==============================================================================
  [INFO] C1 ISACParams fields: 15
           b, code_rate, delta_f, fc, g_rx, g_tx, m_mod, n_sub, n_sym, nf, p_tx_dbm, p_tx_w, t0, t_cp, t_sym
  [PASS] C1 no antenna count and no spatial-stream count in the parameters
  [INFO] C2 comm_sinr(params: isac_mimo.ISACParams, R: float) -> float
  [PASS] C2 the channel model returns a scalar SINR from range alone; it has no
           channel matrix and no antenna-count argument, so 4x4 is not expressible
  [PASS] C3 spectral_efficiency takes a scalar SINR; a channel matrix could not
           be passed, so MIMO multiplexing has no path to SE
  [INFO] C4 artifact columns: snr_db,pe,ber,se,sinr_db,crlb_r,crlb_v,type,r_true,v_true,r_est,v_est,snr_lin,sinr_lin,snr_cmp_lin
  [PASS] C4 no artifact column can carry a spatial-multiplexing result
  [INFO] C5 adjudication:
           main.tex L278 claims '>10 bps/Hz' with 4x4 spatial multiplexing.
           C1-C4 establish that the package contains no 4x4 configuration,
           no channel matrix, no path from a matrix to SE, and no artifact
           column that could hold such a result.
           Disposition: NOT VERIFIED / NEW EXPERIMENT REQUIRED -- NO PACKAGE
           COVERAGE. Not CONTRADICTED: the package cannot speak to the claim
           in either direction, and recording it as false would assert
           something the evidence does not support.
           No 4x4 experiment is written to rescue the claim. Inventing one
           during an audit would produce a number with no evidentiary
           standing.
==============================================================================
PASSED: MIMO coverage is absent and recorded as such, not as a refutation
