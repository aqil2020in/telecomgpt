"""NR link budget + SINR vs RSRQ explanation with worked examples (TS 38.215 / ShareTechnote RF Handbook)."""

from __future__ import annotations

import math
import re
from typing import Any

from .rf_kpi import grade_value, load_kpi_thresholds

# Typical n78 FR1 macro scenario (editable via query tokens)
_DEFAULT_SCENARIO: dict[str, Any] = {
    "band": "n78",
    "freq_mhz": 3500.0,
    "bandwidth_mhz": 100,
    "n_rb": 273,  # 100 MHz @ 30 kHz SCS (TS 38.101-1)
    "distance_km": 0.5,
    "tx_eirp_dbm": 55.0,  # gNB EIRP incl. antenna gain
    "extra_path_loss_db": 10.0,  # clutter / shadowing beyond free space
    "rx_antenna_gain_dbi": 0.0,
    "cable_body_loss_db": 3.0,
    "noise_floor_dbm": -100.0,  # thermal + NF in measurement BW (~100 MHz)
    "interference_clean_dbm": -115.0,
    "interference_loaded_dbm": -88.0,
    "clean_rsrq_db": -8.0,
}

_BAND_FREQ_MHZ: dict[str, float] = {
    "n41": 2500.0,
    "n77": 3700.0,
    "n78": 3500.0,
    "n79": 4700.0,
    "n261": 28000.0,
}

_LINK_BUDGET_KW = (
    "link budget",
    "linkbudget",
    "friis",
    "path loss",
    "pathloss",
)
_SINR_KW = ("sinr", "ss-sinr", "ss sinr", "signal to interference")
_RSRQ_KW = ("rsrq", "ss-rsrq", "ss rsrq", "reference signal received quality")
_COMPARE_KW = (" vs ", " versus ", "compare", "difference", "explain")


def looks_like_link_budget_query(query: str) -> bool:
    """True when the user wants SINR/RSRQ explanation and/or link-budget math."""
    ql = query.lower().strip()
    if not ql:
        return False
    has_sinr = any(k in ql for k in _SINR_KW)
    has_rsrq = any(k in ql for k in _RSRQ_KW)
    has_lb = any(k in ql for k in _LINK_BUDGET_KW)
    if has_lb:
        return True
    if has_sinr and has_rsrq:
        return True
    if (has_sinr or has_rsrq) and any(k in ql for k in _COMPARE_KW):
        return True
    if has_sinr and "link" in ql:
        return True
    if has_rsrq and "link" in ql:
        return True
    return False


def friis_path_loss_db(distance_km: float, freq_mhz: float) -> float:
    """Free-space path loss (dB). FSPL = 20·log10(d_km) + 20·log10(f_MHz) + 32.44."""
    if distance_km <= 0 or freq_mhz <= 0:
        raise ValueError("distance_km and freq_mhz must be positive")
    return 20.0 * math.log10(distance_km) + 20.0 * math.log10(freq_mhz) + 32.44


def dl_rsrp_dbm(
    tx_eirp_dbm: float,
    path_loss_db: float,
    *,
    rx_antenna_gain_dbi: float = 0.0,
    cable_body_loss_db: float = 0.0,
) -> float:
    """Downlink SS-RSRP from link budget (dBm)."""
    return tx_eirp_dbm - path_loss_db + rx_antenna_gain_dbi - cable_body_loss_db


def rsrq_db(rsrp_dbm: float, rssi_dbm: float, n_rb: int) -> float:
    """SS-RSRQ (dB) per TS 38.215: RSRQ = N·RSRP/RSSI (linear power ratio)."""
    if n_rb < 1:
        raise ValueError("n_rb must be >= 1")
    rsrp_lin = 10.0 ** (rsrp_dbm / 10.0)
    rssi_lin = 10.0 ** (rssi_dbm / 10.0)
    if rssi_lin <= 0:
        return float("-inf")
    return 10.0 * math.log10(n_rb * rsrp_lin / rssi_lin)


def sinr_db(signal_dbm: float, interference_dbm: float, noise_dbm: float) -> float:
    """SS-SINR (dB): wanted signal vs interference + noise (linear sum in denominator)."""
    sig = 10.0 ** (signal_dbm / 10.0)
    intf = 10.0 ** (interference_dbm / 10.0)
    noise = 10.0 ** (noise_dbm / 10.0)
    denom = intf + noise
    if denom <= 0:
        return float("inf")
    return 10.0 * math.log10(sig / denom)


def rssi_for_rsrq(rsrp_dbm: float, rsrq_db_target: float, n_rb: int) -> float:
    """RSSI (dBm) consistent with target RSRQ: RSSI = N·RSRP / RSRQ (linear)."""
    rsrp_lin = 10.0 ** (rsrp_dbm / 10.0)
    rsrq_lin = 10.0 ** (rsrq_db_target / 10.0)
    rssi_lin = n_rb * rsrp_lin / rsrq_lin
    return 10.0 * math.log10(rssi_lin)


def rssi_loaded_dbm(rsrp_dbm: float, interference_dbm: float, n_rb: int, *, clean_rsrq_db: float = -8.0) -> float:
    """Wideband RSSI when other-cell power is added to the lightly loaded baseline."""
    base_lin = 10.0 ** (rssi_for_rsrq(rsrp_dbm, clean_rsrq_db, n_rb) / 10.0)
    intf_lin = 10.0 ** (interference_dbm / 10.0)
    return 10.0 * math.log10(base_lin + intf_lin)


def _parse_scenario(query: str, base: dict[str, Any] | None = None) -> dict[str, Any]:
    s = dict(base or _DEFAULT_SCENARIO)
    ql = query.lower()

    band_m = re.search(r"\bn(\d{1,3})\b", ql)
    if band_m:
        band = f"n{band_m.group(1)}"
        s["band"] = band
        if band in _BAND_FREQ_MHZ:
            s["freq_mhz"] = _BAND_FREQ_MHZ[band]

    dist_m = re.search(r"(\d+(?:\.\d+)?)\s*km", ql)
    if dist_m:
        s["distance_km"] = float(dist_m.group(1))

    freq_m = re.search(r"(\d+(?:\.\d+)?)\s*ghz", ql)
    if freq_m:
        s["freq_mhz"] = float(freq_m.group(1)) * 1000.0
    else:
        freq_mhz = re.search(r"(\d+(?:\.\d+)?)\s*mhz", ql)
        if freq_mhz:
            s["freq_mhz"] = float(freq_mhz.group(1))

    eirp_m = re.search(r"eirp[:\s=]*(-?\d+(?:\.\d+)?)\s*dbm", ql)
    if eirp_m:
        s["tx_eirp_dbm"] = float(eirp_m.group(1))

    return s


def _grade_kpi(kpi_id: str, value: float) -> str:
    thresholds = load_kpi_thresholds().get("kpis", {})
    kpi = thresholds.get(kpi_id)
    if not kpi:
        return "unknown"
    return grade_value(kpi, value)


def compute_link_budget_scenario(scenario: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return structured link-budget + KPI numbers for one DL scenario."""
    s = dict(_DEFAULT_SCENARIO)
    if scenario:
        s.update(scenario)

    fspl = friis_path_loss_db(s["distance_km"], s["freq_mhz"])
    total_pl = fspl + s["extra_path_loss_db"]
    rsrp = dl_rsrp_dbm(
        s["tx_eirp_dbm"],
        total_pl,
        rx_antenna_gain_dbi=s["rx_antenna_gain_dbi"],
        cable_body_loss_db=s["cable_body_loss_db"],
    )

    def _scenario_kpis(interference_dbm: float, label: str, *, clean: bool = False) -> dict[str, Any]:
        if clean:
            rssi = rssi_for_rsrq(rsrp, s["clean_rsrq_db"], s["n_rb"])
            rsrq = rsrq_db(rsrp, rssi, s["n_rb"])
        else:
            rssi = rssi_loaded_dbm(rsrp, interference_dbm, s["n_rb"], clean_rsrq_db=s["clean_rsrq_db"])
            rsrq = rsrq_db(rsrp, rssi, s["n_rb"])
        sinr = sinr_db(rsrp, interference_dbm, s["noise_floor_dbm"])
        return {
            "label": label,
            "interference_dbm": interference_dbm,
            "rssi_dbm": round(rssi, 2),
            "rsrq_db": round(rsrq, 2),
            "sinr_db": round(sinr, 2),
            "rsrq_grade": _grade_kpi("ss_rsrq", rsrq),
            "sinr_grade": _grade_kpi("ss_sinr", sinr),
        }

    return {
        "band": s["band"],
        "freq_mhz": s["freq_mhz"],
        "bandwidth_mhz": s["bandwidth_mhz"],
        "n_rb": s["n_rb"],
        "distance_km": s["distance_km"],
        "tx_eirp_dbm": s["tx_eirp_dbm"],
        "free_space_path_loss_db": round(fspl, 2),
        "extra_path_loss_db": s["extra_path_loss_db"],
        "total_path_loss_db": round(total_pl, 2),
        "rsrp_dbm": round(rsrp, 2),
        "rsrp_grade": _grade_kpi("ss_rsrp", rsrp),
        "noise_floor_dbm": s["noise_floor_dbm"],
        "kpi_scenarios": [
            _scenario_kpis(s["interference_clean_dbm"], "low_interference", clean=True),
            _scenario_kpis(s["interference_loaded_dbm"], "moderate_interference"),
        ],
    }


def explain_sinr_vs_rsrq_link_budget(query: str = "") -> str:
    """Full markdown explanation with definitions, formulas, and worked link-budget example."""
    scenario = _parse_scenario(query)
    calc = compute_link_budget_scenario(scenario)
    clean = calc["kpi_scenarios"][0]
    loaded = calc["kpi_scenarios"][1]
    thresholds = load_kpi_thresholds().get("kpis", {})

    rsrp_th = thresholds.get("ss_rsrp", {})
    rsrq_th = thresholds.get("ss_rsrq", {})
    sinr_th = thresholds.get("ss_sinr", {})

    lines = [
        "## SINR vs RSRQ — and how they connect to the link budget",
        "",
        "### What each KPI measures (NR SS measurements, TS 38.215)",
        "",
        "| KPI | Measures | Link-budget role | Test-engineer use |",
        "|-----|----------|------------------|-------------------|",
        "| **SS-RSRP** | Average power of SS/PBCH reference signals (dBm) | **Direct link-budget output** — Tx EIRP − path loss + Rx gain − losses | Coverage, cell edge, handover threshold |",
        "| **SS-RSRQ** | `(N·RSRP) / RSSI` — RSRP relative to **total in-band received power** (dB) | Depends on RSRP **and** loading/interference in the measurement BW | Detect interference-heavy cells where RSRP still looks OK |",
        "| **SS-SINR** | Wanted signal / (**interference + noise**) after receiver (dB) | Derived from RSRP vs (I+N); strongest **scheduler/throughput** predictor | MCS, BLER, peak throughput troubleshooting |",
        "",
        "**Key insight:** RSRP answers *\"how strong is the cell?\"* RSRQ answers *\"how clean is the channel vs total in-band energy?\"* SINR answers *\"how much usable signal does the scheduler see?\"*",
        "",
        "### Formulas used in this worked example",
        "",
        "```",
        "FSPL (dB)     = 20·log10(d_km) + 20·log10(f_MHz) + 32.44     [Friis free space]",
        "RSRP (dBm)    = EIRP − path_loss + G_rx − cable/body_loss   [DL link budget]",
        "RSRQ (dB)     = 10·log10(N_RB · RSRP / RSSI)                 [TS 38.215 §5.1.3]",
        "SINR (dB)     = 10·log10(RSRP / (I + N))                     [TS 38.215 §5.1.5]",
        "```",
        "",
        f"### Worked DL link budget — **{calc['band']}** @ {calc['freq_mhz']:.0f} MHz, {calc['distance_km']} km",
        "",
        "| Step | Value |",
        "|------|-------|",
        f"| gNB EIRP | {calc['tx_eirp_dbm']:.1f} dBm |",
        f"| Free-space path loss @ {calc['distance_km']} km | {calc['free_space_path_loss_db']:.1f} dB |",
        f"| Clutter / shadow margin | {calc['extra_path_loss_db']:.1f} dB |",
        f"| **Total path loss** | **{calc['total_path_loss_db']:.1f} dB** |",
        f"| UE cable + body loss | {scenario['cable_body_loss_db']:.1f} dB |",
        f"| **Predicted SS-RSRP** | **{calc['rsrp_dbm']:.1f} dBm** ({calc['rsrp_grade']}) |",
        "",
        f"Measurement bandwidth: {calc['bandwidth_mhz']} MHz → N_RB = {calc['n_rb']} (30 kHz SCS).",
        "",
        "### From the same RSRP — RSRQ and SINR diverge under interference",
        "",
        "| Scenario | Interference (dBm) | RSSI (dBm) | RSRQ (dB) | SINR (dB) |",
        "|----------|-------------------|------------|-----------|-----------|",
        f"| Low interference (quiet cell) | {clean['interference_dbm']:.0f} | {clean['rssi_dbm']:.1f} | **{clean['rsrq_db']:.1f}** ({clean['rsrq_grade']}) | **{clean['sinr_db']:.1f}** ({clean['sinr_grade']}) |",
        f"| Moderate interference (loaded cell) | {loaded['interference_dbm']:.0f} | {loaded['rssi_dbm']:.1f} | **{loaded['rsrq_db']:.1f}** ({loaded['rsrq_grade']}) | **{loaded['sinr_db']:.1f}** ({loaded['sinr_grade']}) |",
        "",
        f"Same RSRP ({calc['rsrp_dbm']:.1f} dBm), but RSRQ drops **{clean['rsrq_db'] - loaded['rsrq_db']:.1f} dB** and SINR drops **{clean['sinr_db'] - loaded['sinr_db']:.1f} dB** when interference rises — "
        "this is why drive-test reports show *good RSRP but poor throughput*.",
        "",
        "### Lab thresholds (from `rf_kpi_thresholds.json`)",
        "",
        f"- **RSRP** — good ≥ {rsrp_th.get('good', {}).get('min', '?')} dBm, fair ≥ {rsrp_th.get('fair', {}).get('min', '?')} dBm ({rsrp_th.get('spec', 'TS 38.215')})",
        f"- **RSRQ** — good ≥ {rsrq_th.get('good', {}).get('min', '?')} dB, fair ≥ {rsrq_th.get('fair', {}).get('min', '?')} dB ({rsrq_th.get('spec', 'TS 38.215')})",
        f"- **SINR** — good ≥ {sinr_th.get('good', {}).get('min', '?')} dB, fair ≥ {sinr_th.get('fair', {}).get('min', '?')} dB ({sinr_th.get('spec', 'TS 38.215')})",
        "",
        "### When to use which metric",
        "",
        "1. **Link budget / site planning** → compute **RSRP** from EIRP, path loss, and margins.",
        "2. **Interference audit** (same RSRP, bad user experience) → check **RSRQ** and wideband RSSI.",
        "3. **Throughput / MCS / BLER debug** → prioritize **SINR**; correlate with CQI and RI.",
        "4. **Handover tuning** → RSRP for threshold, but verify SINR on target cell before HO.",
        "",
        "### References",
        "",
        "- [ShareTechnote — Link budget](https://www.sharetechnote.com/html/RF_Handbook_LinkBudget.html)",
        "- [ShareTechnote — SNR / SINR](https://www.sharetechnote.com/html/RF_Handbook_SNR.html)",
        "- [ShareTechnote — Friis equation](https://www.sharetechnote.com/html/RF_Handbook_FriisTransmissionEquation.html)",
        "- 3GPP TS 38.215 §5.1 — SS-RSRP / SS-RSRQ / SS-SINR definitions",
        "",
        "*Tip: pass distance (`0.8 km`), band (`n77`), or EIRP (`EIRP=52 dBm`) in your query to recalculate.*",
    ]
    return "\n".join(lines)


def explain_link_budget_dict(query: str = "") -> dict[str, Any]:
    """Structured payload for API / tools."""
    scenario = _parse_scenario(query)
    calc = compute_link_budget_scenario(scenario)
    return {
        "ok": True,
        "query": query,
        "scenario": scenario,
        "calculation": calc,
        "markdown": explain_sinr_vs_rsrq_link_budget(query),
    }
