"""NR-ARFCN <-> frequency conversion per 3GPP TS 38.104 §5.4.2.1.

F_REF = F_REF-Offs + dF_Global * (N_REF - N_REF-Offs)

Global frequency raster (Table 5.4.2.1-1):

    Range (MHz)        dF_Global   F_REF-Offs (MHz)   N_REF-Offs   N_REF range
    0       – 3000     5 kHz       0                  0            0       – 599999
    3000    – 24250    15 kHz      3000               600000       600000  – 2016666
    24250   – 100000   60 kHz      24250.08           2016667      2016667 – 3279165
"""

from __future__ import annotations

from typing import Any

# (low_mhz, high_mhz, delta_f_khz, f_offs_mhz, n_offs, n_max, label)
_RASTER = [
    (0.0, 3000.0, 5, 0.0, 0, 599999, "FR1 low (<3 GHz)"),
    (3000.0, 24250.0, 15, 3000.0, 600000, 2016666, "FR1 high (3–24.25 GHz)"),
    (24250.0, 100000.0, 60, 24250.08, 2016667, 3279165, "FR2 (mmWave)"),
]


def arfcn_to_freq(arfcn: int, band_info: dict) -> float:
    """Band-specific NR-ARFCN → MHz (per-band raster from arfcn_bands)."""
    return band_info["f_off_dl"] + band_info["step"] * (arfcn - band_info["n_off_dl"])


def freq_to_arfcn(freq_mhz: float, band_info: dict) -> int:
    """MHz → nearest band-specific NR-ARFCN."""
    return int((freq_mhz - band_info["f_off_dl"]) / band_info["step"] + band_info["n_off_dl"])


def arfcn_to_frequency(arfcn: int) -> dict[str, Any]:
    """Convert an NR-ARFCN to its RF reference frequency in MHz."""
    if not 0 <= arfcn <= 3279165:
        raise ValueError(f"NR-ARFCN must be in [0, 3279165], got {arfcn}")
    for low, _high, df_khz, f_offs, n_offs, n_max, label in _RASTER:
        if arfcn <= n_max:
            freq_mhz = f_offs + (df_khz / 1000.0) * (arfcn - n_offs)
            return {
                "arfcn": arfcn,
                "frequency_mhz": round(freq_mhz, 6),
                "delta_f_global_khz": df_khz,
                "range": label,
            }
    raise AssertionError("unreachable")


def frequency_to_arfcn(freq_mhz: float) -> dict[str, Any]:
    """Convert a frequency in MHz to the nearest NR-ARFCN on the global raster."""
    if not 0 <= freq_mhz <= 100000:
        raise ValueError(f"Frequency must be in [0, 100000] MHz, got {freq_mhz}")
    for low, high, df_khz, f_offs, n_offs, n_max, label in _RASTER:
        if low <= freq_mhz < high or (freq_mhz == high == 100000.0):
            n = n_offs + round((freq_mhz - f_offs) / (df_khz / 1000.0))
            n = max(n_offs, min(n, n_max))
            exact = f_offs + (df_khz / 1000.0) * (n - n_offs)
            return {
                "arfcn": n,
                "frequency_mhz": round(exact, 6),
                "requested_mhz": freq_mhz,
                "delta_f_global_khz": df_khz,
                "range": label,
            }
    raise AssertionError("unreachable")


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else "632448"
    if "." in arg or float(arg) < 1 or "mhz" in arg.lower():
        print(frequency_to_arfcn(float(arg.lower().replace("mhz", ""))))
    else:
        print(arfcn_to_frequency(int(arg)))
