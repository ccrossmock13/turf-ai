"""
Comprehensive tests for the turf_intelligence module and all enhanced modules.

Tests cover:
- Seasonal/GDD awareness (calculate_gdd, estimate_season_gdd, build_seasonal_context)
- Dynamic model routing (select_model)
- FRAC rotation enforcement (get_frac_code, check_frac_rotation, build_frac_rotation_context)
- Follow-up question generation (generate_follow_up_suggestions)
- Knowledge gap transparency (assess_knowledge_gaps)
- Weather spray windows (assess_spray_window, build_weather_spray_context)
- Photo diagnosis pipeline (build_diagnostic_context)
- Cultivar recommendations (get_cultivar_context)
- Cross-module intelligence (build_cross_module_context)
- Tank mix compatibility (check_tank_mix_compatibility)
- Regional disease pressure (get_regional_disease_pressure, get_turfgrass_zone)
- Cost per application (calculate_cost_per_application, build_cost_context)
- Predictive alerts (generate_predictive_alerts)
- Community knowledge loop (process_community_feedback, log_knowledge_gap)
- Updated query_expansion (acronyms, expanded products)
- Updated scoring_service (question-type multipliers, diversity, credibility)
- Updated answer_grounding (domain-specific validation)
"""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("PINECONE_API_KEY", "test-key-not-real")
os.environ.setdefault("DEMO_MODE", "true")


# =====================================================================
# 1. SEASONAL / GDD AWARENESS
# =====================================================================

class TestGDDCalculation:
    def test_calculate_gdd_basic(self):
        from turf_intelligence import calculate_gdd
        # Average of 80 and 60 = 70, minus base 50 = 20 GDD
        assert calculate_gdd(80, 60, 50) == 20.0

    def test_calculate_gdd_cold_day(self):
        from turf_intelligence import calculate_gdd
        # Average of 40 and 30 = 35, minus base 50 = negative → clamped to 0
        assert calculate_gdd(40, 30, 50) == 0.0

    def test_calculate_gdd_exact_base(self):
        from turf_intelligence import calculate_gdd
        # Average of 60 and 40 = 50, minus base 50 = 0
        assert calculate_gdd(60, 40, 50) == 0.0

    def test_calculate_gdd_hot_day(self):
        from turf_intelligence import calculate_gdd
        # Average of 100 and 80 = 90, minus base 50 = 40
        assert calculate_gdd(100, 80, 50) == 40.0

    def test_calculate_gdd_different_base(self):
        from turf_intelligence import calculate_gdd
        # Average of 70 and 50 = 60, minus base 32 = 28
        assert calculate_gdd(70, 50, 32) == 28.0


class TestEstimateSeasonGDD:
    def test_winter_gdd_cool_season(self):
        from turf_intelligence import estimate_season_gdd
        gdd = estimate_season_gdd(1, 15, 'cool_season')
        assert gdd == 0  # January in cool-season should be ~0

    def test_summer_gdd_warm_season(self):
        from turf_intelligence import estimate_season_gdd
        gdd = estimate_season_gdd(7, 15, 'warm_season')
        assert gdd > 1000  # Should be substantial by July

    def test_gdd_increases_through_year(self):
        from turf_intelligence import estimate_season_gdd
        jan = estimate_season_gdd(1, 15, 'cool_season')
        apr = estimate_season_gdd(4, 15, 'cool_season')
        jul = estimate_season_gdd(7, 15, 'cool_season')
        assert jan <= apr <= jul

    def test_warm_season_more_gdd_than_cool(self):
        from turf_intelligence import estimate_season_gdd
        cool = estimate_season_gdd(6, 15, 'cool_season')
        warm = estimate_season_gdd(6, 15, 'warm_season')
        assert warm > cool


class TestTurfgrassZone:
    def test_cool_season_state(self):
        from turf_intelligence import get_turfgrass_zone
        assert get_turfgrass_zone('michigan') == 'cool_season'

    def test_warm_season_state(self):
        from turf_intelligence import get_turfgrass_zone
        assert get_turfgrass_zone('florida') == 'warm_season'

    def test_transition_state(self):
        from turf_intelligence import get_turfgrass_zone
        assert get_turfgrass_zone('virginia') == 'transition'

    def test_unknown_state(self):
        from turf_intelligence import get_turfgrass_zone
        assert get_turfgrass_zone('narnia') is None

    def test_none_state(self):
        from turf_intelligence import get_turfgrass_zone
        assert get_turfgrass_zone(None) is None

    def test_case_insensitive(self):
        from turf_intelligence import get_turfgrass_zone
        assert get_turfgrass_zone('FLORIDA') == 'warm_season'


class TestBuildSeasonalContext:
    def test_basic_context(self):
        from turf_intelligence import build_seasonal_context
        ctx = build_seasonal_context(month=7, day=15, state='ohio')
        assert 'SEASONAL CONTEXT' in ctx
        assert 'Summer' in ctx or 'summer' in ctx.lower()

    def test_transition_zone_note(self):
        from turf_intelligence import build_seasonal_context
        ctx = build_seasonal_context(month=6, day=15, state='virginia')
        assert 'Transition' in ctx

    def test_winter_context(self):
        from turf_intelligence import build_seasonal_context
        ctx = build_seasonal_context(month=1, day=15, state='michigan')
        assert 'winter' in ctx.lower() or 'Winter' in ctx

    def test_gdd_included(self):
        from turf_intelligence import build_seasonal_context
        ctx = build_seasonal_context(month=6, day=15)
        assert 'GDD' in ctx

    def test_disease_pressure_included(self):
        from turf_intelligence import build_seasonal_context
        ctx = build_seasonal_context(month=7, day=15)
        assert 'Disease Pressure' in ctx or 'disease' in ctx.lower()


# =====================================================================
# 2. DYNAMIC MODEL ROUTING
# =====================================================================

class TestSelectModel:
    def test_simple_rate_question(self):
        from turf_intelligence import select_model
        result = select_model("What is the rate for Heritage?")
        assert result['model'] == 'gpt-4o-mini'
        assert result['reason'] == 'simple_lookup'

    def test_complex_diagnosis(self):
        from turf_intelligence import select_model
        result = select_model("Help me diagnose brown patches appearing on my bentgrass greens")
        assert result['model'] == 'gpt-4o'
        assert result['reason'] == 'complex_query'

    def test_strategy_question(self):
        from turf_intelligence import select_model
        result = select_model("What's the best resistance management program for dollar spot?")
        assert result['model'] == 'gpt-4o'

    def test_short_simple_question(self):
        from turf_intelligence import select_model
        result = select_model("Heritage rate?")
        assert result['model'] == 'gpt-4o-mini'

    def test_image_question(self):
        from turf_intelligence import select_model
        result = select_model("Can you diagnose from this photo?")
        assert result['model'] == 'gpt-4o'
        assert result['reason'] == 'image_diagnosis'

    def test_intent_overrides(self):
        from turf_intelligence import select_model
        intent = {'type': 'rate', 'wants_rate': True, 'wants_diagnosis': False}
        result = select_model("How much do I use?", intent=intent)
        assert result['model'] == 'gpt-4o-mini'

    def test_returns_all_fields(self):
        from turf_intelligence import select_model
        result = select_model("What rate for Daconil?")
        assert 'model' in result
        assert 'reason' in result
        assert 'max_tokens' in result
        assert 'temperature' in result
        assert isinstance(result['max_tokens'], int)
        assert isinstance(result['temperature'], float)


# =====================================================================
# 3. FRAC CODE ROTATION
# =====================================================================

class TestFRACCode:
    def test_known_product(self):
        from turf_intelligence import get_frac_code
        assert get_frac_code('heritage') == 'FRAC11'

    def test_dmi_product(self):
        from turf_intelligence import get_frac_code
        assert get_frac_code('banner maxx') == 'FRAC3'

    def test_sdhi_product(self):
        from turf_intelligence import get_frac_code
        assert get_frac_code('xzemplar') == 'FRAC7'

    def test_unknown_product(self):
        from turf_intelligence import get_frac_code
        assert get_frac_code('not-a-real-product') is None

    def test_contact_fungicide(self):
        from turf_intelligence import get_frac_code
        assert get_frac_code('daconil') == 'FRACM5'

    def test_case_insensitive(self):
        from turf_intelligence import get_frac_code
        assert get_frac_code('Heritage') == 'FRAC11'


class TestFRACRotation:
    def test_no_user_returns_compliant(self):
        from turf_intelligence import check_frac_rotation
        result = check_frac_rotation(user_id=99999)
        assert result['compliant'] is True

    def test_returns_expected_keys(self):
        from turf_intelligence import check_frac_rotation
        result = check_frac_rotation(user_id=1)
        assert 'compliant' in result
        assert 'recent_frac_codes' in result
        assert 'warning' in result
        assert 'suggestion' in result


# =====================================================================
# 4. FOLLOW-UP SUGGESTIONS
# =====================================================================

class TestFollowUpSuggestions:
    def test_disease_follow_ups(self):
        from turf_intelligence import generate_follow_up_suggestions
        suggestions = generate_follow_up_suggestions(
            "What fungicide for dollar spot?",
            "Use Heritage at 0.4 oz/1000...",
            intent={'type': 'disease'},
            disease='dollar spot'
        )
        assert len(suggestions) >= 2
        assert len(suggestions) <= 3
        assert all(isinstance(s, str) for s in suggestions)

    def test_product_follow_ups(self):
        from turf_intelligence import generate_follow_up_suggestions
        suggestions = generate_follow_up_suggestions(
            "What is the rate for Heritage?",
            "Heritage rate is 0.2-0.4 oz...",
            intent={'type': 'rate'},
            product='heritage'
        )
        assert len(suggestions) >= 2

    def test_no_duplicate_of_original(self):
        from turf_intelligence import generate_follow_up_suggestions
        suggestions = generate_follow_up_suggestions(
            "What is the rate for Heritage?",
            "Heritage rate is...",
            intent={'type': 'rate'},
            product='heritage'
        )
        for s in suggestions:
            assert s.lower() != "what is the rate for heritage?"

    def test_general_follow_ups(self):
        from turf_intelligence import generate_follow_up_suggestions
        suggestions = generate_follow_up_suggestions(
            "How do I manage my greens?",
            "For bentgrass greens...",
            intent={'type': 'general'},
        )
        assert len(suggestions) >= 2

    def test_cost_question_added_for_products(self):
        from turf_intelligence import generate_follow_up_suggestions
        suggestions = generate_follow_up_suggestions(
            "What fungicide for brown patch?",
            "Use Daconil...",
            intent={'type': 'disease'},
            product='daconil',
            disease='brown patch'
        )
        cost_suggestions = [s for s in suggestions if 'cost' in s.lower()]
        assert len(cost_suggestions) >= 1 or len(suggestions) == 3  # may be capped


# =====================================================================
# 5. KNOWLEDGE GAP TRANSPARENCY
# =====================================================================

class TestKnowledgeGaps:
    def test_no_sources_is_major_gap(self):
        from turf_intelligence import assess_knowledge_gaps
        result = assess_knowledge_gaps(sources=[], confidence=50, question="What about X?")
        assert result['has_gaps'] is True
        assert result['severity'] == 'major'
        assert result['message'] is not None

    def test_low_confidence_is_major_gap(self):
        from turf_intelligence import assess_knowledge_gaps
        sources = [{'name': 'test.pdf'}]
        result = assess_knowledge_gaps(sources=sources, confidence=30, question="What about X?")
        assert result['has_gaps'] is True
        assert result['severity'] == 'major'

    def test_few_sources_low_confidence_is_minor(self):
        from turf_intelligence import assess_knowledge_gaps
        sources = [{'name': 'a.pdf'}, {'name': 'b.pdf'}]
        result = assess_knowledge_gaps(sources=sources, confidence=55, question="What about X?")
        assert result['has_gaps'] is True
        assert result['severity'] == 'minor'

    def test_good_sources_no_gap(self):
        from turf_intelligence import assess_knowledge_gaps
        sources = [{'name': f'source{i}.pdf'} for i in range(5)]
        result = assess_knowledge_gaps(sources=sources, confidence=85, question="What rate?")
        assert result['has_gaps'] is False
        assert result['severity'] == 'none'

    def test_complex_question_short_context(self):
        from turf_intelligence import assess_knowledge_gaps
        sources = [{'name': 'a.pdf'}]
        long_q = "How do I develop a comprehensive integrated pest management program for dollar spot on bentgrass greens in transition zone?"
        result = assess_knowledge_gaps(sources=sources, confidence=70, question=long_q, context="Short.")
        assert result['has_gaps'] is True


# =====================================================================
# 6. WEATHER SPRAY WINDOWS
# =====================================================================

class TestSprayWindow:
    def test_good_conditions(self):
        from turf_intelligence import assess_spray_window
        result = assess_spray_window({
            'temp': 75, 'wind_speed': 5, 'humidity': 50, 'rain_chance': 10
        })
        assert result['quality'] == 'good'
        assert result['phytotoxicity_risk'] is False

    def test_high_wind_is_poor(self):
        from turf_intelligence import assess_spray_window
        result = assess_spray_window({
            'temp': 75, 'wind_speed': 18, 'humidity': 50, 'rain_chance': 10
        })
        assert result['quality'] == 'poor'
        assert any('wind' in r.lower() for r in result['reasons'])

    def test_high_rain_chance_is_poor(self):
        from turf_intelligence import assess_spray_window
        result = assess_spray_window({
            'temp': 75, 'wind_speed': 5, 'humidity': 50, 'rain_chance': 70
        })
        assert result['quality'] == 'poor'

    def test_high_temp_phytotoxicity(self):
        from turf_intelligence import assess_spray_window
        result = assess_spray_window({
            'temp': 95, 'wind_speed': 5, 'humidity': 50, 'rain_chance': 10
        })
        assert result['phytotoxicity_risk'] is True
        assert result['quality'] == 'marginal'

    def test_marginal_wind(self):
        from turf_intelligence import assess_spray_window
        result = assess_spray_window({
            'temp': 75, 'wind_speed': 12, 'humidity': 50, 'rain_chance': 10
        })
        assert result['quality'] == 'marginal'

    def test_no_weather_data(self):
        from turf_intelligence import assess_spray_window
        result = assess_spray_window(None)
        assert result['quality'] == 'unknown'

    def test_recommendations_provided(self):
        from turf_intelligence import assess_spray_window
        result = assess_spray_window({
            'temp': 92, 'wind_speed': 14, 'humidity': 50, 'rain_chance': 40
        })
        assert len(result['recommendations']) > 0

    def test_build_spray_context(self):
        from turf_intelligence import build_weather_spray_context
        ctx = build_weather_spray_context({
            'temp': 75, 'wind_speed': 5, 'humidity': 50, 'rain_chance': 10
        })
        assert 'SPRAY CONDITIONS' in ctx
        assert 'GOOD' in ctx


# =====================================================================
# 7. DIAGNOSTIC CONTEXT
# =====================================================================

class TestDiagnosticContext:
    def test_build_diagnostic_context(self):
        from turf_intelligence import build_diagnostic_context
        ctx = build_diagnostic_context()
        assert 'DIAGNOSTIC REFERENCE' in ctx
        assert 'Dollar Spot' in ctx
        assert 'Brown Patch' in ctx
        assert 'Pythium' in ctx

    def test_contains_visual_descriptions(self):
        from turf_intelligence import build_diagnostic_context
        ctx = build_diagnostic_context()
        assert 'Visual:' in ctx
        assert 'Conditions:' in ctx
        assert 'Key Diagnostic:' in ctx

    def test_contains_approach(self):
        from turf_intelligence import build_diagnostic_context
        ctx = build_diagnostic_context()
        assert 'DIAGNOSTIC APPROACH' in ctx


# =====================================================================
# 8. CULTIVAR RECOMMENDATIONS
# =====================================================================

class TestCultivarContext:
    def test_bentgrass_cultivar(self):
        from turf_intelligence import get_cultivar_context
        ctx = get_cultivar_context('bentgrass', 'Penncross')
        assert 'Penncross' in ctx
        assert 'dollar_spot' in ctx.lower() or 'Dollar Spot' in ctx

    def test_bermuda_cultivars(self):
        from turf_intelligence import get_cultivar_context
        ctx = get_cultivar_context('bermudagrass')
        assert 'TifEagle' in ctx or 'MiniVerde' in ctx

    def test_disease_specific_context(self):
        from turf_intelligence import get_cultivar_context
        ctx = get_cultivar_context('bentgrass', disease='dollar spot')
        assert 'dollar' in ctx.lower()

    def test_unknown_grass_type(self):
        from turf_intelligence import get_cultivar_context
        ctx = get_cultivar_context('buffalograss')
        assert ctx == ''

    def test_no_grass_type(self):
        from turf_intelligence import get_cultivar_context
        ctx = get_cultivar_context(None)
        assert ctx == ''

    def test_unknown_cultivar_falls_back(self):
        from turf_intelligence import get_cultivar_context
        ctx = get_cultivar_context('bentgrass', 'FakeVariety123')
        assert 'not in database' in ctx.lower() or 'general' in ctx.lower() or 'FakeVariety123' in ctx


# =====================================================================
# 9. CROSS-MODULE INTELLIGENCE
# =====================================================================

class TestCrossModuleContext:
    def test_no_user_returns_empty(self):
        from turf_intelligence import build_cross_module_context
        ctx = build_cross_module_context(None, "What fungicide for dollar spot?")
        assert ctx == ''

    def test_returns_string(self):
        from turf_intelligence import build_cross_module_context
        ctx = build_cross_module_context(1, "What fungicide for dollar spot?")
        assert isinstance(ctx, str)


# =====================================================================
# 10. TANK MIX COMPATIBILITY
# =====================================================================

class TestTankMixCompatibility:
    def test_compatible_pair(self):
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility(['Heritage', 'Daconil'])
        assert result['overall'] == 'compatible'

    def test_caution_pair(self):
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility(['Banner Maxx', 'Daconil'])
        assert result['overall'] == 'caution'
        assert len(result['warnings']) > 0

    def test_incompatible_pair(self):
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility(['Prodiamine', 'Dimension'])
        assert result['overall'] == 'incompatible'

    def test_single_product(self):
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility(['Heritage'])
        assert result['overall'] == 'compatible'

    def test_empty_list(self):
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility([])
        assert result['overall'] == 'compatible'

    def test_unknown_pair(self):
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility(['UnknownProduct1', 'UnknownProduct2'])
        assert result['overall'] == 'compatible'  # unknown defaults to compatible
        assert any('unknown' in d['status'] for d in result['details'])

    def test_many_products_warning(self):
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility(['Heritage', 'Daconil', 'Primo', 'Banner Maxx'])
        assert any('jar test' in w.lower() for w in result['warnings'])

    def test_three_way_mix(self):
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility(['Heritage', 'Daconil', 'Primo'])
        assert result['overall'] in ('compatible', 'caution', 'incompatible')
        assert len(result['details']) >= 3  # 3 pairs checked


# =====================================================================
# 11. REGIONAL DISEASE PRESSURE
# =====================================================================

class TestRegionalDiseasePressure:
    def test_summer_cool_season(self):
        from turf_intelligence import get_regional_disease_pressure
        result = get_regional_disease_pressure(state='ohio', month=7)
        assert result['zone'] == 'cool_season'
        assert result['season'] == 'summer'
        assert 'dollar spot' in result['active_diseases'] or 'brown patch' in result['active_diseases']

    def test_winter_diseases(self):
        from turf_intelligence import get_regional_disease_pressure
        result = get_regional_disease_pressure(state='michigan', month=12)
        assert result['season'] == 'winter'
        assert any('snow mold' in d for d in result['active_diseases'])

    def test_warm_season_summer(self):
        from turf_intelligence import get_regional_disease_pressure
        result = get_regional_disease_pressure(state='florida', month=7)
        assert result['zone'] == 'warm_season'
        assert len(result['active_diseases']) > 0

    def test_high_risk_subset(self):
        from turf_intelligence import get_regional_disease_pressure
        result = get_regional_disease_pressure(state='ohio', month=7)
        assert len(result['high_risk']) <= len(result['active_diseases'])
        assert len(result['high_risk']) <= 3

    def test_transition_zone(self):
        from turf_intelligence import get_regional_disease_pressure
        result = get_regional_disease_pressure(state='virginia', month=6)
        assert result['zone'] == 'transition'


# =====================================================================
# 12. COST PER APPLICATION
# =====================================================================

class TestCostCalculation:
    def test_known_product(self):
        from turf_intelligence import calculate_cost_per_application
        result = calculate_cost_per_application('heritage')
        assert result is not None
        assert result['cost_per_1000_sqft'] > 0
        assert result['cost_per_acre'] > 0

    def test_unknown_product(self):
        from turf_intelligence import calculate_cost_per_application
        result = calculate_cost_per_application('not-a-product')
        assert result is None

    def test_custom_area(self):
        from turf_intelligence import calculate_cost_per_application
        result_1000 = calculate_cost_per_application('heritage', area_sqft=1000)
        result_5000 = calculate_cost_per_application('heritage', area_sqft=5000)
        assert result_5000['cost_for_area'] > result_1000['cost_for_area']
        assert abs(result_5000['cost_for_area'] - result_1000['cost_for_area'] * 5) < 0.01

    def test_custom_rate(self):
        from turf_intelligence import calculate_cost_per_application
        result_low = calculate_cost_per_application('heritage', rate=0.2)
        result_high = calculate_cost_per_application('heritage', rate=0.4)
        assert result_high['cost_per_1000_sqft'] > result_low['cost_per_1000_sqft']

    def test_all_fields_present(self):
        from turf_intelligence import calculate_cost_per_application
        result = calculate_cost_per_application('daconil')
        assert 'product' in result
        assert 'rate' in result
        assert 'rate_unit' in result
        assert 'cost_per_1000_sqft' in result
        assert 'cost_per_acre' in result
        assert 'note' in result

    def test_build_cost_context(self):
        from turf_intelligence import build_cost_context
        ctx = build_cost_context("What is the rate for Heritage?")
        assert 'Heritage' in ctx or 'COST' in ctx

    def test_build_cost_context_no_products(self):
        from turf_intelligence import build_cost_context
        ctx = build_cost_context("How do I aerate my greens?")
        assert ctx == ''

    def test_per_acre_calculation(self):
        from turf_intelligence import calculate_cost_per_application
        result = calculate_cost_per_application('heritage')
        # cost_per_acre should be ~43.56x cost_per_1000
        ratio = result['cost_per_acre'] / result['cost_per_1000_sqft']
        assert abs(ratio - 43.56) < 0.01


# =====================================================================
# 13. PREDICTIVE ALERTS
# =====================================================================

class TestPredictiveAlerts:
    def test_basic_alerts(self):
        from turf_intelligence import generate_predictive_alerts
        alerts = generate_predictive_alerts(
            user_id=1,
            state='ohio',
            grass_type='bentgrass'
        )
        assert isinstance(alerts, list)
        # Should have at least disease pressure alert
        assert len(alerts) >= 1

    def test_pythium_alert_conditions(self):
        from turf_intelligence import generate_predictive_alerts
        alerts = generate_predictive_alerts(
            user_id=1,
            weather_data={'temp': 90, 'humidity': 90, 'wind_speed': 5, 'rain_chance': 20},
            state='ohio',
        )
        pythium_alerts = [a for a in alerts if a['type'] == 'pythium_risk']
        assert len(pythium_alerts) >= 1

    def test_heat_stress_alert(self):
        from turf_intelligence import generate_predictive_alerts
        alerts = generate_predictive_alerts(
            user_id=1,
            weather_data={'temp': 95, 'humidity': 60, 'wind_speed': 5, 'rain_chance': 10},
        )
        heat_alerts = [a for a in alerts if a['type'] == 'heat_stress']
        assert len(heat_alerts) >= 1
        assert heat_alerts[0]['severity'] == 'critical'

    def test_alert_structure(self):
        from turf_intelligence import generate_predictive_alerts
        alerts = generate_predictive_alerts(user_id=1, state='ohio')
        for alert in alerts:
            assert 'type' in alert
            assert 'severity' in alert
            assert 'message' in alert
            assert alert['severity'] in ('info', 'warning', 'critical')


# =====================================================================
# 14. COMMUNITY KNOWLEDGE LOOP
# =====================================================================

class TestCommunityFeedback:
    def test_wrong_rate_feedback(self):
        from turf_intelligence import process_community_feedback
        result = process_community_feedback(
            question="What rate for Heritage?",
            rating='negative',
            correction='Wrong rate - should be 0.2 oz not 0.4 oz',
        )
        assert result['gap_identified'] is True
        assert result['gap_type'] == 'incorrect_rate'

    def test_safety_feedback(self):
        from turf_intelligence import process_community_feedback
        result = process_community_feedback(
            question="What fungicide for bent?",
            rating='negative',
            correction='This product is not safe on bentgrass',
        )
        assert result['gap_identified'] is True
        assert result['gap_type'] == 'safety_issue'

    def test_outdated_feedback(self):
        from turf_intelligence import process_community_feedback
        result = process_community_feedback(
            question="What about Tartan?",
            rating='negative',
            correction='Tartan is discontinued and no longer available',
        )
        assert result['gap_identified'] is True
        assert result['gap_type'] == 'stale_data'

    def test_positive_feedback_no_gap(self):
        from turf_intelligence import process_community_feedback
        result = process_community_feedback(
            question="What rate?",
            rating='positive',
            correction='',
        )
        assert result['gap_identified'] is False

    def test_no_correction_no_gap(self):
        from turf_intelligence import process_community_feedback
        result = process_community_feedback(
            question="What rate?",
            rating='negative',
            correction='',
        )
        assert result['gap_identified'] is False


# =====================================================================
# 15. UPDATED QUERY EXPANSION (Acronyms + Products)
# =====================================================================

class TestQueryExpansionUpdated:
    def test_acronym_expansion_pgr(self):
        from query_expansion import expand_query
        result = expand_query("What PGR should I use?")
        assert 'plant growth regulator' in result.lower()

    def test_acronym_expansion_gdd(self):
        from query_expansion import expand_query
        result = expand_query("When to apply based on GDD?")
        assert 'growing degree days' in result.lower()

    def test_acronym_expansion_abw(self):
        from query_expansion import expand_query
        result = expand_query("How to control ABW?")
        assert 'annual bluegrass weevil' in result.lower()

    def test_acronym_expansion_frac(self):
        from query_expansion import expand_query
        result = expand_query("What FRAC group is Heritage?")
        assert 'fungicide resistance action committee' in result.lower()

    def test_acronym_expansion_ipm(self):
        from query_expansion import expand_query
        result = expand_query("IPM for dollar spot")
        assert 'integrated pest management' in result.lower()

    def test_new_product_expansion(self):
        from query_expansion import expand_query
        result = expand_query("What about revysol?")
        assert 'mefentrifluconazole' in result.lower()

    def test_biological_product(self):
        from query_expansion import expand_query
        result = expand_query("Can I use rhapsody?")
        assert 'bacillus subtilis' in result.lower()

    def test_expanded_product_list(self):
        from query_expansion import SYNONYMS
        # Check new products are in the synonym list
        assert 'appear' in SYNONYMS
        assert 'revysol' in SYNONYMS
        assert 'compass' in SYNONYMS
        assert 'disarm' in SYNONYMS
        assert 'rhapsody' in SYNONYMS

    def test_acronym_dict_exists(self):
        from query_expansion import ACRONYMS
        assert len(ACRONYMS) >= 30
        assert 'pgr' in ACRONYMS
        assert 'gdd' in ACRONYMS
        assert 'et' in ACRONYMS


# =====================================================================
# 16. UPDATED SCORING SERVICE
# =====================================================================

class TestScoringServiceUpdated:
    def test_question_type_boost_function_exists(self):
        from scoring_service import _apply_question_type_boost
        score = _apply_question_type_boost(1.0, "Rate: 0.4 oz/1000 sq ft", "what is the rate for heritage")
        assert score > 1.0  # Should be boosted for rate question with rate content

    def test_rate_content_boosted(self):
        from scoring_service import _apply_question_type_boost
        # Text with rate info should be boosted for rate questions
        text_with_rate = "Apply at 0.4 oz per 1000 sq ft on 14-day intervals"
        text_without_rate = "Heritage is a strobilurin fungicide for disease control"
        score_with = _apply_question_type_boost(1.0, text_with_rate, "what is the rate")
        score_without = _apply_question_type_boost(1.0, text_without_rate, "what is the rate")
        assert score_with > score_without

    def test_source_credibility_high(self):
        from scoring_service import _apply_source_credibility
        score = _apply_source_credibility(1.0, "Purdue University Extension Publication")
        assert score > 1.0

    def test_source_credibility_low(self):
        from scoring_service import _apply_source_credibility
        score = _apply_source_credibility(1.0, "General Catalog Brochure")
        assert score < 1.0

    def test_source_credibility_neutral(self):
        from scoring_service import _apply_source_credibility
        score = _apply_source_credibility(1.0, "some-random-document.pdf")
        assert score == 1.0

    def test_diversity_penalty_basic(self):
        from scoring_service import _apply_diversity_penalty
        # Create results with same source
        results = [
            {'text': f'text{i}', 'source': 'same-source.pdf', 'score': 10.0 - i, 'metadata': {}}
            for i in range(10)
        ]
        penalized = _apply_diversity_penalty(results)
        # Second occurrence should have lower score than without penalty
        assert penalized[1]['score'] < 10.0  # Should be penalized

    def test_diversity_preserves_different_sources(self):
        from scoring_service import _apply_diversity_penalty
        results = [
            {'text': f'text{i}', 'source': f'source-{i}.pdf', 'score': 10.0 - i, 'metadata': {}}
            for i in range(5)
        ]
        penalized = _apply_diversity_penalty(results)
        # All different sources — no penalties applied
        for i in range(5):
            assert penalized[i]['score'] == results[i]['score']


# =====================================================================
# 17. UPDATED ANSWER GROUNDING
# =====================================================================

class TestAnswerGroundingUpdated:
    def test_domain_validation_reasonable_rate(self):
        from answer_grounding import validate_domain_specific
        result = validate_domain_specific("Apply Heritage at 0.4 oz per 1000 sq ft")
        assert result['valid'] is True
        assert len(result['issues']) == 0

    def test_domain_validation_high_rate(self):
        from answer_grounding import validate_domain_specific
        result = validate_domain_specific("Apply at 50 oz per 1000 sq ft")
        assert len(result['issues']) > 0 or len(result['warnings']) > 0

    def test_domain_validation_glyphosate_warning(self):
        from answer_grounding import validate_domain_specific
        result = validate_domain_specific("Apply glyphosate to the active green for weed control")
        assert len(result['issues']) > 0

    def test_domain_validation_normal_answer(self):
        from answer_grounding import validate_domain_specific
        result = validate_domain_specific(
            "For dollar spot control on bentgrass greens, Heritage provides excellent control. "
            "Rotate with FRAC 7 products like Xzemplar for resistance management."
        )
        assert result['valid'] is True

    def test_domain_validation_returns_structure(self):
        from answer_grounding import validate_domain_specific
        result = validate_domain_specific("Any text")
        assert 'valid' in result
        assert 'warnings' in result
        assert 'issues' in result
        assert isinstance(result['warnings'], list)
        assert isinstance(result['issues'], list)

    def test_excessive_nitrogen(self):
        from answer_grounding import validate_domain_specific
        result = validate_domain_specific("Apply 50 lb nitrogen per 1000 sq ft for green-up")
        assert len(result['issues']) > 0


# =====================================================================
# 18. UPDATED CONSTANTS
# =====================================================================

class TestUpdatedConstants:
    def test_expanded_insecticides(self):
        from constants import INSECTICIDES
        assert len(INSECTICIDES) > 10
        assert 'mainspring' in INSECTICIDES
        assert 'provaunt' in INSECTICIDES

    def test_expanded_pgrs(self):
        from constants import PGRS
        assert 'appear' in PGRS
        assert len(PGRS) > 6

    def test_biologicals_exist(self):
        from constants import BIOLOGICALS
        assert len(BIOLOGICALS) > 0
        assert 'rhapsody' in BIOLOGICALS

    def test_source_credibility_lists(self):
        from constants import SOURCE_CREDIBILITY_HIGH, SOURCE_CREDIBILITY_LOW
        assert 'purdue' in SOURCE_CREDIBILITY_HIGH
        assert 'catalog' in SOURCE_CREDIBILITY_LOW


# =====================================================================
# INTEGRATION TESTS
# =====================================================================

class TestIntegration:
    """Test that modules work together correctly."""

    def test_seasonal_context_with_zone(self):
        """Seasonal context should use turfgrass zone correctly."""
        from turf_intelligence import build_seasonal_context, get_turfgrass_zone
        zone = get_turfgrass_zone('florida')
        ctx = build_seasonal_context(month=7, state='florida')
        assert 'Warm Season' in ctx

    def test_cost_and_frac_together(self):
        """Cost lookup and FRAC code should work for same product."""
        from turf_intelligence import calculate_cost_per_application, get_frac_code
        cost = calculate_cost_per_application('heritage')
        frac = get_frac_code('heritage')
        assert cost is not None
        assert frac == 'FRAC11'

    def test_disease_pressure_and_season(self):
        """Disease pressure should align with seasonal context."""
        from turf_intelligence import get_regional_disease_pressure, SEASONAL_CONTEXT
        pressure = get_regional_disease_pressure(state='ohio', month=7)
        season_info = SEASONAL_CONTEXT[7]
        # Both should reference summer diseases
        assert pressure['season'] == 'summer'
        assert 'summer' in season_info['season'].lower()

    def test_tank_mix_with_compatibility_data(self):
        """Tank mix check should return structured results."""
        from turf_intelligence import check_tank_mix_compatibility
        result = check_tank_mix_compatibility(['Heritage', 'Primo', 'Daconil'])
        assert 'overall' in result
        assert 'details' in result
        assert len(result['details']) == 3  # 3 pairs from 3 products

    def test_follow_ups_from_intent(self):
        """Follow-up suggestions should adapt to intent type."""
        from turf_intelligence import generate_follow_up_suggestions
        disease_followups = generate_follow_up_suggestions(
            "Dollar spot", "Use Heritage...",
            intent={'type': 'disease'}, disease='dollar spot'
        )
        rate_followups = generate_follow_up_suggestions(
            "Heritage rate", "0.4 oz...",
            intent={'type': 'rate'}, product='heritage'
        )
        # Disease and rate follow-ups should be different
        assert disease_followups != rate_followups

    def test_query_expansion_with_acronyms_and_products(self):
        """Acronyms and product synonyms should both expand in same query."""
        from query_expansion import expand_query
        result = expand_query("What PGR to use with heritage?")
        assert 'plant growth regulator' in result.lower()
        assert 'azoxystrobin' in result.lower()

    def test_model_routing_with_intent(self):
        """Model routing should use intent for better selection."""
        from turf_intelligence import select_model
        from query_expansion import get_query_intent
        # Pure rate question with no chemical/diagnosis ambiguity
        intent = get_query_intent("How much Heritage per 1000 sq ft?")
        assert intent['wants_rate'] is True
        result = select_model("How much Heritage per 1000 sq ft?", intent=intent)
        # Rate question should route to mini model
        assert result['model'] == 'gpt-4o-mini'
