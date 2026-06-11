"""Approximate 5G NR peak data rate per 3GPP TS 38.306 §4.1.2.

data rate (Mbps) = 1e-6 * v_layers * Qm * Rmax * (N_PRB * 12 / Ts) * (1 - OH)

where
    Rmax = 948/1024
    Ts   = 1e-3 / (14 * 2^mu)        (average OFDM symbol duration)
    mu   = numerology (scs param in nr_throughput)
    OH   = 0.14 DL FR1 | 0.18 DL FR2 | 0.08 UL FR1 | 0.10 UL FR2
    N_PRB from TS 38.101 tables or throughput_prb in the master DB.
"""

from __future__ import annotations

from typing import Any

R_MAX = 948 / 1024

# TS 38.101-1 Table 5.3.2-1 (FR1) — N_PRB per (SCS kHz, channel BW MHz)
_N_PRB_FR1 = {
    15: {5: 25, 10: 52, 15: 79, 20: 106, 25: 133, 30: 160, 40: 216, 50: 270},
    30: {5: 11, 10: 24, 15: 38, 20: 51, 25: 65, 30: 78, 40: 106, 50: 133,
         60: 162, 70: 189, 80: 217, 90: 245, 100: 273},
    60: {10: 11, 15: 18, 20: 24, 25: 31, 30: 38, 40: 51, 50: 65, 60: 79,
         70: 93, 80: 107, 90: 121, 100: 135},
}
# TS 38.101-2 Table 5.3.2-1 (FR2)
_N_PRB_FR2 = {
    60: {50: 66, 100: 132, 200: 264},
    120: {50: 32, 100: 66, 200: 132, 400: 264},
}

_SCS_TO_MU = {15: 0, 30: 1, 60: 2, 120: 3}

_OVERHEAD = {("dl", "fr1"): 0.14, ("dl", "fr2"): 0.18,
             ("ul", "fr1"): 0.08, ("ul", "fr2"): 0.10}


def nr_throughput(n_prb, q_m, layers, code_rate, scs, overhead):
    """Core NR peak throughput in Mbps.

    ``scs`` is numerology mu (0–3). ``q_m`` is modulation order (Qm).
    ``code_rate`` is the effective code rate (e.g. 948/1024).
    """
    Ts = 1e-3 / (14 * (2 ** scs))
    bits_per_symbol = q_m * code_rate
    symbols_per_sec = 14 * (2 ** scs) * 1000
    res = n_prb * 12 * symbols_per_sec
    raw = res * bits_per_symbol * layers
    return (raw * (1 - overhead)) / 1e6


def peak_nr_throughput(
    bandwidth_mhz: int = 100,
    scs_khz: int = 30,
    layers: int = 4,
    modulation_order: int = 8,
    direction: str = "dl",
    scaling_factor: float = 1.0,
    n_prb: int | None = None,
) -> dict[str, Any]:
    """High-level wrapper: resolves N_PRB/overhead and returns a result dict."""
    if scs_khz not in _SCS_TO_MU:
        raise ValueError(f"SCS must be one of {sorted(_SCS_TO_MU)}, got {scs_khz}")
    if direction not in ("dl", "ul"):
        raise ValueError("direction must be 'dl' or 'ul'")
    if not 1 <= layers <= 8:
        raise ValueError("layers must be in [1, 8]")

    fr = "fr2" if scs_khz == 120 or bandwidth_mhz > 100 else "fr1"
    if n_prb is None:
        table = _N_PRB_FR2 if fr == "fr2" else _N_PRB_FR1
        if scs_khz not in table or bandwidth_mhz not in table[scs_khz]:
            raise ValueError(
                f"No PRB allocation for {bandwidth_mhz} MHz @ {scs_khz} kHz SCS "
                f"({fr.upper()}). Valid: {table.get(scs_khz, {})}"
            )
        n_prb = table[scs_khz][bandwidth_mhz]

    mu = _SCS_TO_MU[scs_khz]
    oh = _OVERHEAD[(direction, fr)]
    mbps = nr_throughput(
        n_prb, modulation_order, layers,
        R_MAX * scaling_factor, mu, oh,
    )
    return {
        "throughput_mbps": round(mbps, 2),
        "n_prb": n_prb,
        "numerology_mu": mu,
        "frequency_range": fr.upper(),
        "overhead": oh,
        "layers": layers,
        "modulation_order_qm": modulation_order,
        "scs_khz": scs_khz,
        "bandwidth_mhz": bandwidth_mhz,
        "direction": direction,
    }


if __name__ == "__main__":
    print(peak_nr_throughput())  # 100 MHz, 30 kHz, 4x4, 256QAM DL -> ~2.34 Gbps
