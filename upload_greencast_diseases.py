"""
Upload GreenCast disease guide content to Pinecone.
Strips Syngenta product recommendations - keeps only disease science
(symptoms, conditions, management tips, causal agents).
"""

import os
import re
import hashlib
import logging
import time
from dotenv import load_dotenv
import openai
from pinecone import Pinecone

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 200
BATCH_SIZE = 50

# ── All 27 GreenCast diseases with scraped content ──────────────────────────

DISEASES = {
    "dollar_spot": {
        "name": "Dollar Spot",
        "causal_agent": "Clarireedia jacksonii, Clarireedia monteithiana, Clarireedia bennettii and C. homoeocarp",
        "susceptible": "Affects all turfgrass",
        "symptoms": "Dollar spot symptoms vary with height of cut. Initial infections appear as specks or small spots of white or tan colored leaves. On close cut golf turfs, spots usually grow to a size of 0.5\" to 2\" in diameter, and normally are bleached white or straw-colored. Huge numbers of spots may develop, coalesce to blight large areas and become pitted. In higher cut lawns and roughs, bleached, tan or straw-colored leaves develop in spots that may enlarge to 3\" or 4\" in diameter. Spots can coalesce and blight large areas. In most species, distinctive hour-glass-shaped leaf spot lesions bordered by dark-brown or purple-colored bands of tissue are diagnostic. In some species, like tall fescue and warm-season-grasses, there may only be tip die-back or irregularly shaped, tan lesions with dark-brown or purple-brown bands bordering lesions. White fluffy or cobweb-like mycelium often is observed in the early morning in the presence of heavy dew. During cooler spring periods, infection centers may appear pinkish or there may be a tan spot with a red/pink periphery.",
        "conditions": "Dollar spot can occur at any time from mid-spring to late fall. Most often, the disease activates in mid-spring when average night temperatures range from 55F to 75F. Dollar spot is mostly favored by warm days, cool nights and heavy dews, but outbreaks can occur during much cooler periods (even in winter during mild periods in some regions). Poorly nourished turf and dry soil conditions enhance disease severity.",
        "management": "Dollar spot, often described as a disease of poorly nourished turf, also is destructive to appropriately fertilized turfs. After disease subsides, apply modest amounts of nitrogen (approximately 0.25 lbs N/1,000 ft2) to enhance recovery to higher maintained turf; spoon-feeding (approximately 0.15 lbs N/1,000 ft2) greens, collars and approaches every 10-14 days is powerful in promoting recovery. Reduce thatch. Increase air circulation. Avoid drought stress and irrigate turf frequently enough to maintain good soil moisture when the disease is active. Rolling, mowing in the morning, and dew removal help reduce disease severity on greens and elsewhere. Convert to a cultivar (especially for bentgrass) with improved dollar spot resistance. Apply appropriate systemic fungicides on a preventive basis. Curatively, it is best to tank-mix an effective contact fungicide and systemic fungicide in combination with a small amount of water-soluble nitrogen.",
        "regions": "Most economically important disease of turfgrasses worldwide.",
        "grasses": ["bentgrass", "bluegrass", "fescue", "ryegrass", "bermuda", "zoysia"]
    },
    "brown_patch": {
        "name": "Brown Patch",
        "causal_agent": "Rhizoctonia solani",
        "susceptible": "Bentgrass; Perennial ryegrass; Tall fescue",
        "symptoms": "Symptoms of brown patch vary depending on turf species and mowing height. Brown patch typically appears as circular spots or patches of blighted turfgrass measuring 3\" to more than 3' in diameter. The sudden, almost overnight, appearance of large, brown patches is diagnostic. Grayish foliar mycelium and grayish-black smoke rings on the peripheries of patches are mostly seen in the early morning. Leaf lesions are most distinctive and common on tall fescue, which are variously shaped, chocolate-brown and have a dark-brown border. On other species, there normally is just a brownish blighting and/or twisting of leaves. In Kentucky bluegrass, usually in wet shade, there can be brown banding lesions somewhat similar to dollar spot; the difference being that lesions are brown and not bleached white.",
        "conditions": "Brown patch is favored by night temperatures > 63F, humidity and long leaf surface wetness periods in summer. Rain, overcast conditions and thunderstorms provide ideal infection conditions. It is severe in shade and full sun, but areas around trees or wherever air circulation is poor are more severely blighted. The pathogen is mostly a leaf blighter and recovery with good management practices normally occurs in the absence of other stress factors.",
        "management": "Use mostly slow release nitrogen sources in fall. Improve air circulation and minimize shade by pruning/clearing trees and brush. Improve surface water drainage. Avoid a high canopy. Reduce thatch. Pre-dawn irrigation that knocks-down mycelium has been shown to reduce brown patch severity. Where common, use effective fungicides to prevent brown patch. Curatively, it is best to tank-mix appropriate contact and systemic fungicides to stop blighting more quickly.",
        "regions": "All regions where cool-season grasses are grown, especially transition areas.",
        "grasses": ["bentgrass", "ryegrass", "fescue", "bluegrass"]
    },
    "anthracnose": {
        "name": "Anthracnose",
        "causal_agent": "Colletotrichum cereale",
        "susceptible": "Creeping bentgrass; Annual bluegrass",
        "symptoms": "Anthracnose can develop at any time of year, but it is most destructive during summer. It can cause a foliar blight and/or basal stem rot. Foliar blight occurs during summer stress, affected leaves exhibit a bright yellow appearance and turf thins-out. Black fruiting bodies (acervuli) burst through leaf surfaces and have distinctive black hairs. In the case of basal rot, infected plants initially have either an orange, bronze or yellow appearance. On greens, the disease usually first appears as speckles or yellow spots. Infected plants die in irregularly shaped areas. In mixed stands on greens, yellow blighted annual bluegrass develops in peripheral areas adjacent to bentgrass. Anthracnose never seems to attack both annual bluegrass and bentgrass on the same green or same golf course. On close inspection the presence of badly blackened stem bases and/or acervuli are diagnostic. Affected bentgrass usually has a reddish-brown color and acervuli normally are present on dying or dead leaves.",
        "conditions": "Conditions range from cold and wet to hot and dry, but it is most damaging in summer. Drought and high temperature stresses as well as low mowing and low nitrogen fertility are associated with severe outbreaks. Other important stress factors include intense traffic, soil compaction, and poor air and water drainage.",
        "management": "Increase height of cut and use solid rollers in summer. Apply small amounts of nitrogen (approximately 0.1 to 0.2 lb N/1,000 ft2) periodically throughout the growing season. Divert traffic and minimize mower stress. Light and frequent sand topdressings throughout the growing season help suppress the disease by cushioning stem bases. Avoid drought stress; syringe and hand water when necessary. Minimize encroachment and domination of annual bluegrass using appropriate growth regulators and/or herbicides. Preventive applications of appropriate systemic fungicides are highly effective, especially when combined with small amounts of nitrogen and an increase in mowing height.",
        "regions": "In all regions where annual bluegrass can dominate golf greens. Less common and more easily controlled in bentgrass if quickly diagnosed.",
        "grasses": ["bentgrass", "poa"]
    },
    "bentgrass_dead_spot": {
        "name": "Bentgrass Dead Spot",
        "causal_agent": "Ophiosphaerella agrostis",
        "susceptible": "Creeping bentgrass; Hybrid bermudagrass",
        "symptoms": "Disease appears initially as small, reddish-brown, tan or copper-colored spots 0.5\" to 1\" in diameter, which mimic ball marks. Spots enlarge to only 3\" in diameter and have tan centers and reddish-brown leaves on the outer periphery of sunken spots. Bentgrass Dead Spots can be numerous and severely pit greens. Bentgrass Dead Spots can be misdiagnosed in new greens as ball marks, dollar spot or Microdochium patch.",
        "conditions": "Bentgrass Dead Spots are mostly a problem in new greens during the first to third summer following construction or via renovation by fumigation or new sand. They are most severe in open, sloped and sunny locations during hot and dry weather. Under ideal conditions, they hit fast and hundreds of Bentgrass Dead Spots may develop in a few days. The disease is not known to occur in turf grown on native soils. Bentgrass Dead Spots naturally decline and are seldom seen in greens older than six years.",
        "management": "Irrigate new greens judiciously with close attention to syringing and hand-watering during hot and dry periods. Apply small amounts of nitrogen (approximately 0.1 to 0.2 lb N/1,000 ft2) every 7-10 days to stimulate recovery from surrounding healthy plants. Fungicides often are applied curatively given the rarity of this disease. Curatively, apply a tank-mix of an appropriate contact fungicide and a systemic fungicide and use follow-up sprays every 7-10 days until the disease is arrested.",
        "regions": "Potentially a problem in all new creeping bentgrass and hybrid bermudagrass greens after constructions and renovations.",
        "grasses": ["bentgrass", "bermuda"]
    },
    "blue_green_algae": {
        "name": "Blue-Green Algae",
        "causal_agent": "Nostoc sp. and other species of blue-green algae, also known as cyanobacteria",
        "susceptible": "Affects all turfgrass",
        "symptoms": "From a standing position on overcast days, turf has a splotchy blackened appearance. The blackening is caused by massive growth of algal filaments. Filaments have a mucus-like coating that develop into scums on thatch surfaces. Scums can seal surfaces causing oxygen deprivation and other problems.",
        "conditions": "Blue-green algae are primitive plants that become highly invasive during extended warm, overcast and rainy periods in summer and fall. These algae are most common in shaded, low-lying, poorly drained, compacted or otherwise wet environments. Completely open, well-drained sites can be affected when rainy and overcast weather becomes prolonged. Scums can develop where water puddles in higher cut turfs that have poor density. Algal blackening also can occur during mild, overcast winter periods in some regions.",
        "management": "Increase mowing height and nitrogen fertility. Improve surface water drainage. Core, spike and/or vertical cut to reduce thatch, break-up scums and improve soil aeration. Remove or trim trees and shrubs to increase air movement and sunlight penetration in chronically affected turfs. Where chronic on greens, apply an effective algae-targeted fungicide (e.g., chlorothalonil) prior to a forecast of extended overcast and rainy weather in summer. Frequent use of some DMI/SI fungicides can promote blue-green algal blooms on greens.",
        "regions": "All regions that experience extended warm, overcast and rainy periods in summer and fall.",
        "grasses": ["bentgrass", "bluegrass", "bermuda"]
    },
    "brown_ring_patch": {
        "name": "Brown Ring Patch (Waitea Patch)",
        "causal_agent": "Waitea circinata var. circinata",
        "susceptible": "Annual bluegrass",
        "symptoms": "The name brown ring patch is a misnomer, as the symptoms more closely resemble yellow patch. This disease is often referred to as Waitea patch for this reason. The disease mostly appears as solitary or clusters of yellow rings, a few inches to a foot or more in diameter. Grass in the center of rings often appears darker green. Aerial mycelium rarely appears in the field, but is easily induced in the lab. Symptoms are similar to yellow patch, which occurs during colder weather. While infected leaves die, turf usually recovers with the advent of sunny and dry weather.",
        "conditions": "Mild to warm temperatures (60F-75F), overcast and rainy periods in late spring promote this disease.",
        "management": "Affected turf normally recovers with the advent of sunny and dry weather. Small amounts of water-soluble nitrogen (approximately 0.25 lb N/1,000 ft2) promote recovery. Rings may become numerous and objectionable and thus an application of an appropriate fungicide may be warranted.",
        "regions": "In all regions where annual bluegrass can dominate golf greens, especially mid-Atlantic, southern California and transition areas.",
        "grasses": ["poa"]
    },
    "fairy_ring": {
        "name": "Fairy Ring",
        "causal_agent": "Agaricus campestris; Lepiota spp.; Lycoperdon spp; Marasmius oreades",
        "susceptible": "Cool-season turfgrass; Warm-season turfgrass",
        "symptoms": "There are three types of fairy ring: Type 3 is a simple ring or crescent of mushrooms; Type 2 has a ring of mushrooms and a green stimulation zone; Type 1 (most important) causes dead zones. Type 1 fairy ring appears in discrete circular rings, crescents and arcs in which edges initially display the blue-gray color of wilt. The reason for the wilt symptom is due to the fungal body (mycelium), which renders soil hydrophobic (repels water penetration). Hence, turf dies mainly from drought stress. As rings become more pronounced, the inner and outer zones of wilted or dead areas are darker green, especially in higher cut turf. On golf greens, distinct green zones are not always present, but some green stimulation usually is noted on peripheries of rings. The inner and outer green dynamic of rings is due to nitrogen release via organic matter degradation activity by the fungus and other microbes. During rainy periods, mushrooms or puffballs often appear in or adjacent to the dying or dead areas. Affected thatch usually has a light brown to orange color and infested thatch/soil typically has a strong mushroom odor.",
        "conditions": "Fairy rings typically appear in early-mid summer, but sometimes develop during mild, late-fall or winter periods. Heavy spring rains are especially conducive to their development. As summer progresses, symptoms and damage become more pronounced in response to heat and/or drought stress. The mechanism of damage is mostly due to the ability of these fungi to render soil hydrophobic; not parasitism.",
        "management": "Reduce thatch by vertical cutting and coring in the fall and/or spring. When wilt symptoms become evident, core or otherwise poke holes and flush a soil wetting agent to help alleviate hydrophobic soil conditions. Small amount of nitrogen or iron may help to mask some rings. On chronically affected greens, collars and approaches, preventively apply an effective fungicide in early spring in combination with a soil wetting agent. Repeat applications on a 28-day interval when soil temperatures are > 60F are recommended to provide season-long control.",
        "regions": "Fairy ring occurs worldwide in all turfgrasses.",
        "grasses": ["bentgrass", "bluegrass", "bermuda", "zoysia", "fescue", "ryegrass"]
    },
    "gray_leaf_spot": {
        "name": "Gray Leaf Spot",
        "causal_agent": "Pyricularia grisea",
        "susceptible": "Perennial ryegrass; Tall fescue; Kikuyugrass; St. Augustinegrass",
        "symptoms": "Symptoms of gray leaf spot vary depending on species. In perennial ryegrass and tall fescue, symptoms first appear as gray lesions on margins of leaves. Lesions may have a yellow halo and grayish leaf tips that are often twisted. Numerous, small, dark-brown lesions may also be present. In early morning hours, infected leaves may have a purple felted appearance, which is due to the production of enormous numbers of spores. Severely infected stands develop a grayish, drought-like appearance and collapse rapidly. Under less severe conditions, turf will appear yellow and thin. In warm-season grasses, gray leaf spot appears as small, brown spots on leaves. Lesions enlarge and become oval to oblong with purple or brown borders up to 0.5\" in length. Lesions may have a yellow halo and appear felted. The disease is mostly debilitating in St. Augustinegrass, but can cause severe damage to kikuyugrass.",
        "conditions": "Gray leaf spot can occur anytime between mid-summer and late autumn. The disease is favored by extended periods of heat and drought stress in late summer, but may develop in perennial ryegrass under colder conditions in late fall.",
        "management": "Avoid medium to high nitrogen levels during mid-summer. When active, mow when the canopy is dry and try to remove clippings. Maintain adequate soil moisture and avoid excessive irrigation. Do not use herbicides or plant growth regulators when the disease is active. Renovate damaged stands with species and/or cultivars with resistance. Where chronic, use appropriate systemic fungicides on a preventive basis.",
        "regions": "Wherever susceptible species are grown; especially mid-Atlantic and transition regions for cool-season grasses, and gulf coast and southwestern regions for warm-season grasses.",
        "grasses": ["ryegrass", "fescue"]
    },
    "large_patch": {
        "name": "Large Patch",
        "causal_agent": "Rhizoctonia solani",
        "susceptible": "Zoysiagrass; St. Augustinegrass; Centipedegrass; Kikuyugrass; Seashore paspalum",
        "symptoms": "Symptoms of large patch vary depending on turf species and cultivar. Large patch was first described as a zoysiagrass disease, but all warm-season grasses can be affected. The pathogen attacks basal leaf sheaths causing small, reddish-brown or black lesions. As the disease progresses, rings and patches of blighted turfgrass measuring 5\" to 10' or greater in diameter can develop. Patches are reddish-brown to yellow in appearance, with a possible orange firing at patch periphery. Damaged leaves detach easily from stems. During winter, blighted patches and rings contrast with healthy dormant turf. At spring green-up, some new leaves may emerge from surviving crowns, but extensive damage can result in little or no recovery. In bermudagrass, enormous patches may appear just after spring green-up. In bermudagrass, leaves are blighted, but usually there is no significant damage to stem bases and plants recover as temperatures rise.",
        "conditions": "The disease is prominent in the fall and spring as warm-season grasses are transitioning into and out of dormancy. This disease is favored by high relative humidity, cool/cold temperatures and extended periods of overcast and rainy weather. Large patch is most severe in shady and/or poorly drained sites. Some fine-textured cultivars of zoysiagrass are highly susceptible.",
        "management": "Zoysiagrass requires only very modest amounts of nitrogen in summer; avoid nitrogen in the fall. In spring, do not apply any nitrogen until the disease becomes inactive. Vertical cutting affected zoysiagrass after 100% green-up and spoon-feeding (approximately 0.25 lb N/1,000 ft2) helps speed recovery. Severely damaged areas may have to be sodded. In bermudagrass, recovery is rapid following the application of a water-soluble nitrogen source. Promote sunlight and air circulation, and improve surface water drainage. Avoid overwatering. Reduce thatch. Where common, apply an effective systemic fungicide preventively. Two applications in fall and one application in spring are recommended in most cases.",
        "regions": "Mostly transition areas where zoysiagrass is commonly grown. Kikuyugrass in southern California and St. Augustinegrass, centipedegrass, and seashore paspalum in the Southeast.",
        "grasses": ["zoysia", "bermuda", "paspalum"]
    },
    "leaf_spot_melting_out": {
        "name": "Leaf Spot / Melting-Out / Net-Blotch",
        "causal_agent": "Drechslera spp. and Bipolaris spp.",
        "susceptible": "Creeping red fescue; Kentucky bluegrass; Perennial ryegrass; Tall fescue; Creeping bentgrass; Bermudagrass",
        "symptoms": "Leaf spot causes reddish-brown or purplish-brown lesions, which may be oblong to irregular in shape. Lesions may have a tan center. In perennial ryegrass and tall fescue, lesions develop in the form of numerous brown specks or larger dark-brown oblong or purplish oblong lesions (net-blotch). Older, lower leaves of infected plants become shriveled. When infection is severe, almost all of the leaves and sometimes tillers die, causing severe browning and thinning of the stand - or melting-out. Most cases of leaf spot and net-blotch occur during extended periods of chilly, rainy and overcast weather in spring. Red leaf spot is an uncommon disease of some creeping bentgrass cultivars during mild summer periods, and as the name implies, lesions are red.",
        "conditions": "Diseases caused by Drechslera spp. are most common in the spring and fall when weather conditions are chilly, rainy and overcast for long periods. Conversely, most Bipolaris spp. infect during warm-to-hot periods and when there are frequent cycles of wet and dry weather. On bermudagrasses, Bipolaris cynodontis and other species are encouraged by cool, cloudy and wet weather in fall through spring.",
        "management": "Increase height of cut. Avoid the application of high rates of water-soluble nitrogen in spring. Reduce thatch and minimize shade. Do not apply broadleaf weed herbicides or growth regulators when any of these diseases are active. Apply an appropriate fungicide at the first indication turf is going-off color and numerous lesions are present.",
        "regions": "All areas where cool-season grasses are grown, especially cool and humid regions.",
        "grasses": ["fescue", "bluegrass", "ryegrass", "bentgrass", "bermuda"]
    },
    "microdochium_patch": {
        "name": "Microdochium Patch (Pink Snow Mold / Fusarium Patch)",
        "causal_agent": "Microdochium nivale",
        "susceptible": "Cool-season turfgrass",
        "symptoms": "Microdochium patch occurs anytime from late fall to early spring whenever conditions are overcast, cold and wet, and at snow melt. In the absence of snow (Fusarium patch phase), circular, reddish-brown, pink or tan spots 1-3\" in diameter develop and grayish smoke rings (foliar mycelium) may be evident. In immature turf, patches may exceed 1' in diameter. In the presence of melting snow (pink snow mold phase), distinct circular patches develop, which usually have tan centers and pinkish-red fringes. Patches become larger under snow and range from 6\" to 2' in diameter.",
        "conditions": "Microdochium patch can occur whenever temperatures range from 32F to 60F, but chilly, wet and overcast weather are required in the absence of snow. The snow-free phase can appear from late fall to late spring, and can severely damage immature, fall seeded stands. The snow phase is more severe when snow cover exceeds 10 days. Leaves are blighted and recovery often occurs, but when snow persists for long periods significant damage can occur.",
        "management": "Mow turf regularly throughout fall until dormancy. Check seedling turf frequently, especially when blankets are used. Avoid heavy applications of water-soluble nitrogen sources in late fall prior to dormancy. In spring, apply small amounts of nitrogen frequently to promote recovery. Where common, apply a tank-mix of an effective contact fungicide plus a systemic fungicide prior to snow cover, and again in mid-to-late winter if additional snow is likely.",
        "regions": "Throughout cool-humid, mountain, and transition regions in cool-season grasses where snowy or extended periods of chilly, wet and overcast weather are common. Is a major winter disease of seashore paspalum in Southeastern U.S.",
        "grasses": ["bentgrass", "bluegrass", "ryegrass", "fescue", "paspalum"]
    },
    "mini_ring": {
        "name": "Mini-Ring / Leaf and Sheath Spot",
        "causal_agent": "Rhizoctonia zeae",
        "susceptible": "Bermudagrass; Seashore paspalum",
        "symptoms": "Symptoms appear in mid- to late-summer and intensify as bermudagrass growth slows due to short day lengths and cool temperatures. Rings are 4 to 18 inches in diameter and typically scalloped or irregularly shaped. Infected turf may initially show signs of drought stress, nutrient deficiency or poor growth before turning tan to orange in color. No distinct foliar or stem lesions are visible as infections are limited to the crown, stolons and roots.",
        "conditions": "Infections occur in late spring through summer when soil temperatures are above 70F. Slowly growing bermudagrass is most prone to damage, particularly from low fertility or drought stress. Fertilizing with urea nitrogen has been shown to suppress mini ring development, whereas ammonium sulfate can increase disease severity.",
        "management": "Provide adequate and balanced fertility based on soil and tissue test results. Fertilize with urea nitrogen at 0.1 to 0.2 lbs N per 1,000 ft2 per week when R. zeae is active. Apply preventive fungicides on a 14- to 21-day interval from late spring through summer. Systemic fungicides should be watered-in to deliver to the crown and root zone where the pathogen is most active.",
        "regions": "Transition zone and south where bermudagrass and seashore paspalum are grown on putting greens.",
        "grasses": ["bermuda", "paspalum"]
    },
    "necrotic_ring_spot": {
        "name": "Necrotic Ring Spot",
        "causal_agent": "Ophiosphaerella korrae",
        "susceptible": "Creeping red fescue; Kentucky bluegrass",
        "symptoms": "Necrotic ring spot (NRS) first appears as small, light-green spots and progresses to thinned, circular patches approximately 3\" to 15\" in diameter. Patches can expand up to 3' in diameter; eventually turn brown or straw-colored. The frog-eye symptom of living grass within a ring may be prominent, but arcs and rings can be diffuse, especially in red fescue. Disease is severe in shaded and sunny areas in bluegrass, but mostly restricted to shade for red fescue. The pathogen attacks roots and rhizomes, and there are no distinctive leaf lesions or foliar mycelium. Roots of infected plants turn brown to black.",
        "conditions": "Necrotic ring spot typically develops in moist areas in spring, but may not become apparent until heat and drought stresses place a lethal stress on infected roots in the summer. Seeded, as well as sodded sites, in newly cleared woodlands/sub-divisions are most susceptible, but older stands also are prone to damage, especially red fescue. Compacted soil, shade, high soil pH and high nitrogen fertility promote the disease.",
        "management": "Minimize shade. Raise mowing height. Reduce soil compaction through core aeration. Maintain adequate nitrogen and balanced phosphorous and potassium fertility. Avoid drought stress. Reduce thatch. Overseed with resistant cultivars or immune species (e.g., perennial ryegrass, and hard or tall fescue) where appropriate. Apply a proper systemic fungicide in late fall on a preventive basis where the disease is chronic.",
        "regions": "Mostly Rocky Mountain states and Pacific Northwest; less common in the Northeast and Midwest; and uncommon in the Mid-Atlantic and transition areas.",
        "grasses": ["fescue", "bluegrass"]
    },
    "powdery_mildew": {
        "name": "Powdery Mildew",
        "causal_agent": "Blumeria graminis",
        "susceptible": "Kentucky bluegrass; Creeping red fescue",
        "symptoms": "The pathogen is an obligate parasite that can only survive and reproduce within living tissues. Powdery mildew first appears on leaf surfaces as a coating of fine, white mycelium bearing chains of spores. Affected areas appear to have been dusted with lime. Severely infected leaves turn yellow, then tan or brown in color. Infected turf in shaded areas often loses density. Highly susceptible cultivars may be severely damaged in shade.",
        "conditions": "Powdery mildew is mostly a disease of shaded turf and where air circulation is poor. The disease is favored by humid, cloudy weather with air temperatures between 60F and 72F. It can appear at any time from spring to fall, but is most common in the fall.",
        "management": "Prune tree limbs and eliminate brush to improve air circulation and improve sunlight penetration. Shaded turf requires half of the nitrogen versus full sun turf. Avoid high levels of nitrogen and irrigation that produce lush growth. Increase mowing height. Convert to shade-adapted cultivars or resistant grasses like tall fescue and hard fescue where appropriate. Normally, a single application of an appropriate systemic fungicide is highly effective for controlling the disease.",
        "regions": "Mostly in northern, cool, humid regions where Kentucky bluegrass and creeping red fescue are commonly grown.",
        "grasses": ["bluegrass", "fescue"]
    },
    "pythium_blight": {
        "name": "Pythium Blight",
        "causal_agent": "Pythium aphanidermatum and Pythium spp.",
        "susceptible": "Affects all turfgrass",
        "symptoms": "Pythium blight on cool-season grasses appears suddenly during hot, humid weather, especially following thunderstorms. In contrast, outbreaks on warm-season grasses are most common during periods of cool, cloudy and wet weather. Initially, infected areas appear dark-gray and water-soaked in the early morning. Spots turn orange or bronze-colored, and turf dies in spots about 0.75\" to 2\" in diameter. Spots may increase to > 6\" diameter, coalesce and rapidly blight large areas. Extreme blighting can occur in water drainage patterns. Fluffy, grayish masses of fungal mycelium often are seen in affected areas in the early morning when dew is present. Grayish-black smoke rings may develop at peripheries. Leaves collapse, mat and may have a slimy/soapy feel. Affected plants mat and usually are killed.",
        "conditions": "Pythium blight of cool-season grasses is promoted by night temperatures > 68F and very high humidity. It is most severe following a thunderstorm or heavy rain in summer, especially in wet and shaded areas where water puddles and/or in surface water drainage patterns. Seedlings and immature turfs in wet areas are extremely vulnerable. On ultradwarf bermudagrass putting greens, Pythium blight is common during periods of cool, cloudy, and wet weather in fall, winter and spring.",
        "management": "Improve surface water drainage. Minimize shade and increase air circulation to speed drying of the canopy. Irrigate turf deeply and infrequently early in the day; avoid late-day and night irrigation. Avoid mowing wet turf when foliar mycelium is evident to minimize spread of the pathogen. Minimize nitrogen use during hot and humid weather. Monitor seedlings closely in late summer. Where a common problem, apply an appropriate fungicide preventively when weather conditions are favorable.",
        "regions": "Temperate and humid regions on cool- and warm-season turfgrasses.",
        "grasses": ["bentgrass", "ryegrass", "bluegrass", "bermuda"]
    },
    "pythium_root_dysfunction": {
        "name": "Pythium Root Dysfunction",
        "causal_agent": "Pythium volutum, P. arrhenomanes and P. aristosporum",
        "susceptible": "Creeping bentgrass",
        "symptoms": "Pythium root dysfunction symptoms appear during periods of stress, especially heat, drought, and/or low fertility. Circles or irregular patches are up to two feet in diameter and initially show signs of wilt or nutrient deficiency. As the disease progresses, affected areas turn orange and eventually collapse to the ground. Roots are tan in color and sand falls away from them easily due to lack of root hairs. Reductions in root depth may not be evident during the fall and spring, but infected roots die back rapidly when soil temperatures exceed 85F.",
        "conditions": "Pythium root dysfunction is most common in creeping bentgrass putting greens less than 10 years old. Symptoms are most severe during hot weather in summer, but may also appear during fall, winter, or spring. Root infection occurs in fall to spring when soil temperatures are between 50F and 75F. Above-ground symptoms are usually not apparent at this time except under extreme drought or nutrient deficiency. Root dieback occurs rapidly once soil temperatures exceed 85F. The appearance of symptoms are enhanced by low fertility, drought stress, and low soil oxygen levels.",
        "management": "Provide adequate fertility based on soil and tissue tests; newly constructed creeping bentgrass greens should receive 4 to 6 lbs N/1,000 ft2 annually. Raise mowing heights above 0.125 in. during summer to alleviate stress. Avoid severe drought stress and apply soil surfactants on prescribed intervals. Employ hollow-tine aerification and topdressing in fall and spring followed by solid-tine aerification or venting in the summer to improve root survival. Apply effective fungicides in the fall and spring on a 21- to 28-day interval when soil temperatures are between 50F and 75F.",
        "regions": "Most common in the transition zone where creeping bentgrass is marginally adapted; may also occur in northern locations during abnormally hot weather or intense management.",
        "grasses": ["bentgrass"]
    },
    "pythium_root_rot": {
        "name": "Pythium Root Rot",
        "causal_agent": "Pythium spp.",
        "susceptible": "Annual bluegrass; Creeping bentgrass; Bermudagrass",
        "symptoms": "Symptoms of Pythium root rot (PRR) are highly diverse and a lab analysis usually is needed to confirm this disease. In high density bentgrasses, the disease appears as reddish-brown, blue-gray or purplish spots, patches and splotches that mimic wilt. In older bentgrasses, symptoms are non-descript and may appear as yellow, reddish-brown or bronze-colored, irregularly shaped areas of thinning and dying turf. PRR usually is first noted in clean-up areas and/or surface water drainage patterns where mowing stress is greatest. Pathogen activity is limited to roots and stems and there is no foliar mycelium.",
        "conditions": "At least 30 Pythium species are known to infect turfgrass roots, and as a group they infect across a wide range of soil temperatures. Wet soil conditions are the primary contributing factor, whether from frequent rainfall, over-irrigation, or poor soil drainage. Stress from heat, low mowing, traffic, and shade often trigger expression of symptoms and increase severity of the disease.",
        "management": "Improve soil drainage and avoid over-irrigation. Reduce mowing frequency, increase height of cut and use lightweight mowers; skip mowing clean-up passes as needed to minimize stress. Cultivate and topdress regularly to increase soil aeration and root growth. Reduce shade and increase air movement to maximize turf health. Where Pythium root rot is a chronic problem, apply preventive fungicides on a 14- to 21-day interval when soil temperatures are above 65F.",
        "regions": "All humid climates where annual bluegrass, creeping bentgrass, or bermudagrass are grown on putting greens.",
        "grasses": ["poa", "bentgrass", "bermuda"]
    },
    "red_thread": {
        "name": "Red Thread",
        "causal_agent": "Laetisaria fuciformis",
        "susceptible": "Creeping red fescue; Perennial ryegrass; Tall fescue",
        "symptoms": "Red thread blights in distinct spots or circular patches, which appear pink or reddish-colored and range from 2\" to 3' in diameter. When active in the presence of dew or even melting snow, a bright pink to red gelatinous fungal growth can be observed on leaves and sheaths. Resting bodies (sclerotia) called red threads are invariably present. Red threads initially are gelatinous, but soon become bright red, hard and brittle. Blighted leaves eventually turn tan, but on close inspection red threads can be seen embedded in dead tissues. White to pink cotton candy-like fungal flocks occasionally develop within blighted canopies.",
        "conditions": "Red thread can develop almost any time of the year including at snow melt and in summer, but is most common during extended, overcast and rainy weather in spring. While red thread is widely reported to be most severe in poorly nourished turf, it can severely blight professionally managed turf fertilized with more than adequate nitrogen. Red thread can cause severe thinning and promote weed invasion, but turf normally recovers with adequate nitrogen fertilization.",
        "management": "Maintain proper nitrogen and potassium fertility. Apply small amounts (approximately 0.25-0.5 lbs N/1,000 ft2) of water-soluble nitrogen to blighted areas to promote recovery. Blighting often reduces density when crabgrass and other weeds are germinating in spring and a preemergence herbicide should be used where the disease is common. Increase air circulation, improve water drainage and reduce shade. Preventive fungicide applications during cool, wet weather are highly effective.",
        "regions": "In all areas where susceptible cool-season grasses are grown.",
        "grasses": ["fescue", "ryegrass"]
    },
    "rust": {
        "name": "Rusts",
        "causal_agent": "Crown - Puccinia coronata; Leaf - Puccinia reconditia; Stem - Puccinia graminis; Stripe - Puccinia striiformis",
        "susceptible": "Kentucky bluegrass; Perennial ryegrass; Zoysiagrass",
        "symptoms": "Rusts are obligate parasites that survive and reproduce only within living tissues. Rusts become noticeable only when spores are produced. These pathogens cause light yellow flecks to form on leaves and sheaths. Yellow flecks enlarge and elongate. Mycelial masses formed within leaves rise and rupture the epidermis releasing spores that are yellow, orange, reddish-orange and rarely black. Severely infected stands lose density and appear yellow, orange or reddish-brown from a distance. Spores are so abundant that they can coat shoes with a yellow or rust dust of spores.",
        "conditions": "Rust diseases typically develop during cool and moist periods in fall, and sometimes spring. Rusts develop mostly in wet and shaded environments, but also affects open locations if weather conditions are overcast for long periods. Rust infections are most severe in slow-growing turfgrasses maintained under low nitrogen or where turf was stressed by heat and drought in summer. Although properly fertilized, highly susceptible cultivars can be severely damaged, even in full sun locations.",
        "management": "Convert to a species or cultivars that are resistant. Apply adequate levels of nitrogen. Reduce shade and improve air circulation. Reduce thatch and avoid drought stress. Normally, a single application of an appropriate fungicide is highly effective in controlling the disease.",
        "regions": "All states where susceptible species are grown; especially the Northeast, upper Midwest and Pacific Northwest.",
        "grasses": ["bluegrass", "ryegrass", "zoysia"]
    },
    "smuts": {
        "name": "Smuts (Stripe Smut / Flag Smut)",
        "causal_agent": "Stripe: Ustilago striiformis; Flag: Ustilago agropyri",
        "susceptible": "Kentucky bluegrass",
        "symptoms": "Smuts are obligate parasites that live and reproduce only within living tissues; they become noticeable only when spores are produced. Flag smut is less common, but both smut diseases produce identical symptoms. Initially, symptomatic plants appear stunted and yellow-green. Spore bearing bodies (sori) are produced below the epidermis, and as they mature, narrow, silvery-gray to black, elongated streaks of sori appear in parallel lines along leaf surfaces. As sori mature, they split the epidermis, shed their black spores, and leaves twist and shred. Infected stands lose density and generally appear drought stressed and/or in need of nitrogen.",
        "conditions": "Smut diseases develop during periods of overcast and wet weather in spring and fall, but are most prominent in spring.",
        "management": "Smuts are uncommon today since most improved Kentucky bluegrass cultivars are resistant. If smuts are a chronic problem, convert to a resistant bluegrass cultivar or to another appropriate species. Infected stands should be irrigated to avoid drought stress and fertilized appropriately to offset damage and promote recovery. A single application of an appropriate systemic fungicide normally is highly effective in controlling the disease.",
        "regions": "Mostly where older cultivars of Kentucky bluegrass are grown. Inexpensive seed mixes can contain highly susceptible cultivars.",
        "grasses": ["bluegrass"]
    },
    "southern_blight": {
        "name": "Southern Blight",
        "causal_agent": "Sclerotium rolfsii",
        "susceptible": "Creeping bentgrass; Annual bluegrass; Kentucky bluegrass; Bermudagrass",
        "symptoms": "Symptoms appear suddenly as small, circular, yellow, orange or reddish-brown circular patches; frog-eyes and crescents also are common. Patches increase rapidly in size and range from 6\" to 3' in diameter. During early morning hours when foliage is wet, a grayish-white mycelium may be seen, especially at the edges of patches. Numerous reddish to mustard-brown resting bodies (similar to sulfur coated urea granules) called sclerotia often are produced on thatch or soil in blighted areas. Turf is killed or severely damaged in a relatively short period of time.",
        "conditions": "Southern blight is promoted by very warm-to-hot nights, and extremely humid weather. High soil moisture and dense thatch layers promote the disease. In southern California, the disease can appear as early as May and continue throughout the summer.",
        "management": "Reduce thatch by coring and vertical cutting. Avoid excessively wet soil and thatch conditions. Use a soil acidifying fertilizer (e.g., ammonium sulfate and SCU) as the primary nitrogen source where the disease is common. Apply an appropriate systemic fungicide preventively where the disease has been a problem in the past. Curatively, tank-mix an effective contact fungicide and a systemic fungicide. Repeat applications may be necessary until the disease has been arrested.",
        "regions": "Mostly southeast and southwest, especially southern California; sometimes in transition zone areas.",
        "grasses": ["bentgrass", "poa", "bluegrass", "bermuda"]
    },
    "spring_dead_spot": {
        "name": "Spring Dead Spot",
        "causal_agent": "Ophiosphaerella korrae, Ophiosphaerella herpotricha and Ophiosphaerella narmari",
        "susceptible": "Bermudagrass; Zoysiagrass; Buffalograss",
        "symptoms": "Infected turf shows disease symptoms as they emerge from winter dormancy. SDS appears as bleached, straw-colored, circular patches that measure from 6\" to several feet in diameter. Roots of affected plants shorten and turn dark-brown to black. Sometimes there is living grass in the center of patches (frog-eye symptom). Patches may be solitary or numerous and widespread.",
        "conditions": "SDS pathogens are favored by cool, wet weather in the fall when soil temperatures are below 70F, followed by a cold winter. Significant levels of SDS may follow a mild winter, especially in highly susceptible cultivars. This disease is typically found where thatch is more than 0.5\" thick and in exposed locations. Heavy applications of nitrogen in late summer or fall increase disease severity. SDS is more severe in bermudagrass that is over three years old and in locations with long winter dormancy periods.",
        "management": "Avoid high amounts of late-summer or fall applications of nitrogen fertilizers. Modest amounts of nitrogen (less than 0.75 lb N/1,000 ft2) in late summer do not appear to enhance the disease. Potassium should also be applied in the fall where the disease is chronic to boost winter hardiness. Apply ammonium sulfate or other acidifying nitrogen sources combined with potassium at spring green-up and thereafter until full recovery has been achieved. It is very important to control competing weeds in affected turf to enhance recovery of patches. Improve drainage and reduce thatch. Use hybrid bermudagrass cultivars with good winter hardiness. Apply preventive fungicides in the fall when soil temperatures are below 70F. Two applications on a 28-day interval are recommended in most cases.",
        "regions": "SDS occurs in bermudagrass where winter dormancy occurs. SDS is more severe in regions where winters are cold and there is a long dormancy period.",
        "grasses": ["bermuda", "zoysia"]
    },
    "summer_patch": {
        "name": "Summer Patch",
        "causal_agent": "Magnaporthiopsis poae",
        "susceptible": "Annual bluegrass; Creeping red fescue; Kentucky bluegrass; Creeping bentgrass",
        "symptoms": "In Kentucky bluegrass, patches initially appear as slow-growing, thinned or wilted turfgrass. Tips of leaves are bleached-white (and can mimic dollar spot), and eventually spots/patches grow and turn yellow or straw-colored. As disease progresses, affected areas appear as circular or irregularly shaped patches that measure from several inches to 18\" in diameter. Active patches are bronze-colored at periphery, then turn straw or tan-colored. Patches may become sunken and coalesce as they increase in size. Symptoms may exhibit a distinct ring frog-eye appearance. In annual bluegrass on greens, yellow rings, ribbons, or spots may appear. In severe cases, infected areas are typically reddish-brown or bronze and creeping bentgrass is unaffected. Where there is a good mix with bentgrass, the disease begins at the interface between species. Creeping bentgrass is susceptible to summer patch in the transition zone, particularly in high pH soils or where nematode populations are high.",
        "conditions": "Root infection is initiated when soil temperatures exceed 65F; however, foliar symptoms are favored by day air temperatures over 85F and nights over 70F. Symptoms become noticeable during periods of summer heat and usually in areas of mostly full sun; the disease is far less common in shaded areas. Slopes and low areas prone to flooding are especially vulnerable. In greens, it is commonly found in areas that are sunny, exposed, and wet. Compacted areas and soil pH > 6.8 favor the disease.",
        "management": "Use acidifying nitrogen fertilizers at appropriate times of year. Spoon-feed greens after disease subsides to promote bentgrass growth into damaged areas. Increase height of cut. Use lightweight equipment on affected greens. Avoid light and frequent irrigation; excessively wet soils favor the disease. Improve water drainage and air circulation. Convert to resistant species, such as tall fescue, bentgrass, or perennial ryegrass where appropriate. Preventively apply on a 21-28 day interval beginning in late-spring (mid-May most regions) until early August. Application timing coincides with 65F soil temperatures for three consecutive days at a 2\" depth.",
        "regions": "Wherever Kentucky and annual bluegrass, and creeping red fescue are grown, but is most common in transition zone regions. May occur in creeping bentgrass greens in southern areas.",
        "grasses": ["poa", "fescue", "bluegrass", "bentgrass"]
    },
    "take_all_patch": {
        "name": "Take-All Patch",
        "causal_agent": "Gaeumannomyces graminis var. avenae",
        "susceptible": "Colonial bentgrass; Creeping bentgrass",
        "symptoms": "Take-all patch symptoms initially appear as small, circular reddish-brown spots. While infection of roots occurs during cool, wet weather in spring or fall, symptoms are most evident during periods of heat stress in rapidly drying soils due to dysfunction of infected roots. Symptoms progress to wilted (especially noted early a.m. in dew patterns), circular patches that are blue-gray, red-brown or bronze-colored. Patches can measure up to several feet in diameter. As bentgrass ages, or in less severe cases, patches often appear yellow (take-all decline).",
        "conditions": "Root infection typically begins during cool and wet weather between fall and spring and in areas with a root zone soil pH > 6.5. Take-all is most common in new sand-based rootzone constructions or where woodlands have been recently cleared. The disease typically appears in the second year following establishment. Severity normally decreases as bentgrass matures over a 2 to 5 year period, but in rare cases it can remain a chronic problem. Take-all can recur sporadically on much older sites when there is abnormally high rainfall in late winter and spring.",
        "management": "Ammonium sulfate used in conjunction with manganese sulfate has been shown to reduce take-all severity. Improve water drainage. Reduce thatch. In chronically severe cases, acidification of irrigation water may be necessary. Apply a proper systemic fungicide preventively twice in the fall with a follow-up application in early spring after the first mowing until decline is complete.",
        "regions": "Take-all occurs wherever bentgrasses are grown, but is most common in the Northeast, mid-Atlantic, Midwest, and Pacific Northwest.",
        "grasses": ["bentgrass"]
    },
    "take_all_root_rot": {
        "name": "Take-All Root Rot",
        "causal_agent": "Gaeumannomyces graminis var. graminis",
        "susceptible": "Bermudagrass; St. Augustinegrass; Seashore paspalum; Kikuyugrass",
        "symptoms": "Symptoms appear in patches or rings up to several feet in diameter. Patches may coalesce to form large irregularly shaped areas, especially where turf is stressed from traffic, poor drainage, or shade. Affected turf initially shows symptoms of reduced growth, chlorosis, or leaf dieback. As the turf continues to decline it may turn tan, yellow or orange before collapsing and dying. Roots, stolons, and/or rhizomes are sparse and noticeably rotten in affected areas.",
        "conditions": "The take-all root rot pathogen grows across a wide range of soil temperatures, but most infection likely occurs when the turf is weak or stressed. Low light levels combined with cool temperatures or extended periods of wet weather are the most common triggers. The disease is most severe in poorly drained areas and where soil pH is greater than 7.0. Stress from low mowing, inadequate fertility, excessive traffic, or shade cause the turf to be more susceptible. High populations of plant-parasitic nematodes also contribute to take-all root rot development.",
        "management": "Maintain soil pH below 7; most turfgrasses perform best when soil pH is between 6 and 6.5. Avoid lime applications unless directed by soil test results. Reduce turf stress by increasing mowing height, providing adequate fertility, and minimizing mechanical wear. Implement a nematicide program if populations are at damaging levels. Cultivate regularly to increase soil aeration and root growth. Improve soil drainage and avoid over-irrigation. Make preventive fungicide applications on a 14- to 28-day interval when conditions are conducive to development.",
        "regions": "On golf course putting greens, take-all root rot occurs throughout the transition zone and south. Limited to the Deep South on higher-cut turfgrasses, especially coastal areas where soil pH is high.",
        "grasses": ["bermuda", "paspalum"]
    },
    "yellow_patch": {
        "name": "Yellow Patch",
        "causal_agent": "Rhizoctonia cerealis",
        "susceptible": "Annual bluegrass; Creeping bentgrass",
        "symptoms": "The most common symptom of yellow patch is the appearance of yellow rings a few inches to over a foot in diameter. Rings may be solitary or numerous. Less commonly, solid yellow patches or reddish-brown rings develop. Reddish-brown rings are more common in bentgrass and may loop together like those on the Olympic flag. There are no distinctive leaf lesions and foliar mycelium seldom develop. Damage usually is superficial and affected plants normally recover with the advent of sunny and dry weather. This disease is very similar in appearance to Waitea patch (aka brown ring patch); which occurs during warm and rainy periods in mid-to-late spring.",
        "conditions": "Yellow patch occurs from fall to spring during extended overcast, rainy and chilly (50 to 65F) weather. The disease is most severe when thatch is cold and wet for long periods.",
        "management": "Improve soil and surface water drainage. Reduce shade and increase air circulation. Apply small amounts of nitrogen (approximately 0.25 lb N/1,000 ft2) to promote recovery when turf begins growth in spring. Use a proper fungicide preventively in late fall/early spring where yellow patch is a chronic problem. Curatively, apply a proper contact fungicide plus a systemic fungicide, but recovery depends on sunny and dry conditions.",
        "regions": "In all cool-humid and transition regions. Also in rough bluegrass in southern areas.",
        "grasses": ["poa", "bentgrass"]
    },
    "yellow_tuft": {
        "name": "Yellow Tuft (Downy Mildew)",
        "causal_agent": "Sclerophthora macrospora",
        "susceptible": "Affects all turfgrass",
        "symptoms": "Yellow tuft is most notable in annual bluegrass and bentgrass golf greens and seldom fatal. The pathogen is an obligate parasite that survives and reproduces only in living tissues. Infection occurs during cool and wet weather in spring and fall, and is most severe in low and wet areas. The disease becomes evident during prolonged periods of overcast weather at almost any time of year, especially late fall, winter and spring. In summer, infected plants normally appear healthy. Symptoms appear as yellow spots of tufted plants 0.25\" to 1\" in diameter. Leaves and tillers are yellow and clustered due to an abnormal, fungal-induced proliferation of tillers. Tufts are easily detached from turf, exposing clusters of short, stubby roots. Yellow tuft mimics annual bluegrass invasion in bentgrass greens in winter. In St. Augustinegrass, the disease appears as white streaks parallel to the leaf veins, primarily during humid summer weather in wet and shaded areas. There is no tufting.",
        "conditions": "Yellow tuft mostly occurs in wet, poorly drained areas that are depressed, but infected plants can be found on slopes and other well-drained areas. This sophisticated pathogen produces swimming spores that infect seedlings and stem buds during rainy periods in spring and fall.",
        "management": "Improve surface water drainage. Increase air circulation. On greens, tufts are effectively detached via vertical cutting. Apply appropriate fungicides labeled for yellow tuft control.",
        "regions": "Common in New England and the Pacific Northwest in all cool-season grasses and mostly bentgrass and annual bluegrass greens elsewhere. Seldom in zoysiagrass. In St. Augustinegrass, the disease is mostly found in the Gulf Coast region.",
        "grasses": ["bentgrass", "poa", "bluegrass"]
    }
}


def clean_text(text):
    """Clean text for embedding."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'http[s]?://\S+', '', text)
    return text.strip()


def build_disease_document(key, disease):
    """Build a clean disease document for embedding - no brand product names."""
    parts = [
        f"Disease: {disease['name']}",
        f"Causal Agent: {disease['causal_agent']}",
        f"Susceptible Turfgrasses: {disease['susceptible']}",
        f"Symptoms: {disease['symptoms']}",
        f"Conditions Favoring Disease: {disease['conditions']}",
        f"Management Tips: {disease['management']}",
        f"Frequently Occurs In: {disease['regions']}"
    ]
    return "\n\n".join(parts)


def smart_chunk(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks at sentence boundaries."""
    if len(text) < chunk_size:
        return [text] if len(text) > MIN_CHUNK_SIZE else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunk = text[start:]
            if len(chunk) > MIN_CHUNK_SIZE:
                chunks.append(chunk)
            break

        search_start = max(start + chunk_size - 100, start)
        search_text = text[search_start:end + 50]
        best_break = -1
        for pattern in ['. ', '.\n', '? ', '! ', '\n\n']:
            idx = search_text.rfind(pattern)
            if idx > best_break:
                best_break = idx
        if best_break > 0:
            end = search_start + best_break + 1

        chunk = text[start:end].strip()
        if len(chunk) > MIN_CHUNK_SIZE:
            chunks.append(chunk)
        start = end - overlap

    return chunks


def embed_texts(client, texts):
    """Embed a batch of texts."""
    try:
        response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return []


def main():
    # Initialize clients
    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("turf-research")

    logger.info(f"Processing {len(DISEASES)} diseases for Pinecone upload...")

    all_vectors = []

    for key, disease in DISEASES.items():
        # Build clean document
        doc_text = build_disease_document(key, disease)
        doc_text = clean_text(doc_text)

        # Chunk it
        chunks = smart_chunk(doc_text)
        if not chunks:
            chunks = [doc_text]  # Small docs stay as single chunk

        logger.info(f"  {disease['name']}: {len(chunks)} chunks ({len(doc_text)} chars)")

        # Build vectors
        base_id = f"greencast-{key}"
        for i, chunk in enumerate(chunks):
            vector_id = f"{base_id}-{i}"
            metadata = {
                'text': chunk,
                'source': f"GreenCast Disease Guide - {disease['name']}",
                'type': 'disease_guide',
                'diseases': disease['name'].lower(),
                'causal_agent': disease['causal_agent'],
            }
            if disease.get('grasses'):
                metadata['grass_types'] = ', '.join(disease['grasses'])

            all_vectors.append({
                'id': vector_id,
                'chunk': chunk,
                'metadata': metadata
            })

    logger.info(f"\nTotal vectors to upload: {len(all_vectors)}")

    # Embed and upsert in batches
    uploaded = 0
    for batch_start in range(0, len(all_vectors), BATCH_SIZE):
        batch = all_vectors[batch_start:batch_start + BATCH_SIZE]
        texts = [v['chunk'] for v in batch]

        embeddings = embed_texts(openai_client, texts)
        if not embeddings:
            logger.error(f"Failed to embed batch starting at {batch_start}")
            continue

        upsert_batch = []
        for v, embedding in zip(batch, embeddings):
            upsert_batch.append({
                'id': v['id'],
                'values': embedding,
                'metadata': v['metadata']
            })

        try:
            index.upsert(vectors=upsert_batch)
            uploaded += len(upsert_batch)
            logger.info(f"  Upserted batch: {uploaded}/{len(all_vectors)} vectors")
        except Exception as e:
            logger.error(f"Upsert error: {e}")

        time.sleep(0.5)  # Rate limiting

    logger.info(f"\nDone! Uploaded {uploaded} vectors for {len(DISEASES)} diseases.")


if __name__ == "__main__":
    main()
