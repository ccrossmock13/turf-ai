"""
Climate data module for Greenside AI turfgrass management application.

Provides state-level climate normals (temperature, precipitation, frost dates, GDD),
season determination logic, and GDD calculation utilities. Data is based on
representative city climate normals for each of the 50 US states.

No external dependencies required.
"""

from datetime import datetime

# ---------------------------------------------------------------------------
# Region classifications used for turf-season determination
# ---------------------------------------------------------------------------

COOL_SEASON_STATES = {
    "maine", "new hampshire", "vermont", "massachusetts", "rhode island",
    "connecticut", "new york", "new jersey", "pennsylvania", "ohio",
    "michigan", "indiana", "illinois", "wisconsin", "minnesota", "iowa",
    "north dakota", "south dakota", "nebraska", "montana", "wyoming",
    "idaho", "washington", "oregon", "colorado", "utah", "alaska",
}

WARM_SEASON_STATES = {
    "florida", "georgia", "south carolina", "alabama", "mississippi",
    "louisiana", "texas", "arizona", "new mexico", "hawaii", "california",
    "nevada",
}

TRANSITION_ZONE_STATES = {
    "virginia", "north carolina", "tennessee", "kentucky", "west virginia",
    "maryland", "delaware", "missouri", "kansas", "oklahoma", "arkansas",
}

# ---------------------------------------------------------------------------
# 50-state climate normals
# ---------------------------------------------------------------------------

STATE_CLIMATE_DATA = {
    # ── Alabama (Birmingham) ──────────────────────────────────────────────
    "alabama": {
        "avg_temps": {
            "jan": 43, "feb": 47, "mar": 55, "apr": 63, "may": 71,
            "jun": 79, "jul": 82, "aug": 81, "sep": 75, "oct": 64,
            "nov": 54, "dec": 45,
        },
        "avg_precip": {
            "jan": 4.8, "feb": 4.9, "mar": 5.5, "apr": 4.4, "may": 4.7,
            "jun": 3.9, "jul": 5.1, "aug": 3.7, "sep": 3.8, "oct": 3.1,
            "nov": 4.3, "dec": 4.7,
        },
        "first_frost": "November 5",
        "last_frost": "March 25",
        "gdd_base50_annual": 4600,
    },

    # ── Alaska (Anchorage) ────────────────────────────────────────────────
    "alaska": {
        "avg_temps": {
            "jan": 16, "feb": 19, "mar": 26, "apr": 37, "may": 48,
            "jun": 56, "jul": 59, "aug": 57, "sep": 48, "oct": 34,
            "nov": 22, "dec": 17,
        },
        "avg_precip": {
            "jan": 0.7, "feb": 0.7, "mar": 0.5, "apr": 0.5, "may": 0.7,
            "jun": 1.0, "jul": 1.7, "aug": 2.1, "sep": 2.6, "oct": 1.6,
            "nov": 1.1, "dec": 1.0,
        },
        "first_frost": "September 15",
        "last_frost": "May 15",
        "gdd_base50_annual": 800,
    },

    # ── Arizona (Phoenix) ─────────────────────────────────────────────────
    "arizona": {
        "avg_temps": {
            "jan": 55, "feb": 59, "mar": 64, "apr": 72, "may": 81,
            "jun": 91, "jul": 95, "aug": 93, "sep": 87, "oct": 75,
            "nov": 63, "dec": 54,
        },
        "avg_precip": {
            "jan": 0.7, "feb": 0.8, "mar": 0.9, "apr": 0.3, "may": 0.1,
            "jun": 0.0, "jul": 0.9, "aug": 1.0, "sep": 0.7, "oct": 0.6,
            "nov": 0.6, "dec": 0.8,
        },
        "first_frost": "December 15",
        "last_frost": "February 5",
        "gdd_base50_annual": 6800,
    },

    # ── Arkansas (Little Rock) ────────────────────────────────────────────
    "arkansas": {
        "avg_temps": {
            "jan": 40, "feb": 45, "mar": 53, "apr": 62, "may": 71,
            "jun": 79, "jul": 83, "aug": 82, "sep": 74, "oct": 63,
            "nov": 51, "dec": 42,
        },
        "avg_precip": {
            "jan": 3.5, "feb": 3.4, "mar": 4.8, "apr": 5.0, "may": 5.4,
            "jun": 4.1, "jul": 3.4, "aug": 2.9, "sep": 3.6, "oct": 4.1,
            "nov": 4.9, "dec": 4.3,
        },
        "first_frost": "November 5",
        "last_frost": "March 25",
        "gdd_base50_annual": 4400,
    },

    # ── California (Sacramento) ───────────────────────────────────────────
    "california": {
        "avg_temps": {
            "jan": 46, "feb": 50, "mar": 54, "apr": 59, "may": 66,
            "jun": 73, "jul": 78, "aug": 77, "sep": 73, "oct": 63,
            "nov": 52, "dec": 45,
        },
        "avg_precip": {
            "jan": 3.7, "feb": 3.5, "mar": 2.6, "apr": 1.2, "may": 0.6,
            "jun": 0.1, "jul": 0.0, "aug": 0.1, "sep": 0.3, "oct": 0.9,
            "nov": 2.2, "dec": 3.2,
        },
        "first_frost": "December 1",
        "last_frost": "February 15",
        "gdd_base50_annual": 4500,
    },

    # ── Colorado (Denver) ─────────────────────────────────────────────────
    "colorado": {
        "avg_temps": {
            "jan": 30, "feb": 33, "mar": 40, "apr": 48, "may": 57,
            "jun": 67, "jul": 73, "aug": 71, "sep": 62, "oct": 50,
            "nov": 38, "dec": 30,
        },
        "avg_precip": {
            "jan": 0.5, "feb": 0.5, "mar": 1.3, "apr": 1.7, "may": 2.3,
            "jun": 1.6, "jul": 2.2, "aug": 1.8, "sep": 1.1, "oct": 1.0,
            "nov": 0.8, "dec": 0.6,
        },
        "first_frost": "October 7",
        "last_frost": "May 3",
        "gdd_base50_annual": 2800,
    },

    # ── Connecticut (Hartford) ────────────────────────────────────────────
    "connecticut": {
        "avg_temps": {
            "jan": 26, "feb": 29, "mar": 37, "apr": 48, "may": 59,
            "jun": 68, "jul": 73, "aug": 71, "sep": 63, "oct": 51,
            "nov": 41, "dec": 31,
        },
        "avg_precip": {
            "jan": 3.3, "feb": 2.8, "mar": 3.7, "apr": 3.9, "may": 4.0,
            "jun": 3.9, "jul": 3.8, "aug": 3.8, "sep": 3.8, "oct": 3.9,
            "nov": 3.5, "dec": 3.4,
        },
        "first_frost": "October 10",
        "last_frost": "April 25",
        "gdd_base50_annual": 2700,
    },

    # ── Delaware (Wilmington) ─────────────────────────────────────────────
    "delaware": {
        "avg_temps": {
            "jan": 32, "feb": 35, "mar": 43, "apr": 53, "may": 63,
            "jun": 72, "jul": 77, "aug": 75, "sep": 68, "oct": 56,
            "nov": 46, "dec": 36,
        },
        "avg_precip": {
            "jan": 3.2, "feb": 2.8, "mar": 3.7, "apr": 3.5, "may": 3.7,
            "jun": 3.5, "jul": 4.1, "aug": 3.3, "sep": 3.7, "oct": 3.2,
            "nov": 3.1, "dec": 3.3,
        },
        "first_frost": "October 28",
        "last_frost": "April 10",
        "gdd_base50_annual": 3400,
    },

    # ── Florida (Orlando) ────────────────────────────────────────────────
    "florida": {
        "avg_temps": {
            "jan": 60, "feb": 62, "mar": 66, "apr": 71, "may": 77,
            "jun": 81, "jul": 82, "aug": 82, "sep": 81, "oct": 75,
            "nov": 68, "dec": 62,
        },
        "avg_precip": {
            "jan": 2.4, "feb": 2.8, "mar": 3.5, "apr": 2.4, "may": 3.5,
            "jun": 7.3, "jul": 7.3, "aug": 6.8, "sep": 5.6, "oct": 3.4,
            "nov": 2.2, "dec": 2.5,
        },
        "first_frost": "December 26",
        "last_frost": "January 31",
        "gdd_base50_annual": 6500,
    },

    # ── Georgia (Atlanta) ────────────────────────────────────────────────
    "georgia": {
        "avg_temps": {
            "jan": 43, "feb": 47, "mar": 54, "apr": 62, "may": 70,
            "jun": 78, "jul": 81, "aug": 80, "sep": 74, "oct": 63,
            "nov": 53, "dec": 44,
        },
        "avg_precip": {
            "jan": 4.2, "feb": 4.5, "mar": 4.7, "apr": 3.5, "may": 3.6,
            "jun": 3.9, "jul": 5.2, "aug": 3.7, "sep": 3.4, "oct": 3.1,
            "nov": 3.6, "dec": 3.8,
        },
        "first_frost": "November 15",
        "last_frost": "March 20",
        "gdd_base50_annual": 4400,
    },

    # ── Hawaii (Honolulu) ────────────────────────────────────────────────
    "hawaii": {
        "avg_temps": {
            "jan": 73, "feb": 73, "mar": 74, "apr": 76, "may": 78,
            "jun": 80, "jul": 81, "aug": 82, "sep": 82, "oct": 80,
            "nov": 77, "dec": 74,
        },
        "avg_precip": {
            "jan": 2.5, "feb": 2.2, "mar": 2.1, "apr": 1.2, "may": 0.9,
            "jun": 0.4, "jul": 0.5, "aug": 0.6, "sep": 0.7, "oct": 1.6,
            "nov": 2.6, "dec": 2.9,
        },
        "first_frost": "December 31",
        "last_frost": "January 1",
        "gdd_base50_annual": 8800,
    },

    # ── Idaho (Boise) ────────────────────────────────────────────────────
    "idaho": {
        "avg_temps": {
            "jan": 30, "feb": 35, "mar": 42, "apr": 49, "may": 58,
            "jun": 66, "jul": 75, "aug": 74, "sep": 63, "oct": 50,
            "nov": 38, "dec": 30,
        },
        "avg_precip": {
            "jan": 1.3, "feb": 1.0, "mar": 1.2, "apr": 1.2, "may": 1.2,
            "jun": 0.8, "jul": 0.3, "aug": 0.3, "sep": 0.5, "oct": 0.7,
            "nov": 1.3, "dec": 1.4,
        },
        "first_frost": "October 9",
        "last_frost": "May 6",
        "gdd_base50_annual": 2700,
    },

    # ── Illinois (Springfield) ───────────────────────────────────────────
    "illinois": {
        "avg_temps": {
            "jan": 26, "feb": 31, "mar": 41, "apr": 53, "may": 63,
            "jun": 73, "jul": 76, "aug": 74, "sep": 67, "oct": 55,
            "nov": 42, "dec": 30,
        },
        "avg_precip": {
            "jan": 2.0, "feb": 2.0, "mar": 3.0, "apr": 3.7, "may": 4.6,
            "jun": 4.2, "jul": 4.0, "aug": 3.2, "sep": 3.0, "oct": 2.9,
            "nov": 3.4, "dec": 2.7,
        },
        "first_frost": "October 12",
        "last_frost": "April 17",
        "gdd_base50_annual": 3200,
    },

    # ── Indiana (Indianapolis) ───────────────────────────────────────────
    "indiana": {
        "avg_temps": {
            "jan": 28, "feb": 32, "mar": 42, "apr": 53, "may": 63,
            "jun": 73, "jul": 76, "aug": 74, "sep": 67, "oct": 55,
            "nov": 43, "dec": 32,
        },
        "avg_precip": {
            "jan": 2.7, "feb": 2.5, "mar": 3.4, "apr": 3.9, "may": 4.6,
            "jun": 4.3, "jul": 4.5, "aug": 3.5, "sep": 3.0, "oct": 3.0,
            "nov": 3.5, "dec": 3.1,
        },
        "first_frost": "October 15",
        "last_frost": "April 18",
        "gdd_base50_annual": 3200,
    },

    # ── Iowa (Des Moines) ────────────────────────────────────────────────
    "iowa": {
        "avg_temps": {
            "jan": 21, "feb": 26, "mar": 38, "apr": 50, "may": 62,
            "jun": 72, "jul": 76, "aug": 73, "sep": 64, "oct": 52,
            "nov": 38, "dec": 24,
        },
        "avg_precip": {
            "jan": 1.1, "feb": 1.2, "mar": 2.1, "apr": 3.5, "may": 4.7,
            "jun": 5.1, "jul": 4.4, "aug": 4.2, "sep": 3.1, "oct": 2.6,
            "nov": 2.0, "dec": 1.4,
        },
        "first_frost": "October 8",
        "last_frost": "April 26",
        "gdd_base50_annual": 2900,
    },

    # ── Kansas (Topeka) ──────────────────────────────────────────────────
    "kansas": {
        "avg_temps": {
            "jan": 29, "feb": 34, "mar": 44, "apr": 55, "may": 65,
            "jun": 75, "jul": 80, "aug": 78, "sep": 69, "oct": 57,
            "nov": 43, "dec": 31,
        },
        "avg_precip": {
            "jan": 1.1, "feb": 1.2, "mar": 2.4, "apr": 3.3, "may": 4.9,
            "jun": 5.2, "jul": 4.2, "aug": 3.8, "sep": 3.6, "oct": 2.9,
            "nov": 1.8, "dec": 1.3,
        },
        "first_frost": "October 15",
        "last_frost": "April 14",
        "gdd_base50_annual": 3600,
    },

    # ── Kentucky (Louisville) ────────────────────────────────────────────
    "kentucky": {
        "avg_temps": {
            "jan": 33, "feb": 37, "mar": 46, "apr": 57, "may": 66,
            "jun": 75, "jul": 79, "aug": 78, "sep": 70, "oct": 58,
            "nov": 47, "dec": 36,
        },
        "avg_precip": {
            "jan": 3.4, "feb": 3.2, "mar": 4.4, "apr": 4.1, "may": 5.0,
            "jun": 4.0, "jul": 4.5, "aug": 3.2, "sep": 3.1, "oct": 3.0,
            "nov": 3.7, "dec": 3.7,
        },
        "first_frost": "October 25",
        "last_frost": "April 13",
        "gdd_base50_annual": 3700,
    },

    # ── Louisiana (Baton Rouge) ──────────────────────────────────────────
    "louisiana": {
        "avg_temps": {
            "jan": 49, "feb": 53, "mar": 60, "apr": 67, "may": 75,
            "jun": 81, "jul": 83, "aug": 83, "sep": 78, "oct": 68,
            "nov": 58, "dec": 50,
        },
        "avg_precip": {
            "jan": 5.2, "feb": 4.7, "mar": 4.5, "apr": 5.0, "may": 5.0,
            "jun": 5.8, "jul": 6.2, "aug": 5.6, "sep": 4.6, "oct": 3.8,
            "nov": 4.5, "dec": 5.3,
        },
        "first_frost": "November 25",
        "last_frost": "March 1",
        "gdd_base50_annual": 5200,
    },

    # ── Maine (Portland) ─────────────────────────────────────────────────
    "maine": {
        "avg_temps": {
            "jan": 22, "feb": 24, "mar": 33, "apr": 44, "may": 54,
            "jun": 63, "jul": 69, "aug": 68, "sep": 59, "oct": 48,
            "nov": 38, "dec": 27,
        },
        "avg_precip": {
            "jan": 3.5, "feb": 3.1, "mar": 3.8, "apr": 3.8, "may": 3.6,
            "jun": 3.4, "jul": 3.2, "aug": 2.9, "sep": 3.4, "oct": 4.2,
            "nov": 4.3, "dec": 3.9,
        },
        "first_frost": "October 2",
        "last_frost": "May 5",
        "gdd_base50_annual": 2100,
    },

    # ── Maryland (Baltimore) ─────────────────────────────────────────────
    "maryland": {
        "avg_temps": {
            "jan": 33, "feb": 36, "mar": 44, "apr": 55, "may": 64,
            "jun": 74, "jul": 79, "aug": 77, "sep": 69, "oct": 57,
            "nov": 47, "dec": 37,
        },
        "avg_precip": {
            "jan": 3.1, "feb": 2.8, "mar": 3.7, "apr": 3.1, "may": 3.8,
            "jun": 3.6, "jul": 3.7, "aug": 3.6, "sep": 3.8, "oct": 3.2,
            "nov": 3.0, "dec": 3.3,
        },
        "first_frost": "October 27",
        "last_frost": "April 11",
        "gdd_base50_annual": 3500,
    },

    # ── Massachusetts (Boston) ───────────────────────────────────────────
    "massachusetts": {
        "avg_temps": {
            "jan": 29, "feb": 31, "mar": 38, "apr": 49, "may": 59,
            "jun": 68, "jul": 74, "aug": 73, "sep": 65, "oct": 54,
            "nov": 44, "dec": 34,
        },
        "avg_precip": {
            "jan": 3.4, "feb": 3.2, "mar": 4.1, "apr": 3.6, "may": 3.4,
            "jun": 3.5, "jul": 3.4, "aug": 3.4, "sep": 3.4, "oct": 3.8,
            "nov": 3.7, "dec": 3.6,
        },
        "first_frost": "October 15",
        "last_frost": "April 22",
        "gdd_base50_annual": 2600,
    },

    # ── Michigan (Lansing) ───────────────────────────────────────────────
    "michigan": {
        "avg_temps": {
            "jan": 22, "feb": 25, "mar": 34, "apr": 47, "may": 58,
            "jun": 67, "jul": 72, "aug": 70, "sep": 62, "oct": 50,
            "nov": 39, "dec": 27,
        },
        "avg_precip": {
            "jan": 1.8, "feb": 1.6, "mar": 2.0, "apr": 3.0, "may": 3.3,
            "jun": 3.3, "jul": 3.1, "aug": 3.4, "sep": 3.4, "oct": 2.7,
            "nov": 2.6, "dec": 2.0,
        },
        "first_frost": "October 8",
        "last_frost": "May 3",
        "gdd_base50_annual": 2400,
    },

    # ── Minnesota (Minneapolis) ──────────────────────────────────────────
    "minnesota": {
        "avg_temps": {
            "jan": 14, "feb": 19, "mar": 32, "apr": 47, "may": 59,
            "jun": 69, "jul": 74, "aug": 71, "sep": 61, "oct": 48,
            "nov": 33, "dec": 18,
        },
        "avg_precip": {
            "jan": 0.9, "feb": 0.8, "mar": 1.6, "apr": 2.7, "may": 3.4,
            "jun": 4.3, "jul": 4.0, "aug": 4.1, "sep": 2.9, "oct": 2.2,
            "nov": 1.6, "dec": 1.0,
        },
        "first_frost": "October 3",
        "last_frost": "April 30",
        "gdd_base50_annual": 2400,
    },

    # ── Mississippi (Jackson) ────────────────────────────────────────────
    "mississippi": {
        "avg_temps": {
            "jan": 45, "feb": 49, "mar": 57, "apr": 64, "may": 73,
            "jun": 80, "jul": 83, "aug": 82, "sep": 76, "oct": 65,
            "nov": 55, "dec": 46,
        },
        "avg_precip": {
            "jan": 5.0, "feb": 4.8, "mar": 5.5, "apr": 5.2, "may": 5.0,
            "jun": 3.9, "jul": 4.8, "aug": 3.6, "sep": 3.3, "oct": 3.5,
            "nov": 4.6, "dec": 5.3,
        },
        "first_frost": "November 8",
        "last_frost": "March 18",
        "gdd_base50_annual": 4800,
    },

    # ── Missouri (Kansas City) ───────────────────────────────────────────
    "missouri": {
        "avg_temps": {
            "jan": 29, "feb": 34, "mar": 44, "apr": 55, "may": 65,
            "jun": 74, "jul": 79, "aug": 77, "sep": 69, "oct": 57,
            "nov": 44, "dec": 32,
        },
        "avg_precip": {
            "jan": 1.2, "feb": 1.4, "mar": 2.6, "apr": 3.8, "may": 5.0,
            "jun": 5.0, "jul": 4.0, "aug": 3.9, "sep": 3.9, "oct": 3.3,
            "nov": 2.2, "dec": 1.6,
        },
        "first_frost": "October 18",
        "last_frost": "April 9",
        "gdd_base50_annual": 3500,
    },

    # ── Montana (Billings) ───────────────────────────────────────────────
    "montana": {
        "avg_temps": {
            "jan": 24, "feb": 28, "mar": 37, "apr": 46, "may": 56,
            "jun": 65, "jul": 73, "aug": 72, "sep": 60, "oct": 47,
            "nov": 34, "dec": 24,
        },
        "avg_precip": {
            "jan": 0.8, "feb": 0.6, "mar": 1.1, "apr": 1.8, "may": 2.4,
            "jun": 2.1, "jul": 1.1, "aug": 1.0, "sep": 1.3, "oct": 1.2,
            "nov": 0.8, "dec": 0.8,
        },
        "first_frost": "September 26",
        "last_frost": "May 12",
        "gdd_base50_annual": 2200,
    },

    # ── Nebraska (Omaha) ─────────────────────────────────────────────────
    "nebraska": {
        "avg_temps": {
            "jan": 23, "feb": 28, "mar": 40, "apr": 52, "may": 63,
            "jun": 73, "jul": 78, "aug": 75, "sep": 65, "oct": 53,
            "nov": 39, "dec": 25,
        },
        "avg_precip": {
            "jan": 0.7, "feb": 0.8, "mar": 1.8, "apr": 2.9, "may": 4.5,
            "jun": 4.4, "jul": 3.4, "aug": 3.5, "sep": 2.8, "oct": 2.2,
            "nov": 1.3, "dec": 0.9,
        },
        "first_frost": "October 8",
        "last_frost": "April 22",
        "gdd_base50_annual": 3000,
    },

    # ── Nevada (Las Vegas) ───────────────────────────────────────────────
    "nevada": {
        "avg_temps": {
            "jan": 47, "feb": 52, "mar": 58, "apr": 66, "may": 76,
            "jun": 86, "jul": 92, "aug": 90, "sep": 82, "oct": 69,
            "nov": 55, "dec": 46,
        },
        "avg_precip": {
            "jan": 0.6, "feb": 0.8, "mar": 0.4, "apr": 0.2, "may": 0.1,
            "jun": 0.1, "jul": 0.4, "aug": 0.5, "sep": 0.3, "oct": 0.3,
            "nov": 0.3, "dec": 0.4,
        },
        "first_frost": "November 21",
        "last_frost": "March 7",
        "gdd_base50_annual": 5600,
    },

    # ── New Hampshire (Concord) ──────────────────────────────────────────
    "new hampshire": {
        "avg_temps": {
            "jan": 20, "feb": 23, "mar": 33, "apr": 45, "may": 57,
            "jun": 65, "jul": 70, "aug": 68, "sep": 59, "oct": 48,
            "nov": 37, "dec": 25,
        },
        "avg_precip": {
            "jan": 2.7, "feb": 2.5, "mar": 3.0, "apr": 3.3, "may": 3.5,
            "jun": 3.5, "jul": 3.5, "aug": 3.2, "sep": 3.2, "oct": 3.8,
            "nov": 3.3, "dec": 2.9,
        },
        "first_frost": "September 25",
        "last_frost": "May 13",
        "gdd_base50_annual": 2100,
    },

    # ── New Jersey (Newark) ──────────────────────────────────────────────
    "new jersey": {
        "avg_temps": {
            "jan": 32, "feb": 34, "mar": 42, "apr": 53, "may": 63,
            "jun": 72, "jul": 78, "aug": 76, "sep": 68, "oct": 56,
            "nov": 46, "dec": 36,
        },
        "avg_precip": {
            "jan": 3.6, "feb": 2.8, "mar": 4.0, "apr": 3.8, "may": 4.2,
            "jun": 3.9, "jul": 4.6, "aug": 4.1, "sep": 4.0, "oct": 3.5,
            "nov": 3.5, "dec": 3.7,
        },
        "first_frost": "October 20",
        "last_frost": "April 15",
        "gdd_base50_annual": 3100,
    },

    # ── New Mexico (Albuquerque) ─────────────────────────────────────────
    "new mexico": {
        "avg_temps": {
            "jan": 36, "feb": 41, "mar": 49, "apr": 57, "may": 66,
            "jun": 76, "jul": 80, "aug": 77, "sep": 70, "oct": 57,
            "nov": 44, "dec": 35,
        },
        "avg_precip": {
            "jan": 0.4, "feb": 0.4, "mar": 0.5, "apr": 0.5, "may": 0.6,
            "jun": 0.6, "jul": 1.4, "aug": 1.5, "sep": 0.9, "oct": 0.8,
            "nov": 0.5, "dec": 0.5,
        },
        "first_frost": "October 29",
        "last_frost": "April 13",
        "gdd_base50_annual": 3600,
    },

    # ── New York (Albany) ────────────────────────────────────────────────
    "new york": {
        "avg_temps": {
            "jan": 22, "feb": 25, "mar": 35, "apr": 48, "may": 59,
            "jun": 68, "jul": 73, "aug": 70, "sep": 62, "oct": 50,
            "nov": 40, "dec": 28,
        },
        "avg_precip": {
            "jan": 2.5, "feb": 2.2, "mar": 3.0, "apr": 3.3, "may": 3.7,
            "jun": 3.8, "jul": 3.6, "aug": 3.5, "sep": 3.3, "oct": 3.3,
            "nov": 3.1, "dec": 2.8,
        },
        "first_frost": "October 5",
        "last_frost": "May 1",
        "gdd_base50_annual": 2500,
    },

    # ── North Carolina (Raleigh) ─────────────────────────────────────────
    "north carolina": {
        "avg_temps": {
            "jan": 40, "feb": 43, "mar": 51, "apr": 60, "may": 68,
            "jun": 76, "jul": 80, "aug": 78, "sep": 72, "oct": 61,
            "nov": 51, "dec": 42,
        },
        "avg_precip": {
            "jan": 3.5, "feb": 3.2, "mar": 3.8, "apr": 3.1, "may": 3.7,
            "jun": 3.8, "jul": 4.4, "aug": 4.2, "sep": 4.1, "oct": 3.2,
            "nov": 3.0, "dec": 3.2,
        },
        "first_frost": "November 1",
        "last_frost": "April 5",
        "gdd_base50_annual": 3900,
    },

    # ── North Dakota (Bismarck) ──────────────────────────────────────────
    "north dakota": {
        "avg_temps": {
            "jan": 10, "feb": 16, "mar": 29, "apr": 44, "may": 56,
            "jun": 66, "jul": 72, "aug": 70, "sep": 58, "oct": 44,
            "nov": 28, "dec": 14,
        },
        "avg_precip": {
            "jan": 0.5, "feb": 0.5, "mar": 0.8, "apr": 1.3, "may": 2.3,
            "jun": 3.0, "jul": 2.5, "aug": 1.9, "sep": 1.5, "oct": 1.2,
            "nov": 0.6, "dec": 0.5,
        },
        "first_frost": "September 22",
        "last_frost": "May 14",
        "gdd_base50_annual": 2000,
    },

    # ── Ohio (Columbus) ──────────────────────────────────────────────────
    "ohio": {
        "avg_temps": {
            "jan": 28, "feb": 31, "mar": 41, "apr": 52, "may": 62,
            "jun": 71, "jul": 75, "aug": 73, "sep": 66, "oct": 54,
            "nov": 43, "dec": 32,
        },
        "avg_precip": {
            "jan": 2.7, "feb": 2.3, "mar": 3.0, "apr": 3.4, "may": 4.1,
            "jun": 4.2, "jul": 4.2, "aug": 3.4, "sep": 2.8, "oct": 2.6,
            "nov": 3.0, "dec": 2.8,
        },
        "first_frost": "October 12",
        "last_frost": "April 20",
        "gdd_base50_annual": 2900,
    },

    # ── Oklahoma (Oklahoma City) ─────────────────────────────────────────
    "oklahoma": {
        "avg_temps": {
            "jan": 37, "feb": 41, "mar": 50, "apr": 60, "may": 69,
            "jun": 78, "jul": 83, "aug": 82, "sep": 73, "oct": 62,
            "nov": 49, "dec": 38,
        },
        "avg_precip": {
            "jan": 1.4, "feb": 1.6, "mar": 2.8, "apr": 3.3, "may": 5.2,
            "jun": 4.5, "jul": 2.8, "aug": 3.1, "sep": 3.9, "oct": 3.4,
            "nov": 2.4, "dec": 1.7,
        },
        "first_frost": "November 2",
        "last_frost": "March 30",
        "gdd_base50_annual": 4100,
    },

    # ── Oregon (Portland) ────────────────────────────────────────────────
    "oregon": {
        "avg_temps": {
            "jan": 40, "feb": 43, "mar": 47, "apr": 51, "may": 57,
            "jun": 63, "jul": 69, "aug": 70, "sep": 63, "oct": 53,
            "nov": 44, "dec": 39,
        },
        "avg_precip": {
            "jan": 4.9, "feb": 3.7, "mar": 3.7, "apr": 2.7, "may": 2.3,
            "jun": 1.5, "jul": 0.6, "aug": 0.7, "sep": 1.5, "oct": 3.0,
            "nov": 5.3, "dec": 5.5,
        },
        "first_frost": "October 25",
        "last_frost": "April 15",
        "gdd_base50_annual": 2200,
    },

    # ── Pennsylvania (Harrisburg) ────────────────────────────────────────
    "pennsylvania": {
        "avg_temps": {
            "jan": 28, "feb": 31, "mar": 40, "apr": 51, "may": 62,
            "jun": 71, "jul": 75, "aug": 73, "sep": 65, "oct": 53,
            "nov": 43, "dec": 32,
        },
        "avg_precip": {
            "jan": 2.9, "feb": 2.6, "mar": 3.3, "apr": 3.3, "may": 3.7,
            "jun": 3.7, "jul": 3.7, "aug": 3.3, "sep": 3.5, "oct": 3.1,
            "nov": 3.1, "dec": 3.1,
        },
        "first_frost": "October 12",
        "last_frost": "April 20",
        "gdd_base50_annual": 2900,
    },

    # ── Rhode Island (Providence) ────────────────────────────────────────
    "rhode island": {
        "avg_temps": {
            "jan": 29, "feb": 31, "mar": 38, "apr": 49, "may": 59,
            "jun": 68, "jul": 74, "aug": 73, "sep": 65, "oct": 54,
            "nov": 44, "dec": 34,
        },
        "avg_precip": {
            "jan": 3.8, "feb": 3.2, "mar": 4.2, "apr": 3.9, "may": 3.4,
            "jun": 3.5, "jul": 3.1, "aug": 3.5, "sep": 3.4, "oct": 3.8,
            "nov": 3.7, "dec": 3.7,
        },
        "first_frost": "October 15",
        "last_frost": "April 20",
        "gdd_base50_annual": 2600,
    },

    # ── South Carolina (Columbia) ────────────────────────────────────────
    "south carolina": {
        "avg_temps": {
            "jan": 46, "feb": 50, "mar": 57, "apr": 65, "may": 73,
            "jun": 80, "jul": 83, "aug": 82, "sep": 76, "oct": 65,
            "nov": 56, "dec": 47,
        },
        "avg_precip": {
            "jan": 3.7, "feb": 3.4, "mar": 3.8, "apr": 3.0, "may": 3.3,
            "jun": 5.0, "jul": 5.3, "aug": 5.5, "sep": 3.7, "oct": 3.1,
            "nov": 2.9, "dec": 3.2,
        },
        "first_frost": "November 10",
        "last_frost": "March 22",
        "gdd_base50_annual": 4600,
    },

    # ── South Dakota (Sioux Falls) ───────────────────────────────────────
    "south dakota": {
        "avg_temps": {
            "jan": 16, "feb": 21, "mar": 33, "apr": 47, "may": 59,
            "jun": 69, "jul": 74, "aug": 72, "sep": 61, "oct": 48,
            "nov": 32, "dec": 19,
        },
        "avg_precip": {
            "jan": 0.5, "feb": 0.6, "mar": 1.4, "apr": 2.5, "may": 3.4,
            "jun": 3.9, "jul": 3.0, "aug": 2.7, "sep": 2.1, "oct": 1.8,
            "nov": 0.9, "dec": 0.6,
        },
        "first_frost": "September 29",
        "last_frost": "May 6",
        "gdd_base50_annual": 2400,
    },

    # ── Tennessee (Nashville) ────────────────────────────────────────────
    "tennessee": {
        "avg_temps": {
            "jan": 38, "feb": 42, "mar": 51, "apr": 60, "may": 69,
            "jun": 77, "jul": 80, "aug": 80, "sep": 73, "oct": 61,
            "nov": 50, "dec": 40,
        },
        "avg_precip": {
            "jan": 3.8, "feb": 3.7, "mar": 4.4, "apr": 3.9, "may": 5.1,
            "jun": 3.8, "jul": 4.0, "aug": 3.1, "sep": 3.4, "oct": 2.9,
            "nov": 4.0, "dec": 4.3,
        },
        "first_frost": "October 28",
        "last_frost": "April 6",
        "gdd_base50_annual": 3900,
    },

    # ── Texas (Austin) ───────────────────────────────────────────────────
    "texas": {
        "avg_temps": {
            "jan": 50, "feb": 54, "mar": 62, "apr": 69, "may": 76,
            "jun": 83, "jul": 86, "aug": 86, "sep": 80, "oct": 71,
            "nov": 59, "dec": 51,
        },
        "avg_precip": {
            "jan": 2.1, "feb": 2.0, "mar": 2.6, "apr": 2.5, "may": 4.3,
            "jun": 3.9, "jul": 1.9, "aug": 2.2, "sep": 3.1, "oct": 3.9,
            "nov": 2.7, "dec": 2.3,
        },
        "first_frost": "November 28",
        "last_frost": "March 3",
        "gdd_base50_annual": 5400,
    },

    # ── Utah (Salt Lake City) ────────────────────────────────────────────
    "utah": {
        "avg_temps": {
            "jan": 29, "feb": 34, "mar": 43, "apr": 51, "may": 60,
            "jun": 70, "jul": 79, "aug": 77, "sep": 66, "oct": 53,
            "nov": 39, "dec": 29,
        },
        "avg_precip": {
            "jan": 1.3, "feb": 1.2, "mar": 1.6, "apr": 2.0, "may": 1.8,
            "jun": 0.9, "jul": 0.7, "aug": 0.8, "sep": 1.1, "oct": 1.5,
            "nov": 1.3, "dec": 1.4,
        },
        "first_frost": "October 15",
        "last_frost": "April 30",
        "gdd_base50_annual": 2800,
    },

    # ── Vermont (Burlington) ─────────────────────────────────────────────
    "vermont": {
        "avg_temps": {
            "jan": 18, "feb": 21, "mar": 31, "apr": 44, "may": 56,
            "jun": 66, "jul": 70, "aug": 68, "sep": 59, "oct": 47,
            "nov": 36, "dec": 23,
        },
        "avg_precip": {
            "jan": 2.0, "feb": 1.7, "mar": 2.1, "apr": 2.8, "may": 3.3,
            "jun": 3.6, "jul": 3.7, "aug": 3.7, "sep": 3.2, "oct": 3.2,
            "nov": 2.8, "dec": 2.2,
        },
        "first_frost": "September 28",
        "last_frost": "May 10",
        "gdd_base50_annual": 2000,
    },

    # ── Virginia (Richmond) ──────────────────────────────────────────────
    "virginia": {
        "avg_temps": {
            "jan": 36, "feb": 39, "mar": 47, "apr": 57, "may": 66,
            "jun": 74, "jul": 79, "aug": 77, "sep": 70, "oct": 58,
            "nov": 48, "dec": 38,
        },
        "avg_precip": {
            "jan": 3.2, "feb": 2.8, "mar": 3.6, "apr": 3.2, "may": 3.8,
            "jun": 3.5, "jul": 4.4, "aug": 4.0, "sep": 3.7, "oct": 3.2,
            "nov": 3.1, "dec": 3.1,
        },
        "first_frost": "October 26",
        "last_frost": "April 10",
        "gdd_base50_annual": 3700,
    },

    # ── Washington (Seattle) ─────────────────────────────────────────────
    "washington": {
        "avg_temps": {
            "jan": 41, "feb": 43, "mar": 46, "apr": 50, "may": 56,
            "jun": 61, "jul": 66, "aug": 66, "sep": 61, "oct": 52,
            "nov": 44, "dec": 39,
        },
        "avg_precip": {
            "jan": 5.1, "feb": 3.5, "mar": 3.8, "apr": 2.7, "may": 1.9,
            "jun": 1.5, "jul": 0.7, "aug": 0.9, "sep": 1.6, "oct": 3.2,
            "nov": 5.6, "dec": 5.4,
        },
        "first_frost": "November 5",
        "last_frost": "March 25",
        "gdd_base50_annual": 1800,
    },

    # ── West Virginia (Charleston) ───────────────────────────────────────
    "west virginia": {
        "avg_temps": {
            "jan": 33, "feb": 36, "mar": 45, "apr": 55, "may": 64,
            "jun": 72, "jul": 76, "aug": 74, "sep": 68, "oct": 56,
            "nov": 46, "dec": 36,
        },
        "avg_precip": {
            "jan": 3.1, "feb": 2.8, "mar": 3.5, "apr": 3.3, "may": 4.0,
            "jun": 3.7, "jul": 4.5, "aug": 3.6, "sep": 2.9, "oct": 2.6,
            "nov": 3.1, "dec": 3.0,
        },
        "first_frost": "October 15",
        "last_frost": "April 22",
        "gdd_base50_annual": 3200,
    },

    # ── Wisconsin (Madison) ──────────────────────────────────────────────
    "wisconsin": {
        "avg_temps": {
            "jan": 17, "feb": 21, "mar": 33, "apr": 46, "may": 57,
            "jun": 67, "jul": 72, "aug": 69, "sep": 61, "oct": 48,
            "nov": 35, "dec": 21,
        },
        "avg_precip": {
            "jan": 1.3, "feb": 1.2, "mar": 1.8, "apr": 3.0, "may": 3.5,
            "jun": 4.4, "jul": 4.1, "aug": 4.0, "sep": 3.2, "oct": 2.3,
            "nov": 2.2, "dec": 1.5,
        },
        "first_frost": "October 3",
        "last_frost": "May 1",
        "gdd_base50_annual": 2200,
    },

    # ── Wyoming (Cheyenne) ───────────────────────────────────────────────
    "wyoming": {
        "avg_temps": {
            "jan": 26, "feb": 28, "mar": 34, "apr": 42, "may": 51,
            "jun": 61, "jul": 68, "aug": 66, "sep": 56, "oct": 44,
            "nov": 33, "dec": 25,
        },
        "avg_precip": {
            "jan": 0.5, "feb": 0.5, "mar": 0.9, "apr": 1.5, "may": 2.3,
            "jun": 1.7, "jul": 1.9, "aug": 1.5, "sep": 1.0, "oct": 0.8,
            "nov": 0.6, "dec": 0.5,
        },
        "first_frost": "September 18",
        "last_frost": "May 21",
        "gdd_base50_annual": 1800,
    },
}


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------

def get_climate_data(state):
    """Return climate data dict for a US state, or None if not found.

    Parameters
    ----------
    state : str
        State name (case-insensitive), e.g. "Texas" or "new york".

    Returns
    -------
    dict or None
        Climate data dictionary with keys ``avg_temps``, ``avg_precip``,
        ``first_frost``, ``last_frost``, and ``gdd_base50_annual``.
    """
    if not isinstance(state, str):
        return None
    return STATE_CLIMATE_DATA.get(state.strip().lower())


def calculate_gdd(base_temp, daily_highs, daily_lows):
    """Calculate accumulated Growing Degree Days (GDD).

    Uses the standard averaging method:
        GDD_day = max(0, (T_high + T_low) / 2 - base_temp)

    Parameters
    ----------
    base_temp : float
        Base temperature in degF.  Typical values are 50 degF for cool-season
        turfgrass and 60 degF for warm-season turfgrass.
    daily_highs : list[float]
        Daily high temperatures in degF.
    daily_lows : list[float]
        Daily low temperatures in degF.  Must be the same length as
        *daily_highs*.

    Returns
    -------
    float
        Total accumulated GDD over the supplied period.

    Raises
    ------
    ValueError
        If *daily_highs* and *daily_lows* have different lengths.
    """
    if len(daily_highs) != len(daily_lows):
        raise ValueError(
            "daily_highs and daily_lows must have the same length "
            f"({len(daily_highs)} != {len(daily_lows)})"
        )

    total = 0.0
    for high, low in zip(daily_highs, daily_lows):
        avg = (high + low) / 2.0
        gdd = max(0.0, avg - base_temp)
        total += gdd
    return total


def get_current_season(state, month=None):
    """Determine the current turf management season for a state.

    The season is inferred from region-based groupings (cool-season,
    warm-season, transition zone) and the given month.

    Parameters
    ----------
    state : str
        US state name (case-insensitive).
    month : int or None
        Month number (1-12).  Defaults to the current calendar month if
        *None*.

    Returns
    -------
    dict
        ``{'season': str, 'description': str}`` where *season* is one of
        ``'dormant'``, ``'spring_transition'``, ``'active_growth'``,
        ``'summer_stress'``, ``'fall_recovery'``, ``'fall_transition'``.

    Raises
    ------
    ValueError
        If *state* is not recognised or *month* is outside 1-12.
    """
    if month is None:
        month = datetime.now().month

    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1-12, got {month}")

    state_lower = state.strip().lower() if isinstance(state, str) else ""

    if state_lower not in STATE_CLIMATE_DATA:
        raise ValueError(f"Unknown state: {state!r}")

    # Determine region
    if state_lower in TRANSITION_ZONE_STATES:
        return _transition_zone_season(month)
    elif state_lower in WARM_SEASON_STATES:
        return _warm_season(month)
    else:
        # Default to cool-season (includes COOL_SEASON_STATES)
        return _cool_season(month)


# ---------------------------------------------------------------------------
# Internal season helpers
# ---------------------------------------------------------------------------

def _cool_season(month):
    """Cool-season region schedule (NE, Midwest, Northern West)."""
    if month in (11, 12, 1, 2):
        return {
            "season": "dormant",
            "description": (
                "Turf is dormant. Avoid traffic on frozen turf. Plan for "
                "spring pre-emergent applications."
            ),
        }
    if month in (3, 4):
        return {
            "season": "spring_transition",
            "description": (
                "Turf is breaking dormancy. Apply pre-emergent herbicide "
                "when soil temps reach 55\u00b0F. Begin mowing as growth "
                "resumes."
            ),
        }
    if month in (5, 6):
        return {
            "season": "active_growth",
            "description": (
                "Peak growth period for cool-season grasses. Maintain "
                "regular mowing, fertilization, and irrigation schedules."
            ),
        }
    if month in (7, 8):
        return {
            "season": "summer_stress",
            "description": (
                "Heat and drought stress are likely. Raise mowing height, "
                "ensure adequate irrigation, and avoid heavy fertilization."
            ),
        }
    # month in (9, 10)
    return {
        "season": "fall_recovery",
        "description": (
            "Ideal window for overseeding, aeration, and fall "
            "fertilization. Cool-season grasses recover and thicken."
        ),
    }


def _warm_season(month):
    """Warm-season region schedule (SE, SW, HI)."""
    if month in (12, 1, 2):
        return {
            "season": "dormant",
            "description": (
                "Warm-season turf is dormant or semi-dormant. Overseeding "
                "with ryegrass may maintain green color. Minimize traffic."
            ),
        }
    if month == 3:
        return {
            "season": "spring_transition",
            "description": (
                "Warm-season grasses begin greening up. Apply pre-emergent "
                "herbicide and prepare for the growing season."
            ),
        }
    if month in (4, 5, 6, 7, 8, 9):
        return {
            "season": "active_growth",
            "description": (
                "Peak growing season for warm-season turf. Maintain "
                "regular mowing, fertilization, and pest monitoring."
            ),
        }
    # month in (10, 11)
    return {
        "season": "fall_transition",
        "description": (
            "Growth is slowing. Final fertilization window. Consider "
            "overseeding with ryegrass for winter color."
        ),
    }


def _transition_zone_season(month):
    """Transition-zone region schedule (VA, NC, TN, KY, WV, MD, DE, MO, KS, OK, AR)."""
    if month in (12, 1, 2):
        return {
            "season": "dormant",
            "description": (
                "Transition-zone turf is mostly dormant. Cool-season "
                "species may show limited activity in mild spells."
            ),
        }
    if month == 3:
        return {
            "season": "spring_transition",
            "description": (
                "Turf begins greening. Apply pre-emergent herbicide when "
                "forsythia blooms. Start mowing as growth resumes."
            ),
        }
    if month in (4, 5):
        return {
            "season": "active_growth",
            "description": (
                "Both cool- and warm-season species are actively growing. "
                "Fertilize, mow regularly, and monitor for weeds."
            ),
        }
    if month in (6, 7, 8):
        return {
            "season": "summer_stress",
            "description": (
                "Heat stress impacts cool-season grasses. Warm-season "
                "species thrive. Irrigate deeply and raise mowing height."
            ),
        }
    if month in (9, 10):
        return {
            "season": "fall_recovery",
            "description": (
                "Cool-season grasses recover; ideal time for overseeding "
                "and aeration. Warm-season growth begins slowing."
            ),
        }
    # month == 11
    return {
        "season": "fall_transition",
        "description": (
            "Growth winding down. Apply winterizer fertilizer. Last "
            "mowing of the season for warm-season turf."
        ),
    }
