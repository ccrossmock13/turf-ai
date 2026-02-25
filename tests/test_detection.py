"""Tests for detection.py — grass type, region, and product need detection."""

import pytest
from detection import detect_grass_type, detect_region, detect_product_need


# ── Grass Type Detection ──

class TestDetectGrassType:
    def test_bentgrass(self):
        assert detect_grass_type("Heritage rate for bentgrass greens") == "bentgrass"

    def test_bentgrass_variant(self):
        assert detect_grass_type("creeping bent fairways") == "bentgrass"

    def test_bermuda(self):
        assert detect_grass_type("bermuda fairways spring transition") == "bermudagrass"

    def test_bermudagrass_full(self):
        assert detect_grass_type("bermudagrass scalping in spring") == "bermudagrass"

    def test_poa_annua(self):
        assert detect_grass_type("poa annua control on greens") == "poa annua"

    def test_poa_short(self):
        assert detect_grass_type("poa greens summer stress") == "poa annua"

    def test_kentucky_bluegrass(self):
        assert detect_grass_type("kentucky bluegrass lawn care") == "kentucky bluegrass"

    def test_kbg_abbreviation(self):
        assert detect_grass_type("KBG fairway renovation") == "kentucky bluegrass"

    def test_tall_fescue(self):
        assert detect_grass_type("tall fescue brown patch treatment") == "tall fescue"

    def test_zoysia(self):
        assert detect_grass_type("zoysia maintenance tips") == "zoysiagrass"

    def test_ryegrass(self):
        assert detect_grass_type("perennial ryegrass overseed rate") == "perennial ryegrass"

    def test_no_grass(self):
        assert detect_grass_type("what fungicide for dollar spot?") is None

    def test_empty_string(self):
        assert detect_grass_type("") is None


# ── Region Detection ──

class TestDetectRegion:
    def test_northeast(self):
        assert detect_region("golf course in connecticut") == "northeast"

    def test_southeast(self):
        assert detect_region("bermuda turf in georgia") == "southeast"

    def test_midwest(self):
        assert detect_region("lawn care in ohio") == "midwest"

    def test_southwest(self):
        assert detect_region("turf management in texas") == "southwest"

    def test_west(self):
        assert detect_region("california golf course irrigation") == "west"

    def test_no_region(self):
        assert detect_region("how to control dollar spot") is None


# ── Product Need Detection ──

class TestDetectProductNeed:
    def test_fungicide_from_disease(self):
        assert detect_product_need("dollar spot on my greens") == "fungicide"

    def test_fungicide_from_keyword(self):
        assert detect_product_need("what fungicide should I use") == "fungicide"

    def test_herbicide_from_weed(self):
        assert detect_product_need("crabgrass in my fairways") == "herbicide"

    def test_herbicide_from_keyword(self):
        assert detect_product_need("best pre-emergent herbicide") == "herbicide"

    def test_insecticide(self):
        assert detect_product_need("grub damage on fairways") == "insecticide"

    def test_pgr(self):
        assert detect_product_need("primo growth regulator rate") == "pgr"

    def test_no_product(self):
        assert detect_product_need("how to aerate greens") is None

    def test_empty(self):
        assert detect_product_need("") is None

    def test_disease_priority_over_weed(self):
        # Disease keywords checked first
        assert detect_product_need("brown patch and crabgrass") == "fungicide"
