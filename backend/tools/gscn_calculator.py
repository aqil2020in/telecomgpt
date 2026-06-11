"""GSCN (Global Synchronization Channel Number) <-> SSB frequency conversion
per 3GPP TS 38.104 §5.4.3.1 (Table 5.4.3.1-1).

    Range (MHz)       SS_ref formula                            GSCN
    0      – 3000     N * 1200 kHz + M * 50 kHz                 3N + (M-3)/2
                      (N = 1..2499, M in {1,3,5}; M=3 default)  2 – 7498
    3000   – 24250    3000 MHz + N * 1.44 MHz   (N = 0..14756)  7499 – 22255
    24250  – 100000   24250.08 MHz + N * 17.28 MHz (N=0..4383)  22256 – 26639
"""

from __future__ import annotations

from typing import Any


def gscn_to_freq(gscn: int, fr: str) -> float:
    """Simplified GSCN → SSB frequency (MHz) for FR1 or FR2 raster."""
    if fr == "fr1":
        return 1.2 * gscn + 3000
    return 1.44 * gscn + 24240


def freq_to_gscn(freq_mhz: float, fr: str) -> int:
    """Simplified SSB frequency (MHz) → GSCN for FR1 or FR2 raster."""
    if fr == "fr1":
        return int((freq_mhz - 3000) / 1.2)
    return int((freq_mhz - 24240) / 1.44)


def gscn_to_frequency(gscn: int) -> dict[str, Any]:
    """Convert a GSCN to the SSB reference frequency (SS_ref) in MHz."""
    if 2 <= gscn <= 7498:
        # GSCN = 3N + (M-3)/2 with M in {1,3,5}, i.e. (M-3)/2 in {-1,0,1}
        k = ((gscn + 1) % 3) - 1
        n = (gscn - k) // 3
        m = 2 * k + 3
        ss_ref = (n * 1200 + m * 50) / 1000.0
        return {"gscn": gscn, "ss_ref_mhz": round(ss_ref, 4), "n": n, "m": m,
                "range": "FR1 low (<3 GHz)"}
    if 7499 <= gscn <= 22255:
        n = gscn - 7499
        ss_ref = 3000.0 + n * 1.44
        return {"gscn": gscn, "ss_ref_mhz": round(ss_ref, 4), "n": n,
                "range": "FR1 high (3–24.25 GHz)"}
    if 22256 <= gscn <= 26639:
        n = gscn - 22256
        ss_ref = 24250.08 + n * 17.28
        return {"gscn": gscn, "ss_ref_mhz": round(ss_ref, 4), "n": n,
                "range": "FR2 (mmWave)"}
    raise ValueError(f"GSCN must be in [2, 26639], got {gscn}")


def frequency_to_gscn(freq_mhz: float) -> dict[str, Any]:
    """Find the GSCN whose SS_ref is closest to ``freq_mhz`` (M=3 in FR1 low)."""
    if 0 < freq_mhz < 3000:
        n = max(1, min(2499, round((freq_mhz * 1000 - 150) / 1200)))
        gscn = 3 * n
        return {**gscn_to_frequency(gscn), "requested_mhz": freq_mhz}
    if 3000 <= freq_mhz < 24250:
        n = max(0, min(14756, round((freq_mhz - 3000.0) / 1.44)))
        return {**gscn_to_frequency(7499 + n), "requested_mhz": freq_mhz}
    if 24250 <= freq_mhz <= 100000:
        n = max(0, min(4383, round((freq_mhz - 24250.08) / 17.28)))
        return {**gscn_to_frequency(22256 + n), "requested_mhz": freq_mhz}
    raise ValueError(f"Frequency must be in (0, 100000] MHz, got {freq_mhz}")


if __name__ == "__main__":
    import sys

    arg = float(sys.argv[1]) if len(sys.argv) > 1 else 7880
    if arg <= 26639 and arg == int(arg) and arg >= 2:
        print(gscn_to_frequency(int(arg)))
    else:
        print(frequency_to_gscn(arg))
