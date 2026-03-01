"""
Seed data for the Equipment Manager module.
Contains comprehensive manufacturer/model catalog and standard service intervals
for turfgrass and golf course maintenance equipment.

Usage:
    from equipment_seed_data import MANUFACTURERS, EQUIPMENT_MODELS, SERVICE_INTERVALS
"""

# ---------------------------------------------------------------------------
# Manufacturers
# ---------------------------------------------------------------------------

MANUFACTURERS = [
    {"id": "toro", "name": "Toro", "country": "USA", "website": "https://www.toro.com"},
    {"id": "john_deere", "name": "John Deere", "country": "USA", "website": "https://www.deere.com"},
    {"id": "jacobsen", "name": "Jacobsen (Textron)", "country": "USA", "website": "https://www.jacobsen.com"},
    {"id": "kubota", "name": "Kubota", "country": "Japan", "website": "https://www.kubotausa.com"},
    {"id": "husqvarna", "name": "Husqvarna", "country": "Sweden", "website": "https://www.husqvarna.com"},
    {"id": "stihl", "name": "STIHL", "country": "Germany", "website": "https://www.stihlusa.com"},
    {"id": "honda", "name": "Honda", "country": "Japan", "website": "https://powerequipment.honda.com"},
    {"id": "yamaha", "name": "Yamaha", "country": "Japan", "website": "https://www.yamahagolfcar.com"},
    {"id": "club_car", "name": "Club Car", "country": "USA", "website": "https://www.clubcar.com"},
    {"id": "cushman", "name": "Cushman (Textron)", "country": "USA", "website": "https://cushman.txtsv.com"},
    {"id": "smithco", "name": "Smithco", "country": "USA", "website": "https://smithco.com"},
    {"id": "wiedenmann", "name": "Wiedenmann", "country": "Germany", "website": "https://wiedenmann.com"},
    {"id": "graden", "name": "Graden", "country": "Australia", "website": "https://gradenturfmachinery.com.au"},
    {"id": "progressive", "name": "Progressive Turf Equipment", "country": "Canada", "website": "https://www.progressiveturfequip.com"},
    {"id": "ryan", "name": "Ryan (Bobcat)", "country": "USA", "website": "https://shop.bobcat.com"},
    {"id": "ez_go", "name": "E-Z-GO (Textron)", "country": "USA", "website": "https://ezgo.txtsv.com"},
    {"id": "harper", "name": "Harper Turf", "country": "USA", "website": "https://harperturf.com"},
    {"id": "redexim", "name": "Redexim", "country": "Netherlands", "website": "https://www.redexim.com"},
    {"id": "dakota", "name": "Dakota Peat & Equipment", "country": "USA", "website": "https://www.dakotapeat.com"},
    {"id": "billy_goat", "name": "Billy Goat", "country": "USA", "website": "https://www.billygoat.com"},
    {"id": "echo", "name": "Echo", "country": "Japan", "website": "https://www.echo-usa.com"},
    {"id": "lastec", "name": "Lastec", "country": "USA", "website": "https://www.lastec.com"},
]


# ---------------------------------------------------------------------------
# Equipment Models — organized by manufacturer then by equipment type
# ---------------------------------------------------------------------------

EQUIPMENT_MODELS = [
    # =====================================================================
    # TORO
    # =====================================================================

    # --- Toro: Greens Mowers (Walk) ---
    {"manufacturer": "toro", "model": "Greensmaster 1000", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 18, "fuel_type": "gas", "description": "Walk-behind greens mower, 18-inch cut"},
    {"manufacturer": "toro", "model": "Greensmaster 1018", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 18, "fuel_type": "gas", "description": "Walk-behind greens mower, 18-inch cut, 1000 Series"},
    {"manufacturer": "toro", "model": "Greensmaster 1021", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 21, "fuel_type": "gas", "description": "Walk-behind greens mower, 21-inch cut, 1000 Series"},
    {"manufacturer": "toro", "model": "Greensmaster 1026", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 26, "fuel_type": "gas", "description": "Walk-behind greens mower, 26-inch cut, 1000 Series"},
    {"manufacturer": "toro", "model": "Greensmaster Flex 1820", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 18, "fuel_type": "gas", "description": "Walk-behind greens mower, 18-inch, Flex series"},
    {"manufacturer": "toro", "model": "Greensmaster Flex 2120", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 21, "fuel_type": "gas", "description": "Walk-behind greens mower, 21-inch, Flex series"},
    {"manufacturer": "toro", "model": "Greensmaster eFlex 1021", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 21, "fuel_type": "electric", "description": "Electric walk-behind greens mower, 21-inch cut"},
    {"manufacturer": "toro", "model": "Greensmaster eFlex 2120", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 21, "fuel_type": "electric", "description": "Electric walk-behind greens mower, Flex series"},

    # --- Toro: Greens Mowers (Riding) ---
    {"manufacturer": "toro", "model": "Greensmaster 3100", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 62, "fuel_type": "gas", "description": "Riding triplex greens mower"},
    {"manufacturer": "toro", "model": "Greensmaster 3120", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 62, "fuel_type": "gas", "description": "Riding triplex greens mower"},
    {"manufacturer": "toro", "model": "Greensmaster 3150-Q", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 62, "fuel_type": "gas", "description": "Riding triplex greens mower with quick-adjust cutting units"},
    {"manufacturer": "toro", "model": "Greensmaster 3250-D", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 62, "fuel_type": "diesel", "description": "Riding diesel triplex greens mower"},
    {"manufacturer": "toro", "model": "Greensmaster TriFlex 3300", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "gas", "description": "TriFlex riding triplex greens mower, independent suspension"},
    {"manufacturer": "toro", "model": "Greensmaster TriFlex 3370", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "gas", "description": "TriFlex riding triplex greens mower"},
    {"manufacturer": "toro", "model": "Greensmaster TriFlex Hybrid 3420", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "diesel", "description": "TriFlex hybrid-drive riding triplex greens mower"},

    # --- Toro: Fairway Mowers ---
    {"manufacturer": "toro", "model": "Reelmaster 3555-D", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 82, "fuel_type": "diesel", "description": "Compact 3-plex fairway mower"},
    {"manufacturer": "toro", "model": "Reelmaster 3575-D", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 82, "fuel_type": "diesel", "description": "Compact 3-plex fairway mower with DPA cutting units"},
    {"manufacturer": "toro", "model": "Reelmaster 5010-H", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex hybrid-drive fairway mower, reduced hydraulic leaks"},
    {"manufacturer": "toro", "model": "Reelmaster 5410", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex fairway mower"},
    {"manufacturer": "toro", "model": "Reelmaster 5510", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex fairway mower, crosstrax all-wheel drive"},
    {"manufacturer": "toro", "model": "Reelmaster 5610", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex fairway mower with DPA cutting units"},
    {"manufacturer": "toro", "model": "GeoLink Autonomous Fairway Mower", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 66, "fuel_type": "diesel", "description": "Autonomous TriFlex-based fairway mower with GPS"},

    # --- Toro: Rough Mowers ---
    {"manufacturer": "toro", "model": "Reelmaster 6500-D", "equipment_type": "mower_reel", "sub_type": "rough", "cutting_width": 110, "fuel_type": "diesel", "description": "6-plex rough reel mower"},
    {"manufacturer": "toro", "model": "Reelmaster 6700-D", "equipment_type": "mower_reel", "sub_type": "rough", "cutting_width": 110, "fuel_type": "diesel", "description": "6-plex rough reel mower with DPA cutting units"},
    {"manufacturer": "toro", "model": "Groundsmaster 3500-D", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 72, "fuel_type": "diesel", "description": "Rotary rough mower with 3 decks"},
    {"manufacturer": "toro", "model": "Groundsmaster 4000-D", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 108, "fuel_type": "diesel", "description": "Wide-area rotary rough mower"},
    {"manufacturer": "toro", "model": "Groundsmaster 4100-D", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 104, "fuel_type": "diesel", "description": "Rotary rough mower"},
    {"manufacturer": "toro", "model": "Groundsmaster 4300-D", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 124, "fuel_type": "diesel", "description": "Large-area rotary rough mower"},
    {"manufacturer": "toro", "model": "Groundsmaster 4700-D", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 142, "fuel_type": "diesel", "description": "Wide-area rotary rough mower, contour following"},
    {"manufacturer": "toro", "model": "Groundsmaster 5900", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 96, "fuel_type": "diesel", "description": "Out-front rotary rough mower"},
    {"manufacturer": "toro", "model": "Groundsmaster 7210", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 120, "fuel_type": "diesel", "description": "Zero-turn rotary rough mower"},

    # --- Toro: Trim & Surround Mowers ---
    {"manufacturer": "toro", "model": "Reelmaster 2000-D", "equipment_type": "mower_reel", "sub_type": "trim", "cutting_width": 63, "fuel_type": "diesel", "description": "Trim and surround reel mower"},

    # --- Toro: Sprayers ---
    {"manufacturer": "toro", "model": "Multi Pro 1750", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 175, "fuel_type": "gas", "description": "175-gallon ride-on sprayer with GeoLink GPS capability"},
    {"manufacturer": "toro", "model": "Multi Pro 5800-D", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 300, "fuel_type": "diesel", "description": "300-gallon ride-on sprayer with ExcelaRate spray system"},
    {"manufacturer": "toro", "model": "Multi Pro 5800-G", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 300, "fuel_type": "gas", "description": "300-gallon ride-on sprayer, gas engine"},
    {"manufacturer": "toro", "model": "Multi Pro WX", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 200, "fuel_type": "gas", "description": "Workman-based sprayer platform"},

    # --- Toro: Aerifiers ---
    {"manufacturer": "toro", "model": "ProCore 648", "equipment_type": "aerifier", "sub_type": "walk_behind", "working_width": 48, "fuel_type": "gas", "description": "Walk-behind greens aerator, 48-inch swath"},
    {"manufacturer": "toro", "model": "ProCore 864", "equipment_type": "aerifier", "sub_type": "tractor_mounted", "working_width": 64, "fuel_type": "diesel", "description": "Tractor-mounted fairway aerator, 64-inch swath"},
    {"manufacturer": "toro", "model": "ProCore 1298", "equipment_type": "aerifier", "sub_type": "tractor_mounted", "working_width": 98, "fuel_type": "diesel", "description": "Tractor-mounted wide-area aerator, 98-inch swath"},
    {"manufacturer": "toro", "model": "ProCore SR54-S", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 54, "fuel_type": "diesel", "description": "Deep-tine aerator, 54-inch, SR Series"},
    {"manufacturer": "toro", "model": "ProCore SR70-S", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 70, "fuel_type": "diesel", "description": "Deep-tine aerator, 70-inch, SR Series"},
    {"manufacturer": "toro", "model": "ProCore Processor 1200", "equipment_type": "aerifier", "sub_type": "core_processor", "working_width": 120, "fuel_type": "diesel", "description": "Core processor for cleaning up after aeration"},

    # --- Toro: Topdressers ---
    {"manufacturer": "toro", "model": "ProPass 200", "equipment_type": "topdresser", "sub_type": "broadcast", "capacity_cuft": 22, "fuel_type": "gas", "description": "Broadcast topdresser with drop-zone adjustment"},
    {"manufacturer": "toro", "model": "MH-400", "equipment_type": "topdresser", "sub_type": "material_handler", "capacity_cuft": 108, "fuel_type": "diesel", "description": "4 cu yd material handler / large-area topdresser"},

    # --- Toro: Utility Vehicles ---
    {"manufacturer": "toro", "model": "Workman GTX", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "gas", "description": "Light-duty grounds/turf crossover utility vehicle"},
    {"manufacturer": "toro", "model": "Workman GTX Electric", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "electric", "description": "Electric light-duty utility vehicle"},
    {"manufacturer": "toro", "model": "Workman MDX", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "gas", "description": "Medium-duty utility vehicle with SRQ suspension"},
    {"manufacturer": "toro", "model": "Workman HDX", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "gas", "description": "Heavy-duty utility vehicle, 3,352 lb bed capacity"},
    {"manufacturer": "toro", "model": "Workman HDX-D", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "diesel", "description": "Heavy-duty diesel utility vehicle"},
    {"manufacturer": "toro", "model": "Outcross 9060", "equipment_type": "utility_vehicle", "sub_type": "tractor_utility", "fuel_type": "diesel", "description": "Multi-purpose tractor-utility vehicle, 3-pt hitch, PTO"},

    # --- Toro: Bunker Rakes ---
    {"manufacturer": "toro", "model": "Sand Pro 2040Z", "equipment_type": "bunker_rake", "sub_type": "zero_turn", "fuel_type": "gas", "description": "Zero-turn bunker rake"},
    {"manufacturer": "toro", "model": "Sand Pro 3040", "equipment_type": "bunker_rake", "sub_type": "standard", "fuel_type": "gas", "description": "Mid-size bunker rake"},
    {"manufacturer": "toro", "model": "Sand Pro 5040", "equipment_type": "bunker_rake", "sub_type": "heavy_duty", "fuel_type": "gas", "description": "Heavy-duty bunker rake with multiple attachments"},

    # =====================================================================
    # JOHN DEERE
    # =====================================================================

    # --- John Deere: Greens Mowers (Walk) ---
    {"manufacturer": "john_deere", "model": "180SL PrecisionCut", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 18, "fuel_type": "gas", "description": "Walk-behind greens mower, 18-inch cut"},
    {"manufacturer": "john_deere", "model": "220SL PrecisionCut", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 22, "fuel_type": "gas", "description": "Walk-behind greens mower, 22-inch cut, fixed reel"},
    {"manufacturer": "john_deere", "model": "260SL PrecisionCut", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 26, "fuel_type": "gas", "description": "Walk-behind greens mower, 26-inch cut"},
    {"manufacturer": "john_deere", "model": "220E E-Cut Hybrid", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 22, "fuel_type": "gas", "description": "Hybrid electric reel walk greens mower"},

    # --- John Deere: Greens Mowers (Riding) ---
    {"manufacturer": "john_deere", "model": "2500B PrecisionCut", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "gas", "description": "Riding triplex greens mower"},
    {"manufacturer": "john_deere", "model": "2500E E-Cut Hybrid", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "gas", "description": "Hybrid electric reel riding greens mower"},
    {"manufacturer": "john_deere", "model": "2700 PrecisionCut", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "gas", "description": "Riding triplex greens mower"},
    {"manufacturer": "john_deere", "model": "2750 PrecisionCut", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "diesel", "description": "Riding triplex greens mower, diesel"},

    # --- John Deere: Fairway Mowers ---
    {"manufacturer": "john_deere", "model": "6080A PrecisionCut", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex fairway reel mower with TechControl"},
    {"manufacturer": "john_deere", "model": "6500A E-Cut Hybrid", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex hybrid fairway mower, 22-inch QA5 cutting units"},
    {"manufacturer": "john_deere", "model": "7500A E-Cut Hybrid", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex hybrid fairway mower with AutoPedal and TechControl"},
    {"manufacturer": "john_deere", "model": "7700A PrecisionCut", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex fairway mower"},
    {"manufacturer": "john_deere", "model": "8900A PrecisionCut", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 130, "fuel_type": "diesel", "description": "Wide-area 5-plex fairway mower, 130-inch cut"},

    # --- John Deere: Rough/Trim Mowers ---
    {"manufacturer": "john_deere", "model": "9009A TerrainCut", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 108, "fuel_type": "diesel", "description": "Wide-area rotary rough mower"},
    {"manufacturer": "john_deere", "model": "7500 PrecisionCut", "equipment_type": "mower_reel", "sub_type": "trim", "cutting_width": 80, "fuel_type": "diesel", "description": "Trim and surround reel mower"},
    {"manufacturer": "john_deere", "model": "8800 TerrainCut", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 96, "fuel_type": "diesel", "description": "Rotary rough mower, 5 decks"},

    # --- John Deere: Sprayers ---
    {"manufacturer": "john_deere", "model": "ProGator 2030A HD200", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 200, "fuel_type": "diesel", "description": "200-gallon ProGator-mounted sprayer with GPS"},
    {"manufacturer": "john_deere", "model": "ProGator 2030A HD300", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 300, "fuel_type": "diesel", "description": "300-gallon ProGator-mounted sprayer with GPS"},
    {"manufacturer": "john_deere", "model": "SelectSpray", "equipment_type": "sprayer", "sub_type": "precision", "tank_capacity": 200, "fuel_type": "diesel", "description": "Precision individual-nozzle control spray system"},

    # --- John Deere: Aerifiers ---
    {"manufacturer": "john_deere", "model": "Aercore 800", "equipment_type": "aerifier", "sub_type": "walk_behind", "working_width": 32, "fuel_type": "gas", "description": "Walk-behind core aerator with Precision Tines"},
    {"manufacturer": "john_deere", "model": "Aercore 1000", "equipment_type": "aerifier", "sub_type": "tractor_mounted", "working_width": 40, "fuel_type": "diesel", "description": "Tractor-mounted core aerator"},
    {"manufacturer": "john_deere", "model": "Aercore 1500", "equipment_type": "aerifier", "sub_type": "tractor_mounted", "working_width": 60, "fuel_type": "diesel", "description": "Tractor-mounted wide-area core aerator"},
    {"manufacturer": "john_deere", "model": "Aercore 2000", "equipment_type": "aerifier", "sub_type": "tractor_mounted", "working_width": 72, "fuel_type": "diesel", "description": "Large tractor-mounted core aerator"},

    # --- John Deere: Topdressers ---
    {"manufacturer": "john_deere", "model": "TD100 Topdresser", "equipment_type": "topdresser", "sub_type": "broadcast", "fuel_type": "diesel", "description": "Broadcast topdresser for ProGator"},
    {"manufacturer": "john_deere", "model": "TD200 Topdresser", "equipment_type": "topdresser", "sub_type": "broadcast", "fuel_type": "diesel", "description": "Large-area broadcast topdresser"},

    # --- John Deere: Utility Vehicles ---
    {"manufacturer": "john_deere", "model": "ProGator 2020A", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "gas", "description": "Heavy-duty turf utility vehicle"},
    {"manufacturer": "john_deere", "model": "ProGator 2030A", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "diesel", "description": "Heavy-duty diesel turf utility vehicle, 23.6 hp"},
    {"manufacturer": "john_deere", "model": "Gator TE 4x2 Electric", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "electric", "description": "Electric turf utility vehicle"},
    {"manufacturer": "john_deere", "model": "Gator TH 6x4", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "gas", "description": "6-wheel turf utility vehicle"},
    {"manufacturer": "john_deere", "model": "Gator TX 4x2", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "gas", "description": "Light-duty turf utility vehicle"},

    # --- John Deere: Bunker Rakes ---
    {"manufacturer": "john_deere", "model": "1200A Bunker Rake", "equipment_type": "bunker_rake", "sub_type": "standard", "fuel_type": "gas", "description": "Bunker and field rake with multiple attachments"},

    # =====================================================================
    # JACOBSEN (TEXTRON)
    # =====================================================================

    # --- Jacobsen: Greens Mowers (Walk) ---
    {"manufacturer": "jacobsen", "model": "Eclipse 2 Hybrid", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 22, "fuel_type": "gas", "description": "Hybrid walk-behind greens mower"},
    {"manufacturer": "jacobsen", "model": "Eclipse 2 ELiTE", "equipment_type": "mower_reel", "sub_type": "greens_walk", "cutting_width": 22, "fuel_type": "electric", "description": "All-electric walk-behind greens mower"},

    # --- Jacobsen: Greens Mowers (Riding) ---
    {"manufacturer": "jacobsen", "model": "Eclipse 322", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "diesel", "description": "Riding triplex greens mower"},
    {"manufacturer": "jacobsen", "model": "Eclipse 360 Hybrid", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "diesel", "description": "Hybrid riding triplex greens mower"},
    {"manufacturer": "jacobsen", "model": "Eclipse 360 ELiTE", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 66, "fuel_type": "electric", "description": "All-electric riding triplex greens mower"},
    {"manufacturer": "jacobsen", "model": "GP400", "equipment_type": "mower_reel", "sub_type": "greens_riding", "cutting_width": 62, "fuel_type": "diesel", "description": "Riding triplex greens mower, diesel"},

    # --- Jacobsen: Fairway Mowers ---
    {"manufacturer": "jacobsen", "model": "LF550", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 100, "fuel_type": "diesel", "description": "5-plex light fairway mower"},
    {"manufacturer": "jacobsen", "model": "LF570", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 110, "fuel_type": "diesel", "description": "5-plex wide-area fairway mower"},
    {"manufacturer": "jacobsen", "model": "LF577", "equipment_type": "mower_reel", "sub_type": "fairway", "cutting_width": 110, "fuel_type": "diesel", "description": "5-plex fairway mower with 4WD"},

    # --- Jacobsen: Rough Mowers ---
    {"manufacturer": "jacobsen", "model": "AR722T", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 124, "fuel_type": "diesel", "description": "Wide-area rotary contour rough mower"},
    {"manufacturer": "jacobsen", "model": "HR600", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 132, "fuel_type": "diesel", "description": "Wide-area rotary rough mower"},
    {"manufacturer": "jacobsen", "model": "HR800", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 132, "fuel_type": "diesel", "description": "High-performance wide-area rotary rough mower"},
    {"manufacturer": "jacobsen", "model": "HM600", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 120, "fuel_type": "diesel", "description": "Wide-area mulching flail mower"},
    {"manufacturer": "jacobsen", "model": "TR320", "equipment_type": "mower_reel", "sub_type": "trim", "cutting_width": 68, "fuel_type": "diesel", "description": "Small-area trim and surround reel mower"},

    # =====================================================================
    # KUBOTA
    # =====================================================================

    # --- Kubota: Compact Tractors (used on golf courses) ---
    {"manufacturer": "kubota", "model": "BX2380", "equipment_type": "utility_vehicle", "sub_type": "compact_tractor", "fuel_type": "diesel", "description": "Sub-compact tractor, 23 hp, for light course tasks"},
    {"manufacturer": "kubota", "model": "L2502", "equipment_type": "utility_vehicle", "sub_type": "compact_tractor", "fuel_type": "diesel", "description": "Compact tractor, 25 hp, standard duty"},
    {"manufacturer": "kubota", "model": "L3902", "equipment_type": "utility_vehicle", "sub_type": "compact_tractor", "fuel_type": "diesel", "description": "Compact tractor, 37 hp, with front loader option"},
    {"manufacturer": "kubota", "model": "L4802", "equipment_type": "utility_vehicle", "sub_type": "compact_tractor", "fuel_type": "diesel", "description": "Compact tractor, 48 hp, Stage V diesel"},
    {"manufacturer": "kubota", "model": "L6060", "equipment_type": "utility_vehicle", "sub_type": "compact_tractor", "fuel_type": "diesel", "description": "Compact tractor, 61 hp, ROPS or cab"},

    # --- Kubota: Mowers ---
    {"manufacturer": "kubota", "model": "ZD1211", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 60, "fuel_type": "diesel", "description": "Zero-turn rotary mower, 24.8 hp diesel"},
    {"manufacturer": "kubota", "model": "ZD1511", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 60, "fuel_type": "diesel", "description": "Zero-turn rotary mower, 31 hp diesel"},
    {"manufacturer": "kubota", "model": "F3990", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 72, "fuel_type": "diesel", "description": "Front-mount rotary mower, 38 hp diesel"},
    {"manufacturer": "kubota", "model": "SLM-Series", "equipment_type": "mower_reel", "sub_type": "trim", "cutting_width": 60, "fuel_type": "diesel", "description": "Side-discharge reel mowing attachment"},

    # --- Kubota: Utility Vehicles ---
    {"manufacturer": "kubota", "model": "RTV-X900", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "diesel", "description": "Diesel utility vehicle, hydraulic cargo dump"},
    {"manufacturer": "kubota", "model": "RTV-X1120D", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "diesel", "description": "Diesel utility vehicle, 24.8 hp, power steering"},
    {"manufacturer": "kubota", "model": "RTV-XG850", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "gas", "description": "Gas utility vehicle, Sidekick model"},

    # =====================================================================
    # HUSQVARNA
    # =====================================================================
    {"manufacturer": "husqvarna", "model": "Automower 550 EPOS", "equipment_type": "mower_rotary", "sub_type": "robotic", "cutting_width": 9, "fuel_type": "electric", "description": "Robotic mower with satellite navigation, up to 1.25 acres"},
    {"manufacturer": "husqvarna", "model": "Automower 520 EPOS", "equipment_type": "mower_rotary", "sub_type": "robotic", "cutting_width": 9, "fuel_type": "electric", "description": "Commercial robotic mower with EPOS satellite navigation"},
    {"manufacturer": "husqvarna", "model": "Automower 580L EPOS", "equipment_type": "mower_rotary", "sub_type": "robotic", "cutting_width": 9, "fuel_type": "electric", "description": "Large-area commercial robotic mower for golf/sports turf"},
    {"manufacturer": "husqvarna", "model": "Automower 450XH EPOS", "equipment_type": "mower_rotary", "sub_type": "robotic", "cutting_width": 9, "fuel_type": "electric", "description": "High-cut robotic mower with EPOS"},
    {"manufacturer": "husqvarna", "model": "Z500X", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 60, "fuel_type": "gas", "description": "Professional zero-turn rotary mower"},
    {"manufacturer": "husqvarna", "model": "525BX", "equipment_type": "blower", "sub_type": "backpack", "fuel_type": "gas", "description": "Professional backpack blower"},
    {"manufacturer": "husqvarna", "model": "570BTS", "equipment_type": "blower", "sub_type": "backpack", "fuel_type": "gas", "description": "High-performance professional backpack blower"},
    {"manufacturer": "husqvarna", "model": "535RXT", "equipment_type": "other", "sub_type": "trimmer", "fuel_type": "gas", "description": "Professional brushcutter/trimmer"},
    {"manufacturer": "husqvarna", "model": "572 XP", "equipment_type": "chainsaw", "sub_type": "professional", "fuel_type": "gas", "description": "Professional chainsaw for tree management"},

    # =====================================================================
    # STIHL
    # =====================================================================
    {"manufacturer": "stihl", "model": "BR 800 C-E", "equipment_type": "blower", "sub_type": "backpack", "fuel_type": "gas", "description": "Professional backpack blower, highest power"},
    {"manufacturer": "stihl", "model": "BR 700", "equipment_type": "blower", "sub_type": "backpack", "fuel_type": "gas", "description": "High-performance professional backpack blower"},
    {"manufacturer": "stihl", "model": "BR 600", "equipment_type": "blower", "sub_type": "backpack", "fuel_type": "gas", "description": "Professional backpack blower, 4-MIX engine"},
    {"manufacturer": "stihl", "model": "BGA 200", "equipment_type": "blower", "sub_type": "backpack", "fuel_type": "electric", "description": "Battery-powered professional backpack blower"},
    {"manufacturer": "stihl", "model": "BGA 86", "equipment_type": "blower", "sub_type": "handheld", "fuel_type": "electric", "description": "Battery-powered professional handheld blower"},
    {"manufacturer": "stihl", "model": "FS 560 C-EM", "equipment_type": "other", "sub_type": "trimmer", "fuel_type": "gas", "description": "Professional clearing saw / line trimmer"},
    {"manufacturer": "stihl", "model": "FS 131", "equipment_type": "other", "sub_type": "trimmer", "fuel_type": "gas", "description": "Professional brushcutter / trimmer"},
    {"manufacturer": "stihl", "model": "FSA 135", "equipment_type": "other", "sub_type": "trimmer", "fuel_type": "electric", "description": "Battery-powered professional trimmer"},
    {"manufacturer": "stihl", "model": "HL 94 K (0)", "equipment_type": "other", "sub_type": "hedge_trimmer", "fuel_type": "gas", "description": "Professional extended reach hedge trimmer"},
    {"manufacturer": "stihl", "model": "MS 462", "equipment_type": "chainsaw", "sub_type": "professional", "fuel_type": "gas", "description": "Professional chainsaw for tree work"},
    {"manufacturer": "stihl", "model": "MS 261 C-M", "equipment_type": "chainsaw", "sub_type": "professional", "fuel_type": "gas", "description": "Mid-range professional chainsaw"},
    {"manufacturer": "stihl", "model": "MSA 220 C-B", "equipment_type": "chainsaw", "sub_type": "professional", "fuel_type": "electric", "description": "Battery-powered professional chainsaw"},
    {"manufacturer": "stihl", "model": "FC 91", "equipment_type": "other", "sub_type": "edger", "fuel_type": "gas", "description": "Professional lawn edger"},

    # =====================================================================
    # HONDA
    # =====================================================================
    {"manufacturer": "honda", "model": "HRC 216K3HXA", "equipment_type": "mower_rotary", "sub_type": "walk_behind", "cutting_width": 21, "fuel_type": "gas", "description": "Commercial walk-behind rotary mower, blade-brake clutch"},
    {"manufacturer": "honda", "model": "HRC 216K3PDA", "equipment_type": "mower_rotary", "sub_type": "walk_behind", "cutting_width": 21, "fuel_type": "gas", "description": "Commercial walk-behind rotary mower, power-drive"},
    {"manufacturer": "honda", "model": "HRX 217VKA", "equipment_type": "mower_rotary", "sub_type": "walk_behind", "cutting_width": 21, "fuel_type": "gas", "description": "Premium walk-behind rotary mower with Versamow"},
    {"manufacturer": "honda", "model": "EU2200i", "equipment_type": "other", "sub_type": "generator", "fuel_type": "gas", "description": "Inverter generator, 2200W, for on-course power"},
    {"manufacturer": "honda", "model": "EU3000iS", "equipment_type": "other", "sub_type": "generator", "fuel_type": "gas", "description": "Inverter generator, 3000W, electric start"},
    {"manufacturer": "honda", "model": "WX10", "equipment_type": "other", "sub_type": "pump", "fuel_type": "gas", "description": "Lightweight centrifugal water pump"},

    # =====================================================================
    # YAMAHA
    # =====================================================================
    {"manufacturer": "yamaha", "model": "Drive2 Fleet AC", "equipment_type": "utility_vehicle", "sub_type": "golf_car", "fuel_type": "electric", "description": "Electric fleet golf car, AC drive"},
    {"manufacturer": "yamaha", "model": "Drive2 Fleet Gas", "equipment_type": "utility_vehicle", "sub_type": "golf_car", "fuel_type": "gas", "description": "Gas fleet golf car"},
    {"manufacturer": "yamaha", "model": "UMAX One", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "gas", "description": "Light-duty utility vehicle, 13 cu ft cargo bed"},
    {"manufacturer": "yamaha", "model": "UMAX Two", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "gas", "description": "Two-passenger utility vehicle with cargo bed"},
    {"manufacturer": "yamaha", "model": "UMAX Two Rally", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "gas", "description": "Lifted utility vehicle with all-terrain tires"},
    {"manufacturer": "yamaha", "model": "UMAX Bistro", "equipment_type": "utility_vehicle", "sub_type": "specialty", "fuel_type": "gas", "description": "Beverage/food service cart"},
    {"manufacturer": "yamaha", "model": "UMAX Range Picker", "equipment_type": "utility_vehicle", "sub_type": "specialty", "fuel_type": "gas", "description": "Driving range ball picker"},
    {"manufacturer": "yamaha", "model": "UMAX Li-ion", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "electric", "description": "Lithium-ion battery electric utility vehicle"},

    # =====================================================================
    # CLUB CAR
    # =====================================================================
    {"manufacturer": "club_car", "model": "Carryall 300 Turf", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "gas", "description": "Compact turf utility vehicle"},
    {"manufacturer": "club_car", "model": "Carryall 500 Turf", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "gas", "description": "Turf utility vehicle, 1,500 lb capacity, aluminum frame"},
    {"manufacturer": "club_car", "model": "Carryall 550 Turf", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "gas", "description": "Turf utility vehicle with dump bed"},
    {"manufacturer": "club_car", "model": "Carryall 700 Turf", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "gas", "description": "Heavy-duty turf utility vehicle"},
    {"manufacturer": "club_car", "model": "Carryall 300 Turf Electric", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "electric", "description": "Electric compact turf utility vehicle"},
    {"manufacturer": "club_car", "model": "Carryall 500 Turf Electric", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "electric", "description": "Electric turf utility vehicle, aluminum frame"},
    {"manufacturer": "club_car", "model": "Carryall 550 Turf Electric", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "electric", "description": "Electric turf utility vehicle with dump bed"},
    {"manufacturer": "club_car", "model": "Carryall 900", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "gas", "description": "Long-bed utility vehicle, 98.5 in bed"},
    {"manufacturer": "club_car", "model": "Tempo Fleet Golf Car", "equipment_type": "utility_vehicle", "sub_type": "golf_car", "fuel_type": "electric", "description": "Fleet golf car with connected technology"},

    # =====================================================================
    # CUSHMAN (TEXTRON)
    # =====================================================================
    {"manufacturer": "cushman", "model": "Hauler 800", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "gas", "description": "Compact utility vehicle for turf and facility use"},
    {"manufacturer": "cushman", "model": "Hauler 800 Electric", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "electric", "description": "Electric compact utility vehicle"},
    {"manufacturer": "cushman", "model": "Hauler PRO", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "gas", "description": "Medium-duty utility vehicle"},
    {"manufacturer": "cushman", "model": "Hauler PRO ELiTE", "equipment_type": "utility_vehicle", "sub_type": "medium_duty", "fuel_type": "electric", "description": "ELiTE lithium-powered utility vehicle"},
    {"manufacturer": "cushman", "model": "Hauler PRO X", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "gas", "description": "Heavy-duty utility vehicle with high capacity"},
    {"manufacturer": "cushman", "model": "Turf-Truckster", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "gas", "description": "Heavy-duty turf utility vehicle for material handling"},
    {"manufacturer": "cushman", "model": "Turf-Truckster XD", "equipment_type": "utility_vehicle", "sub_type": "heavy_duty", "fuel_type": "diesel", "description": "Extra heavy-duty diesel turf utility vehicle"},

    # =====================================================================
    # SMITHCO
    # =====================================================================

    # --- Smithco: Sprayers ---
    {"manufacturer": "smithco", "model": "Spray Star 1000", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 100, "fuel_type": "gas", "description": "100-gallon ride-on turf sprayer"},
    {"manufacturer": "smithco", "model": "Spray Star 1200 D", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 120, "fuel_type": "diesel", "description": "120-gallon diesel ride-on turf sprayer"},
    {"manufacturer": "smithco", "model": "Spray Star 1300", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 130, "fuel_type": "gas", "description": "130-gallon ride-on turf sprayer"},
    {"manufacturer": "smithco", "model": "Spray Star 2000", "equipment_type": "sprayer", "sub_type": "ride_on", "tank_capacity": 200, "fuel_type": "gas", "description": "200-gallon ride-on turf sprayer with Star Command"},

    # --- Smithco: Rollers ---
    {"manufacturer": "smithco", "model": "Tournament Ultra 7580", "equipment_type": "roller", "sub_type": "greens", "fuel_type": "gas", "description": "Walk-behind greens roller"},
    {"manufacturer": "smithco", "model": "Fairway Roller", "equipment_type": "roller", "sub_type": "fairway", "fuel_type": "diesel", "description": "Ride-on fairway roller"},
    {"manufacturer": "smithco", "model": "Greensroller", "equipment_type": "roller", "sub_type": "greens", "fuel_type": "gas", "description": "Dedicated greens roller"},

    # --- Smithco: Bunker Rakes ---
    {"manufacturer": "smithco", "model": "Sand Star", "equipment_type": "bunker_rake", "sub_type": "standard", "fuel_type": "gas", "description": "Turf-friendly bunker maintenance vehicle"},
    {"manufacturer": "smithco", "model": "Sand Star Electric", "equipment_type": "bunker_rake", "sub_type": "standard", "fuel_type": "electric", "description": "Electric bunker maintenance vehicle"},

    # --- Smithco: Sweepers ---
    {"manufacturer": "smithco", "model": "Sweep Star 60", "equipment_type": "other", "sub_type": "sweeper", "fuel_type": "gas", "description": "60-inch turf sweeper"},

    # =====================================================================
    # WIEDENMANN
    # =====================================================================
    {"manufacturer": "wiedenmann", "model": "Terra Spike GXi 6 HD", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 60, "fuel_type": "diesel", "description": "PTO deep-tine aerator for greens, 6-inch spacing"},
    {"manufacturer": "wiedenmann", "model": "Terra Spike GXi 8 HD", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 80, "fuel_type": "diesel", "description": "PTO deep-tine aerator, 8-inch spacing"},
    {"manufacturer": "wiedenmann", "model": "Terra Spike XF", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 60, "fuel_type": "diesel", "description": "Extra fast PTO deep-tine aerator, up to 3.5 mph"},
    {"manufacturer": "wiedenmann", "model": "Terra Spike XD", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 60, "fuel_type": "diesel", "description": "Extra deep PTO deep-tine aerator with VibraStop"},
    {"manufacturer": "wiedenmann", "model": "Terra Spike XP", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 60, "fuel_type": "diesel", "description": "Extra powerful PTO deep-tine aerator, depth to 40cm"},
    {"manufacturer": "wiedenmann", "model": "Whisper Twister", "equipment_type": "blower", "sub_type": "pto_mounted", "fuel_type": "diesel", "description": "PTO-mounted leaf blower with whisper turbine"},
    {"manufacturer": "wiedenmann", "model": "Mega Twister", "equipment_type": "blower", "sub_type": "pto_mounted", "fuel_type": "diesel", "description": "Large PTO-mounted leaf/debris blower"},

    # =====================================================================
    # GRADEN
    # =====================================================================
    {"manufacturer": "graden", "model": "GS04 Verticutter", "equipment_type": "verticutter", "sub_type": "walk_behind", "working_width": 16, "fuel_type": "gas", "description": "Walk-behind verticutter, 16-inch, compact and light"},
    {"manufacturer": "graden", "model": "SW04 Swing-Wing", "equipment_type": "verticutter", "sub_type": "ride_on", "working_width": 59, "fuel_type": "diesel", "description": "3-head swing-wing verticutter, 59-inch or 79-inch"},
    {"manufacturer": "graden", "model": "GBS 1200", "equipment_type": "verticutter", "sub_type": "tractor_mounted", "working_width": 48, "fuel_type": "diesel", "description": "Straight reel verticutter, 48-inch, for flat areas"},
    {"manufacturer": "graden", "model": "CSI Contour Sand Injector", "equipment_type": "verticutter", "sub_type": "sand_injection", "working_width": 24, "fuel_type": "gas", "description": "Verticutter with sand injection, Honda 20 hp engine"},
    {"manufacturer": "graden", "model": "Double Disc Overseeder 1430", "equipment_type": "other", "sub_type": "overseeder", "working_width": 30, "fuel_type": "diesel", "description": "Double-disc overseeder for turfgrass renovation"},

    # =====================================================================
    # PROGRESSIVE TURF EQUIPMENT
    # =====================================================================
    {"manufacturer": "progressive", "model": "TDR-12", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 144, "fuel_type": "diesel", "description": "Tri-deck roller finishing mower, 12-foot cut, tow-behind"},
    {"manufacturer": "progressive", "model": "TDR-22", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 264, "fuel_type": "diesel", "description": "Tri-deck roller finishing mower, 22-foot cut, tow-behind"},
    {"manufacturer": "progressive", "model": "TDR-X", "equipment_type": "mower_rotary", "sub_type": "trim", "cutting_width": 125, "fuel_type": "diesel", "description": "Tri-deck contour roller finishing mower, tow-behind"},
    {"manufacturer": "progressive", "model": "Pro-Flex 120", "equipment_type": "mower_rotary", "sub_type": "fairway", "cutting_width": 120, "fuel_type": "diesel", "description": "5-deck contour mower, greens/fairway height, tow-behind"},
    {"manufacturer": "progressive", "model": "SDR-65", "equipment_type": "mower_rotary", "sub_type": "trim", "cutting_width": 65, "fuel_type": "diesel", "description": "3-point hitch roller mower, cuts as low as 0.5 inch"},
    {"manufacturer": "progressive", "model": "Pro-Roll 10", "equipment_type": "roller", "sub_type": "fairway", "working_width": 120, "fuel_type": "diesel", "description": "10-foot contour turf roller, tow-behind"},
    {"manufacturer": "progressive", "model": "Pro-Roll 15", "equipment_type": "roller", "sub_type": "fairway", "working_width": 180, "fuel_type": "diesel", "description": "15-foot contour turf roller, tow-behind"},

    # =====================================================================
    # RYAN (BOBCAT)
    # =====================================================================
    {"manufacturer": "ryan", "model": "Lawnaire V-EST", "equipment_type": "aerifier", "sub_type": "walk_behind", "working_width": 26, "fuel_type": "gas", "description": "Walk-behind core aerator, Honda GX120, 26.5 inch"},
    {"manufacturer": "ryan", "model": "Lawnaire IV-EST", "equipment_type": "aerifier", "sub_type": "walk_behind", "working_width": 19, "fuel_type": "gas", "description": "Walk-behind core aerator, Honda GX120, 19 inch"},
    {"manufacturer": "ryan", "model": "Lawnaire ZTS", "equipment_type": "aerifier", "sub_type": "stand_on", "working_width": 30, "fuel_type": "gas", "description": "Stand-on core aerator, Kawasaki 15 hp, 30 inch"},
    {"manufacturer": "ryan", "model": "Lawnaire 48", "equipment_type": "aerifier", "sub_type": "tractor_mounted", "working_width": 48, "fuel_type": "diesel", "description": "3-point hitch core aerator, 48-inch, PTO-driven"},
    {"manufacturer": "ryan", "model": "Mataway Overseeder", "equipment_type": "other", "sub_type": "overseeder", "working_width": 19, "fuel_type": "gas", "description": "Walk-behind overseeder, Honda GX390, 19-inch"},
    {"manufacturer": "ryan", "model": "Jr. Sod Cutter", "equipment_type": "other", "sub_type": "sod_cutter", "working_width": 12, "fuel_type": "gas", "description": "Walk-behind sod cutter, compact design"},
    {"manufacturer": "ryan", "model": "Jr. Sod Cutter Hydro", "equipment_type": "other", "sub_type": "sod_cutter", "working_width": 18, "fuel_type": "gas", "description": "Walk-behind hydro-drive sod cutter, 18-inch"},
    {"manufacturer": "ryan", "model": "Ren-O-Thin Dethatcher", "equipment_type": "verticutter", "sub_type": "walk_behind", "working_width": 19, "fuel_type": "gas", "description": "Walk-behind power rake / dethatcher"},

    # =====================================================================
    # E-Z-GO (TEXTRON)
    # =====================================================================
    {"manufacturer": "ez_go", "model": "RXV Fleet Golf Car", "equipment_type": "utility_vehicle", "sub_type": "golf_car", "fuel_type": "electric", "description": "Electric fleet golf car with AC drive"},
    {"manufacturer": "ez_go", "model": "TXT Fleet Golf Car", "equipment_type": "utility_vehicle", "sub_type": "golf_car", "fuel_type": "electric", "description": "Electric fleet golf car, standard model"},
    {"manufacturer": "ez_go", "model": "Express S4", "equipment_type": "utility_vehicle", "sub_type": "light_duty", "fuel_type": "electric", "description": "4-passenger electric utility vehicle"},
    {"manufacturer": "ez_go", "model": "Liberty", "equipment_type": "utility_vehicle", "sub_type": "golf_car", "fuel_type": "electric", "description": "ELiTE lithium fleet golf car"},

    # =====================================================================
    # REDEXIM (CHARTERHOUSE)
    # =====================================================================
    {"manufacturer": "redexim", "model": "Verti-Drain 2519", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 60, "fuel_type": "diesel", "description": "PTO deep-tine aerator, standard model"},
    {"manufacturer": "redexim", "model": "Verti-Drain 7626", "equipment_type": "aerifier", "sub_type": "deep_tine", "working_width": 64, "fuel_type": "diesel", "description": "PTO deep-tine aerator, heavy-duty"},
    {"manufacturer": "redexim", "model": "Turf Tidy 1710", "equipment_type": "other", "sub_type": "sweeper", "working_width": 67, "fuel_type": "diesel", "description": "PTO turf sweeper/collector, 67-inch"},
    {"manufacturer": "redexim", "model": "Speed Seed", "equipment_type": "other", "sub_type": "overseeder", "working_width": 60, "fuel_type": "diesel", "description": "PTO-driven disc overseeder"},
    {"manufacturer": "redexim", "model": "Double Disc Overseeder", "equipment_type": "other", "sub_type": "overseeder", "working_width": 48, "fuel_type": "diesel", "description": "PTO double-disc overseeder for fairways"},

    # =====================================================================
    # HARPER TURF
    # =====================================================================
    {"manufacturer": "harper", "model": "AT60", "equipment_type": "topdresser", "sub_type": "broadcast", "fuel_type": "gas", "description": "Self-propelled greens topdresser"},
    {"manufacturer": "harper", "model": "TV40", "equipment_type": "topdresser", "sub_type": "broadcast", "fuel_type": "gas", "description": "Tow-behind topdresser, 40 cu ft"},
    {"manufacturer": "harper", "model": "Turf Breeze 5200", "equipment_type": "blower", "sub_type": "tow_behind", "fuel_type": "gas", "description": "Tow-behind debris blower for fairways"},

    # =====================================================================
    # DAKOTA PEAT
    # =====================================================================
    {"manufacturer": "dakota", "model": "Turf Tender 440", "equipment_type": "topdresser", "sub_type": "material_handler", "fuel_type": "gas", "description": "4 cu yd material handler / topdresser"},
    {"manufacturer": "dakota", "model": "Turf Tender 210", "equipment_type": "topdresser", "sub_type": "broadcast", "fuel_type": "gas", "description": "2.1 cu yd broadcast topdresser"},

    # =====================================================================
    # BILLY GOAT
    # =====================================================================
    {"manufacturer": "billy_goat", "model": "QV900HSP", "equipment_type": "other", "sub_type": "vacuum", "fuel_type": "gas", "description": "Self-propelled lawn/leaf vacuum, Honda engine"},
    {"manufacturer": "billy_goat", "model": "F1302H", "equipment_type": "blower", "sub_type": "walk_behind", "fuel_type": "gas", "description": "Walk-behind force blower, Honda engine, 13 hp"},

    # =====================================================================
    # ECHO
    # =====================================================================
    {"manufacturer": "echo", "model": "PB-9010T", "equipment_type": "blower", "sub_type": "backpack", "fuel_type": "gas", "description": "Tube-mount backpack blower, 79.9 cc"},
    {"manufacturer": "echo", "model": "PB-8010T", "equipment_type": "blower", "sub_type": "backpack", "fuel_type": "gas", "description": "Tube-mount backpack blower, 79.9 cc"},
    {"manufacturer": "echo", "model": "SRM-3020T", "equipment_type": "other", "sub_type": "trimmer", "fuel_type": "gas", "description": "Professional string trimmer, 30.5 cc"},
    {"manufacturer": "echo", "model": "CS-7310P", "equipment_type": "chainsaw", "sub_type": "professional", "fuel_type": "gas", "description": "Professional chainsaw, 73.5 cc"},

    # =====================================================================
    # LASTEC
    # =====================================================================
    {"manufacturer": "lastec", "model": "Articulator 3682", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 82, "fuel_type": "diesel", "description": "Articulating rotary mower, 82-inch, out-front"},
    {"manufacturer": "lastec", "model": "Articulator 100Z", "equipment_type": "mower_rotary", "sub_type": "rough", "cutting_width": 100, "fuel_type": "diesel", "description": "Zero-turn articulating rotary mower, 100-inch"},
]


# ---------------------------------------------------------------------------
# Standard service intervals by equipment TYPE
# All intervals in engine/operating hours unless noted
# ---------------------------------------------------------------------------

SERVICE_INTERVALS = {
    "mower_reel": {
        "label": "Reel Mower (Greens / Fairway / Rough)",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 50, "first_service_hours": 5, "notes": "Use manufacturer-specified oil weight. First change at 5 hours on new/rebuilt engines."},
            {"task": "hydraulic_fluid_change", "label": "Hydraulic Fluid & Filter Change", "interval_hours": 500, "first_service_hours": 200, "notes": "Use Toro Hypr-Oil 500 or Mobil 1 15W-50 for extended intervals. Standard hydro oil: 250 hrs."},
            {"task": "reel_backlap", "label": "Reel Backlapping", "interval_hours": 40, "first_service_hours": None, "notes": "Weekly if used 40 hrs/wk. More frequent in sandy conditions. If >7 min with no improvement, grind instead."},
            {"task": "reel_grind", "label": "Reel & Bedknife Grinding", "interval_hours": 200, "first_service_hours": None, "notes": "Spin or relief grind reels. Replace bedknife if worn past minimum thickness."},
            {"task": "air_filter", "label": "Air Filter Inspection / Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Inspect every 50 hours, replace at 100 hours or sooner in dusty conditions."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 50, "first_service_hours": None, "notes": "Grease caster forks, wheel hubs, reel bearings, roller ends. Some daily-grease points exist."},
            {"task": "belt_inspection", "label": "Belt Inspection / Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Inspect for cracks, glazing, fraying. Replace annually or at 200 hours."},
            {"task": "tire_pressure", "label": "Tire Pressure Check", "interval_hours": 50, "first_service_hours": None, "notes": "Check and adjust to spec. Uneven pressure causes uneven cut height."},
            {"task": "battery_check", "label": "Battery Inspection / Clean Terminals", "interval_hours": 200, "first_service_hours": None, "notes": "Check electrolyte level, clean terminals, test charge. Replace every 2-3 seasons."},
            {"task": "fuel_filter", "label": "Fuel Filter Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Replace fuel filter. Drain fuel/water separator on diesel models daily."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Gas engines only. Replace annually or at 200 hours."},
            {"task": "bedknife_adjustment", "label": "Bedknife-to-Reel Adjustment", "interval_hours": 8, "first_service_hours": None, "notes": "Check contact daily or every 8 hours. Light contact cut preferred."},
            {"task": "height_of_cut_check", "label": "Height of Cut Verification", "interval_hours": 8, "first_service_hours": None, "notes": "Verify with HOC gauge before each mowing session."},
        ]
    },

    "mower_rotary": {
        "label": "Rotary Mower (Rough / Walk-Behind / Zero-Turn)",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 50, "first_service_hours": 5, "notes": "First change at 5 hours. Standard interval every 50 hours thereafter."},
            {"task": "hydraulic_fluid_change", "label": "Hydraulic Fluid & Filter Change", "interval_hours": 500, "first_service_hours": 200, "notes": "Check level weekly. Replace fluid and filters per schedule."},
            {"task": "blade_sharpening", "label": "Blade Sharpening / Replacement", "interval_hours": 25, "first_service_hours": None, "notes": "Sharpen every 25 hours. More frequent in sandy soil. Balance blades after sharpening."},
            {"task": "air_filter", "label": "Air Filter Inspection / Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Inspect every 25 hours, replace at 100 hours or sooner in dusty conditions."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 50, "first_service_hours": None, "notes": "Grease spindle bearings, caster pivots, wheel bearings, linkage points."},
            {"task": "belt_inspection", "label": "Belt Inspection / Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Inspect deck drive belts for wear, cracks, stretch. Replace annually."},
            {"task": "tire_pressure", "label": "Tire Pressure Check", "interval_hours": 50, "first_service_hours": None, "notes": "Check before each use. Maintain manufacturer-specified PSI."},
            {"task": "battery_check", "label": "Battery Inspection / Clean Terminals", "interval_hours": 200, "first_service_hours": None, "notes": "Clean terminals, check voltage, inspect cables."},
            {"task": "fuel_filter", "label": "Fuel Filter Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Replace fuel filter. Drain water separator on diesel units."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Gas engines only. Replace annually or at 200 hours."},
            {"task": "deck_cleaning", "label": "Deck Scraping / Cleaning", "interval_hours": 8, "first_service_hours": None, "notes": "Clean underside of deck after each use to prevent buildup."},
        ]
    },

    "sprayer": {
        "label": "Sprayer (Ride-On / Boom)",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 50, "first_service_hours": 5, "notes": "Standard 50-hour oil change interval."},
            {"task": "hydraulic_fluid_change", "label": "Hydraulic Fluid & Filter Change", "interval_hours": 500, "first_service_hours": 200, "notes": "Check hydraulic system for leaks regularly."},
            {"task": "nozzle_inspection", "label": "Nozzle Inspection / Replacement", "interval_hours": 50, "first_service_hours": None, "notes": "Check spray pattern and flow rate every 50 hours. Replace worn nozzles (>10% drift from spec)."},
            {"task": "strainer_cleaning", "label": "Strainer / Screen Cleaning", "interval_hours": 25, "first_service_hours": None, "notes": "Clean boom-line strainers, suction strainer, and nozzle screens."},
            {"task": "pump_inspection", "label": "Pump Inspection / Diaphragm Check", "interval_hours": 100, "first_service_hours": None, "notes": "Inspect pump diaphragms, check valves, seals. Replace diaphragms annually."},
            {"task": "calibration", "label": "Sprayer Calibration", "interval_hours": 50, "first_service_hours": None, "notes": "Calibrate output rate (oz/1000 sq ft) at operating speed. Re-calibrate after nozzle changes."},
            {"task": "air_filter", "label": "Air Filter Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Standard air filter service interval."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 50, "first_service_hours": None, "notes": "Grease boom pivots, steering, wheel bearings."},
            {"task": "tire_pressure", "label": "Tire Pressure Check", "interval_hours": 50, "first_service_hours": None, "notes": "Critical for maintaining consistent application rates."},
            {"task": "hose_inspection", "label": "Hose & Fitting Inspection", "interval_hours": 100, "first_service_hours": None, "notes": "Check all hoses for cracks, leaks, UV degradation. Replace every 3-5 years."},
            {"task": "tank_rinse", "label": "Triple Rinse Tank & Lines", "interval_hours": 0, "first_service_hours": None, "notes": "After EVERY use. Critical to prevent cross-contamination and turf damage."},
            {"task": "fuel_filter", "label": "Fuel Filter Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Replace fuel filter per manufacturer schedule."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Gas engines only."},
        ]
    },

    "aerifier": {
        "label": "Aerifier / Core Aerator / Deep-Tine Aerator",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 50, "first_service_hours": 5, "notes": "For self-powered units. PTO units follow tractor schedule."},
            {"task": "hydraulic_fluid_change", "label": "Hydraulic Fluid & Filter Change", "interval_hours": 500, "first_service_hours": 200, "notes": "Check hydraulic hoses and connections before each use."},
            {"task": "tine_inspection", "label": "Tine Inspection / Replacement", "interval_hours": 25, "first_service_hours": None, "notes": "Inspect tines for wear, bending, breakage. Replace when worn to minimum length."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 25, "first_service_hours": None, "notes": "Grease crankshaft, tine holders, cam mechanism, wheel bearings. More frequent than mowers."},
            {"task": "belt_inspection", "label": "Belt / Chain Inspection", "interval_hours": 50, "first_service_hours": None, "notes": "Check drive belts or chains for wear and proper tension."},
            {"task": "depth_calibration", "label": "Depth Setting Calibration", "interval_hours": 25, "first_service_hours": None, "notes": "Verify actual penetration depth matches setting before each use."},
            {"task": "air_filter", "label": "Air Filter Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "For self-powered units."},
            {"task": "tire_pressure", "label": "Tire / Roller Pressure Check", "interval_hours": 25, "first_service_hours": None, "notes": "Check tire and roller inflation. Affects hole spacing consistency."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Gas engines only."},
        ]
    },

    "topdresser": {
        "label": "Topdresser / Material Handler",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 50, "first_service_hours": 5, "notes": "For engine-powered units."},
            {"task": "hydraulic_fluid_change", "label": "Hydraulic Fluid & Filter Change", "interval_hours": 500, "first_service_hours": 200, "notes": "Check hydraulic lines and fittings for leaks."},
            {"task": "belt_inspection", "label": "Conveyor Belt Inspection / Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Inspect conveyor belt for wear, tracking, tension. Adjust or replace as needed."},
            {"task": "spinner_inspection", "label": "Spinner Disc / Brush Inspection", "interval_hours": 50, "first_service_hours": None, "notes": "Check spinner discs for wear. Inspect brushes for bristle condition."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 50, "first_service_hours": None, "notes": "Grease conveyor bearings, spinner bearings, pivot points."},
            {"task": "calibration", "label": "Spread Rate Calibration", "interval_hours": 50, "first_service_hours": None, "notes": "Calibrate material output rate and spread width."},
            {"task": "hopper_cleaning", "label": "Hopper & Conveyor Cleaning", "interval_hours": 8, "first_service_hours": None, "notes": "Clean after each use to prevent material buildup and corrosion."},
            {"task": "tire_pressure", "label": "Tire Pressure Check", "interval_hours": 50, "first_service_hours": None, "notes": "Check trailer and unit tire pressure."},
        ]
    },

    "utility_vehicle": {
        "label": "Utility Vehicle / Golf Car / Compact Tractor",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 100, "first_service_hours": 20, "notes": "Gas/diesel utility vehicles typically 100-hour intervals. First at 20 hours."},
            {"task": "hydraulic_fluid_change", "label": "Hydraulic / Transmission Fluid Change", "interval_hours": 500, "first_service_hours": 200, "notes": "Check for leaks regularly. Applies to hydrostatic drive units."},
            {"task": "air_filter", "label": "Air Filter Inspection / Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Inspect every 100 hours, replace at 200 hours."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 100, "first_service_hours": None, "notes": "Grease steering, suspension, wheel bearings, driveline."},
            {"task": "belt_inspection", "label": "Drive Belt Inspection", "interval_hours": 200, "first_service_hours": None, "notes": "Inspect drive belt (CVT) for wear and proper tension."},
            {"task": "tire_pressure", "label": "Tire Pressure Check", "interval_hours": 50, "first_service_hours": None, "notes": "Check all four tires. Turf tires require lower pressures."},
            {"task": "battery_check", "label": "Battery Inspection (Electric) / Watering", "interval_hours": 50, "first_service_hours": None, "notes": "Electric: check water level weekly, equalize charge monthly. Gas: check terminals."},
            {"task": "brake_inspection", "label": "Brake Inspection / Adjustment", "interval_hours": 200, "first_service_hours": None, "notes": "Inspect pads, drums/discs, cables. Adjust as needed."},
            {"task": "fuel_filter", "label": "Fuel Filter Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Replace fuel filter (gas/diesel units only)."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 300, "first_service_hours": None, "notes": "Gas engines only. Replace annually or at 300 hours."},
            {"task": "differential_fluid", "label": "Differential / Axle Fluid Change", "interval_hours": 500, "first_service_hours": None, "notes": "Check level at 250 hours, change at 500 hours."},
        ]
    },

    "roller": {
        "label": "Turf Roller (Greens / Fairway)",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 50, "first_service_hours": 5, "notes": "For self-propelled rollers."},
            {"task": "hydraulic_fluid_change", "label": "Hydraulic Fluid Change", "interval_hours": 500, "first_service_hours": 200, "notes": "Check hydraulic system for leaks."},
            {"task": "roller_inspection", "label": "Roller Drum Inspection / Cleaning", "interval_hours": 25, "first_service_hours": None, "notes": "Inspect drums for dents, scratches, buildup. Clean after each use."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 50, "first_service_hours": None, "notes": "Grease roller bearings, steering pivots, frame joints."},
            {"task": "belt_inspection", "label": "Belt Inspection / Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Check drive belt condition and tension."},
            {"task": "tire_pressure", "label": "Tire Pressure Check", "interval_hours": 50, "first_service_hours": None, "notes": "Check transport tires."},
            {"task": "battery_check", "label": "Battery Check", "interval_hours": 200, "first_service_hours": None, "notes": "Check battery terminals and charge level."},
        ]
    },

    "verticutter": {
        "label": "Verticutter / Dethatcher / Scarifier",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 50, "first_service_hours": 5, "notes": "For self-powered units. PTO units follow tractor schedule."},
            {"task": "blade_inspection", "label": "Blade / Knife Inspection / Replacement", "interval_hours": 10, "first_service_hours": None, "notes": "Inspect blades every 10 hours. Replace when worn past minimum width or cracked."},
            {"task": "blade_sharpening", "label": "Blade Sharpening", "interval_hours": 25, "first_service_hours": None, "notes": "Sharpen verticutter blades every 25 hours of operation."},
            {"task": "belt_inspection", "label": "Belt Inspection / Replacement", "interval_hours": 50, "first_service_hours": None, "notes": "Check drive belt tension and condition frequently. High-stress application."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 25, "first_service_hours": None, "notes": "Grease reel bearings, shaft bearings, wheel bearings."},
            {"task": "depth_calibration", "label": "Cutting Depth Calibration", "interval_hours": 10, "first_service_hours": None, "notes": "Verify cutting depth before each use. Critical for turf health."},
            {"task": "air_filter", "label": "Air Filter Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "For self-powered units only."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Gas engines only."},
        ]
    },

    "blower": {
        "label": "Blower (Backpack / Walk-Behind / PTO)",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil Change", "interval_hours": 50, "first_service_hours": 10, "notes": "2-stroke: premix oil in fuel. 4-stroke: change oil every 50 hours."},
            {"task": "air_filter", "label": "Air Filter Cleaning / Replacement", "interval_hours": 25, "first_service_hours": None, "notes": "Clean foam pre-filter every 25 hours. Replace main element every 100 hours."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Replace every 100 hours or annually."},
            {"task": "fuel_filter", "label": "Fuel Filter Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Replace in-line fuel filter."},
            {"task": "impeller_inspection", "label": "Impeller / Fan Inspection", "interval_hours": 100, "first_service_hours": None, "notes": "Inspect for cracks, debris damage, balance."},
            {"task": "throttle_cable", "label": "Throttle Cable / Linkage Check", "interval_hours": 100, "first_service_hours": None, "notes": "Check cable routing, lubricate, adjust as needed."},
            {"task": "tube_inspection", "label": "Tube / Nozzle Inspection", "interval_hours": 100, "first_service_hours": None, "notes": "Check for cracks, obstructions, secure attachment."},
        ]
    },

    "bunker_rake": {
        "label": "Bunker Rake / Sand Pro",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil & Filter Change", "interval_hours": 100, "first_service_hours": 20, "notes": "Standard 100-hour interval for light-duty engines."},
            {"task": "hydraulic_fluid_change", "label": "Hydraulic Fluid Change", "interval_hours": 500, "first_service_hours": 200, "notes": "Check hydraulic system for leaks."},
            {"task": "air_filter", "label": "Air Filter Replacement", "interval_hours": 200, "first_service_hours": None, "notes": "Inspect every 100 hours, replace at 200 hours. Sandy environment clogs filters faster."},
            {"task": "grease_points", "label": "Grease All Fittings", "interval_hours": 50, "first_service_hours": None, "notes": "Grease steering, caster pivots, wheel bearings. Sand is abrasive - grease more often."},
            {"task": "attachment_inspection", "label": "Rake / Plow / Drag Mat Inspection", "interval_hours": 25, "first_service_hours": None, "notes": "Check rake tines, plow edge, drag mat condition. Replace worn components."},
            {"task": "tire_pressure", "label": "Tire Pressure Check", "interval_hours": 50, "first_service_hours": None, "notes": "Low-pressure turf tires. Check before each use."},
            {"task": "belt_inspection", "label": "Belt Inspection", "interval_hours": 200, "first_service_hours": None, "notes": "Inspect drive belt for wear."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 300, "first_service_hours": None, "notes": "Gas engines only."},
            {"task": "battery_check", "label": "Battery Inspection", "interval_hours": 200, "first_service_hours": None, "notes": "Check battery terminals, voltage, cable condition."},
        ]
    },

    "chainsaw": {
        "label": "Chainsaw",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil (2-Stroke Premix)", "interval_hours": 0, "first_service_hours": None, "notes": "2-stroke: use correct fuel:oil ratio (typically 50:1) with every fill. No oil changes needed."},
            {"task": "chain_sharpening", "label": "Chain Sharpening", "interval_hours": 5, "first_service_hours": None, "notes": "Sharpen with every refueling or when cutting efficiency drops."},
            {"task": "chain_tension", "label": "Chain Tension Adjustment", "interval_hours": 2, "first_service_hours": None, "notes": "Check and adjust chain tension frequently, especially when warm."},
            {"task": "air_filter", "label": "Air Filter Cleaning / Replacement", "interval_hours": 10, "first_service_hours": None, "notes": "Clean after every use. Replace every 50-100 hours."},
            {"task": "bar_inspection", "label": "Guide Bar Inspection / Dressing", "interval_hours": 25, "first_service_hours": None, "notes": "Inspect for wear, burrs. Dress bar rails with flat file. Flip bar periodically."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Replace annually or at 100 hours."},
            {"task": "fuel_filter", "label": "Fuel Filter Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Replace in-tank fuel filter."},
            {"task": "sprocket_inspection", "label": "Drive Sprocket Inspection", "interval_hours": 50, "first_service_hours": None, "notes": "Replace sprocket every 2 chains or when wear exceeds 0.5mm."},
        ]
    },

    "other": {
        "label": "Other Equipment (Trimmers, Edgers, Generators, Pumps, Overseeders, Sod Cutters)",
        "tasks": [
            {"task": "engine_oil_change", "label": "Engine Oil Change", "interval_hours": 50, "first_service_hours": 5, "notes": "Standard interval. 2-stroke engines use premix instead."},
            {"task": "air_filter", "label": "Air Filter Inspection / Replacement", "interval_hours": 50, "first_service_hours": None, "notes": "Clean regularly, replace every 50-100 hours depending on dust."},
            {"task": "spark_plug", "label": "Spark Plug Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Replace annually or every 100 hours."},
            {"task": "fuel_filter", "label": "Fuel Filter Replacement", "interval_hours": 100, "first_service_hours": None, "notes": "Replace in-line or in-tank fuel filter."},
            {"task": "grease_points", "label": "Grease / Lubrication", "interval_hours": 50, "first_service_hours": None, "notes": "Lubricate all moving parts per manufacturer recommendation."},
            {"task": "blade_inspection", "label": "Blade / Cutting Element Inspection", "interval_hours": 25, "first_service_hours": None, "notes": "Inspect and sharpen or replace cutting elements as needed."},
            {"task": "belt_inspection", "label": "Belt / Drive Inspection", "interval_hours": 100, "first_service_hours": None, "notes": "Check drive mechanism for wear and proper tension."},
            {"task": "general_inspection", "label": "General Safety Inspection", "interval_hours": 50, "first_service_hours": None, "notes": "Check guards, switches, handles, controls, fasteners."},
        ]
    },
}


# ---------------------------------------------------------------------------
# Equipment sub-type labels (for UI display)
# ---------------------------------------------------------------------------

EQUIPMENT_SUB_TYPES = {
    "mower_reel": [
        ("greens_walk", "Walk-Behind Greens Mower"),
        ("greens_riding", "Riding Greens Mower (Triplex)"),
        ("fairway", "Fairway Reel Mower"),
        ("rough", "Rough Reel Mower"),
        ("trim", "Trim & Surround Reel Mower"),
    ],
    "mower_rotary": [
        ("walk_behind", "Walk-Behind Rotary Mower"),
        ("rough", "Rotary Rough Mower"),
        ("fairway", "Rotary Fairway Mower"),
        ("trim", "Rotary Trim Mower"),
        ("robotic", "Robotic Mower"),
    ],
    "sprayer": [
        ("ride_on", "Ride-On Sprayer"),
        ("tow_behind", "Tow-Behind Sprayer"),
        ("precision", "Precision / GPS Sprayer"),
        ("backpack", "Backpack Sprayer"),
    ],
    "aerifier": [
        ("walk_behind", "Walk-Behind Core Aerator"),
        ("stand_on", "Stand-On Core Aerator"),
        ("tractor_mounted", "Tractor-Mounted Core Aerator"),
        ("deep_tine", "Deep-Tine Aerator"),
        ("core_processor", "Core Processor"),
    ],
    "topdresser": [
        ("broadcast", "Broadcast Topdresser"),
        ("drop", "Drop Topdresser"),
        ("material_handler", "Material Handler / Large-Area Topdresser"),
    ],
    "utility_vehicle": [
        ("light_duty", "Light-Duty Utility Vehicle"),
        ("medium_duty", "Medium-Duty Utility Vehicle"),
        ("heavy_duty", "Heavy-Duty Utility Vehicle"),
        ("tractor_utility", "Tractor-Utility Vehicle"),
        ("golf_car", "Golf Car / Fleet Vehicle"),
        ("compact_tractor", "Compact Tractor"),
        ("specialty", "Specialty Vehicle"),
    ],
    "roller": [
        ("greens", "Greens Roller"),
        ("fairway", "Fairway Roller"),
    ],
    "verticutter": [
        ("walk_behind", "Walk-Behind Verticutter"),
        ("ride_on", "Ride-On Verticutter"),
        ("tractor_mounted", "Tractor-Mounted Verticutter"),
        ("sand_injection", "Sand Injection Verticutter"),
    ],
    "blower": [
        ("backpack", "Backpack Blower"),
        ("handheld", "Handheld Blower"),
        ("walk_behind", "Walk-Behind Blower"),
        ("pto_mounted", "PTO-Mounted Blower"),
        ("tow_behind", "Tow-Behind Blower"),
    ],
    "bunker_rake": [
        ("standard", "Standard Bunker Rake"),
        ("zero_turn", "Zero-Turn Bunker Rake"),
        ("heavy_duty", "Heavy-Duty Bunker Rake"),
    ],
    "chainsaw": [
        ("professional", "Professional Chainsaw"),
    ],
    "other": [
        ("trimmer", "String Trimmer / Brushcutter"),
        ("hedge_trimmer", "Hedge Trimmer"),
        ("edger", "Lawn Edger"),
        ("generator", "Generator"),
        ("pump", "Water Pump"),
        ("overseeder", "Overseeder"),
        ("sod_cutter", "Sod Cutter"),
        ("sweeper", "Turf Sweeper"),
        ("vacuum", "Lawn / Leaf Vacuum"),
    ],
}


# ---------------------------------------------------------------------------
# Helper: get models for a specific manufacturer
# ---------------------------------------------------------------------------

def get_models_by_manufacturer(manufacturer_id):
    """Return all equipment models for a given manufacturer."""
    return [m for m in EQUIPMENT_MODELS if m["manufacturer"] == manufacturer_id]


def get_models_by_type(equipment_type):
    """Return all equipment models for a given equipment type."""
    return [m for m in EQUIPMENT_MODELS if m["equipment_type"] == equipment_type]


def get_service_tasks(equipment_type):
    """Return the service interval tasks for a given equipment type."""
    return SERVICE_INTERVALS.get(equipment_type, SERVICE_INTERVALS["other"])


def get_all_manufacturer_names():
    """Return a list of (id, name) tuples for all manufacturers."""
    return [(m["id"], m["name"]) for m in MANUFACTURERS]


def search_models(query):
    """Search equipment models by manufacturer name, model name, or description."""
    query_lower = query.lower()
    results = []
    for model in EQUIPMENT_MODELS:
        if (query_lower in model.get("model", "").lower() or
            query_lower in model.get("manufacturer", "").lower() or
            query_lower in model.get("description", "").lower() or
            query_lower in model.get("equipment_type", "").lower() or
            query_lower in model.get("sub_type", "").lower()):
            results.append(model)
    return results
