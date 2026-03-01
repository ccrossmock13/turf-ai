"""
Unit Conversion and Rate Calculator for Greenside AI.

Comprehensive conversion and calculation tools used by golf course
superintendents for spray applications, fertilizer programs, irrigation
scheduling, and general turfgrass management math.

No database tables required -- pure calculation logic.
"""

import logging
import math
from typing import Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Area
SQFT_PER_ACRE = 43_560
SQFT_PER_1000 = 1_000
SQYD_PER_ACRE = 4_840
SQYD_PER_SQFT = 1 / 9
SQMETERS_PER_ACRE = 4_046.8564224
SQMETERS_PER_HECTARE = 10_000
SQFT_PER_SQMETER = 10.7639104
ACRES_PER_HECTARE = 2.47105
HECTARES_PER_ACRE = 1 / ACRES_PER_HECTARE

# Volume
FL_OZ_PER_GALLON = 128
LITERS_PER_GALLON = 3.78541
ML_PER_LITER = 1_000
ML_PER_GALLON = LITERS_PER_GALLON * ML_PER_LITER
QUARTS_PER_GALLON = 4
PINTS_PER_GALLON = 8
CUPS_PER_GALLON = 16
FL_OZ_PER_LITER = FL_OZ_PER_GALLON / LITERS_PER_GALLON

# Weight
OZ_PER_LB = 16
GRAMS_PER_OZ = 28.3495
GRAMS_PER_LB = OZ_PER_LB * GRAMS_PER_OZ
GRAMS_PER_KG = 1_000
KG_PER_LB = GRAMS_PER_LB / GRAMS_PER_KG
LBS_PER_KG = 1 / KG_PER_LB
LBS_PER_TON = 2_000

# Irrigation
GALLONS_PER_CUBIC_FT = 7.48052
CUBIC_FT_PER_CUBIC_YD = 27
GALLONS_PER_ACRE_INCH = 27_154

# Sprayer
# GPA formula constant: (5940) = (43560 sqft/acre * 60 min/hr) / (5280 ft/mile * 12 in/ft)
GPA_CONSTANT = 5_940


# ---------------------------------------------------------------------------
# Error Helpers
# ---------------------------------------------------------------------------

class ConversionError(ValueError):
    """Raised when a unit conversion cannot be performed."""
    pass


def _validate_positive(value: float, name: str = "value") -> None:
    """Raise ConversionError if *value* is not a positive finite number."""
    if not isinstance(value, (int, float)):
        raise ConversionError(f"{name} must be a number, got {type(value).__name__}")
    if math.isnan(value) or math.isinf(value):
        raise ConversionError(f"{name} must be finite, got {value}")
    if value < 0:
        raise ConversionError(f"{name} must be non-negative, got {value}")

def _validate_strictly_positive(value: float, name: str = "value") -> None:
    """Raise ConversionError if *value* is not strictly > 0."""
    _validate_positive(value, name)
    if value == 0:
        raise ConversionError(f"{name} must be greater than zero")


def _normalize_unit(unit: str) -> str:
    """Lower-case and collapse common aliases for a unit string."""
    u = unit.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    aliases = {
        # Area
        "sqft": "sqft", "squarefeet": "sqft", "squarefoot": "sqft",
        "ft2": "sqft", "sf": "sqft",
        "sqyd": "sqyd", "squareyard": "sqyd", "squareyards": "sqyd",
        "yd2": "sqyd",
        "sqm": "sqm", "squaremeter": "sqm", "squaremeters": "sqm",
        "m2": "sqm",
        "acre": "acre", "acres": "acre", "ac": "acre",
        "hectare": "hectare", "hectares": "hectare", "ha": "hectare",
        "1000sqft": "1000sqft", "ksqft": "1000sqft", "msf": "1000sqft",
        "1000sf": "1000sqft",
        # Volume
        "gal": "gal", "gallon": "gal", "gallons": "gal",
        "floz": "floz", "fl.oz": "floz", "fluidounce": "floz",
        "fluidounces": "floz", "fluidoz": "floz",
        "liter": "liter", "liters": "liter", "litre": "liter",
        "litres": "liter", "l": "liter",
        "ml": "ml", "milliliter": "ml", "milliliters": "ml",
        "millilitre": "ml", "millilitres": "ml",
        "quart": "quart", "quarts": "quart", "qt": "quart",
        "pint": "pint", "pints": "pint", "pt": "pint",
        "cup": "cup", "cups": "cup",
        # Weight
        "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
        "oz": "oz", "ounce": "oz", "ounces": "oz",
        "g": "g", "gram": "g", "grams": "g",
        "kg": "kg", "kilogram": "kg", "kilograms": "kg",
        "ton": "ton", "tons": "ton", "shortton": "ton",
    }
    return aliases.get(u, u)


# ---------------------------------------------------------------------------
# Conversion Factor Tables (relative to base units)
# ---------------------------------------------------------------------------

# Area: everything relative to sqft
_AREA_TO_SQFT = {
    "sqft":     1.0,
    "sqyd":     9.0,
    "sqm":      SQFT_PER_SQMETER,
    "acre":     float(SQFT_PER_ACRE),
    "hectare":  float(SQFT_PER_ACRE) * ACRES_PER_HECTARE,
    "1000sqft": float(SQFT_PER_1000),
}

# Volume: everything relative to gallons
_VOLUME_TO_GAL = {
    "gal":   1.0,
    "floz":  1.0 / FL_OZ_PER_GALLON,
    "liter": 1.0 / LITERS_PER_GALLON,
    "ml":    1.0 / ML_PER_GALLON,
    "quart": 1.0 / QUARTS_PER_GALLON,
    "pint":  1.0 / PINTS_PER_GALLON,
    "cup":   1.0 / CUPS_PER_GALLON,
}

# Weight: everything relative to lbs
_WEIGHT_TO_LB = {
    "lb":  1.0,
    "oz":  1.0 / OZ_PER_LB,
    "g":   1.0 / GRAMS_PER_LB,
    "kg":  LBS_PER_KG,
    "ton": float(LBS_PER_TON),
}

# ---------------------------------------------------------------------------
# 1. Area Conversions
# ---------------------------------------------------------------------------

def convert_area(value: float, from_unit: str, to_unit: str) -> Dict:
    """
    Convert an area measurement between supported units.

    Supported units: sqft, sqyd, sqm, acre, hectare, 1000sqft

    Returns dict with 'value', 'unit', and 'formula'.
    """
    _validate_positive(value, "area")
    fu = _normalize_unit(from_unit)
    tu = _normalize_unit(to_unit)

    if fu not in _AREA_TO_SQFT:
        raise ConversionError(
            f"Unknown area unit '{from_unit}'. "
            f"Supported: {', '.join(sorted(_AREA_TO_SQFT))}"
        )
    if tu not in _AREA_TO_SQFT:
        raise ConversionError(
            f"Unknown area unit '{to_unit}'. "
            f"Supported: {', '.join(sorted(_AREA_TO_SQFT))}"
        )

    sqft = value * _AREA_TO_SQFT[fu]
    result = sqft / _AREA_TO_SQFT[tu]
    return {
        "value": round(result, 6),
        "unit": to_unit,
        "formula": (
            f"{value} {from_unit} * ({_AREA_TO_SQFT[fu]} sqft/{from_unit})"
            f" / ({_AREA_TO_SQFT[tu]} sqft/{to_unit})"
            f" = {round(result, 6)} {to_unit}"
        ),
    }


# ---------------------------------------------------------------------------
# 2. Volume Conversions
# ---------------------------------------------------------------------------

def convert_volume(value: float, from_unit: str, to_unit: str) -> Dict:
    """
    Convert a volume measurement between supported units.

    Supported units: gal, floz, liter, ml, quart, pint, cup

    Returns dict with 'value', 'unit', and 'formula'.
    """
    _validate_positive(value, "volume")
    fu = _normalize_unit(from_unit)
    tu = _normalize_unit(to_unit)
    if fu not in _VOLUME_TO_GAL:
        raise ConversionError(
            f"Unknown volume unit '{from_unit}'. "
            f"Supported: {', '.join(sorted(_VOLUME_TO_GAL))}"
        )
    if tu not in _VOLUME_TO_GAL:
        raise ConversionError(
            f"Unknown volume unit '{to_unit}'. "
            f"Supported: {', '.join(sorted(_VOLUME_TO_GAL))}"
        )

    gallons = value * _VOLUME_TO_GAL[fu]
    result = gallons / _VOLUME_TO_GAL[tu]

    return {
        "value": round(result, 6),
        "unit": to_unit,
        "formula": (
            f"{value} {from_unit} -> {round(gallons, 6)} gal"
            f" -> {round(result, 6)} {to_unit}"
        ),
    }


# ---------------------------------------------------------------------------
# 3. Weight Conversions
# ---------------------------------------------------------------------------
def convert_weight(value: float, from_unit: str, to_unit: str) -> Dict:
    """
    Convert a weight measurement between supported units.

    Supported units: lb, oz, g, kg, ton

    Returns dict with 'value', 'unit', and 'formula'.
    """
    _validate_positive(value, "weight")
    fu = _normalize_unit(from_unit)
    tu = _normalize_unit(to_unit)

    if fu not in _WEIGHT_TO_LB:
        raise ConversionError(
            f"Unknown weight unit '{from_unit}'. "
            f"Supported: {', '.join(sorted(_WEIGHT_TO_LB))}"
        )
    if tu not in _WEIGHT_TO_LB:
        raise ConversionError(
            f"Unknown weight unit '{to_unit}'. "
            f"Supported: {', '.join(sorted(_WEIGHT_TO_LB))}"
        )

    lbs = value * _WEIGHT_TO_LB[fu]
    result = lbs / _WEIGHT_TO_LB[tu]

    return {
        "value": round(result, 6),
        "unit": to_unit,
        "formula": (
            f"{value} {from_unit} -> {round(lbs, 6)} lb"
            f" -> {round(result, 6)} {to_unit}"
        ),
    }


# ---------------------------------------------------------------------------
# 4. Rate Conversions
# ---------------------------------------------------------------------------

# Rate strings use the form "<amount_unit>/<area_unit>".
# We parse them into (amount_unit, area_unit) and convert each dimension
# independently.

_RATE_AMOUNT_TYPE = {
    # Volume amounts
    "floz": "volume", "gal": "volume", "liter": "volume",
    "ml": "volume", "quart": "volume", "pint": "volume", "cup": "volume",
    # Weight amounts
    "lb": "weight", "oz": "weight", "g": "weight",
    "kg": "weight", "ton": "weight",
}

def _parse_rate(rate_str: str) -> Tuple[str, str]:
    """
    Parse a rate string like 'fl oz/1000 sqft' into (amount_unit, area_unit).

    Handles common superintendent shorthand:
      'fl oz/1000 sqft', 'oz/acre', 'lbs/A', 'ml/100 sqm',
      'gal/1000 sqft', 'kg/ha', 'g/100 sqm', 'L/ha'
    """
    raw = rate_str.strip().lower()

    if "/" not in raw:
        raise ConversionError(
            f"Rate string must contain '/' separating amount and area:"
            f" '{rate_str}'"
        )

    amount_raw, area_raw = raw.split("/", 1)
    amount_raw = amount_raw.strip()
    area_raw = area_raw.strip().replace(" ", "")

    # Map common area rate denominators
    area_aliases = {
        "1000sqft": "1000sqft", "1000sf": "1000sqft",
        "msf": "1000sqft", "ksqft": "1000sqft", "m": "1000sqft",
        "a": "acre", "ac": "acre", "acre": "acre", "acres": "acre",
        "ha": "hectare", "hectare": "hectare", "hectares": "hectare",
        "100sqm": "100sqm", "100m2": "100sqm",
        "sqft": "sqft", "sqm": "sqm",
    }
    area_unit = area_aliases.get(area_raw)
    if area_unit is None:
        raise ConversionError(
            f"Unknown area unit in rate denominator: '{area_raw}'. "
            f"Supported: {', '.join(sorted(area_aliases))}"
        )

    amount_unit = _normalize_unit(amount_raw)
    if amount_unit not in _RATE_AMOUNT_TYPE:
        raise ConversionError(
            f"Unknown amount unit in rate numerator: '{amount_raw}'. "
            f"Supported: fl oz, oz, lbs, gal, ml, liter, g, kg"
        )

    return amount_unit, area_unit


# Area denominators expressed in sq ft so we can cross-convert
_RATE_AREA_IN_SQFT = {
    "1000sqft": 1_000.0,
    "acre": float(SQFT_PER_ACRE),
    "hectare": float(SQFT_PER_ACRE) * ACRES_PER_HECTARE,
    "100sqm": 100.0 * SQFT_PER_SQMETER,
    "sqft": 1.0,
    "sqm": SQFT_PER_SQMETER,
}

def convert_rate(value: float, from_rate: str, to_rate: str) -> Dict:
    """
    Convert an application rate between different unit combinations.

    Common conversions:
      - fl oz/1000 sqft  <->  fl oz/acre  <->  ml/100 sqm
      - oz/1000 sqft     <->  lbs/acre    <->  g/100 sqm  <->  kg/ha
      - lbs/1000 sqft    <->  lbs/acre    <->  kg/ha
      - gal/acre         <->  gal/1000 sqft <-> L/ha

    The numerator (amount) and denominator (area) are each converted
    independently.

    Returns dict with 'value', 'unit', and 'formula'.
    """
    _validate_positive(value, "rate")

    from_amount, from_area = _parse_rate(from_rate)
    to_amount, to_area = _parse_rate(to_rate)

    # Validate that amount types are compatible (both volume or both weight)
    from_type = _RATE_AMOUNT_TYPE[from_amount]
    to_type = _RATE_AMOUNT_TYPE[to_amount]
    if from_type != to_type:
        raise ConversionError(
            f"Cannot convert between volume rate ({from_rate}) and"
            f" weight rate ({to_rate}). Both numerator units must be"
            f" the same dimension (volume or weight)."
        )
    # Step 1: Convert the amount numerator to a common base
    if from_type == "volume":
        base_from = _VOLUME_TO_GAL[from_amount]
        base_to = _VOLUME_TO_GAL[to_amount]
    else:
        base_from = _WEIGHT_TO_LB[from_amount]
        base_to = _WEIGHT_TO_LB[to_amount]

    amount_factor = base_from / base_to  # converts 1 from_amount to to_amount

    # Step 2: Convert the area denominator
    # If to_area is larger => rate number gets bigger
    area_factor = _RATE_AREA_IN_SQFT[to_area] / _RATE_AREA_IN_SQFT[from_area]

    result = value * amount_factor * area_factor

    return {
        "value": round(result, 6),
        "unit": to_rate,
        "formula": (
            f"{value} {from_rate}"
            f" * (amount factor {round(amount_factor, 6)})"
            f" * (area factor {round(area_factor, 6)})"
            f" = {round(result, 6)} {to_rate}"
        ),
    }

# ---------------------------------------------------------------------------
# 5. Spray Calculators
# ---------------------------------------------------------------------------

def calculate_product_needed(
    rate: float,
    rate_unit: str,
    area_acres: float,
) -> Dict:
    """
    Calculate total product needed for a given area at a given rate.

    *rate*       -- application rate (e.g. 3.0)
    *rate_unit*  -- rate expression (e.g. 'fl oz/1000 sqft')
    *area_acres* -- total area in acres

    Returns dict with product amount, unit, and formula.
    """
    _validate_positive(rate, "rate")
    _validate_strictly_positive(area_acres, "area_acres")

    amount_unit, area_unit = _parse_rate(rate_unit)

    # Convert the rate's area denominator to acres, then multiply by area
    area_sqft = _RATE_AREA_IN_SQFT[area_unit]
    rate_per_sqft = rate / area_sqft
    total_sqft = area_acres * SQFT_PER_ACRE
    total_amount = rate_per_sqft * total_sqft
    # Determine a friendly output unit label
    friendly_labels = {
        "floz": "fl oz", "gal": "gal", "liter": "L", "ml": "mL",
        "oz": "oz", "lb": "lbs", "g": "g", "kg": "kg",
    }
    unit_display = friendly_labels.get(amount_unit, amount_unit)

    return {
        "value": round(total_amount, 4),
        "unit": unit_display,
        "area_acres": area_acres,
        "area_sqft": round(total_sqft, 2),
        "formula": (
            f"{rate} {rate_unit} * {round(total_sqft, 2)} sqft"
            f" / {area_sqft} sqft"
            f" = {round(total_amount, 4)} {unit_display}"
        ),
    }


def calculate_tank_loads(total_gallons: float, tank_size: float) -> Dict:
    """
    Calculate number of tank loads required.

    Returns dict with full loads, partial last load, and total loads.
    """
    _validate_positive(total_gallons, "total_gallons")
    _validate_strictly_positive(tank_size, "tank_size")
    full_loads = int(total_gallons // tank_size)
    remainder = total_gallons - (full_loads * tank_size)
    remainder = round(remainder, 4)
    total_loads = full_loads + (1 if remainder > 0 else 0)

    return {
        "total_loads": total_loads,
        "full_loads": full_loads,
        "partial_load_gallons": remainder if remainder > 0 else None,
        "tank_size": tank_size,
        "total_gallons": round(total_gallons, 4),
        "unit": "loads",
        "formula": (
            f"{round(total_gallons, 4)} gal / {tank_size} gal/tank"
            f" = {full_loads} full + "
            + (
                f"1 partial ({remainder} gal)"
                if remainder > 0
                else "0 partial"
            )
        ),
    }


def calculate_gpa(
    speed_mph: float,
    nozzle_spacing_inches: float,
    flow_rate_gpm: float,
) -> Dict:
    """
    Calculate gallons per acre (GPA) from sprayer setup.

    Formula: GPA = (flow_rate_gpm * 5940) / (speed_mph * nozzle_spacing_inches)

    Where 5940 = (43560 * 60) / (5280 * 12)

    Returns dict with GPA value and formula.
    """
    _validate_strictly_positive(speed_mph, "speed_mph")
    _validate_strictly_positive(nozzle_spacing_inches, "nozzle_spacing_inches")
    _validate_strictly_positive(flow_rate_gpm, "flow_rate_gpm")

    gpa = (flow_rate_gpm * GPA_CONSTANT) / (speed_mph * nozzle_spacing_inches)

    return {
        "value": round(gpa, 2),
        "unit": "gal/acre",
        "formula": (
            f"({flow_rate_gpm} GPM * {GPA_CONSTANT})"
            f" / ({speed_mph} mph * {nozzle_spacing_inches} in)"
            f" = {round(gpa, 2)} GPA"
        ),
    }


def calculate_nozzle_flow_rate(
    gpa: float,
    speed_mph: float,
    nozzle_spacing_inches: float,
) -> Dict:
    """
    Calculate required nozzle flow rate (GPM) for a target GPA.

    Formula: GPM = (GPA * speed_mph * nozzle_spacing_inches) / 5940
    """
    _validate_strictly_positive(gpa, "gpa")
    _validate_strictly_positive(speed_mph, "speed_mph")
    _validate_strictly_positive(nozzle_spacing_inches, "nozzle_spacing_inches")

    gpm = (gpa * speed_mph * nozzle_spacing_inches) / GPA_CONSTANT

    return {
        "value": round(gpm, 4),
        "unit": "GPM",
        "formula": (
            f"({gpa} GPA * {speed_mph} mph * {nozzle_spacing_inches} in)"
            f" / {GPA_CONSTANT} = {round(gpm, 4)} GPM"
        ),
    }


def calculate_speed(
    gpa: float,
    nozzle_spacing_inches: float,
    flow_rate_gpm: float,
) -> Dict:
    """
    Calculate required travel speed (mph) for a target GPA and nozzle setup.

    Formula: mph = (flow_rate_gpm * 5940) / (GPA * nozzle_spacing_inches)
    """
    _validate_strictly_positive(gpa, "gpa")
    _validate_strictly_positive(nozzle_spacing_inches, "nozzle_spacing_inches")
    _validate_strictly_positive(flow_rate_gpm, "flow_rate_gpm")

    mph = (flow_rate_gpm * GPA_CONSTANT) / (gpa * nozzle_spacing_inches)

    return {
        "value": round(mph, 2),
        "unit": "mph",
        "formula": (
            f"({flow_rate_gpm} GPM * {GPA_CONSTANT})"
            f" / ({gpa} GPA * {nozzle_spacing_inches} in)"
            f" = {round(mph, 2)} mph"
        ),
    }

# ---------------------------------------------------------------------------
# 6. Fertilizer Calculators
# ---------------------------------------------------------------------------

def _parse_npk(npk_analysis: str) -> Tuple[float, float, float]:
    """
    Parse an N-P-K analysis string like '21-0-0' or '10-10-10' into
    (n_pct, p_pct, k_pct) as decimals (e.g. 21 -> 0.21).
    """
    parts = npk_analysis.replace(" ", "").split("-")
    if len(parts) != 3:
        raise ConversionError(
            f"NPK analysis must be in 'N-P-K' format (e.g. '21-0-0'),"
            f" got '{npk_analysis}'"
        )
    try:
        values = [float(p) for p in parts]
    except ValueError:
        raise ConversionError(
            f"NPK analysis contains non-numeric values: '{npk_analysis}'"
        )
    for i, v in enumerate(values):
        if v < 0 or v > 100:
            raise ConversionError(
                f"NPK value {v} at position {i} is out of range 0-100"
            )
    return values[0] / 100.0, values[1] / 100.0, values[2] / 100.0

def calculate_nutrient_rate(
    product_rate: float,
    npk_analysis: str,
) -> Dict:
    """
    Calculate lbs of N, P2O5, and K2O per 1000 sq ft from a product
    application rate.

    *product_rate*  -- lbs of product per 1000 sq ft
    *npk_analysis*  -- fertilizer grade, e.g. '21-0-0'

    Returns dict with N, P, K rates per 1000 sqft.
    """
    _validate_positive(product_rate, "product_rate")
    n_pct, p_pct, k_pct = _parse_npk(npk_analysis)

    n_rate = product_rate * n_pct
    p_rate = product_rate * p_pct
    k_rate = product_rate * k_pct

    return {
        "nitrogen_lbs_per_1000sqft": round(n_rate, 4),
        "phosphorus_lbs_per_1000sqft": round(p_rate, 4),
        "potassium_lbs_per_1000sqft": round(k_rate, 4),
        "product_rate_lbs_per_1000sqft": product_rate,
        "npk_analysis": npk_analysis,
        "unit": "lbs/1000 sqft",
        "formula": (
            f"{product_rate} lbs product * {npk_analysis} analysis ="
            f" N: {round(n_rate, 4)}, P2O5: {round(p_rate, 4)},"
            f" K2O: {round(k_rate, 4)} lbs/1000 sqft"
        ),
    }


def calculate_product_rate_for_target_n(
    target_n_per_1000: float,
    n_pct: float,
) -> Dict:
    """
    Calculate product application rate (lbs/1000 sqft) to achieve a target
    nitrogen rate.

    *target_n_per_1000* -- desired lbs N per 1000 sqft (e.g. 1.0)
    *n_pct*             -- nitrogen percentage of product (e.g. 21 for 21-0-0)

    Returns dict with product rate and formula.
    """
    _validate_strictly_positive(target_n_per_1000, "target_n_per_1000")
    if n_pct <= 0 or n_pct > 100:
        raise ConversionError(
            f"Nitrogen percentage must be between 0 and 100, got {n_pct}"
        )

    n_decimal = n_pct / 100.0
    product_rate = target_n_per_1000 / n_decimal
    return {
        "value": round(product_rate, 4),
        "unit": "lbs product/1000 sqft",
        "target_n": target_n_per_1000,
        "n_pct": n_pct,
        "formula": (
            f"{target_n_per_1000} lbs N / ({n_pct}% / 100)"
            f" = {round(product_rate, 4)} lbs product/1000 sqft"
        ),
    }


def calculate_spreader_setting(
    product_rate: float,
    spreader_width_ft: float,
    speed_mph: float,
    product_density: float = 50.0,
) -> Dict:
    """
    Estimate a spreader opening setting based on desired rate, pass width,
    travel speed, and product bulk density.

    This gives an *approximate starting point* -- calibration with a catch
    test is always required.

    *product_rate*      -- lbs product per 1000 sqft
    *spreader_width_ft* -- effective swath width in feet
    *speed_mph*         -- travel speed in mph
    *product_density*   -- bulk density in lbs/cuft (default 50)
    Returns dict with lbs per minute feed rate needed (the superintendent
    then matches this to their spreader chart).
    """
    _validate_strictly_positive(product_rate, "product_rate")
    _validate_strictly_positive(spreader_width_ft, "spreader_width_ft")
    _validate_strictly_positive(speed_mph, "speed_mph")
    _validate_strictly_positive(product_density, "product_density")

    # feet per minute at given speed
    ft_per_min = speed_mph * 5280 / 60

    # sqft covered per minute
    sqft_per_min = ft_per_min * spreader_width_ft

    # lbs needed per minute
    lbs_per_min = (product_rate / SQFT_PER_1000) * sqft_per_min

    # cubic feet per minute (for gate opening estimate)
    cuft_per_min = lbs_per_min / product_density

    return {
        "lbs_per_minute": round(lbs_per_min, 4),
        "cuft_per_minute": round(cuft_per_min, 6),
        "sqft_per_minute": round(sqft_per_min, 2),
        "ft_per_minute": round(ft_per_min, 2),
        "unit": "lbs/min",
        "note": (
            "Use this feed rate with your spreader's calibration chart."
            " Always verify with a catch test."
        ),
        "formula": (
            f"Speed {speed_mph} mph = {round(ft_per_min, 2)} ft/min *"
            f" {spreader_width_ft} ft width ="
            f" {round(sqft_per_min, 2)} sqft/min."
            f" Rate {product_rate} lbs/1000sqft *"
            f" {round(sqft_per_min, 2)} sqft/min / 1000"
            f" = {round(lbs_per_min, 4)} lbs/min"
        ),
    }

# ---------------------------------------------------------------------------
# 7. Irrigation Calculators
# ---------------------------------------------------------------------------

def inches_to_gallons(inches: float, area_sqft: float) -> Dict:
    """
    Convert inches of water depth to gallons over a given area.

    1 inch of water over 1 sqft = 1/12 cubic foot
    """
    _validate_positive(inches, "inches")
    _validate_strictly_positive(area_sqft, "area_sqft")

    cuft = (inches / 12.0) * area_sqft
    gallons = cuft * GALLONS_PER_CUBIC_FT

    return {
        "value": round(gallons, 2),
        "unit": "gallons",
        "inches": inches,
        "area_sqft": area_sqft,
        "formula": (
            f"{inches} in / 12 * {area_sqft} sqft"
            f" = {round(cuft, 4)} cuft * {GALLONS_PER_CUBIC_FT} gal/cuft"
            f" = {round(gallons, 2)} gal"
        ),
    }

def gallons_to_inches(gallons: float, area_sqft: float) -> Dict:
    """
    Convert gallons of water to depth in inches over a given area.
    """
    _validate_positive(gallons, "gallons")
    _validate_strictly_positive(area_sqft, "area_sqft")

    cuft = gallons / GALLONS_PER_CUBIC_FT
    inches = (cuft / area_sqft) * 12.0

    return {
        "value": round(inches, 4),
        "unit": "inches",
        "gallons": gallons,
        "area_sqft": area_sqft,
        "formula": (
            f"{gallons} gal / {GALLONS_PER_CUBIC_FT} gal/cuft"
            f" = {round(cuft, 4)} cuft."
            f" {round(cuft, 4)} cuft / {area_sqft} sqft * 12"
            f" = {round(inches, 4)} inches"
        ),
    }


def calculate_run_time(
    inches_needed: float,
    precip_rate_iph: float,
) -> Dict:
    """
    Calculate irrigation run time in minutes to apply a target depth.

    *inches_needed*    -- target water depth in inches
    *precip_rate_iph*  -- precipitation rate in inches per hour
    """
    _validate_positive(inches_needed, "inches_needed")
    _validate_strictly_positive(precip_rate_iph, "precip_rate_iph")

    hours = inches_needed / precip_rate_iph
    minutes = hours * 60.0

    return {
        "value": round(minutes, 2),
        "unit": "minutes",
        "hours": round(hours, 4),
        "inches_needed": inches_needed,
        "precip_rate_iph": precip_rate_iph,
        "formula": (
            f"{inches_needed} in / {precip_rate_iph} in/hr"
            f" = {round(hours, 4)} hr = {round(minutes, 2)} min"
        ),
    }


def calculate_precip_rate(
    gpm: float,
    spacing_ft: float,
    row_spacing_ft: float,
) -> Dict:
    """
    Calculate irrigation precipitation rate in inches per hour from
    sprinkler output, head spacing, and row spacing.

    Formula: PR (in/hr) = (96.25 * GPM) / (spacing_ft * row_spacing_ft)

    Where 96.25 = (60 min/hr * 12 in/ft) / 7.48052 gal/cuft
    """
    _validate_strictly_positive(gpm, "gpm")
    _validate_strictly_positive(spacing_ft, "spacing_ft")
    _validate_strictly_positive(row_spacing_ft, "row_spacing_ft")

    pr_constant = 96.25
    precip_rate = (pr_constant * gpm) / (spacing_ft * row_spacing_ft)

    return {
        "value": round(precip_rate, 4),
        "unit": "in/hr",
        "gpm": gpm,
        "spacing_ft": spacing_ft,
        "row_spacing_ft": row_spacing_ft,
        "formula": (
            f"({pr_constant} * {gpm} GPM)"
            f" / ({spacing_ft} ft * {row_spacing_ft} ft)"
            f" = {round(precip_rate, 4)} in/hr"
        ),
    }

# ---------------------------------------------------------------------------
# 8. Turf-Specific Utilities
# ---------------------------------------------------------------------------

def calculate_gdd(
    high_temp: float,
    low_temp: float,
    base_temp: float = 50.0,
) -> Dict:
    """
    Calculate growing degree days (GDD) using the averaging method.

    Formula: GDD = max(0, ((high + low) / 2) - base)

    Common base temperatures:
      - Cool-season turf: 32 F or 50 F
      - Warm-season turf: 50 F or 60 F
      - Crabgrass germination tracking: 50 F
    """
    if not isinstance(high_temp, (int, float)):
        raise ConversionError("high_temp must be a number")
    if not isinstance(low_temp, (int, float)):
        raise ConversionError("low_temp must be a number")
    if high_temp < low_temp:
        raise ConversionError(
            f"High temp ({high_temp}) must be >= low temp ({low_temp})"
        )

    avg_temp = (high_temp + low_temp) / 2.0
    gdd = max(0.0, avg_temp - base_temp)

    return {
        "value": round(gdd, 2),
        "unit": "GDD",
        "high_temp": high_temp,
        "low_temp": low_temp,
        "base_temp": base_temp,
        "avg_temp": round(avg_temp, 2),
        "formula": (
            f"max(0, (({high_temp} + {low_temp}) / 2) - {base_temp})"
            f" = max(0, {round(avg_temp, 2)} - {base_temp})"
            f" = {round(gdd, 2)} GDD"
        ),
    }


def calculate_seeding_rate(
    lbs_per_1000sqft: float,
    area_acres: float,
) -> Dict:
    """
    Calculate total seed needed for an area.

    *lbs_per_1000sqft* -- seeding rate in lbs per 1000 sqft
    *area_acres*       -- total area in acres
    """
    _validate_positive(lbs_per_1000sqft, "lbs_per_1000sqft")
    _validate_strictly_positive(area_acres, "area_acres")
    total_sqft = area_acres * SQFT_PER_ACRE
    total_lbs = lbs_per_1000sqft * (total_sqft / SQFT_PER_1000)

    return {
        "value": round(total_lbs, 2),
        "unit": "lbs",
        "bags_50lb": math.ceil(total_lbs / 50.0),
        "area_sqft": round(total_sqft, 2),
        "formula": (
            f"{lbs_per_1000sqft} lbs/1000sqft"
            f" * {round(total_sqft, 2)} sqft / 1000"
            f" = {round(total_lbs, 2)} lbs total"
        ),
    }


def mowing_height_conversions(inches: float) -> Dict:
    """
    Convert a mowing height in inches to millimeters and common fractional
    inch representations.

    Useful for superintendents moving between metric and imperial bench
    settings.
    """
    _validate_positive(inches, "inches")

    mm = inches * 25.4

    # Common bench settings: 32nds for greens, 16ths, 8ths, 4ths
    thirty_seconds = round(inches * 32)
    sixteenths = round(inches * 16)
    eighths = round(inches * 8)
    quarters = round(inches * 4)

    return {
        "inches": round(inches, 4),
        "mm": round(mm, 2),
        "thirty_seconds": f"{thirty_seconds}/32\"",
        "sixteenths": f"{sixteenths}/16\"",
        "eighths": f"{eighths}/8\"",
        "quarters": f"{quarters}/4\"",
        "unit": "mm",
        "formula": f"{inches} in * 25.4 = {round(mm, 2)} mm",
    }


def topdressing_volume(depth_inches: float, area_sqft: float) -> Dict:
    """
    Calculate cubic yards of topdressing material (sand, compost, etc.)
    needed for a target depth over a given area.

    Formula: cubic_yards = (depth_inches / 12) * area_sqft / 27
    """
    _validate_positive(depth_inches, "depth_inches")
    _validate_strictly_positive(area_sqft, "area_sqft")

    cuft = (depth_inches / 12.0) * area_sqft
    cuyd = cuft / CUBIC_FT_PER_CUBIC_YD
    # Approximate: 1 cuyd of sand ~ 2700 lbs ~ 1.35 tons
    tons_sand = cuyd * 1.35
    return {
        "value": round(cuyd, 2),
        "unit": "cubic yards",
        "cubic_feet": round(cuft, 2),
        "approx_tons_sand": round(tons_sand, 2),
        "depth_inches": depth_inches,
        "area_sqft": area_sqft,
        "formula": (
            f"({depth_inches} in / 12) * {area_sqft} sqft"
            f" = {round(cuft, 2)} cuft / 27"
            f" = {round(cuyd, 2)} cubic yards"
        ),
    }


def lime_rate_to_product(
    caco3_lbs_per_1000: float,
    product_cce: float,
) -> Dict:
    """
    Adjust a lime recommendation (expressed as pure CaCO3 equivalent
    lbs/1000 sqft) for the actual calcium carbonate equivalent (CCE)
    percentage of a lime product.

    Soil labs report lime needs as CaCO3 equivalent.  A product with 80%
    CCE requires more product than one with 100% CCE.

    *caco3_lbs_per_1000* -- recommended lbs CaCO3 eq per 1000 sqft
    *product_cce*        -- CCE% of the lime product (e.g. 90 for 90%)
    """
    _validate_positive(caco3_lbs_per_1000, "caco3_lbs_per_1000")
    if product_cce <= 0 or product_cce > 150:
        raise ConversionError(
            f"Product CCE must be between 0 and 150%, got {product_cce}"
        )

    cce_decimal = product_cce / 100.0
    product_lbs = caco3_lbs_per_1000 / cce_decimal

    return {
        "value": round(product_lbs, 4),
        "unit": "lbs product/1000 sqft",
        "caco3_equivalent": caco3_lbs_per_1000,
        "product_cce_pct": product_cce,
        "formula": (
            f"{caco3_lbs_per_1000} lbs CaCO3 eq"
            f" / ({product_cce}% CCE / 100)"
            f" = {round(product_lbs, 4)} lbs product/1000 sqft"
        ),
    }

# ---------------------------------------------------------------------------
# Convenience: list all available converters (for API/UI integration)
# ---------------------------------------------------------------------------

AVAILABLE_CONVERTERS = {
    "area": {
        "function": "convert_area",
        "units": list(_AREA_TO_SQFT.keys()),
        "description": (
            "Convert between area units:"
            " sqft, sqyd, sqm, acre, hectare, 1000sqft"
        ),
    },
    "volume": {
        "function": "convert_volume",
        "units": list(_VOLUME_TO_GAL.keys()),
        "description": (
            "Convert between volume units:"
            " gal, floz, liter, ml, quart, pint, cup"
        ),
    },
    "weight": {
        "function": "convert_weight",
        "units": list(_WEIGHT_TO_LB.keys()),
        "description": (
            "Convert between weight units: lb, oz, g, kg, ton"
        ),
    },
    "rate": {
        "function": "convert_rate",
        "description": (
            "Convert application rates between unit/area combinations"
        ),
    },
    "spray": {
        "functions": [
            "calculate_product_needed",
            "calculate_tank_loads",
            "calculate_gpa",
            "calculate_nozzle_flow_rate",
            "calculate_speed",
        ],
        "description": (
            "Spray application calculators for product amounts,"
            " tank loads, and sprayer setup"
        ),
    },
    "fertilizer": {
        "functions": [
            "calculate_nutrient_rate",
            "calculate_product_rate_for_target_n",
            "calculate_spreader_setting",
        ],
        "description": (
            "Fertilizer rate calculators for NPK analysis"
            " and spreader calibration"
        ),
    },
    "irrigation": {
        "functions": [
            "inches_to_gallons",
            "gallons_to_inches",
            "calculate_run_time",
            "calculate_precip_rate",
        ],
        "description": (
            "Irrigation calculators for depth/volume conversion"
            " and run times"
        ),
    },
    "turf": {
        "functions": [
            "calculate_gdd",
            "calculate_seeding_rate",
            "mowing_height_conversions",
            "topdressing_volume",
            "lime_rate_to_product",
        ],
        "description": (
            "Turf-specific utilities: GDD, seeding, mowing heights,"
            " topdressing, lime"
        ),
    },
}