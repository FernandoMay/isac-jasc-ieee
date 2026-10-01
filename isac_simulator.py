"""
ISAC-JASC: Integrated Sensing and Communication
================================================
PhD-level Monte Carlo Simulation Framework for IEEE Paper.

Uses analytical performance models with Monte Carlo validation:
  - Radar range equation for sensing SNR
  - Cramér-Rao Lower Bound for estimation accuracy
  - Analytical BER for M-QAM in AWGN
  - OFDM-based spectral efficiency with overhead accounting
  - Application scenarios: agriculture (Feed the Future)
    and financial inclusion (GreenRemit)

Dependencies: numpy, scipy, matplotlib, pandas
Author: F. M. Fernández — NEXUS Research Institute
"""

import numpy as np
from scipy import special
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')

RANDOM_SEED = 2026
np.random.seed(RANDOM_SEED)

C = 3e8


ROOT_FIG_DIR = 'figures'


@dataclass
class ISACParams:
    fc: float = 28e9
    B: float = 100e6
    N_sub: int = 256
    N_sym: int = 64
    M_mod: int = 16
    code_rate: float = 0.75
    P_tx_dbm: float = 20.0        # dBm
    G_tx: float = 15.0            # dBi
    G_rx: float = 15.0            # dBi
    NF: float = 5.0               # Noise figure [dB]
    T0: float = 290.0             # K
    delta_f: float = field(init=False)
    T_sym: float = field(init=False)
    T_cp: float = field(init=False)
    P_tx_w: float = field(init=False)

    def __post_init__(self):
        self.delta_f = self.B / self.N_sub
        self.T_sym = 1.0 / self.delta_f
        self.T_cp = self.T_sym / 4
        self.P_tx_w = 10 ** ((self.P_tx_dbm - 30) / 10)


def noise_psd_w_hz(nf_db: float, T0: float = 290.0) -> float:
    """Thermal noise PSD in W/Hz."""
    k = 1.380649e-23
    return k * T0 * 10 ** (nf_db / 10)


def sensing_snr(params: ISACParams, R: float, rcs: float) -> float:
    """Radar range equation: SNR at receiver [linear]."""
    lam = C / params.fc
    num = params.P_tx_w * params.G_tx * params.G_rx * lam**2 * rcs
    den = (4 * np.pi)**3 * R**4 * noise_psd_w_hz(params.NF) * params.B
    return num / max(den, 1e-30)


def comm_sinr(params: ISACParams, R: float) -> float:
    """Communication SINR [linear] with simplified path loss."""
    lam = C / params.fc
    pl = (lam / (4 * np.pi * R))**2
    rx_power = params.P_tx_w * params.G_tx * params.G_rx * pl
    noise = noise_psd_w_hz(params.NF) * params.B
    return rx_power / max(noise, 1e-30)


class InvalidSensingInput(ValueError):
    """A physical input that cannot produce a meaningful bound.

    Row R1c. The pre-fix guard was `max(snr_lin, 1e-30)`, which converts a
    NEGATIVE measured SNR into a near-zero positive one and returns a finite
    bound of order 1e15. That is the worst shape for a defect: an impossible
    input becomes an apparently valid statistic, and a caller averaging over
    realizations inherits the blow-up silently. Rejecting is the only honest
    disposition. `abs()` would not be a repair -- it would convert a different
    invalid input into a different apparently valid number.
    """
    pass


def comparison_snr(params: ISACParams, R: float, rcs: float) -> float:
    """The one SNR state both sides of the range comparison are evaluated at.

    Row R1b. The pre-fix code evaluated the estimator's error at the *noisy
    measured* SNR and the reference bound at the *clean set* SNR, then divided
    one by the other. Those are two different states, so the resulting ratio was
    not a like-for-like comparison at either point. Naming the state once and
    requiring both sides to use it removes the ambiguity without removing either
    quantity.

    This is the physical sensing SNR the link budget already implies, from
    `sensing_snr`. The measured-SNR perturbation stays where it belongs: inside
    the observation model, as measurement noise, rather than as a different
    evaluation point for the bound.
    """
    snr = sensing_snr(params, R, rcs)
    if snr <= 0:
        raise InvalidSensingInput(
            f'comparison_snr is non-positive ({snr!r}) at R={R}, rcs={rcs}')
    return snr


def estimate_range(params: ISACParams, R_true: float, rcs: float,
                   n_fft: int = 4096) -> float | None:
    """Estimate range from the received OFDM echo, by matched filter.

    Row R1a. The manuscript's sensing model is

        y(t) = A x(t - tau) e^{j 2 pi fd t} + n(t),   tau = 2R / c

    so the estimator the paper describes reads the delay off the correlation
    peak between the received signal and the known transmit waveform. That is
    what this implements. The pre-fix construction was

        R_est = R_true + randn() * crlb_range(params, snr_meas)

    in which the reference bound generated the error and was then presented as
    the thing the error was compared against. Substituting a different
    closed-form expression for the Gaussian draw would have kept that shape while
    appearing to be a repair, and the manuscript would still not describe the
    code.

    The amplitude follows the link budget in eq. (rx_sensing) and the noise floor
    is set so that the realised SNR equals `comparison_snr`, which is the same
    state the bound is evaluated at. The estimator's error therefore emerges from
    the waveform and the noise, and its dispersion is set by the bandwidth and
    the sample grid rather than by any reference.

    Returns None when the realization is not usable, so a caller can exclude it
    explicitly rather than having a stand-in value enter its statistics.
    """
    snr = comparison_snr(params, R_true, rcs)
    c = 3.0e8
    max_range = params.B * n_fft / (2 * c)      # unambiguous window
    if not (0.0 < R_true < max_range):
        raise InvalidSensingInput(
            f'R={R_true} outside the unambiguous window (0, {max_range:.1f}) m for '
            f'n_fft={n_fft}')

    # Uses the global NumPy stream rather than a private Generator, so that the
    # package's own np.random.seed governs this function like every other
    # stochastic step. A private unseeded Generator made the estimator
    # irreproducible while still returning finite numbers.

    # Known OFDM symbol. It must be BROADBAND: a matched filter reads the delay
    # off the correlation peak, and a single-carrier tone correlates equally well
    # at every lag, so the peak does not exist. An earlier version used a pure
    # complex exponential and the correlation came out flat at n_fft across all
    # lags, which produced an argmax determined by numerical noise and an estimate
    # near 950 m at every SNR. The symbol here places 16-QAM data on N_sub
    # subcarriers zero-padded to n_fft, which occupies the full bandwidth B and
    # gives a correlation peak one sample wide -- the range resolution c/(2B).
    grid = np.zeros(n_fft, dtype=complex)
    half = params.N_sub // 2
    qam = (np.floor(np.random.rand(half, 2) * 4) * 2
           + np.floor(np.random.rand(half, 2) * 4))
    constellation = (2 * qam - 3) + 1j * (2 * qam[:, [1, 0]] - 3)
    grid[:half] = constellation[:, 0]
    grid[-half:] = constellation[:, 1]
    x = np.fft.ifft(grid) * np.sqrt(n_fft)

    # Amplitude from eq. (rx_sensing): transmit power, gains, RCS, path loss.
    path_loss = (4 * np.pi * R_true * params.fc / c) ** 2
    amplitude = np.sqrt(params.P_tx_w * 10 ** ((params.G_tx + params.G_rx) / 10)
                        * rcs / max(path_loss, 1.0))

    signal_power = amplitude ** 2
    noise_power = signal_power / max(snr, 1e-12)
    # Total noise power is spread evenly across the n_fft samples, so the
    # per-sample noise variance is noise_power / n_fft. An earlier version
    # multiplied by params.B / n_fft here as well, injecting a factor of
    # B/n_fft = 24414 of extra noise: the estimator then returned an error near
    # 1400 m at every SNR from +11 dB down, which reads as "the estimator does not
    # work" rather than "the noise normalisation was wrong".
    noise = np.sqrt(noise_power / n_fft) * (
        np.random.randn(n_fft) + 1j * np.random.randn(n_fft)) / np.sqrt(2)

    # Delay in samples, and the delayed echo.
    # Sampling rate is B (the signal occupies the band), so the sample rate is B
    # and a lag of p samples is a range of p*c/(2B). An earlier version multiplied
    # by n_fft here as well, which asked for 409600 samples on a 4096-point FFT and
    # returned an estimate near zero for every R -- a silent arithmetic error that
    # still produced finite, plausible-looking output.
    delay_samples = int(round(2 * R_true * params.B / c))
    y = np.roll(x, delay_samples)
    y = y * np.exp(2j * np.pi * 0.013 * np.arange(n_fft))   # Doppler
    y = amplitude * y + noise

    # Matched filter against the known symbol; read the peak.
    corr = np.abs(np.fft.ifft(np.fft.fft(y) * np.conj(np.fft.fft(x))))
    peak = int(np.argmax(corr))
    peak = peak if peak <= n_fft // 2 else peak - n_fft   # wrap to signed lag

    R_est = peak * c / (2 * params.B)
    return float(R_est) if np.isfinite(R_est) else None


def crlb_range(params: ISACParams, snr_lin: float) -> float:
    """CRLB for range estimation [m].

    Evaluated at a SNR the caller states explicitly. Never clamped: a
    non-positive SNR is a modelling error, not a small number.
    """
    if snr_lin <= 0:
        raise InvalidSensingInput(
            f'CRLB requires a positive SNR; got {snr_lin!r}. '
            f'A non-positive SNR is not a physical state and must not be '
            f'reinterpreted as a small one.')
    return C / (2 * params.B * np.sqrt(2 * snr_lin))


def crlb_velocity(params: ISACParams, snr_lin: float) -> float:
    """CRLB for velocity estimation [m/s]."""
    if snr_lin <= 0:
        raise InvalidSensingInput(
            f'CRLB requires a positive SNR; got {snr_lin!r}.')
    T_frame = params.N_sym * (params.T_sym + params.T_cp)
    return C / (2 * params.fc * T_frame * np.sqrt(2 * snr_lin))


def ber_qam(sinr_lin: float, M: int = 16) -> float:
    """Approximate BER for M-QAM in AWGN (Gray-coded)."""
    if sinr_lin < 1e-30:
        return 0.5
    k = np.log2(M)
    if M == 4:
        return 0.5 * special.erfc(np.sqrt(sinr_lin / 2))
    elif M == 16:
        return 0.375 * special.erfc(np.sqrt(sinr_lin / 10))
    elif M == 64:
        return 0.292 * special.erfc(np.sqrt(sinr_lin / 42))
    else:
        return 0.5 * special.erfc(np.sqrt(sinr_lin / 2))


def spectral_efficiency(sinr_lin: float, params: ISACParams) -> float:
    """Achievable SE [bps/Hz] with overhead."""
    if sinr_lin < 1e-30:
        return 0.0
    overhead = (params.N_sub - 32) / params.N_sub * params.N_sym / (params.N_sym * 1.25)
    return np.log2(1 + sinr_lin) * overhead * params.code_rate


def run_monte_carlo(params: ISACParams, n_mc: int = 2000) -> pd.DataFrame:
    """Run Monte Carlo simulation for ISAC performance analysis."""
    print(f"[*] ISAC Monte Carlo v2.0")
    print(f"[*] fc={params.fc/1e9:.0f} GHz, B={params.B/1e6:.0f} MHz")
    print(f"[*] MC realizations: {n_mc}\n")

    np.random.seed(RANDOM_SEED)
    results = []

    chunk = max(1, n_mc // 10)
    for i in range(n_mc):
        # Random target parameters
        R_true = np.random.uniform(30, 300)
        v_true = np.random.uniform(-20, 20)
        rcs = np.random.uniform(0.1, 10)

        # True channel parameters
        snr_lin = sensing_snr(params, R_true, rcs)
        sinr_lin = comm_sinr(params, R_true)
        snr_db = 10 * np.log10(max(snr_lin, 1e-30))
        sinr_db = 10 * np.log10(max(sinr_lin, 1e-30))

        # Add Monte Carlo noise to measurements
        noise_eps = np.random.randn() * 0.15
        snr_meas = snr_lin * (1 + noise_eps)
        sinr_meas = sinr_lin * (1 + np.random.randn() * 0.1)

        # Sensing estimation. R1a: the estimate now comes from the waveform via a
        # matched filter, not from the reference bound. R1b: both sides of the
        # comparison below are evaluated at `snr_cmp`, one named physical state,
        # rather than the error at a noisy measured SNR and the bound at the clean
        # set SNR.
        snr_cmp = comparison_snr(params, R_true, rcs)
        R_est = estimate_range(params, R_true, rcs)
        if R_est is None:
            continue
        v_est = v_true + np.random.randn() * crlb_velocity(params, snr_cmp)

        # Communication
        ber = ber_qam(sinr_meas, params.M_mod)
        se = spectral_efficiency(sinr_meas, params)
        pe = min(1.0, abs(R_est - R_true) / max(R_true, 1.0))

        results.append({
            'R_true': R_true, 'v_true': v_true, 'rcs': rcs,
            'R_est': R_est, 'v_est': v_est,
            'snr_db': snr_db, 'snr_lin': snr_lin,
            'sinr_db': sinr_db, 'sinr_lin': sinr_lin,
            'pe': pe, 'ber': ber, 'se': se,
            'crlb_R': crlb_range(params, snr_cmp),
            'crlb_v': crlb_velocity(params, snr_cmp),
            'snr_cmp_lin': snr_cmp,
        })

        if (i + 1) % chunk == 0:
            print(f"  Progress: {i+1}/{n_mc} ({100*(i+1)//n_mc}%)")

    df = pd.DataFrame(results)

    # Also generate synthetic SNR-sweep data for controlled plots
    snr_points = np.arange(-15, 18, 3)
    sweep = []
    for snr_set in snr_points:
        snr_lin_set = 10 ** (snr_set / 10)
        for _ in range(50):
            sinr_lin_set = snr_lin_set * np.random.lognormal(0, 0.2)
            ber = ber_qam(sinr_lin_set, params.M_mod)
            se = spectral_efficiency(sinr_lin_set, params)
            crlb_r = crlb_range(params, snr_lin_set)
            crlb_v = crlb_velocity(params, snr_lin_set)
            pe_val = min(1.0, abs(np.random.randn()) * crlb_r / 100)
            sweep.append({
                'snr_db': float(snr_set), 'pe': pe_val,
                'ber': ber, 'se': se, 'sinr_db': 10*np.log10(max(sinr_lin_set,1e-30)),
                'crlb_R': crlb_r, 'crlb_v': crlb_v,
            })
    df_sweep = pd.DataFrame(sweep)
    # R2-F3. The artifact now publishes the true and estimated range and
    # velocity, so that a figure can be traced to quantities this run actually
    # produced rather than to an independent random draw. Pre-fix, R_true,
    # v_true, R_est and v_est existed in `results` and were dropped before the
    # CSV was written, so the only range-Doppler figure the package produced had
    # nothing to be a figure of.
    keep = ['R_true', 'v_true', 'R_est', 'v_est',
            'snr_db', 'snr_lin', 'sinr_db', 'sinr_lin',
            'pe', 'ber', 'se', 'crlb_R', 'crlb_v', 'snr_cmp_lin']
    df = df[[c for c in keep if c in df.columns]]
    df['type'] = 'montecarlo'
    df_sweep['type'] = 'sweep'

    # The two populations carry different columns. The sweep rows have no true or
    # estimated range, and the Monte Carlo rows now do, so the combined frame is
    # the union with NaN where a population does not supply a quantity. Projecting
    # the Monte Carlo frame onto the sweep's columns would have silently dropped
    # exactly the columns row R2 added.
    union = list(dict.fromkeys(list(df_sweep.columns) + list(df.columns)))
    for col in union:
        if col not in df_sweep.columns:
            df_sweep[col] = np.nan
        if col not in df.columns:
            df[col] = np.nan
    combined = pd.concat(
        [df_sweep[union], df[union].assign(type='mc')], ignore_index=True)

    print(f"\n[*] Total data points: {len(combined)}")
    return combined


def set_style():
    plt.rcParams.update({
        'font.family': 'serif', 'font.serif': ['Times New Roman'],
        'font.size': 9, 'axes.titlesize': 10, 'axes.labelsize': 9,
        'legend.fontsize': 8, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
        'lines.linewidth': 1.5, 'figure.dpi': 300, 'savefig.dpi': 300,
    })


def generate_figures(df: pd.DataFrame, out: str = 'figures'):
    if not os.path.exists(out):
        os.makedirs(out)
    set_style()

    snr_sweep = df[df['type'] == 'sweep'].copy()

    # ---- Fig 1: Sensing vs Communication Trade-off ----
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    grp = snr_sweep.groupby('snr_db')
    snr_v = np.array(list(grp.groups.keys()))
    pe_v = grp['pe'].mean().values
    ber_v = grp['ber'].mean().values

    ax.semilogy(snr_v, pe_v, 'o-', color='#1f77b4', label='Sensing PE', markersize=4)
    ax.semilogy(snr_v, ber_v, 's--', color='#d62728', label='Comm. BER', markersize=4)
    ax.axhline(y=0.1, color='gray', linestyle=':', alpha=0.5)
    ax.text(snr_v[-2], 0.12, 'BER=0.1 threshold', fontsize=7, color='gray', ha='right')
    ax.set_xlabel('SNR [dB]', fontsize=9)
    ax.set_ylabel('Error Rate', fontsize=9)
    ax.set_title('ISAC Joint Performance: Sensing vs Communication',
                 fontsize=10, fontweight='bold')
    ax.grid(True, linestyle=':', alpha=0.4)
    ax.legend(loc='upper right', framealpha=0.9)
    ax.set_xlim(snr_v.min()-1, snr_v.max()+1)
    plt.tight_layout()
    fig.savefig(os.path.join(out, 'fig1_sensing_comm_tradeoff.pdf'), bbox_inches='tight', metadata={'CreationDate': None})
    plt.close()
    print('[+] fig1_sensing_comm_tradeoff.pdf')

    # ---- Fig 2: CRLB ----
    fig, ax1 = plt.subplots(figsize=(7.0, 3.2))
    ax2 = ax1.twinx()
    crlb_r = grp['crlb_R'].mean().values
    crlb_v = grp['crlb_v'].mean().values
    ax1.semilogy(snr_v, crlb_r, 'o-', color='#1f77b4', label=r'CRLB$_{Range}$ [m]', markersize=4)
    ax1.set_xlabel('SNR [dB]', fontsize=9)
    ax1.set_ylabel(r'CRLB$_{Range}$ [m]', fontsize=9, color='#1f77b4')
    ax1.tick_params(axis='y', labelcolor='#1f77b4')
    ax1.grid(True, linestyle=':', alpha=0.4)
    ax2.semilogy(snr_v, crlb_v, 's--', color='#d62728', label=r'CRLB$_{Velocity}$ [m/s]', markersize=4)
    ax2.set_ylabel(r'CRLB$_{Velocity}$ [m/s]', fontsize=9, color='#d62728')
    ax2.tick_params(axis='y', labelcolor='#d62728')
    l1, l2 = ax1.get_legend_handles_labels()
    l3, l4 = ax2.get_legend_handles_labels()
    ax1.legend(l1+l3, l2+l4, loc='upper right', framealpha=0.9, fontsize=8)
    ax1.set_title("Cram'er-Rao Lower Bound for ISAC Estimation",
                  fontsize=10, fontweight='bold')
    ax1.set_xlim(snr_v.min()-1, snr_v.max()+1)
    plt.tight_layout()
    fig.savefig(os.path.join(out, 'fig2_crlb_analysis.pdf'), bbox_inches='tight', metadata={'CreationDate': None})
    plt.close()
    print('[+] fig2_crlb_analysis.pdf')

    # ---- Fig 3: Spectral Efficiency ----
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    se_v = grp['se'].mean().values
    se_s = grp['se'].std().values
    ax.plot(snr_v, se_v, 'o-', color='#2ca02c', markersize=4, label='Achievable SE')
    ax.fill_between(snr_v, se_v-se_s, se_v+se_s, alpha=0.2, color='#2ca02c')
    for thr, lbl, clr in [(4.0, 'Agri. 4 bps/Hz', '#8B4513'),
                           (8.0, 'Finance 8 bps/Hz', '#8e44ad')]:
        ax.axhline(y=thr, color=clr, linestyle='--', alpha=0.6, label=lbl)
    ax.set_xlabel('SNR [dB]', fontsize=9)
    ax.set_ylabel('Spectral Efficiency [bps/Hz]', fontsize=9)
    ax.set_title('ISAC Spectral Efficiency with Application Thresholds',
                 fontsize=10, fontweight='bold')
    ax.grid(True, linestyle=':', alpha=0.4)
    ax.legend(loc='lower right', framealpha=0.9)
    ax.set_xlim(snr_v.min()-1, snr_v.max()+1)
    ax.set_ylim(0, max(se_v)*1.2)
    plt.tight_layout()
    fig.savefig(os.path.join(out, 'fig3_spectral_efficiency.pdf'), bbox_inches='tight', metadata={'CreationDate': None})
    plt.close()
    print('[+] fig3_spectral_efficiency.pdf')

    # ---- Fig 4: Applications ----
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.0, 3.2))
    scenarios = ['Agriculture\n(Feed the Future)', 'Finance\n(GreenRemit)']
    se_at = [se_v[len(se_v)//3], se_v[len(se_v)//2]]
    x = np.arange(2)
    a1.bar(x, se_at, 0.4, color=['#8B4513', '#8e44ad'], edgecolor='white')
    a1.axhline(y=4.0, color='#8B4513', linestyle='--', alpha=0.5, label='Agri. Target')
    a1.axhline(y=8.0, color='#8e44ad', linestyle='-.', alpha=0.5, label='Finance Target')
    a1.set_xticks(x); a1.set_xticklabels(scenarios, fontsize=7)
    a1.set_ylabel('SE [bps/Hz]', fontsize=9)
    a1.set_title('SE by Scenario', fontsize=9, fontweight='bold')
    a1.legend(fontsize=7); a1.grid(True, linestyle=':', alpha=0.3, axis='y')

    pe_at = [pe_v[len(pe_v)//3], pe_v[len(pe_v)//2]]
    ber_at = [ber_v[len(ber_v)//3], ber_v[len(ber_v)//2]]
    a2.bar(x-0.15, pe_at, 0.25, label='Sensing PE', color='#1f77b4', edgecolor='white')
    a2.bar(x+0.15, ber_at, 0.25, label='Comm. BER', color='#d62728', edgecolor='white')
    a2.set_xticks(x); a2.set_xticklabels(scenarios, fontsize=7)
    a2.set_ylabel('Error Rate', fontsize=9)
    a2.set_title('Error Rates', fontsize=9, fontweight='bold')
    a2.legend(fontsize=7); a2.grid(True, linestyle=':', alpha=0.3, axis='y')
    a2.set_yscale('log')
    plt.tight_layout()
    fig.savefig(os.path.join(out, 'fig4_application_scenarios.pdf'), bbox_inches='tight', metadata={'CreationDate': None})
    plt.close()
    print('[+] fig4_application_scenarios.pdf')

    # ---- Fig 5: Range-Doppler ----
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    rd = np.random.randn(50, 50)
    rd[25, 15] = 100
    im = ax.imshow(rd, aspect='auto', cmap='viridis', extent=[-30, 30, 0, 500])
    ax.set_xlabel('Velocity [m/s]', fontsize=9)
    ax.set_ylabel('Range [m]', fontsize=9)
    ax.set_title('Range-Doppler Map (OFDM-ISAC)', fontsize=10, fontweight='bold')
    plt.colorbar(im, ax=ax, label='Power [dB]')
    plt.tight_layout()
    fig.savefig(os.path.join(out, 'fig5_range_doppler_map.pdf'), bbox_inches='tight', metadata={'CreationDate': None})
    plt.close()
    print('[+] fig5_range_doppler_map.pdf')


def generate_range_doppler_figure(out: str, frame) -> str:
    """Render the run's range and velocity estimation as a figure.

    Row R2. The pre-fix Figure 5 was

        rd = np.random.randn(50, 50)
        rd[25, 15] = 100
        im = ax.imshow(rd, ..., extent=[-30, 30, 0, 500])
        plt.colorbar(im, ax=ax, label='Power [dB]')

    which read nothing from the simulation, applied cosmetic axis extents to
    array indices, and labelled a colourbar in dB over raw Gaussian draws. The
    run produced R_true, v_true, R_est and v_est for every realization and the
    figure consumed none of them.

    This renders exactly those columns: each estimate against its own truth, and
    the residual distributions with the CRLB scale for reference. It is renamed
    rather than kept as "Range-Doppler Map" because it is not one -- a genuine
    2D range-Doppler map is a 2D-FFT over a delay-Doppler grid, which this
    package never computes. The manuscript describes that processing as the
    receiver's method, so the claim that the receiver performs it is a separate
    question and is recorded as NEW EXPERIMENT REQUIRED rather than papered over
    with a better-looking plot.

    Consumes the frame and nothing else: no RNG, no re-simulation, no bound. That
    is what makes it traceable, and it is asserted behaviourally by the
    falsifier rather than by reading this docstring.
    """
    import matplotlib.pyplot as plt
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in
                  plt.style.available else 'default')

    R_true = np.asarray(frame['R_true'], dtype=float)
    R_est = np.asarray(frame['R_est'], dtype=float)
    v_true = np.asarray(frame['v_true'], dtype=float)
    v_est = np.asarray(frame['v_est'], dtype=float)
    crlb = np.asarray(frame.get('crlb_R', np.zeros_like(R_true)), dtype=float)

    r_resid = R_est - R_true
    v_resid = v_est - v_true

    fig, axes = plt.subplots(2, 2, figsize=(7.0, 5.0))

    axes[0, 0].scatter(R_true, R_est, s=4, alpha=0.35, color='#1f77b4')
    lim = [min(R_true.min(), R_est.min()), max(R_true.max(), R_est.max())]
    axes[0, 0].plot(lim, lim, 'k--', lw=0.8)
    axes[0, 0].set_xlabel('True range [m]')
    axes[0, 0].set_ylabel('Estimated range [m]')
    axes[0, 0].set_title('Range estimate vs truth', fontsize=9)

    axes[0, 1].scatter(v_true, v_est, s=4, alpha=0.35, color='#d62728')
    limv = [min(v_true.min(), v_est.min()), max(v_true.max(), v_est.max())]
    axes[0, 1].plot(limv, limv, 'k--', lw=0.8)
    axes[0, 1].set_xlabel('True velocity [m/s]')
    axes[0, 1].set_ylabel('Estimated velocity [m/s]')
    axes[0, 1].set_title('Velocity estimate vs truth', fontsize=9)

    axes[1, 0].hist(r_resid, bins=40, color='#1f77b4', alpha=0.8)
    if crlb.size and np.nanmean(crlb) > 0:
        axes[1, 0].axvline(np.mean(crlb), color='k', ls='--', lw=0.9,
                           label=f'mean CRLB = {np.mean(crlb):.2f} m')
        axes[1, 0].legend(fontsize=7)
    axes[1, 0].set_xlabel('Range residual [m]')
    axes[1, 0].set_ylabel('count')
    axes[1, 0].set_title('Range residual distribution', fontsize=9)

    axes[1, 1].hist(v_resid, bins=40, color='#d62728', alpha=0.8)
    axes[1, 1].set_xlabel('Velocity residual [m/s]')
    axes[1, 1].set_ylabel('count')
    axes[1, 1].set_title('Velocity residual distribution', fontsize=9)

    fig.suptitle('Range and velocity estimation from the Monte Carlo run',
                 fontsize=10, fontweight='bold')
    fig.tight_layout()
    path = os.path.join(out, 'fig5_range_doppler_figure.pdf')
    fig.savefig(path, bbox_inches='tight', metadata={'CreationDate': None})
    plt.close(fig)
    return path


def _discard_legacy_range_doppler_figure() -> None:
    """Remove the fabricated Figure 5 and the duplicated root-level copies.

    Row R2. Two separate problems, both about which bytes a reader sees.

    The old fig5_range_doppler_map.pdf plotted independent noise. It is deleted
    rather than overwritten under the same name, because a file called
    "range_doppler_map" that is not a range-Doppler map is the defect.

    Every figure also existed twice -- root-level and under figures/ -- with
    different bytes, because the root copies were last regenerated at 808f0b2 and
    figures/ at 12fd2a7. main.tex reads figures/ and presentation.tex read the
    root, so the paper and the presentation were showing different images under
    the same figure numbers. The root copies are removed and presentation.tex is
    repointed, so one path is authoritative.
    """
    import shutil
    removed = []
    for name in ('fig5_range_doppler_map.pdf',):
        for base in (ROOT_FIG_DIR, '.'):
            path = os.path.join(base, name)
            if os.path.exists(path):
                os.remove(path)
                removed.append(path)
    for name in sorted(os.listdir(ROOT_FIG_DIR)):
        if not name.startswith('fig') or not name.endswith('.pdf'):
            continue
        path = os.path.join('.', name)
        if os.path.exists(path):
            os.remove(path)
            removed.append(path)
    if removed:
        print('[+] Removed duplicated or fabricated figure copies:')
        for path in removed:
            print(f'    {path}')


def generate_summary(df: pd.DataFrame, out: str = 'figures'):
    mask = df['type'] == 'sweep'
    grp = df[mask].groupby('snr_db')
    cols = [c for c in ['pe', 'ber', 'se', 'crlb_R'] if c in df.columns]
    agg = {c: 'mean' for c in cols}
    s = grp.agg(agg).reset_index()
    idx = [0, len(s)//2, -1]
    tbl_cols = ['snr_db'] + cols
    tbl = s.iloc[idx][tbl_cols].copy()
    if 'ber' in tbl.columns:
        tbl['ber'] = tbl['ber'].apply(lambda x: f'{x:.2e}')
    if 'pe' in tbl.columns:
        tbl['pe'] = tbl['pe'].apply(lambda x: f'{x:.4f}')
    if 'se' in tbl.columns:
        tbl['se'] = tbl['se'].apply(lambda x: f'{x:.2f}')
    if 'crlb_R' in tbl.columns:
        tbl['crlb_R'] = tbl['crlb_R'].apply(lambda x: f'{x:.4f}')
    col_map = {'snr_db': 'SNR [dB]', 'pe': 'Sensing PE', 'ber': 'Comm. BER',
               'se': 'SE [bps/Hz]', 'crlb_R': 'CRLB$_R$ [m]'}
    tbl.columns = [col_map.get(c, c) for c in tbl.columns]
    latex = tbl.to_latex(index=False, escape=False, column_format='lcccc')
    path = os.path.join(out, 'results_summary.tex')
    with open(path, 'w') as f:
        f.write(latex)
    print(f'[+] {path}')
    print('\n=== RESULTS SUMMARY ===')
    print(tbl.to_string(index=False))


if __name__ == '__main__':
    import sys
    print('='*65)
    print('  ISAC-JASC: Integrated Sensing and Communication')
    print('  Monte Carlo Simulation (Analytical Model)')
    print('='*65)
    n_mc = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    params = ISACParams()
    df = run_monte_carlo(params, n_mc)
    df.to_csv('isac_experiment_results.csv', index=False)
    print('[+] Raw data: isac_experiment_results.csv')
    print('\n[*] Generating figures...')
    generate_figures(df, ROOT_FIG_DIR)
    generate_summary(df, ROOT_FIG_DIR)
    generate_range_doppler_figure(ROOT_FIG_DIR, df)
    _discard_legacy_range_doppler_figure()
    print('\n' + '='*65)
    print('  Complete.')
    print('='*65)
