"""
NTEP Cultivar Decision Support Tool for Greenside AI.

Provides cultivar search, comparison, recommendation, blend suggestions,
seeding rate calculations, renovation project planning, and establishment
timelines based on NTEP trial data.
"""

import json
import logging
from datetime import datetime

from db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SPECIES = [
    'creeping_bentgrass', 'bermudagrass', 'kentucky_bluegrass',
    'perennial_ryegrass', 'tall_fescue', 'zoysiagrass',
    'fine_fescue', 'seashore_paspalum',
]

VALID_CATEGORIES = ['greens', 'fairway_tee', 'lawn_turf', 'sports']

VALID_PLANTING_METHODS = ['seed', 'sod', 'sprig', 'plug']

VALID_STATUSES = ['planning', 'in_progress', 'established', 'completed']

TRAIT_COLUMNS = [
    'quality_score', 'color_score', 'density_score', 'disease_resistance',
    'drought_tolerance', 'heat_tolerance', 'cold_tolerance', 'shade_tolerance',
    'traffic_tolerance', 'establishment_rate', 'mowing_tolerance',
]

# Default criteria weights when none are provided (equal weighting)
DEFAULT_WEIGHTS = {t: 1.0 for t in TRAIT_COLUMNS}

# ---------------------------------------------------------------------------
# Establishment timeline data (hardcoded reference)
# ---------------------------------------------------------------------------

ESTABLISHMENT_TIMELINES = {
    'creeping_bentgrass': {
        'seed': {
            'germination_days': '10-14',
            'first_mow_days': '60-90',
            'full_coverage_months': '3-6',
            'full_establishment_months': '6-12',
            'best_planting': 'Late summer (Aug-Sep)',
            'notes': 'Maintain consistent moisture during germination. '
                     'Seed at 1-2 lbs/1000 sq ft. Keep mowing height at '
                     '0.5 inch until established.',
        },
        'sod': {
            'germination_days': 'N/A',
            'first_mow_days': '14-21',
            'full_coverage_months': '1-2',
            'full_establishment_months': '3-6',
            'best_planting': 'Spring or early fall',
            'notes': 'Keep sod moist for first 2 weeks. '
                     'Avoid heavy traffic for 4-6 weeks.',
        },
    },    'bermudagrass': {
        'seed': {
            'germination_days': '7-14',
            'first_mow_days': '30-45',
            'full_coverage_months': '2-4',
            'full_establishment_months': '4-8',
            'best_planting': 'Late spring to early summer (May-Jun)',
            'notes': 'Soil temps must be above 65F. '
                     'Seed at 1-2 lbs/1000 sq ft for common types.',
        },
        'sprig': {
            'germination_days': 'N/A',
            'first_mow_days': '21-30',
            'full_coverage_months': '2-3',
            'full_establishment_months': '3-6',
            'best_planting': 'Late spring (May-Jun)',
            'notes': 'Plant sprigs 6-12 inches apart. '
                     'Topdress lightly and keep moist. '
                     'Roll after planting.',
        },
        'sod': {
            'germination_days': 'N/A',
            'first_mow_days': '10-14',
            'full_coverage_months': '1-2',
            'full_establishment_months': '2-4',
            'best_planting': 'Late spring to summer',
            'notes': 'Water immediately after installation. '
                     'Avoid heavy use for 3-4 weeks.',
        },        'plug': {
            'germination_days': 'N/A',
            'first_mow_days': '30-45',
            'full_coverage_months': '3-6',
            'full_establishment_months': '6-12',
            'best_planting': 'Late spring to early summer',
            'notes': 'Space plugs 6-12 inches apart. '
                     'Fertilize lightly every 4 weeks during grow-in.',
        },
    },
    'kentucky_bluegrass': {
        'seed': {
            'germination_days': '21-28',
            'first_mow_days': '45-60',
            'full_coverage_months': '4-6',
            'full_establishment_months': '8-12',
            'best_planting': 'Late summer to early fall (Aug-Sep)',
            'notes': 'Seed at 2-3 lbs/1000 sq ft. '
                     'Keep seedbed moist. Slow to germinate but '
                     'forms dense turf once established.',
        },
        'sod': {
            'germination_days': 'N/A',
            'first_mow_days': '10-14',
            'full_coverage_months': '1-2',
            'full_establishment_months': '3-6',
            'best_planting': 'Spring or fall',
            'notes': 'Water sod immediately. '
                     'Mow when grass reaches 3-3.5 inches.',
        },
    },    'perennial_ryegrass': {
        'seed': {
            'germination_days': '5-10',
            'first_mow_days': '14-21',
            'full_coverage_months': '1-2',
            'full_establishment_months': '2-4',
            'best_planting': 'Fall (Sep-Oct) or spring (Mar-Apr)',
            'notes': 'Fastest germinating cool-season grass. '
                     'Seed at 6-8 lbs/1000 sq ft for new lawns, '
                     '3-4 lbs/1000 sq ft for overseeding.',
        },
        'sod': {
            'germination_days': 'N/A',
            'first_mow_days': '7-14',
            'full_coverage_months': '1',
            'full_establishment_months': '2-3',
            'best_planting': 'Spring or fall',
            'notes': 'Roots establish quickly. '
                     'Excellent for quick repairs.',
        },
    },
    'tall_fescue': {
        'seed': {
            'germination_days': '10-14',
            'first_mow_days': '21-30',
            'full_coverage_months': '2-3',
            'full_establishment_months': '4-8',
            'best_planting': 'Fall (Sep-Oct)',
            'notes': 'Seed at 6-8 lbs/1000 sq ft. '
                     'Deep roots develop in first season. '
                     'Excellent heat and drought tolerance once established.',
        },        'sod': {
            'germination_days': 'N/A',
            'first_mow_days': '10-14',
            'full_coverage_months': '1-2',
            'full_establishment_months': '3-6',
            'best_planting': 'Spring or fall',
            'notes': 'Keep sod moist for first 10 days. '
                     'Mow at 3-4 inches.',
        },
    },
    'zoysiagrass': {
        'seed': {
            'germination_days': '14-21',
            'first_mow_days': '45-60',
            'full_coverage_months': '4-8',
            'full_establishment_months': '12-24',
            'best_planting': 'Late spring to early summer (May-Jun)',
            'notes': 'Very slow from seed. Soil temps must be above 70F. '
                     'Seed at 1-2 lbs/1000 sq ft.',
        },
        'sprig': {
            'germination_days': 'N/A',
            'first_mow_days': '30-45',
            'full_coverage_months': '3-6',
            'full_establishment_months': '6-12',
            'best_planting': 'Late spring to early summer',
            'notes': 'Plant sprigs 6 inches apart. '
                     'Topdress and roll after planting.',
        },        'sod': {
            'germination_days': 'N/A',
            'first_mow_days': '14-21',
            'full_coverage_months': '1-2',
            'full_establishment_months': '3-6',
            'best_planting': 'Late spring to summer',
            'notes': 'Water frequently for first 2 weeks. '
                     'Slow lateral growth initially.',
        },
        'plug': {
            'germination_days': 'N/A',
            'first_mow_days': '30-60',
            'full_coverage_months': '6-12',
            'full_establishment_months': '12-24',
            'best_planting': 'Late spring',
            'notes': 'Space plugs 6 inches apart for faster coverage. '
                     'Patience required -- zoysia is slow to fill.',
        },
    },
    'fine_fescue': {
        'seed': {
            'germination_days': '10-14',
            'first_mow_days': '21-30',
            'full_coverage_months': '2-4',
            'full_establishment_months': '4-8',
            'best_planting': 'Fall (Sep-Oct)',
            'notes': 'Seed at 4-5 lbs/1000 sq ft. '
                     'Excellent shade tolerance. Low fertilizer needs.',
        },
    },    'seashore_paspalum': {
        'sprig': {
            'germination_days': 'N/A',
            'first_mow_days': '21-30',
            'full_coverage_months': '2-4',
            'full_establishment_months': '4-8',
            'best_planting': 'Late spring to early summer',
            'notes': 'Salt tolerant -- ideal for coastal areas. '
                     'Requires warm soil temps above 65F.',
        },
        'sod': {
            'germination_days': 'N/A',
            'first_mow_days': '10-14',
            'full_coverage_months': '1-2',
            'full_establishment_months': '3-6',
            'best_planting': 'Late spring to summer',
            'notes': 'Excellent salt tolerance. '
                     'Can be irrigated with reclaimed water.',
        },
    },
}


# ---------------------------------------------------------------------------
# Renovation checklists (hardcoded reference)
# ---------------------------------------------------------------------------
RENOVATION_CHECKLISTS = {
    'seed': {
        'pre_planting': [
            'Soil test -- check pH, P, K, and organic matter',
            'Kill existing vegetation if needed (glyphosate 2-3 weeks prior)',
            'Grade and level the area',
            'Amend soil based on soil test (lime, sulfur, organic matter)',
            'Incorporate starter fertilizer (high-P, e.g. 18-24-12)',
            'Fine rake to create smooth, firm seedbed',
        ],
        'planting': [
            'Calibrate drop or slit seeder to recommended rate',
            'Apply seed in two perpendicular passes for even coverage',
            'Lightly rake or drag seed into top 1/4 inch of soil',
            'Roll with light roller to ensure seed-to-soil contact',
            'Apply thin layer of straw mulch or hydromulch on slopes',
        ],
        'post_planting': [
            'Irrigate lightly 2-3 times daily to keep seedbed moist',
            'Reduce irrigation frequency as seedlings establish',
            'First mow when grass reaches 50% above target height',
            'Apply second fertilizer application at 4-6 weeks',
            'Begin regular mowing schedule once fully germinated',
            'Avoid heavy traffic for first 8-12 weeks',
        ],
    },    'sod': {
        'pre_planting': [
            'Soil test and amend as needed',
            'Grade area to final elevation minus sod thickness',
            'Apply starter fertilizer',
            'Moisten soil surface before laying sod',
        ],
        'planting': [
            'Lay sod within 24 hours of delivery',
            'Start along a straight edge (sidewalk, string line)',
            'Stagger seams like brickwork',
            'Push edges tightly together -- no gaps or overlaps',
            'Roll with water-filled roller',
            'Cut around obstacles with sharp knife',
        ],
        'post_planting': [
            'Water immediately and heavily -- soak through sod into soil',
            'Continue daily watering for 2 weeks',
            'Check root attachment by gently pulling at edges',
            'First mow when sod cannot be easily lifted (7-14 days)',
            'Gradually reduce watering frequency over 4-6 weeks',
        ],
    },    'sprig': {
        'pre_planting': [
            'Soil test and amend as needed',
            'Till area to 4-6 inches depth',
            'Apply starter fertilizer and incorporate',
            'Smooth and firm seedbed',
        ],
        'planting': [
            'Spread sprigs uniformly at recommended rate (200-400 bu/acre)',
            'Press sprigs into soil with sprig planter or disk',
            'Topdress with 1/4 inch of soil or sand',
            'Roll with heavy roller to ensure contact',
        ],
        'post_planting': [
            'Irrigate immediately -- keep moist for first 3 weeks',
            'Apply nitrogen at 0.5 lb N/1000 sq ft every 2-3 weeks',
            'Mow when sprigs reach 50% above target height',
            'Watch for washouts and replant bare areas',
            'Expect full coverage in 2-4 months depending on species',
        ],
    },    'plug': {
        'pre_planting': [
            'Soil test and amend as needed',
            'Remove existing vegetation or prepare planting holes',
            'Apply starter fertilizer',
        ],
        'planting': [
            'Cut or purchase plugs (2-4 inch diameter)',
            'Space plugs 6-12 inches apart (closer = faster fill)',
            'Set plugs level with surrounding soil surface',
            'Firm soil around each plug',
            'Topdress lightly with sand or soil mix',
        ],
        'post_planting': [
            'Water thoroughly immediately after planting',
            'Irrigate daily for first 2 weeks',
            'Apply light nitrogen every 3-4 weeks',
            'Mow surrounding area to reduce competition',
            'Fill bare areas between plugs as needed',
            'Full coverage may take 6-24 months depending on species',
        ],
    },
}


# ---------------------------------------------------------------------------
# Default seeding / planting rates per 1000 sq ft
# ---------------------------------------------------------------------------
DEFAULT_SEEDING_RATES = {
    'creeping_bentgrass': {
        'seed': {'new': '1-2 lbs', 'overseed': '0.5-1 lb'},
    },
    'bermudagrass': {
        'seed': {'new': '1-2 lbs', 'overseed': '0.5-1 lb'},
        'sprig': {'new': '200-400 bushels/acre'},
    },
    'kentucky_bluegrass': {
        'seed': {'new': '2-3 lbs', 'overseed': '1-2 lbs'},
    },
    'perennial_ryegrass': {
        'seed': {'new': '6-8 lbs', 'overseed': '3-4 lbs'},
    },
    'tall_fescue': {
        'seed': {'new': '6-8 lbs', 'overseed': '3-5 lbs'},
    },
    'zoysiagrass': {
        'seed': {'new': '1-2 lbs', 'overseed': 'Not recommended'},
        'sprig': {'new': '200-400 bushels/acre'},
        'plug': {'new': '1 plug per 6-12 inches'},
    },
    'fine_fescue': {
        'seed': {'new': '4-5 lbs', 'overseed': '2-3 lbs'},
    },
    'seashore_paspalum': {
        'sprig': {'new': '200-400 bushels/acre'},
    },
}


# ---------------------------------------------------------------------------
# Table Initialisation
# ---------------------------------------------------------------------------

def init_cultivar_tables():
    """Create cultivar-related tables if they do not exist."""
    try:
        with get_db() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cultivar_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cultivar_name TEXT NOT NULL,
                    species TEXT NOT NULL,
                    category TEXT NOT NULL,
                    quality_score REAL,
                    color_score REAL,
                    density_score REAL,
                    disease_resistance REAL,
                    drought_tolerance REAL,
                    heat_tolerance REAL,
                    cold_tolerance REAL,
                    shade_tolerance REAL,
                    traffic_tolerance REAL,
                    establishment_rate REAL,
                    mowing_tolerance REAL,                    ntep_trial_year TEXT,
                    region TEXT,
                    state TEXT,
                    trial_location TEXT,
                    seed_available INTEGER DEFAULT 1,
                    seeding_rate TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS cultivar_comparisons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    name TEXT,
                    cultivar_ids TEXT,
                    criteria_weights TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS renovation_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    area TEXT,
                    target_species TEXT,
                    selected_cultivars TEXT,
                    planting_method TEXT,
                    planting_date TEXT,
                    area_sqft REAL,
                    status TEXT DEFAULT 'planning',
                    establishment_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        logger.info("Cultivar tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize cultivar tables: {e}")
        raise


# ---------------------------------------------------------------------------
# Seed data -- top-performing NTEP cultivars with realistic scores
# ---------------------------------------------------------------------------

def _build_cultivar_records():
    """Return a list of dicts representing built-in cultivar data."""
    records = []

    def _add(name, species, category, scores, year='2020', region='National',
             seed_available=1, seeding_rate=None, notes=None):
        """Helper to build a cultivar record dict.

        *scores* is a dict keyed by trait name with NTEP-scale values (1-9).
        """
        rec = {
            'cultivar_name': name,
            'species': species,
            'category': category,
            'ntep_trial_year': year,
            'region': region,
            'state': None,
            'trial_location': None,
            'seed_available': seed_available,
            'seeding_rate': seeding_rate,
            'notes': notes,
        }
        for trait in TRAIT_COLUMNS:
            rec[trait] = scores.get(trait, 5.0)
        return rec
    # ----- Creeping Bentgrass (Greens) -----
    records.append(_add(
        '007', 'creeping_bentgrass', 'greens',
        {'quality_score': 7.8, 'color_score': 7.5, 'density_score': 8.2,
         'disease_resistance': 7.0, 'drought_tolerance': 5.5, 'heat_tolerance': 6.8,
         'cold_tolerance': 7.5, 'shade_tolerance': 5.0, 'traffic_tolerance': 7.2,
         'establishment_rate': 7.0, 'mowing_tolerance': 8.5},
        year='2019', seeding_rate='1-1.5 lbs/1000 sq ft',
        notes='Top-performing putting green cultivar. Excellent density and '
              'ball roll. Moderate dollar spot resistance.',
    ))
    records.append(_add(
        'Pure Distinction', 'creeping_bentgrass', 'greens',
        {'quality_score': 8.1, 'color_score': 7.8, 'density_score': 8.4,
         'disease_resistance': 7.5, 'drought_tolerance': 5.8, 'heat_tolerance': 7.0,
         'cold_tolerance': 7.2, 'shade_tolerance': 5.2, 'traffic_tolerance': 7.5,
         'establishment_rate': 7.2, 'mowing_tolerance': 8.7},
        year='2020', seeding_rate='1-1.5 lbs/1000 sq ft',
        notes='Premium putting green bentgrass. Improved disease resistance '
              'over previous generation.',
    ))
    records.append(_add(
        'Crystal Bluelinks', 'creeping_bentgrass', 'greens',
        {'quality_score': 7.9, 'color_score': 8.0, 'density_score': 8.0,
         'disease_resistance': 7.2, 'drought_tolerance': 5.6, 'heat_tolerance': 6.5,
         'cold_tolerance': 7.8, 'shade_tolerance': 5.5, 'traffic_tolerance': 7.0,
         'establishment_rate': 6.8, 'mowing_tolerance': 8.3},
        year='2019', seeding_rate='1-1.5 lbs/1000 sq ft',
        notes='Outstanding blue-green color. Very good putting quality.',
    ))
    records.append(_add(
        'Tyee', 'creeping_bentgrass', 'greens',
        {'quality_score': 7.5, 'color_score': 7.2, 'density_score': 7.8,
         'disease_resistance': 7.8, 'drought_tolerance': 5.5, 'heat_tolerance': 6.5,
         'cold_tolerance': 7.6, 'shade_tolerance': 5.8, 'traffic_tolerance': 7.0,
         'establishment_rate': 7.5, 'mowing_tolerance': 8.0},
        year='2018', seeding_rate='1-1.5 lbs/1000 sq ft',
        notes='Good disease resistance package, especially dollar spot. '
              'Reliable performer across regions.',
    ))
    records.append(_add(
        'Memorial', 'creeping_bentgrass', 'greens',
        {'quality_score': 7.6, 'color_score': 7.4, 'density_score': 8.0,
         'disease_resistance': 7.3, 'drought_tolerance': 5.4, 'heat_tolerance': 6.7,
         'cold_tolerance': 7.4, 'shade_tolerance': 5.0, 'traffic_tolerance': 7.3,
         'establishment_rate': 7.0, 'mowing_tolerance': 8.2},
        year='2019', seeding_rate='1-1.5 lbs/1000 sq ft',
        notes='Consistent NTEP performer. Good density for tournament conditions.',
    ))
    records.append(_add(
        'Alpha', 'creeping_bentgrass', 'greens',
        {'quality_score': 7.4, 'color_score': 7.0, 'density_score': 7.6,
         'disease_resistance': 7.5, 'drought_tolerance': 5.8, 'heat_tolerance': 7.0,
         'cold_tolerance': 7.0, 'shade_tolerance': 5.3, 'traffic_tolerance': 7.0,
         'establishment_rate': 7.3, 'mowing_tolerance': 8.0},
        year='2018', seeding_rate='1-1.5 lbs/1000 sq ft',
        notes='Good heat tolerance for a bentgrass. Solid all-around performer.',
    ))
    records.append(_add(
        'V8', 'creeping_bentgrass', 'greens',
        {'quality_score': 7.7, 'color_score': 7.6, 'density_score': 8.1,
         'disease_resistance': 7.1, 'drought_tolerance': 5.3, 'heat_tolerance': 6.9,
         'cold_tolerance': 7.3, 'shade_tolerance': 5.1, 'traffic_tolerance': 7.4,
         'establishment_rate': 7.4, 'mowing_tolerance': 8.6},
        year='2020', seeding_rate='1-1.5 lbs/1000 sq ft',
        notes='High-density putting surface. Excellent mowing tolerance '
              'at ultra-low heights.',
    ))

    # ----- Bermudagrass (Fairways/Tees) -----
    records.append(_add(
        'TifTuf', 'bermudagrass', 'fairway_tee',
        {'quality_score': 8.0, 'color_score': 7.8, 'density_score': 8.0,
         'disease_resistance': 7.2, 'drought_tolerance': 8.8, 'heat_tolerance': 8.5,
         'cold_tolerance': 6.5, 'shade_tolerance': 5.0, 'traffic_tolerance': 8.2,
         'establishment_rate': 7.5, 'mowing_tolerance': 7.8},
        year='2020', seed_available=0, seeding_rate='Vegetative only (sod/sprig)',
        notes='Outstanding drought tolerance -- uses 38% less water than Tifway 419. '
              'Vegetative cultivar.',
    ))
    records.append(_add(
        'Latitude 36', 'bermudagrass', 'fairway_tee',
        {'quality_score': 7.8, 'color_score': 7.5, 'density_score': 7.8,
         'disease_resistance': 7.0, 'drought_tolerance': 7.5, 'heat_tolerance': 8.2,
         'cold_tolerance': 7.8, 'shade_tolerance': 4.5, 'traffic_tolerance': 8.0,
         'establishment_rate': 7.8, 'mowing_tolerance': 7.5},
        year='2019', seed_available=0, seeding_rate='Vegetative only (sod/sprig)',
        notes='Exceptional cold tolerance for bermudagrass. '
              'Developed at Oklahoma State. Survives northern transition zone winters.',
    ))
    records.append(_add(
        'NorthBridge', 'bermudagrass', 'fairway_tee',
        {'quality_score': 7.6, 'color_score': 7.3, 'density_score': 7.6,
         'disease_resistance': 6.8, 'drought_tolerance': 7.2, 'heat_tolerance': 8.0,
         'cold_tolerance': 7.5, 'shade_tolerance': 4.5, 'traffic_tolerance': 7.8,
         'establishment_rate': 8.0, 'mowing_tolerance': 7.3},
        year='2019', seed_available=0, seeding_rate='Vegetative only (sod/sprig)',
        notes='Cold-hardy bermuda with early spring green-up. '
              'Fast establishment from sprigs.',
    ))
    records.append(_add(
        'Tifway 419', 'bermudagrass', 'fairway_tee',
        {'quality_score': 7.5, 'color_score': 7.5, 'density_score': 8.0,
         'disease_resistance': 6.8, 'drought_tolerance': 7.0, 'heat_tolerance': 8.5,
         'cold_tolerance': 5.8, 'shade_tolerance': 4.0, 'traffic_tolerance': 8.5,
         'establishment_rate': 7.0, 'mowing_tolerance': 8.0},
        year='2018', seed_available=0, seeding_rate='Vegetative only (sod/sprig)',
        notes='Industry standard for bermuda fairways. '
              'Proven performer for decades. Dense, dark green turf.',
    ))
    records.append(_add(
        'Celebration', 'bermudagrass', 'fairway_tee',
        {'quality_score': 7.9, 'color_score': 8.0, 'density_score': 8.2,
         'disease_resistance': 7.5, 'drought_tolerance': 8.0, 'heat_tolerance': 8.5,
         'cold_tolerance': 6.0, 'shade_tolerance': 5.5, 'traffic_tolerance': 8.5,
         'establishment_rate': 7.5, 'mowing_tolerance': 8.0},
        year='2020', seed_available=0, seeding_rate='Vegetative only (sod/sprig)',
        notes='Dark blue-green color. Exceptional traffic recovery. '
              'Good shade tolerance for a bermuda.',
    ))
    records.append(_add(
        'Bimini', 'bermudagrass', 'fairway_tee',
        {'quality_score': 7.7, 'color_score': 7.8, 'density_score': 8.0,
         'disease_resistance': 7.0, 'drought_tolerance': 7.5, 'heat_tolerance': 8.3,
         'cold_tolerance': 6.2, 'shade_tolerance': 4.8, 'traffic_tolerance': 8.0,
         'establishment_rate': 8.0, 'mowing_tolerance': 7.8},
        year='2020', seed_available=0, seeding_rate='Vegetative only (sod/sprig)',
        notes='Fine-textured bermuda with rapid lateral growth. '
              'Excellent for tees and fairways.',
    ))

    # ----- Kentucky Bluegrass -----
    records.append(_add(
        'Bluebank', 'kentucky_bluegrass', 'lawn_turf',
        {'quality_score': 7.5, 'color_score': 7.8, 'density_score': 7.5,
         'disease_resistance': 7.2, 'drought_tolerance': 6.5, 'heat_tolerance': 6.0,
         'cold_tolerance': 8.5, 'shade_tolerance': 5.5, 'traffic_tolerance': 7.0,
         'establishment_rate': 5.5, 'mowing_tolerance': 7.0},
        year='2019', seeding_rate='2-3 lbs/1000 sq ft',
        notes='Top-rated KBG for overall quality. Excellent winter color '
              'and cold hardiness.',
    ))
    records.append(_add(
        'Mazama', 'kentucky_bluegrass', 'lawn_turf',
        {'quality_score': 7.3, 'color_score': 7.5, 'density_score': 7.8,
         'disease_resistance': 7.5, 'drought_tolerance': 6.8, 'heat_tolerance': 6.2,
         'cold_tolerance': 8.2, 'shade_tolerance': 6.0, 'traffic_tolerance': 7.2,
         'establishment_rate': 5.8, 'mowing_tolerance': 7.2},
        year='2018', seeding_rate='2-3 lbs/1000 sq ft',
        notes='Improved shade tolerance for KBG. Good disease package.',
    ))
    records.append(_add(
        'Midnight', 'kentucky_bluegrass', 'lawn_turf',
        {'quality_score': 7.8, 'color_score': 8.5, 'density_score': 8.0,
         'disease_resistance': 7.0, 'drought_tolerance': 6.2, 'heat_tolerance': 5.8,
         'cold_tolerance': 8.5, 'shade_tolerance': 5.5, 'traffic_tolerance': 7.5,
         'establishment_rate': 5.2, 'mowing_tolerance': 7.5},
        year='2019', seeding_rate='2-3 lbs/1000 sq ft',
        notes='Industry benchmark for dark green color. Dense, attractive turf. '
              'Slow to establish but outstanding once mature.',
    ))
    records.append(_add(
        'Award', 'kentucky_bluegrass', 'lawn_turf',
        {'quality_score': 7.2, 'color_score': 7.3, 'density_score': 7.5,
         'disease_resistance': 7.8, 'drought_tolerance': 7.0, 'heat_tolerance': 6.5,
         'cold_tolerance': 8.0, 'shade_tolerance': 5.8, 'traffic_tolerance': 7.0,
         'establishment_rate': 6.0, 'mowing_tolerance': 7.0},
        year='2018', seeding_rate='2-3 lbs/1000 sq ft',
        notes='Strong disease resistance. Reliable across multiple regions.',
    ))
    records.append(_add(
        'Bewitched', 'kentucky_bluegrass', 'lawn_turf',
        {'quality_score': 7.4, 'color_score': 7.6, 'density_score': 7.6,
         'disease_resistance': 7.3, 'drought_tolerance': 6.5, 'heat_tolerance': 6.0,
         'cold_tolerance': 8.3, 'shade_tolerance': 5.5, 'traffic_tolerance': 7.2,
         'establishment_rate': 5.5, 'mowing_tolerance': 7.3},
        year='2020', seeding_rate='2-3 lbs/1000 sq ft',
        notes='Fine leaf texture. Good sod-forming ability.',
    ))
    records.append(_add(
        'Barzan', 'kentucky_bluegrass', 'lawn_turf',
        {'quality_score': 7.0, 'color_score': 7.2, 'density_score': 7.3,
         'disease_resistance': 7.5, 'drought_tolerance': 7.2, 'heat_tolerance': 6.5,
         'cold_tolerance': 8.0, 'shade_tolerance': 5.5, 'traffic_tolerance': 7.0,
         'establishment_rate': 6.2, 'mowing_tolerance': 7.0},
        year='2019', seeding_rate='2-3 lbs/1000 sq ft',
        notes='Good drought performance for KBG. Moderate establishment speed.',
    ))

    # ----- Perennial Ryegrass -----
    records.append(_add(
        'Caddieshack', 'perennial_ryegrass', 'fairway_tee',
        {'quality_score': 7.8, 'color_score': 8.0, 'density_score': 8.0,
         'disease_resistance': 7.5, 'drought_tolerance': 5.8, 'heat_tolerance': 5.5,
         'cold_tolerance': 7.0, 'shade_tolerance': 6.0, 'traffic_tolerance': 7.8,
         'establishment_rate': 8.5, 'mowing_tolerance': 7.5},
        year='2020', seeding_rate='6-8 lbs/1000 sq ft',
        notes='Top-performing ryegrass for fairway use. '
              'Dark green color and fine texture.',
    ))
    records.append(_add(
        'Stellar 3GL', 'perennial_ryegrass', 'fairway_tee',
        {'quality_score': 7.6, 'color_score': 7.8, 'density_score': 7.8,
         'disease_resistance': 7.8, 'drought_tolerance': 5.5, 'heat_tolerance': 5.2,
         'cold_tolerance': 7.2, 'shade_tolerance': 6.2, 'traffic_tolerance': 7.5,
         'establishment_rate': 8.5, 'mowing_tolerance': 7.3},
        year='2020', seeding_rate='6-8 lbs/1000 sq ft',
        notes='Gray leaf spot resistant (3GL designation). '
              'Improved disease tolerance.',
    ))
    records.append(_add(
        'Fiesta 4', 'perennial_ryegrass', 'lawn_turf',
        {'quality_score': 7.4, 'color_score': 7.5, 'density_score': 7.5,
         'disease_resistance': 7.2, 'drought_tolerance': 5.5, 'heat_tolerance': 5.5,
         'cold_tolerance': 7.5, 'shade_tolerance': 6.5, 'traffic_tolerance': 7.2,
         'establishment_rate': 8.8, 'mowing_tolerance': 7.0},
        year='2019', seeding_rate='6-8 lbs/1000 sq ft',
        notes='Excellent home lawn variety. Fast establishment and good shade '
              'tolerance.',
    ))
    records.append(_add(
        'Manhattan 5 GLR', 'perennial_ryegrass', 'sports',
        {'quality_score': 7.5, 'color_score': 7.6, 'density_score': 7.8,
         'disease_resistance': 7.6, 'drought_tolerance': 5.8, 'heat_tolerance': 5.5,
         'cold_tolerance': 7.0, 'shade_tolerance': 6.0, 'traffic_tolerance': 8.0,
         'establishment_rate': 8.5, 'mowing_tolerance': 7.2},
        year='2020', seeding_rate='6-8 lbs/1000 sq ft',
        notes='Sports turf specialist. Excellent wear tolerance and '
              'recovery. Gray leaf spot resistant.',
    ))
    # ----- Tall Fescue -----
    records.append(_add(
        'Regenerate', 'tall_fescue', 'lawn_turf',
        {'quality_score': 7.8, 'color_score': 7.5, 'density_score': 7.5,
         'disease_resistance': 7.5, 'drought_tolerance': 8.0, 'heat_tolerance': 7.5,
         'cold_tolerance': 7.5, 'shade_tolerance': 7.0, 'traffic_tolerance': 7.5,
         'establishment_rate': 7.5, 'mowing_tolerance': 7.2},
        year='2020', seeding_rate='6-8 lbs/1000 sq ft',
        notes='Top-rated TTTF. Excellent drought tolerance with deep root system. '
              'Fine-bladed for improved aesthetics.',
    ))
    records.append(_add(
        'Titanium 2LS', 'tall_fescue', 'lawn_turf',
        {'quality_score': 7.6, 'color_score': 7.8, 'density_score': 7.3,
         'disease_resistance': 7.8, 'drought_tolerance': 7.8, 'heat_tolerance': 7.5,
         'cold_tolerance': 7.2, 'shade_tolerance': 7.2, 'traffic_tolerance': 7.2,
         'establishment_rate': 7.2, 'mowing_tolerance': 7.0},
        year='2020', seeding_rate='6-8 lbs/1000 sq ft',
        notes='Lateral spreading tall fescue (2LS). Self-repairs thin areas. '
              'Good brown patch resistance.',
    ))
    records.append(_add(
        'Traverse 2 SRP', 'tall_fescue', 'lawn_turf',
        {'quality_score': 7.5, 'color_score': 7.3, 'density_score': 7.0,
         'disease_resistance': 7.2, 'drought_tolerance': 8.2, 'heat_tolerance': 7.8,
         'cold_tolerance': 7.0, 'shade_tolerance': 6.8, 'traffic_tolerance': 7.0,
         'establishment_rate': 7.8, 'mowing_tolerance': 7.0},
        year='2019', seeding_rate='6-8 lbs/1000 sq ft',
        notes='Self-Repair Plus technology. Exceptional drought and heat '
              'tolerance. Fast establishment.',
    ))
    records.append(_add(
        'Bullseye', 'tall_fescue', 'sports',
        {'quality_score': 7.4, 'color_score': 7.2, 'density_score': 7.5,
         'disease_resistance': 7.0, 'drought_tolerance': 7.5, 'heat_tolerance': 7.2,
         'cold_tolerance': 7.5, 'shade_tolerance': 6.5, 'traffic_tolerance': 8.0,
         'establishment_rate': 7.5, 'mowing_tolerance': 7.5},
        year='2020', seeding_rate='6-8 lbs/1000 sq ft',
        notes='Developed for sports turf use. High traffic tolerance '
              'with good recovery.',
    ))

    # ----- Zoysiagrass -----
    records.append(_add(
        'Innovation', 'zoysiagrass', 'lawn_turf',
        {'quality_score': 7.8, 'color_score': 7.5, 'density_score': 8.5,
         'disease_resistance': 7.5, 'drought_tolerance': 8.0, 'heat_tolerance': 8.0,
         'cold_tolerance': 7.0, 'shade_tolerance': 6.5, 'traffic_tolerance': 8.0,
         'establishment_rate': 5.0, 'mowing_tolerance': 7.5},
        year='2020', seed_available=0, seeding_rate='Vegetative only (sod/plug)',
        notes='Fine-textured zoysia with improved cold tolerance. '
              'Dense, carpet-like turf. Very low maintenance once established.',
    ))
    records.append(_add(
        'Geo', 'zoysiagrass', 'lawn_turf',
        {'quality_score': 7.5, 'color_score': 7.8, 'density_score': 8.2,
         'disease_resistance': 7.2, 'drought_tolerance': 8.2, 'heat_tolerance': 8.2,
         'cold_tolerance': 6.5, 'shade_tolerance': 7.0, 'traffic_tolerance': 7.8,
         'establishment_rate': 5.5, 'mowing_tolerance': 7.2},
        year='2019', seed_available=0, seeding_rate='Vegetative only (sod/plug)',
        notes='Best shade tolerance among zoysias. Good for '
              'partially shaded lawns in warm climates.',
    ))
    records.append(_add(
        'Zenith', 'zoysiagrass', 'lawn_turf',
        {'quality_score': 7.0, 'color_score': 7.0, 'density_score': 7.5,
         'disease_resistance': 7.0, 'drought_tolerance': 7.8, 'heat_tolerance': 8.0,
         'cold_tolerance': 7.2, 'shade_tolerance': 5.5, 'traffic_tolerance': 7.5,
         'establishment_rate': 6.0, 'mowing_tolerance': 7.0},
        year='2018', seeding_rate='1-2 lbs/1000 sq ft',
        notes='One of the few seeded zoysias available. Coarser texture '
              'than vegetative types but much easier and cheaper to establish.',
    ))
    records.append(_add(
        'Zeon', 'zoysiagrass', 'fairway_tee',
        {'quality_score': 8.0, 'color_score': 8.0, 'density_score': 8.5,
         'disease_resistance': 7.5, 'drought_tolerance': 8.0, 'heat_tolerance': 8.2,
         'cold_tolerance': 6.8, 'shade_tolerance': 6.8, 'traffic_tolerance': 8.2,
         'establishment_rate': 5.2, 'mowing_tolerance': 8.0},
        year='2020', seed_available=0, seeding_rate='Vegetative only (sod/plug)',
        notes='Premium fine-textured zoysia for golf and high-end lawns. '
              'Excellent density and color. Tolerates low mowing heights.',
    ))

    return records

def seed_cultivar_data():
    """Populate the cultivar_data table with built-in top performers.

    Skips insertion if the table already contains data to avoid duplicates.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM cultivar_data')
            row = cursor.fetchone()
            count = row[0] if row else 0

            if count > 0:
                logger.info(f"Cultivar data already seeded ({count} records). Skipping.")
                return count

            records = _build_cultivar_records()

            cols = [
                'cultivar_name', 'species', 'category',
                'quality_score', 'color_score', 'density_score',
                'disease_resistance', 'drought_tolerance', 'heat_tolerance',
                'cold_tolerance', 'shade_tolerance', 'traffic_tolerance',
                'establishment_rate', 'mowing_tolerance',
                'ntep_trial_year', 'region', 'state', 'trial_location',
                'seed_available', 'seeding_rate', 'notes',
            ]
            placeholders = ', '.join(['?'] * len(cols))
            col_str = ', '.join(cols)
            for rec in records:
                vals = tuple(rec.get(c) for c in cols)
                conn.execute(
                    f'INSERT INTO cultivar_data ({col_str}) VALUES ({placeholders})',
                    vals,
                )

            logger.info(f"Seeded {len(records)} cultivar records")
            return len(records)

    except Exception as e:
        logger.error(f"Failed to seed cultivar data: {e}")
        raise


# ---------------------------------------------------------------------------
# Search & Lookup
# ---------------------------------------------------------------------------

def search_cultivars(species=None, category=None, region=None, min_quality=None):
    """Search cultivars with optional filters.

    Args:
        species: Filter by species (e.g. 'bermudagrass')
        category: Filter by use category (e.g. 'greens')
        region: Filter by trial region
        min_quality: Minimum overall quality score (1-9)

    Returns:
        list of cultivar dicts
    """
    try:
        clauses = []
        params = []

        if species:
            clauses.append('species = ?')
            params.append(species)
        if category:
            clauses.append('category = ?')
            params.append(category)
        if region:
            clauses.append('region = ?')
            params.append(region)
        if min_quality is not None:
            clauses.append('quality_score >= ?')
            params.append(float(min_quality))

        where = ''
        if clauses:
            where = 'WHERE ' + ' AND '.join(clauses)

        sql = f'SELECT * FROM cultivar_data {where} ORDER BY quality_score DESC'

        with get_db() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    except Exception as e:
        logger.error(f"Cultivar search failed: {e}")
        return []


def get_cultivar_by_name(name):
    """Fetch a cultivar by exact name (case-insensitive).

    Returns:
        dict or None
    """
    try:
        with get_db() as conn:
            row = conn.execute(
                'SELECT * FROM cultivar_data WHERE LOWER(cultivar_name) = LOWER(?)',
                (name,),
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Cultivar lookup failed for '{name}': {e}")
        return None

def get_cultivar_detail(cultivar_id):
    """Get full details for a cultivar by ID.

    Returns:
        dict or None
    """
    try:
        with get_db() as conn:
            row = conn.execute(
                'SELECT * FROM cultivar_data WHERE id = ?',
                (cultivar_id,),
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Cultivar detail failed for id={cultivar_id}: {e}")
        return None


def compare_cultivars(cultivar_names, criteria_weights=None):
    """Compare multiple cultivars with optional weighted scoring.

    Args:
        cultivar_names: list of cultivar name strings
        criteria_weights: optional dict mapping trait names to weight floats.
                          Traits not in the dict get weight 0.
                          If None, all traits weighted equally.

    Returns:
        dict with 'cultivars' (list of dicts with scores) and
        'ranking' (sorted by weighted total, descending)
    """
    if not cultivar_names:
        return {'cultivars': [], 'ranking': []}

    weights = criteria_weights or DEFAULT_WEIGHTS

    try:
        results = []
        for name in cultivar_names:
            cv = get_cultivar_by_name(name)
            if not cv:
                logger.warning(f"Cultivar '{name}' not found -- skipping")
                continue

            weighted_total = 0.0
            weight_sum = 0.0
            trait_scores = {}
            for trait in TRAIT_COLUMNS:
                w = weights.get(trait, 0.0)
                score = cv.get(trait) or 0.0
                trait_scores[trait] = score
                weighted_total += score * w
                weight_sum += w

            weighted_avg = round(weighted_total / weight_sum, 2) if weight_sum else 0.0

            results.append({
                'cultivar_name': cv['cultivar_name'],
                'species': cv['species'],
                'category': cv['category'],                'trait_scores': trait_scores,
                'weighted_average': weighted_avg,
                'notes': cv.get('notes'),
                'seed_available': cv.get('seed_available'),
            })

        ranking = sorted(results, key=lambda x: x['weighted_average'], reverse=True)
        for i, item in enumerate(ranking):
            item['rank'] = i + 1

        return {'cultivars': results, 'ranking': ranking}

    except Exception as e:
        logger.error(f"Cultivar comparison failed: {e}")
        return {'cultivars': [], 'ranking': [], 'error': str(e)}


def get_top_cultivars(species, category=None, region=None, limit=10):
    """Get top-performing cultivars for a species/category/region.

    Returns:
        list of cultivar dicts ordered by quality_score descending
    """
    try:
        clauses = ['species = ?']
        params = [species]

        if category:
            clauses.append('category = ?')
            params.append(category)
        if region:
            clauses.append('region = ?')
            params.append(region)

        where = 'WHERE ' + ' AND '.join(clauses)
        sql = f'SELECT * FROM cultivar_data {where} ORDER BY quality_score DESC LIMIT ?'
        params.append(limit)

        with get_db() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    except Exception as e:
        logger.error(f"Top cultivars query failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Decision Support / Recommendations
# ---------------------------------------------------------------------------

def recommend_cultivars(user_requirements):
    """AI-style cultivar recommendation based on user requirements.

    Args:
        user_requirements: dict with optional keys:
            - species: preferred species
            - category: primary use (greens, fairway_tee, lawn_turf, sports)
            - region: climate region
            - priority_traits: list of trait names to prioritise
                               (e.g. ['drought_tolerance', 'disease_resistance'])
            - budget: 'premium' or 'economy' (premium allows vegetative-only)
            - min_quality: minimum acceptable quality score
            - shade: True if shade tolerance is important
            - traffic: 'high', 'moderate', or 'low'

    Returns:
        dict with 'recommendations' (sorted list) and 'reasoning'
    """
    try:
        species = user_requirements.get('species')
        category = user_requirements.get('category')
        region = user_requirements.get('region')
        priority_traits = user_requirements.get('priority_traits', [])
        budget = user_requirements.get('budget', 'premium')
        min_quality = user_requirements.get('min_quality', 5.0)
        shade = user_requirements.get('shade', False)
        traffic = user_requirements.get('traffic', 'moderate')

        # Build query
        clauses = []
        params = []

        if species:
            clauses.append('species = ?')
            params.append(species)
        if category:
            clauses.append('category = ?')
            params.append(category)
        if region:
            clauses.append('region = ?')
            params.append(region)

        clauses.append('quality_score >= ?')
        params.append(float(min_quality))

        if budget == 'economy':
            clauses.append('seed_available = 1')

        where = ''
        if clauses:
            where = 'WHERE ' + ' AND '.join(clauses)

        sql = f'SELECT * FROM cultivar_data {where} ORDER BY quality_score DESC'
        with get_db() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            cultivars = [dict(r) for r in rows]

        if not cultivars:
            return {
                'recommendations': [],
                'reasoning': 'No cultivars matched the given requirements. '
                             'Try broadening your search criteria.',
            }

        # Build dynamic weights based on requirements
        weights = {t: 1.0 for t in TRAIT_COLUMNS}

        # Boost priority traits
        for trait in priority_traits:
            if trait in weights:
                weights[trait] = 3.0

        # Contextual boosts
        if shade:
            weights['shade_tolerance'] = max(weights.get('shade_tolerance', 1.0), 2.5)

        if traffic == 'high':
            weights['traffic_tolerance'] = max(weights.get('traffic_tolerance', 1.0), 2.5)
            weights['establishment_rate'] = max(weights.get('establishment_rate', 1.0), 1.5)
        elif traffic == 'low':
            weights['traffic_tolerance'] = 0.5
        if category == 'greens':
            weights['density_score'] = max(weights.get('density_score', 1.0), 2.0)
            weights['mowing_tolerance'] = max(weights.get('mowing_tolerance', 1.0), 2.5)
        elif category == 'sports':
            weights['traffic_tolerance'] = max(weights.get('traffic_tolerance', 1.0), 2.5)
            weights['establishment_rate'] = max(weights.get('establishment_rate', 1.0), 2.0)

        # Score each cultivar
        scored = []
        weight_sum = sum(weights.values())

        for cv in cultivars:
            total = 0.0
            for trait in TRAIT_COLUMNS:
                score = cv.get(trait) or 0.0
                total += score * weights.get(trait, 1.0)
            weighted_avg = round(total / weight_sum, 2) if weight_sum else 0.0
            cv['recommendation_score'] = weighted_avg
            scored.append(cv)

        scored.sort(key=lambda x: x['recommendation_score'], reverse=True)
        # Build reasoning
        reasoning_parts = []
        if species:
            reasoning_parts.append(f"Filtered to {species.replace('_', ' ')}.")
        if category:
            reasoning_parts.append(f"Use category: {category.replace('_', '/')}.")
        if priority_traits:
            trait_str = ', '.join(t.replace('_', ' ') for t in priority_traits)
            reasoning_parts.append(f"Prioritised traits: {trait_str}.")
        if budget == 'economy':
            reasoning_parts.append("Limited to seed-available cultivars (economy budget).")
        if shade:
            reasoning_parts.append("Boosted shade tolerance weighting.")
        if traffic == 'high':
            reasoning_parts.append("Boosted traffic tolerance for high-use areas.")

        top = scored[:5]
        if top:
            reasoning_parts.append(
                f"Top recommendation: {top[0]['cultivar_name']} "
                f"(score {top[0]['recommendation_score']})."
            )

        return {
            'recommendations': scored[:10],
            'reasoning': ' '.join(reasoning_parts) if reasoning_parts else
                         'Ranked by overall NTEP quality score.',
            'weights_used': weights,
            'total_matches': len(scored),
        }

    except Exception as e:
        logger.error(f"Cultivar recommendation failed: {e}")
        return {'recommendations': [], 'reasoning': f'Error: {e}'}

def get_blend_recommendation(species, category=None, region=None):
    """Suggest a 2-3 cultivar blend for genetic diversity and resilience.

    Blends are chosen by selecting cultivars with complementary strengths
    from the top performers.

    Returns:
        dict with 'blend' (list of cultivar dicts), 'rationale', and
        'blend_percentages'
    """
    try:
        top = get_top_cultivars(species, category=category, region=region, limit=10)

        if len(top) < 2:
            return {
                'blend': top,
                'rationale': 'Not enough cultivars available for a blend recommendation.',
                'blend_percentages': {},
            }

        # Strategy: pick cultivars with complementary trait strengths
        # 1st pick: highest overall quality
        pick1 = top[0]

        # 2nd pick: best in a weakness area of pick1
        # Find pick1's weakest trait
        pick1_traits = {t: pick1.get(t, 0) for t in TRAIT_COLUMNS}
        weakest_trait = min(pick1_traits, key=pick1_traits.get)
        pick2 = None
        for cv in top[1:]:
            if (cv.get(weakest_trait, 0) or 0) > (pick1.get(weakest_trait, 0) or 0):
                pick2 = cv
                break
        if not pick2:
            pick2 = top[1]

        # 3rd pick (if available): adds genetic diversity
        pick3 = None
        used_names = {pick1['cultivar_name'], pick2['cultivar_name']}
        for cv in top[2:]:
            if cv['cultivar_name'] not in used_names:
                pick3 = cv
                break

        blend = [pick1, pick2]
        percentages = {}

        if pick3:
            blend.append(pick3)
            percentages = {
                pick1['cultivar_name']: '40%',
                pick2['cultivar_name']: '30%',
                pick3['cultivar_name']: '30%',
            }
        else:
            percentages = {
                pick1['cultivar_name']: '60%',
                pick2['cultivar_name']: '40%',
            }
        rationale_parts = [
            f"{pick1['cultivar_name']}: highest overall quality "
            f"(score {pick1.get('quality_score', 'N/A')}).",
            f"{pick2['cultivar_name']}: complements with stronger "
            f"{weakest_trait.replace('_', ' ')} "
            f"({pick2.get(weakest_trait, 'N/A')} vs "
            f"{pick1.get(weakest_trait, 'N/A')}).",
        ]
        if pick3:
            rationale_parts.append(
                f"{pick3['cultivar_name']}: adds genetic diversity "
                f"(quality {pick3.get('quality_score', 'N/A')})."
            )

        return {
            'blend': blend,
            'rationale': ' '.join(rationale_parts),
            'blend_percentages': percentages,
            'species': species,
            'category': category or 'general',
        }

    except Exception as e:
        logger.error(f"Blend recommendation failed: {e}")
        return {'blend': [], 'rationale': f'Error: {e}', 'blend_percentages': {}}

def calculate_seeding_rate(cultivar_name, method='seed', area_sqft=1000.0):
    """Calculate total seed/material needed for a given area.

    Args:
        cultivar_name: name of the cultivar
        method: planting method (seed, sod, sprig, plug)
        area_sqft: area in square feet

    Returns:
        dict with rate info and total needed, or None if not applicable
    """
    try:
        cv = get_cultivar_by_name(cultivar_name)
        if not cv:
            return {'error': f"Cultivar '{cultivar_name}' not found."}

        species = cv.get('species', '')
        stored_rate = cv.get('seeding_rate', '')
        seed_available = cv.get('seed_available', 1)

        # Check if method is available for this cultivar
        if method == 'seed' and not seed_available:
            return {
                'cultivar': cultivar_name,
                'method': method,
                'error': f'{cultivar_name} is a vegetative-only cultivar. '
                         f'Use sod, sprig, or plug instead.',
                'available_methods': ['sod', 'sprig', 'plug'],
            }
        # Get default rate for species + method
        species_rates = DEFAULT_SEEDING_RATES.get(species, {})
        method_rates = species_rates.get(method, {})

        if not method_rates:
            return {
                'cultivar': cultivar_name,
                'method': method,
                'error': f'No {method} rate data available for {species.replace("_", " ")}.',
                'stored_rate': stored_rate,
            }

        rate_str = method_rates.get('new', 'Unknown')
        units_per_1000 = area_sqft / 1000.0

        # Parse numeric rate range (e.g. "6-8 lbs")
        total_str = None
        try:
            parts = rate_str.replace(' lbs', '').replace(' lb', '').split('-')
            low = float(parts[0])
            high = float(parts[1]) if len(parts) > 1 else low
            total_low = round(low * units_per_1000, 1)
            total_high = round(high * units_per_1000, 1)
            total_str = f"{total_low}-{total_high} lbs" if total_low != total_high \
                else f"{total_low} lbs"
        except (ValueError, IndexError):
            total_str = f"{rate_str} (per 1000 sq ft x {units_per_1000:.1f})"
        return {
            'cultivar': cultivar_name,
            'species': species,
            'method': method,
            'rate_per_1000sqft': rate_str,
            'area_sqft': area_sqft,
            'total_needed': total_str,
            'overseed_rate': method_rates.get('overseed', 'N/A'),
            'notes': stored_rate or None,
        }

    except Exception as e:
        logger.error(f"Seeding rate calculation failed: {e}")
        return {'error': str(e)}


# ---------------------------------------------------------------------------
# Establishment Timelines & Checklists
# ---------------------------------------------------------------------------

def get_establishment_timeline(species, planting_method, region=None):
    """Get expected establishment timeline for a species and planting method.

    Args:
        species: turfgrass species key
        planting_method: seed, sod, sprig, or plug
        region: optional region for adjusted estimates (not yet implemented)

    Returns:
        dict with timeline stages or error
    """
    species_timelines = ESTABLISHMENT_TIMELINES.get(species)
    if not species_timelines:
        return {
            'error': f'No timeline data for species: {species}',
            'available_species': list(ESTABLISHMENT_TIMELINES.keys()),
        }

    method_timeline = species_timelines.get(planting_method)
    if not method_timeline:
        return {
            'error': f'No {planting_method} timeline for {species.replace("_", " ")}',
            'available_methods': list(species_timelines.keys()),
        }

    result = dict(method_timeline)
    result['species'] = species
    result['planting_method'] = planting_method

    if region:
        result['region_note'] = (
            f'Timelines shown are national averages. Actual times in '
            f'{region} may vary based on local climate and soil conditions.'
        )

    return result

def get_renovation_checklist(species, planting_method):
    """Get a step-by-step renovation checklist.

    Args:
        species: turfgrass species key (used for species-specific notes)
        planting_method: seed, sod, sprig, or plug

    Returns:
        dict with 'pre_planting', 'planting', 'post_planting' step lists
    """
    checklist = RENOVATION_CHECKLISTS.get(planting_method)
    if not checklist:
        return {
            'error': f'No checklist for planting method: {planting_method}',
            'available_methods': list(RENOVATION_CHECKLISTS.keys()),
        }

    result = {
        'species': species,
        'planting_method': planting_method,
        'pre_planting': list(checklist.get('pre_planting', [])),
        'planting': list(checklist.get('planting', [])),
        'post_planting': list(checklist.get('post_planting', [])),
    }

    # Add species-specific notes
    timeline = ESTABLISHMENT_TIMELINES.get(species, {}).get(planting_method, {})
    if timeline:
        best_planting = timeline.get('best_planting')
        if best_planting:
            result['pre_planting'].insert(
                0, f"Schedule planting for optimal window: {best_planting}"
            )
        species_notes = timeline.get('notes')
        if species_notes:
            result['species_notes'] = species_notes

    return result


# ---------------------------------------------------------------------------
# Renovation Projects (CRUD)
# ---------------------------------------------------------------------------

def create_renovation_project(user_id, data):
    """Create a new renovation project.

    Args:
        user_id: owner user id string
        data: dict with project fields:
            - project_name (required)
            - area, target_species, selected_cultivars (JSON list),
              planting_method, planting_date, area_sqft, status,
              establishment_notes

    Returns:
        dict with project id or error
    """
    if not user_id:
        return {'error': 'user_id is required'}
    if not data.get('project_name'):
        return {'error': 'project_name is required'}

    try:
        selected = data.get('selected_cultivars')
        if isinstance(selected, list):
            selected = json.dumps(selected)
        now = datetime.utcnow().isoformat()

        with get_db() as conn:
            cursor = conn.execute(
                '''INSERT INTO renovation_projects
                   (user_id, project_name, area, target_species,
                    selected_cultivars, planting_method, planting_date,
                    area_sqft, status, establishment_notes,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    user_id,
                    data['project_name'],
                    data.get('area'),
                    data.get('target_species'),
                    selected,
                    data.get('planting_method'),
                    data.get('planting_date'),
                    data.get('area_sqft'),
                    data.get('status', 'planning'),
                    data.get('establishment_notes'),
                    now,
                    now,
                ),
            )
            project_id = cursor.lastrowid

        logger.info(f"Created renovation project {project_id} for user {user_id}")
        return {'id': project_id, 'status': 'created'}
    except Exception as e:
        logger.error(f"Failed to create renovation project: {e}")
        return {'error': str(e)}


def update_renovation_project(project_id, user_id, data):
    """Update an existing renovation project.

    Args:
        project_id: project row id
        user_id: owner user id (for access check)
        data: dict of fields to update

    Returns:
        dict with status or error
    """
    if not project_id or not user_id:
        return {'error': 'project_id and user_id are required'}

    # Allowed update fields
    allowed = {
        'project_name', 'area', 'target_species', 'selected_cultivars',
        'planting_method', 'planting_date', 'area_sqft', 'status',
        'establishment_notes',
    }

    updates = {}
    for key in allowed:
        if key in data:
            val = data[key]
            if key == 'selected_cultivars' and isinstance(val, list):
                val = json.dumps(val)
            if key == 'status' and val not in VALID_STATUSES:
                return {'error': f"Invalid status '{val}'. Must be one of: {VALID_STATUSES}"}
            updates[key] = val

    if not updates:
        return {'error': 'No valid fields to update'}

    updates['updated_at'] = datetime.utcnow().isoformat()

    try:
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        params = list(updates.values()) + [project_id, user_id]

        with get_db() as conn:
            cursor = conn.execute(
                f'UPDATE renovation_projects SET {set_clause} WHERE id = ? AND user_id = ?',
                tuple(params),
            )
            if cursor.rowcount == 0:
                return {'error': 'Project not found or access denied'}

        logger.info(f"Updated renovation project {project_id}")
        return {'id': project_id, 'status': 'updated'}

    except Exception as e:
        logger.error(f"Failed to update renovation project {project_id}: {e}")
        return {'error': str(e)}

def get_renovation_projects(user_id):
    """Get all renovation projects for a user.

    Returns:
        list of project dicts
    """
    if not user_id:
        return []

    try:
        with get_db() as conn:
            rows = conn.execute(
                'SELECT * FROM renovation_projects WHERE user_id = ? ORDER BY updated_at DESC',
                (user_id,),
            ).fetchall()

            results = []
            for row in rows:
                project = dict(row)
                # Parse JSON fields
                for json_field in ('selected_cultivars',):
                    raw = project.get(json_field)
                    if raw and isinstance(raw, str):
                        try:
                            project[json_field] = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            pass
                results.append(project)

            return results
    except Exception as e:
        logger.error(f"Failed to get renovation projects for user {user_id}: {e}")
        return []


# ---------------------------------------------------------------------------
# Comparison save / load (user-saved comparisons)
# ---------------------------------------------------------------------------

def save_comparison(user_id, name, cultivar_ids, criteria_weights=None, notes=None):
    """Save a cultivar comparison for later reference.

    Args:
        user_id: owner user id
        name: comparison name
        cultivar_ids: list of cultivar id ints
        criteria_weights: optional dict of trait weights
        notes: optional notes text

    Returns:
        dict with comparison id or error
    """
    try:
        ids_json = json.dumps(cultivar_ids) if isinstance(cultivar_ids, list) else cultivar_ids
        weights_json = json.dumps(criteria_weights) if criteria_weights else None

        with get_db() as conn:
            cursor = conn.execute(
                '''INSERT INTO cultivar_comparisons
                   (user_id, name, cultivar_ids, criteria_weights, notes)
                   VALUES (?, ?, ?, ?, ?)''',
                (user_id, name, ids_json, weights_json, notes),
            )
            comp_id = cursor.lastrowid

        logger.info(f"Saved comparison {comp_id} for user {user_id}")
        return {'id': comp_id, 'status': 'saved'}

    except Exception as e:
        logger.error(f"Failed to save comparison: {e}")
        return {'error': str(e)}


def get_saved_comparisons(user_id):
    """Get all saved comparisons for a user.

    Returns:
        list of comparison dicts with parsed JSON fields
    """
    try:
        with get_db() as conn:
            rows = conn.execute(
                'SELECT * FROM cultivar_comparisons WHERE user_id = ? ORDER BY created_at DESC',
                (user_id,),
            ).fetchall()

            results = []
            for row in rows:
                comp = dict(row)
                for json_field in ('cultivar_ids', 'criteria_weights'):
                    raw = comp.get(json_field)
                    if raw and isinstance(raw, str):
                        try:
                            comp[json_field] = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            pass
                results.append(comp)

            return results

    except Exception as e:
        logger.error(f"Failed to get comparisons for user {user_id}: {e}")
        return []


def delete_renovation_project(project_id, user_id):
    """Delete a renovation project."""
    with get_db() as conn:
        conn.execute(
            'DELETE FROM renovation_projects WHERE id = ? AND user_id = ?',
            (project_id, user_id)
        )
    return {'deleted': True}