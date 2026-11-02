"""
Water Quality Index (WQI) calculator and utility functions.
Uses the weighted average method from the project proposal:
    WQI = Σ(qi * wi) / Σ(wi)
"""

import numpy as np
from datetime import datetime, timedelta


# ── Standard limits for water quality parameters ──────────────────
# Based on WHO and BIS drinking water standards
PARAM_STANDARDS = {
    "ph":               {"ideal": 7.0,  "min": 6.5,  "max": 8.5,   "weight": 0.22, "unit": ""},
    "turbidity":        {"ideal": 0.0,  "min": 0.0,  "max": 5.0,   "weight": 0.18, "unit": "NTU"},
    "dissolved_oxygen": {"ideal": 14.0, "min": 5.0,  "max": 14.0,  "weight": 0.25, "unit": "mg/L"},
    "temperature":      {"ideal": 25.0, "min": 10.0, "max": 35.0,  "weight": 0.10, "unit": "°C"},
    "tds":              {"ideal": 0.0,  "min": 0.0,  "max": 500.0, "weight": 0.25, "unit": "ppm"},
}

# Thresholds for automated alerts
ALERT_THRESHOLDS = {
    "ph":               {"low": 6.0,   "high": 9.0},
    "turbidity":        {"low": None,  "high": 50.0},
    "dissolved_oxygen": {"low": 4.0,   "high": None},
    "temperature":      {"low": 5.0,   "high": 40.0},
    "tds":              {"low": None,  "high": 1000.0},
}


def compute_quality_rating(param_name: str, value: float) -> float:
    """
    Compute the quality rating qi for a single parameter.
    qi = ((value - ideal) / (standard - ideal)) * 100
    Returns a score where 0 = perfect, 100 = at the limit.
    """
    if value is None or param_name not in PARAM_STANDARDS:
        return None

    std = PARAM_STANDARDS[param_name]
    ideal = std["ideal"]

    # For pH, deviation in either direction is bad
    if param_name == "ph":
        deviation = abs(value - ideal)
        max_deviation = max(abs(std["max"] - ideal), abs(ideal - std["min"]))
        qi = (deviation / max_deviation) * 100 if max_deviation > 0 else 0
    # For dissolved oxygen, higher is better
    elif param_name == "dissolved_oxygen":
        if value >= std["max"]:
            qi = 0
        elif value <= std["min"]:
            qi = 100
        else:
            qi = ((std["max"] - value) / (std["max"] - std["min"])) * 100
    # For turbidity and TDS, lower is better
    elif param_name in ("turbidity", "tds"):
        qi = min((value / std["max"]) * 100, 100) if std["max"] > 0 else 0
    # For temperature, deviation from ideal
    elif param_name == "temperature":
        deviation = abs(value - ideal)
        max_deviation = max(abs(std["max"] - ideal), abs(ideal - std["min"]))
        qi = (deviation / max_deviation) * 100 if max_deviation > 0 else 0
    else:
        qi = 50  # fallback

    return max(0, min(qi, 100))


def compute_wqi(ph=None, turbidity=None, dissolved_oxygen=None,
                temperature=None, tds=None) -> tuple:
    """
    Compute the Water Quality Index using the weighted average formula:
        WQI = Σ(qi * wi) / Σ(wi)
    Returns (wqi_score, risk_level)
    """
    params = {
        "ph": ph,
        "turbidity": turbidity,
        "dissolved_oxygen": dissolved_oxygen,
        "temperature": temperature,
        "tds": tds,
    }

    numerator = 0.0
    denominator = 0.0

    for name, value in params.items():
        if value is not None:
            qi = compute_quality_rating(name, value)
            if qi is not None:
                wi = PARAM_STANDARDS[name]["weight"]
                numerator += qi * wi
                denominator += wi

    if denominator == 0:
        return None, None

    wqi = numerator / denominator

    # Map to risk levels: lower WQI = better water quality
    if wqi <= 25:
        risk = "Good"
    elif wqi <= 50:
        risk = "Moderate"
    elif wqi <= 75:
        risk = "Poor"
    else:
        risk = "Critical"

    return round(wqi, 2), risk


def check_thresholds(ph=None, turbidity=None, dissolved_oxygen=None,
                     temperature=None, tds=None) -> list:
    """
    Check parameter values against alert thresholds.
    Returns list of (parameter, direction, value, threshold) tuples.
    """
    violations = []
    params = {
        "ph": ph,
        "turbidity": turbidity,
        "dissolved_oxygen": dissolved_oxygen,
        "temperature": temperature,
        "tds": tds,
    }

    for name, value in params.items():
        if value is None or name not in ALERT_THRESHOLDS:
            continue
        thresh = ALERT_THRESHOLDS[name]
        if thresh["low"] is not None and value < thresh["low"]:
            violations.append((name, "low", value, thresh["low"]))
        if thresh["high"] is not None and value > thresh["high"]:
            violations.append((name, "high", value, thresh["high"]))

    return violations


def severity_from_wqi(wqi: float) -> str:
    """Map WQI score to alert severity."""
    if wqi is None:
        return "info"
    if wqi <= 25:
        return "info"
    elif wqi <= 50:
        return "warning"
    else:
        return "critical"
