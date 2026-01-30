def detect_grass_type(question):
    """Detect grass type from question"""
    question_lower = question.lower()
    
    grass_types = {
        'bentgrass': ['bentgrass', 'bent grass', 'agrostis', 'creeping bent'],
        'bermudagrass': ['bermudagrass', 'bermuda', 'cynodon'],
        'poa annua': ['poa', 'poa annua', 'annual bluegrass'],
        'kentucky bluegrass': ['kentucky bluegrass', 'kbg', 'poa pratensis'],
        'tall fescue': ['tall fescue', 'fescue'],
        'perennial ryegrass': ['perennial ryegrass', 'ryegrass', 'rye grass'],
        'zoysiagrass': ['zoysiagrass', 'zoysia'],
    }
    
    for grass_type, keywords in grass_types.items():
        if any(keyword in question_lower for keyword in keywords):
            return grass_type
    
    return None

def detect_region(question):
    """Detect region/state from question"""
    question_lower = question.lower()
    
    regions = {
        'northeast': ['massachusetts', 'connecticut', 'rhode island', 'vermont', 'new hampshire', 'maine', 'new york', 'pennsylvania', 'new jersey'],
        'southeast': ['florida', 'georgia', 'alabama', 'south carolina', 'north carolina', 'virginia', 'tennessee'],
        'midwest': ['illinois', 'indiana', 'ohio', 'michigan', 'wisconsin', 'minnesota', 'iowa'],
        'southwest': ['texas', 'oklahoma', 'arizona', 'new mexico'],
        'west': ['california', 'oregon', 'washington', 'nevada', 'colorado'],
    }
    
    for region, states in regions.items():
        if any(state in question_lower for state in states):
            return region
    
    return None

def detect_product_need(question):
    """Detect what type of product is needed based on question"""
    question_lower = question.lower()
    
    disease_keywords = ['dollar spot', 'brown patch', 'pythium', 'anthracnose', 'fairy ring', 
                       'summer patch', 'fusarium', 'snow mold', 'rust', 'leaf spot', 
                       'take-all', 'spring dead spot', 'disease', 'fungicide', 'gray leaf spot',
                       'red thread', 'pink patch', 'microdochium', 'typhula', 'algae', 'moss']
    
    weed_keywords = ['weed', 'crabgrass', 'poa', 'goosegrass', 'sedge', 'clover', 
                    'dandelion', 'herbicide', 'pre-emergent', 'post-emergent']
    
    insect_keywords = ['grub', 'armyworm', 'cutworm', 'billbug', 'mole cricket', 
                      'chinch bug', 'insect', 'insecticide', 'pest']
    
    pgr_keywords = ['growth', 'pgr', 'primo', 'reduce mowing', 'plant growth regulator']
    
    if any(keyword in question_lower for keyword in disease_keywords):
        return 'fungicide'
    elif any(keyword in question_lower for keyword in weed_keywords):
        return 'herbicide'
    elif any(keyword in question_lower for keyword in insect_keywords):
        return 'insecticide'
    elif any(keyword in question_lower for keyword in pgr_keywords):
        return 'pgr'
    
    return None
