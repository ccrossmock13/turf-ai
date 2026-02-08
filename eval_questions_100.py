"""
100 Comprehensive Turfgrass Evaluation Questions
Covers disease, weed control, fertility, cultural practices, insects, PGRs, and more
"""

EVAL_QUESTIONS_100 = [
    # =========================================================================
    # DISEASE MANAGEMENT (25 questions)
    # =========================================================================
    {'question': 'What fungicide should I use for dollar spot on bentgrass greens?', 'expected_keywords': ['dollar spot', 'fungicide'], 'expected_products': ['banner', 'daconil', 'heritage'], 'category': 'disease'},
    {'question': 'How do I treat pythium blight on my golf course?', 'expected_keywords': ['pythium', 'fungicide'], 'expected_products': ['subdue', 'mefenoxam', 'segway'], 'category': 'disease'},
    {'question': 'What causes brown patch in tall fescue?', 'expected_keywords': ['brown patch', 'rhizoctonia', 'humidity'], 'expected_products': [], 'category': 'disease'},
    {'question': 'Best fungicide for anthracnose on annual bluegrass?', 'expected_keywords': ['anthracnose', 'poa annua'], 'expected_products': ['heritage', 'daconil', 'concert'], 'category': 'disease'},
    {'question': 'How do I prevent snow mold?', 'expected_keywords': ['snow mold', 'fall', 'winter'], 'expected_products': ['chlorothalonil', 'instrata'], 'category': 'disease'},
    {'question': 'What is the best treatment for fairy ring?', 'expected_keywords': ['fairy ring', 'fungicide'], 'expected_products': ['prostar', 'heritage'], 'category': 'disease'},
    {'question': 'How do I control take-all patch?', 'expected_keywords': ['take-all', 'gaeumannomyces'], 'expected_products': ['rubigan', 'heritage'], 'category': 'disease'},
    {'question': 'What causes summer patch and how do I treat it?', 'expected_keywords': ['summer patch', 'magnaporthe'], 'expected_products': ['banner', 'rubigan'], 'category': 'disease'},
    {'question': 'Best fungicide rotation for disease resistance management?', 'expected_keywords': ['rotation', 'resistance', 'frac'], 'expected_products': [], 'category': 'disease'},
    {'question': 'How do I identify gray leaf spot?', 'expected_keywords': ['gray leaf spot', 'pyricularia', 'perennial ryegrass'], 'expected_products': [], 'category': 'disease'},
    {'question': 'What is the FRAC code for propiconazole?', 'expected_keywords': ['frac', 'dmi', '3'], 'expected_products': ['propiconazole', 'banner'], 'category': 'disease'},
    {'question': 'How do I treat red thread disease?', 'expected_keywords': ['red thread', 'laetisaria', 'nitrogen'], 'expected_products': [], 'category': 'disease'},
    {'question': 'Best fungicide for spring dead spot?', 'expected_keywords': ['spring dead spot', 'bermuda'], 'expected_products': ['rubigan', 'prostar'], 'category': 'disease'},
    {'question': 'How do I control necrotic ring spot?', 'expected_keywords': ['necrotic ring spot', 'ophiosphaerella'], 'expected_products': ['rubigan', 'banner'], 'category': 'disease'},
    {'question': 'What causes leaf spot on Kentucky bluegrass?', 'expected_keywords': ['leaf spot', 'bipolaris', 'drechslera'], 'expected_products': [], 'category': 'disease'},
    {'question': 'Curative vs preventive fungicide applications?', 'expected_keywords': ['curative', 'preventive', 'timing'], 'expected_products': [], 'category': 'disease'},
    {'question': 'How often should I apply fungicides during high disease pressure?', 'expected_keywords': ['interval', 'days', 'pressure'], 'expected_products': [], 'category': 'disease'},
    {'question': 'What is the best tank mix for dollar spot and brown patch?', 'expected_keywords': ['tank mix', 'dollar spot', 'brown patch'], 'expected_products': [], 'category': 'disease'},
    {'question': 'How do I prevent algae on greens?', 'expected_keywords': ['algae', 'drainage', 'shade'], 'expected_products': ['daconil'], 'category': 'disease'},
    {'question': 'What causes yellow patch in cool-season turf?', 'expected_keywords': ['yellow patch', 'rhizoctonia cerealis'], 'expected_products': [], 'category': 'disease'},
    {'question': 'Best cultural practices to reduce disease pressure?', 'expected_keywords': ['cultural', 'mowing', 'irrigation', 'fertility'], 'expected_products': [], 'category': 'disease'},
    {'question': 'How do I treat fusarium patch?', 'expected_keywords': ['fusarium', 'microdochium'], 'expected_products': ['heritage', 'medallion'], 'category': 'disease'},
    {'question': 'What is the difference between pythium blight and pythium root rot?', 'expected_keywords': ['pythium', 'blight', 'root rot'], 'expected_products': [], 'category': 'disease'},
    {'question': 'How do I calibrate my sprayer for fungicide applications?', 'expected_keywords': ['calibrate', 'sprayer', 'gpa', 'gallons'], 'expected_products': [], 'category': 'disease'},
    {'question': 'What causes rapid blight in perennial ryegrass?', 'expected_keywords': ['rapid blight', 'labyrinthula'], 'expected_products': [], 'category': 'disease'},

    # =========================================================================
    # WEED CONTROL (20 questions)
    # =========================================================================
    {'question': 'When should I apply pre-emergent herbicide in the transition zone?', 'expected_keywords': ['pre-emergent', 'soil temperature', '55'], 'expected_products': ['prodiamine', 'dimension', 'barricade'], 'category': 'weed'},
    {'question': 'Best herbicide for poa annua control in bentgrass?', 'expected_keywords': ['poa annua', 'bentgrass'], 'expected_products': ['velocity', 'prograss', 'poa constrictor'], 'category': 'weed'},
    {'question': 'How do I control crabgrass in bermudagrass fairways?', 'expected_keywords': ['crabgrass', 'bermuda'], 'expected_products': ['dimension', 'drive', 'quinclorac'], 'category': 'weed'},
    {'question': 'What is the best post-emergent for broadleaf weeds?', 'expected_keywords': ['broadleaf', 'post-emergent'], 'expected_products': ['trimec', '2,4-d', 'dicamba'], 'category': 'weed'},
    {'question': 'How do I control goosegrass?', 'expected_keywords': ['goosegrass', 'eleusine'], 'expected_products': ['revolver', 'dismiss'], 'category': 'weed'},
    {'question': 'Best herbicide for sedge control?', 'expected_keywords': ['sedge', 'nutsedge'], 'expected_products': ['sedgehammer', 'dismiss', 'certainty'], 'category': 'weed'},
    {'question': 'When is the best time to apply post-emergent herbicides?', 'expected_keywords': ['post-emergent', 'timing', 'temperature'], 'expected_products': [], 'category': 'weed'},
    {'question': 'How do I control clover in lawns?', 'expected_keywords': ['clover', 'trifolium'], 'expected_products': ['triclopyr', 'trimec'], 'category': 'weed'},
    {'question': 'What is the split application rate for prodiamine?', 'expected_keywords': ['prodiamine', 'split', 'rate'], 'expected_products': ['prodiamine', 'barricade'], 'category': 'weed'},
    {'question': 'How do I control dandelions?', 'expected_keywords': ['dandelion', 'taraxacum'], 'expected_products': ['2,4-d', 'trimec'], 'category': 'weed'},
    {'question': 'Best pre-emergent for a bermudagrass golf course?', 'expected_keywords': ['pre-emergent', 'bermuda'], 'expected_products': ['prodiamine', 'ronstar', 'pendimethalin'], 'category': 'weed'},
    {'question': 'How do I control kyllinga?', 'expected_keywords': ['kyllinga'], 'expected_products': ['certainty', 'dismiss'], 'category': 'weed'},
    {'question': 'What herbicide is safe for zoysiagrass?', 'expected_keywords': ['zoysia', 'safe'], 'expected_products': ['certainty', 'celsius'], 'category': 'weed'},
    {'question': 'How do I eliminate bermudagrass from a zoysiagrass lawn?', 'expected_keywords': ['bermuda', 'zoysia'], 'expected_products': ['fusilade', 'ornamec'], 'category': 'weed'},
    {'question': 'Best herbicide for dallisgrass control?', 'expected_keywords': ['dallisgrass', 'paspalum'], 'expected_products': ['msma', 'celsius'], 'category': 'weed'},
    {'question': 'How do I control prostrate spurge?', 'expected_keywords': ['spurge', 'euphorbia'], 'expected_products': ['quicksilver', 'dismiss'], 'category': 'weed'},
    {'question': 'What is the re-seed interval after using tenacity?', 'expected_keywords': ['tenacity', 'reseed', 'interval'], 'expected_products': ['tenacity', 'mesotrione'], 'category': 'weed'},
    {'question': 'How do I control wild violet?', 'expected_keywords': ['violet', 'viola'], 'expected_products': ['triclopyr', 'q4'], 'category': 'weed'},
    {'question': 'Best herbicide for annual bluegrass in cool-season turf?', 'expected_keywords': ['annual bluegrass', 'poa annua', 'cool-season'], 'expected_products': ['velocity', 'prograss'], 'category': 'weed'},
    {'question': 'How do I control doveweed?', 'expected_keywords': ['doveweed', 'murdannia'], 'expected_products': ['celsius', 'dismiss'], 'category': 'weed'},

    # =========================================================================
    # FERTILITY & NUTRITION (15 questions)
    # =========================================================================
    {'question': 'What is the recommended nitrogen rate for bermudagrass fairways?', 'expected_keywords': ['nitrogen', 'bermuda', 'pound'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'How much potassium should I apply to greens?', 'expected_keywords': ['potassium', 'greens'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'When should I apply iron to turfgrass?', 'expected_keywords': ['iron', 'chlorosis', 'green'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'What is the best N-P-K ratio for overseeding?', 'expected_keywords': ['n-p-k', 'overseeding', 'phosphorus'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'How do I calculate fertilizer rates per 1000 sq ft?', 'expected_keywords': ['calculate', 'rate', '1000'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'What causes iron chlorosis in turfgrass?', 'expected_keywords': ['iron', 'chlorosis', 'ph'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'Best time to fertilize cool-season turfgrass?', 'expected_keywords': ['fertilize', 'cool-season', 'fall'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'How much nitrogen do bentgrass greens need annually?', 'expected_keywords': ['nitrogen', 'bentgrass', 'greens', 'annual'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'What is spoon feeding and when should I use it?', 'expected_keywords': ['spoon feeding', 'light', 'frequent'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'How do I interpret a soil test for turfgrass?', 'expected_keywords': ['soil test', 'ph', 'nutrients'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'What is the difference between quick release and slow release nitrogen?', 'expected_keywords': ['quick release', 'slow release', 'nitrogen'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'How do I correct manganese deficiency?', 'expected_keywords': ['manganese', 'deficiency'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'Best fertilizer for establishing new turfgrass?', 'expected_keywords': ['establishing', 'starter', 'phosphorus'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'How much sulfur should I apply to lower soil pH?', 'expected_keywords': ['sulfur', 'ph', 'lower'], 'expected_products': [], 'category': 'fertility'},
    {'question': 'What causes black layer in greens?', 'expected_keywords': ['black layer', 'sulfur', 'anaerobic'], 'expected_products': [], 'category': 'fertility'},

    # =========================================================================
    # CULTURAL PRACTICES (15 questions)
    # =========================================================================
    {'question': 'What is the ideal mowing height for bentgrass greens?', 'expected_keywords': ['mowing height', 'bentgrass', 'greens', 'inch'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'How often should I aerate my fairways?', 'expected_keywords': ['aerate', 'fairway', 'core'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'What is the best time to topdress greens?', 'expected_keywords': ['topdress', 'sand', 'greens'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'How do I calculate topdressing rates?', 'expected_keywords': ['topdress', 'rate', 'cubic'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'When should I verticut bermudagrass?', 'expected_keywords': ['verticut', 'bermuda', 'thatch'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'What is the one-third rule for mowing?', 'expected_keywords': ['one-third', 'mowing', 'stress'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'How do I manage thatch in Kentucky bluegrass?', 'expected_keywords': ['thatch', 'kentucky bluegrass', 'aeration'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'Best practices for overseeding bermudagrass with ryegrass?', 'expected_keywords': ['overseeding', 'bermuda', 'ryegrass'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'How deep should I aerate greens?', 'expected_keywords': ['aerate', 'depth', 'greens'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'What is solid tine vs hollow tine aeration?', 'expected_keywords': ['solid tine', 'hollow tine', 'core'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'How do I manage organic matter in greens?', 'expected_keywords': ['organic matter', 'greens', 'topdress'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'What is the best rolling frequency for greens?', 'expected_keywords': ['rolling', 'greens', 'speed'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'How do I transition from overseeded ryegrass back to bermuda?', 'expected_keywords': ['transition', 'ryegrass', 'bermuda'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'What is venting and when should I do it?', 'expected_keywords': ['venting', 'needle tine', 'aeration'], 'expected_products': [], 'category': 'cultural'},
    {'question': 'How do I manage shade on golf course turf?', 'expected_keywords': ['shade', 'tree', 'thinning'], 'expected_products': [], 'category': 'cultural'},

    # =========================================================================
    # IRRIGATION (10 questions)
    # =========================================================================
    {'question': 'How much water does bermudagrass need per week?', 'expected_keywords': ['water', 'bermuda', 'inch'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'What is ET and how do I use it for irrigation scheduling?', 'expected_keywords': ['evapotranspiration', 'et', 'scheduling'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'How do I calibrate my irrigation system?', 'expected_keywords': ['calibrate', 'irrigation', 'catch can'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'What causes localized dry spots?', 'expected_keywords': ['localized dry spot', 'hydrophobic', 'wetting agent'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'Best time of day to irrigate turfgrass?', 'expected_keywords': ['irrigate', 'morning', 'disease'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'How do I manage irrigation during drought?', 'expected_keywords': ['drought', 'water', 'stress'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'What is deep and infrequent irrigation?', 'expected_keywords': ['deep', 'infrequent', 'root'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'How do wetting agents work?', 'expected_keywords': ['wetting agent', 'surfactant', 'hydrophobic'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'What is the distribution uniformity of my irrigation system?', 'expected_keywords': ['distribution uniformity', 'du', 'efficiency'], 'expected_products': [], 'category': 'irrigation'},
    {'question': 'How do I manage salinity in irrigation water?', 'expected_keywords': ['salinity', 'salt', 'leaching'], 'expected_products': [], 'category': 'irrigation'},

    # =========================================================================
    # INSECTS & PESTS (10 questions)
    # =========================================================================
    {'question': 'How do I control grubs in my lawn?', 'expected_keywords': ['grub', 'white grub', 'larva'], 'expected_products': ['merit', 'imidacloprid', 'dylox'], 'category': 'insect'},
    {'question': 'What is the best insecticide for chinch bugs?', 'expected_keywords': ['chinch bug', 'insecticide'], 'expected_products': ['bifenthrin', 'talstar'], 'category': 'insect'},
    {'question': 'How do I control armyworms?', 'expected_keywords': ['armyworm', 'caterpillar'], 'expected_products': ['bifenthrin', 'acelepryn'], 'category': 'insect'},
    {'question': 'When should I apply preventive grub control?', 'expected_keywords': ['grub', 'preventive', 'timing'], 'expected_products': ['merit', 'acelepryn'], 'category': 'insect'},
    {'question': 'How do I identify billbug damage?', 'expected_keywords': ['billbug', 'damage', 'sawdust'], 'expected_products': [], 'category': 'insect'},
    {'question': 'Best treatment for mole crickets?', 'expected_keywords': ['mole cricket'], 'expected_products': ['fipronil', 'bifenthrin'], 'category': 'insect'},
    {'question': 'How do I control sod webworms?', 'expected_keywords': ['sod webworm', 'caterpillar'], 'expected_products': ['bifenthrin', 'carbaryl'], 'category': 'insect'},
    {'question': 'What causes crane fly damage?', 'expected_keywords': ['crane fly', 'leatherjacket', 'larva'], 'expected_products': [], 'category': 'insect'},
    {'question': 'How do I control fire ants on golf courses?', 'expected_keywords': ['fire ant', 'mound'], 'expected_products': ['fipronil', 'advion'], 'category': 'insect'},
    {'question': 'What is the threshold for treating grubs?', 'expected_keywords': ['threshold', 'grub', 'per square'], 'expected_products': [], 'category': 'insect'},

    # =========================================================================
    # PLANT GROWTH REGULATORS (5 questions)
    # =========================================================================
    {'question': 'How do I apply Primo Maxx to greens?', 'expected_keywords': ['primo', 'trinexapac', 'rate'], 'expected_products': ['primo', 'trinexapac-ethyl'], 'category': 'pgr'},
    {'question': 'What is the rebound effect from PGRs?', 'expected_keywords': ['rebound', 'pgr', 'growth'], 'expected_products': [], 'category': 'pgr'},
    {'question': 'Best PGR for poa annua seedhead suppression?', 'expected_keywords': ['poa', 'seedhead', 'pgr'], 'expected_products': ['proxy', 'embark'], 'category': 'pgr'},
    {'question': 'How do I use ethephon on bermudagrass?', 'expected_keywords': ['ethephon', 'bermuda'], 'expected_products': ['proxy', 'ethephon'], 'category': 'pgr'},
    {'question': 'What is GDD and how do I use it for PGR applications?', 'expected_keywords': ['gdd', 'growing degree days', 'timing'], 'expected_products': [], 'category': 'pgr'},
]


if __name__ == '__main__':
    print(f"Total questions: {len(EVAL_QUESTIONS_100)}")
    categories = {}
    for q in EVAL_QUESTIONS_100:
        cat = q['category']
        categories[cat] = categories.get(cat, 0) + 1
    print("\nBy category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
