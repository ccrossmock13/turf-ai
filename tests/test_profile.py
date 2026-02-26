"""Tests for course profile improvements — multi-course, new fields, templates, context builder."""

import json
import os
import sys
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('FLASK_SECRET_KEY', 'test')
os.environ.setdefault('OPENAI_API_KEY', 'test')
os.environ.setdefault('PINECONE_API_KEY', 'test')
os.environ.setdefault('PINECONE_INDEX', 'test')

from db import get_db
from profile import (
    save_profile, get_profile, get_profiles, set_active_profile,
    duplicate_profile, delete_profile, get_profile_templates,
    create_from_template, build_profile_context, _unpack_profile,
    PROFILE_TEMPLATES,
)
from climate_data import get_climate_data, calculate_gdd, get_current_season


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_profiles():
    """Delete test profiles before and after each test."""
    with get_db() as conn:
        conn.execute("DELETE FROM course_profiles WHERE user_id = 99999")
        conn.execute("DELETE FROM course_profiles WHERE user_id = 99998")
    yield
    with get_db() as conn:
        conn.execute("DELETE FROM course_profiles WHERE user_id = 99999")
        conn.execute("DELETE FROM course_profiles WHERE user_id = 99998")


USER_ID = 99999


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------

class TestProfileCRUD:
    def test_save_and_get(self):
        save_profile(USER_ID, {'course_name': 'Test Course', 'city': 'Austin', 'state': 'Texas'})
        p = get_profile(USER_ID)
        assert p is not None
        assert p['course_name'] == 'Test Course'
        assert p['city'] == 'Austin'

    def test_upsert_updates(self):
        save_profile(USER_ID, {'course_name': 'Test Course', 'city': 'Austin'})
        save_profile(USER_ID, {'course_name': 'Test Course', 'city': 'Dallas'})
        p = get_profile(USER_ID)
        assert p['city'] == 'Dallas'

    def test_auto_derives_region(self):
        save_profile(USER_ID, {'course_name': 'Test', 'state': 'Texas'})
        p = get_profile(USER_ID)
        assert p['region'] == 'southwest'

    def test_auto_derives_climate_zone(self):
        save_profile(USER_ID, {'course_name': 'Test', 'state': 'Ohio'})
        p = get_profile(USER_ID)
        assert p['climate_zone'] == '5b-6b'

    def test_get_profile_returns_none_for_nonexistent(self):
        assert get_profile(99998) is None

    def test_get_profile_returns_none_for_none_user(self):
        assert get_profile(None) is None


# ---------------------------------------------------------------------------
# New fields round-trip
# ---------------------------------------------------------------------------

class TestNewFields:
    def test_irrigation_schedule_round_trip(self):
        irr = {'system_type': 'overhead', 'run_times': '12 min', 'zones': '18'}
        save_profile(USER_ID, {'course_name': 'Test', 'irrigation_schedule': irr})
        p = get_profile(USER_ID)
        assert p['irrigation_schedule'] == irr

    def test_aerification_program_round_trip(self):
        aer = {'dates': 'April, September', 'tine_type': 'hollow', 'depth': '3"'}
        save_profile(USER_ID, {'course_name': 'Test', 'aerification_program': aer})
        p = get_profile(USER_ID)
        assert p['aerification_program'] == aer

    def test_topdressing_program_round_trip(self):
        td = {'material': 'USGA sand', 'rate': '5 cu ft/1000', 'frequency': 'biweekly'}
        save_profile(USER_ID, {'course_name': 'Test', 'topdressing_program': td})
        p = get_profile(USER_ID)
        assert p['topdressing_program'] == td

    def test_pgr_program_round_trip(self):
        pgr = {'product': 'Primo Maxx', 'rate': '0.125 oz/1000', 'interval': '14 days'}
        save_profile(USER_ID, {'course_name': 'Test', 'pgr_program': pgr})
        p = get_profile(USER_ID)
        assert p['pgr_program'] == pgr

    def test_wetting_agent_round_trip(self):
        wa = {'product': 'Revolution', 'rate': '6 oz/1000', 'interval': 'monthly'}
        save_profile(USER_ID, {'course_name': 'Test', 'wetting_agent_program': wa})
        p = get_profile(USER_ID)
        assert p['wetting_agent_program'] == wa

    def test_maintenance_calendar_round_trip(self):
        cal = {'jan': 'Planning', 'mar': 'Pre-emergent', 'sep': 'Aerification'}
        save_profile(USER_ID, {'course_name': 'Test', 'maintenance_calendar': cal})
        p = get_profile(USER_ID)
        assert p['maintenance_calendar'] == cal

    def test_bunker_sand_round_trip(self):
        bs = {'type': 'SP55', 'depth': '4 inches', 'drainage': 'Billy Bunker liner'}
        save_profile(USER_ID, {'course_name': 'Test', 'bunker_sand': bs})
        p = get_profile(USER_ID)
        assert p['bunker_sand'] == bs


# ---------------------------------------------------------------------------
# Multi-course
# ---------------------------------------------------------------------------

class TestMultiCourse:
    def test_multiple_courses_for_same_user(self):
        save_profile(USER_ID, {'course_name': 'Course A', 'city': 'Austin'})
        save_profile(USER_ID, {'course_name': 'Course B', 'city': 'Dallas'})
        profiles = get_profiles(USER_ID)
        assert len(profiles) == 2
        names = {p['course_name'] for p in profiles}
        assert names == {'Course A', 'Course B'}

    def test_get_active_profile(self):
        save_profile(USER_ID, {'course_name': 'Course A', 'is_active': True})
        save_profile(USER_ID, {'course_name': 'Course B', 'is_active': False})
        p = get_profile(USER_ID)
        assert p['course_name'] == 'Course A'

    def test_set_active_profile(self):
        save_profile(USER_ID, {'course_name': 'Course A'})
        save_profile(USER_ID, {'course_name': 'Course B'})
        set_active_profile(USER_ID, 'Course B')
        p = get_profile(USER_ID)
        assert p['course_name'] == 'Course B'
        assert p['is_active'] == 1

    def test_get_profile_by_name(self):
        save_profile(USER_ID, {'course_name': 'Course A', 'city': 'Austin'})
        save_profile(USER_ID, {'course_name': 'Course B', 'city': 'Dallas'})
        p = get_profile(USER_ID, course_name='Course B')
        assert p['city'] == 'Dallas'

    def test_duplicate_profile(self):
        save_profile(USER_ID, {'course_name': 'Source', 'city': 'Austin', 'state': 'Texas'})
        success = duplicate_profile(USER_ID, 'Source', 'Copy')
        assert success
        p = get_profile(USER_ID, course_name='Copy')
        assert p is not None
        assert p['city'] == 'Austin'
        assert p['course_name'] == 'Copy'

    def test_delete_profile(self):
        save_profile(USER_ID, {'course_name': 'A'})
        save_profile(USER_ID, {'course_name': 'B'})
        success = delete_profile(USER_ID, 'B')
        assert success
        profiles = get_profiles(USER_ID)
        assert len(profiles) == 1

    def test_cannot_delete_last_profile(self):
        save_profile(USER_ID, {'course_name': 'Only One'})
        success = delete_profile(USER_ID, 'Only One')
        assert not success
        profiles = get_profiles(USER_ID)
        assert len(profiles) == 1


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

class TestTemplates:
    def test_list_templates(self):
        templates = get_profile_templates()
        assert len(templates) == 5
        ids = {t['id'] for t in templates}
        assert 'golf_18' in ids
        assert 'sports_field' in ids

    def test_create_from_template(self):
        success = create_from_template(USER_ID, 'golf_18', 'My Golf Course')
        assert success
        p = get_profile(USER_ID, course_name='My Golf Course')
        assert p is not None
        assert p['turf_type'] == 'golf_course'
        assert p['greens_grass'] == 'bentgrass'

    def test_invalid_template(self):
        success = create_from_template(USER_ID, 'nonexistent', 'Test')
        assert not success


# ---------------------------------------------------------------------------
# Context builder — new sections
# ---------------------------------------------------------------------------

class TestContextBuilder:
    def test_basic_context(self):
        save_profile(USER_ID, {
            'course_name': 'Test GC', 'state': 'Ohio', 'role': 'superintendent',
            'turf_type': 'golf_course', 'greens_grass': 'bentgrass'
        })
        ctx = build_profile_context(USER_ID)
        assert 'USER PROFILE' in ctx
        assert 'Superintendent' in ctx
        assert 'bentgrass' in ctx.lower()

    def test_pgr_in_context(self):
        save_profile(USER_ID, {
            'course_name': 'Test', 'pgr_program': {'product': 'Primo Maxx', 'rate': '0.125 oz'}
        })
        ctx = build_profile_context(USER_ID, question_topic='pgr')
        assert 'Primo Maxx' in ctx

    def test_cultural_practices_in_context(self):
        save_profile(USER_ID, {
            'course_name': 'Test',
            'aerification_program': {'dates': 'April', 'tine_type': 'hollow'},
            'topdressing_program': {'material': 'USGA sand'}
        })
        ctx = build_profile_context(USER_ID, question_topic='cultural')
        assert 'Aerification' in ctx
        assert 'Topdressing' in ctx

    def test_irrigation_in_context(self):
        save_profile(USER_ID, {
            'course_name': 'Test',
            'irrigation_schedule': {'system_type': 'overhead', 'run_times': '12 min'}
        })
        ctx = build_profile_context(USER_ID, question_topic='irrigation')
        assert 'overhead' in ctx.lower()

    def test_topic_filtering(self):
        save_profile(USER_ID, {
            'course_name': 'Test',
            'pgr_program': {'product': 'Primo'},
            'aerification_program': {'dates': 'April'},
            'soil_type': 'USGA sand-based'
        })
        # PGR topic should include PGR but not necessarily cultural practices
        pgr_ctx = build_profile_context(USER_ID, question_topic='pgr')
        assert 'Primo' in pgr_ctx

        # Cultural topic should include aerification
        cultural_ctx = build_profile_context(USER_ID, question_topic='cultural')
        assert 'April' in cultural_ctx

    def test_seasonal_awareness(self):
        save_profile(USER_ID, {'course_name': 'Test', 'state': 'Massachusetts'})
        ctx = build_profile_context(USER_ID)
        assert 'SEASON' in ctx

    def test_role_tone_superintendent(self):
        save_profile(USER_ID, {'course_name': 'Test', 'role': 'superintendent'})
        ctx = build_profile_context(USER_ID)
        assert 'concise and direct' in ctx.lower()

    def test_role_tone_student(self):
        save_profile(USER_ID, {'course_name': 'Test', 'role': 'student'})
        ctx = build_profile_context(USER_ID)
        assert 'teaching opportunity' in ctx.lower()

    def test_empty_profile_returns_empty(self):
        assert build_profile_context(None) == ''
        assert build_profile_context(99998) == ''


# ---------------------------------------------------------------------------
# Climate data
# ---------------------------------------------------------------------------

class TestClimateData:
    def test_all_50_states(self):
        from climate_data import STATE_CLIMATE_DATA
        assert len(STATE_CLIMATE_DATA) == 50

    def test_get_climate_data(self):
        data = get_climate_data('texas')
        assert data is not None
        assert 'avg_temps' in data
        assert len(data['avg_temps']) == 12

    def test_case_insensitive(self):
        assert get_climate_data('Texas') is not None
        assert get_climate_data('OHIO') is not None
        assert get_climate_data('new york') is not None

    def test_invalid_state(self):
        assert get_climate_data('narnia') is None
        assert get_climate_data('') is None

    def test_gdd_calculation(self):
        gdd = calculate_gdd(50, [70, 80, 90], [50, 60, 70])
        # (70+50)/2=60-50=10, (80+60)/2=70-50=20, (90+70)/2=80-50=30 → 10+20+30=60
        assert gdd == 60.0

    def test_gdd_with_cold_days(self):
        gdd = calculate_gdd(50, [40, 70], [30, 50])
        # Day 1: (40+30)/2=35, 35-50=-15 → 0. Day 2: (70+50)/2=60, 60-50=10 → 10
        assert gdd == 10.0

    def test_gdd_mismatched_lengths(self):
        with pytest.raises(ValueError):
            calculate_gdd(50, [70, 80], [50])

    def test_current_season_cool(self):
        s = get_current_season('massachusetts', month=7)
        assert s['season'] == 'summer_stress'

    def test_current_season_warm(self):
        s = get_current_season('florida', month=6)
        assert s['season'] == 'active_growth'

    def test_current_season_transition(self):
        s = get_current_season('virginia', month=9)
        assert s['season'] == 'fall_recovery'

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError):
            get_current_season('narnia')


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_old_profile_loads(self):
        """Profiles without new columns should still load with None defaults."""
        save_profile(USER_ID, {
            'course_name': 'Old Course', 'city': 'Austin', 'state': 'Texas',
            'primary_grass': 'bermudagrass'
        })
        p = get_profile(USER_ID)
        assert p['city'] == 'Austin'
        assert p.get('irrigation_schedule') is None
        assert p.get('pgr_program') is None
        assert p.get('maintenance_calendar') is None

    def test_get_profile_still_returns_active(self):
        """get_profile(user_id) without course_name returns the active one."""
        save_profile(USER_ID, {'course_name': 'My Course', 'city': 'Austin'})
        p = get_profile(USER_ID)
        assert p is not None
        assert p['course_name'] == 'My Course'
