"""
Constants and static data for the Greenside turf management application.
Centralizes product lists, keyword mappings, and other configuration data.
"""

# Product name lists for filtering search results
HERBICIDES = [
    'specticle', 'tenacity', 'monument', 'certainty', 'sedgehammer',
    'drive', 'barricade', 'dimension', 'prodiamine', 'pendimethalin',
    'acclaim', 'revolver', 'dismiss', 'tribute', 'tower', 'katana',
    'kerb', 'gallery', 'surflan', 'ronstar', 'oryzalin', 'poacure'
]

FUNGICIDES = [
    'heritage', 'lexicon', 'xzemplar', 'headway', 'renown', 'medallion',
    'interface', 'tartan', 'banner', 'bayleton', 'tourney', 'compass',
    'honor', 'posterity', 'secure', 'briskway', 'velista', 'concert',
    'daconil', 'chipco', 'subdue', 'banol', 'segway', 'disarm', 'finale',
    '3336'
]

INSECTICIDES = [
    'acelepryn', 'merit', 'arena', 'allectus', 'meridian', 'chlorpyrifos',
    'bifenthrin', 'dylox', 'sevin', 'talstar'
]

PGRS = ['primo', 'trimmit', 'cutless', 'anuew', 'embark', 'proxy']

# Keywords for topic detection
TOPIC_KEYWORDS = {
    'irrigation': ['irrigation', 'sprinkler', 'water', 'valve', 'pump', 'controller'],
    'equipment': ['mower', 'mowing', 'equipment', 'reel', 'bedknife', 'roller'],
    'cultural': ['aerify', 'aeration', 'topdress', 'seed', 'overseed', 'sod'],
    'timing': ['when', 'timing', 'schedule', 'program', 'month'],
    'algae': ['algae', 'moss', 'slime'],
    'product': ['spray', 'apply', 'fungicide', 'herbicide', 'insecticide', 'control', 'treat', 'product'],
    'water': ['drought', 'water', 'irrigation', 'conservation', 'moisture']
}

# Wrong product type keywords for filtering
WRONG_TYPE_KEYWORDS = {
    'fungicide': ['herbicide', 'pre-emergent', 'post-emergent', 'weed control'],
    'herbicide': ['disease control'],
    'insecticide': ['disease control', 'weed control']
}

# Grass types for relevance scoring
GRASS_TYPES = ['bentgrass', 'bermudagrass', 'poa annua', 'kentucky bluegrass', 'zoysiagrass']

# US States for geographic detection
US_STATES = [
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut',
    'delaware', 'florida', 'georgia', 'hawaii', 'idaho', 'illinois', 'indiana', 'iowa',
    'kansas', 'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts', 'michigan',
    'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire',
    'new jersey', 'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio',
    'oklahoma', 'oregon', 'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington', 'west virginia',
    'wisconsin', 'wyoming'
]

# Static folders for PDF resources
STATIC_FOLDERS = {
    'product-labels': 'Product Labels',
    'epa_labels': 'Product Labels',
    'solution-sheets': 'Solution Sheets',
    'spray-programs': 'Spray Programs',
    'ntep-pdfs': 'NTEP Trials'
}

# Search folders for source URL lookup
SEARCH_FOLDERS = [
    'static/product-labels',
    'static/epa_labels',
    'static/solution-sheets',
    'static/spray-programs',
    'static/pdfs/product-labels',
    'static/ntep-pdfs'
]

# Default sources when no matching PDFs found
DEFAULT_SOURCES = [
    {
        'number': 1,
        'name': 'USGA Green Section',
        'url': 'https://www.usga.org/course-care.html',
        'type': 'reference'
    },
    {
        'number': 2,
        'name': 'GCSAA Resources',
        'url': 'https://www.gcsaa.org/',
        'type': 'reference'
    },
    {
        'number': 3,
        'name': 'Purdue Turfgrass Science',
        'url': 'https://turf.purdue.edu/',
        'type': 'reference'
    },
    {
        'number': 4,
        'name': 'Rutgers Turfgrass',
        'url': 'https://njaes.rutgers.edu/turf/',
        'type': 'reference'
    }
]

# Low-quality source patterns to penalize
LOW_QUALITY_SOURCES = ['hydroseeding', 'small pack', 'info sheet', 'general', 'catalog', 'brochure']

# High-value fungicide source patterns
HIGH_VALUE_FUNGICIDE_SOURCES = ['chemical control', 'turfgrass disease', 'ppa1', 'kentucky']

# Scoring weights
VECTOR_SCORE_WEIGHT = 0.7
KEYWORD_SCORE_WEIGHT = 0.3

# Boost/penalty multipliers
SCORE_BOOSTS = {
    'high_value_fungicide': 50.0,
    'product_label': 3.0,
    'grass_type_match': 1.3,
    'state_match': 2.0,
    'region_match': 1.2,
    'water_keyword_match': 2.0,
    'keyword_in_source': 2.0
}

SCORE_PENALTIES = {
    'solution_sheet': 0.4,
    'low_quality_source': 0.1,
    'wrong_grass': 0.5,
    'canada_product': 0.1,
    'wrong_product_type': 0.05,
    'wrong_type_keyword': 0.1
}

# API configuration
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o"
PINECONE_INDEX = "turf-research"

# Search limits
GENERAL_SEARCH_TOP_K = 30
PRODUCT_SEARCH_TOP_K = 50
TIMING_SEARCH_TOP_K = 20
ALGAE_SEARCH_TOP_K = 20
MAX_CONTEXT_LENGTH = 32000
MAX_CHUNK_LENGTH = 1200
MAX_SOURCES = 12
