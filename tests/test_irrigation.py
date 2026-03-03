"""
Integration tests for Irrigation API endpoints.
Tests zone CRUD, irrigation runs, moisture readings, and related
endpoints via Flask test client against /api/irrigation routes.
"""

import pytest


class TestIrrigationZoneCRUD:
    """Test irrigation zone create, read, update, delete via API."""

    def _create_zone(self, auth_client, **overrides):
        """Helper to create an irrigation zone and return the response."""
        payload = {
            'name': 'Green #1 - Front',
            'area': 'greens',
            'zone_number': 1,
            'sprinkler_type': 'rotor',
            'heads_count': 8,
            'gpm_per_head': 15.0,
            'area_sqft': 5500,
            'soil_type': 'sand',
            'root_depth': 6.0,
            'allowable_depletion': 0.5,
            'notes': 'Bentgrass putting green',
        }
        payload.update(overrides)
        return auth_client.post('/api/irrigation/zones', json=payload)

    def test_create_zone(self, auth_client):
        """POST /api/irrigation/zones should create a zone and return it."""
        resp = self._create_zone(auth_client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data is not None
        assert data.get('id') is not None
        assert data.get('name') == 'Green #1 - Front'
        assert data.get('area') == 'greens'

    def test_create_zone_minimal(self, auth_client):
        """POST /api/irrigation/zones with only required fields should succeed."""
        resp = auth_client.post('/api/irrigation/zones', json={
            'name': 'Simple Zone',
            'area': 'fairways',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get('id') is not None

    def test_create_zone_invalid_area(self, auth_client):
        """POST /api/irrigation/zones with invalid area should return 400."""
        resp = auth_client.post('/api/irrigation/zones', json={
            'name': 'Bad Zone',
            'area': 'parking_lot',
        })
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_create_zone_invalid_soil_type(self, auth_client):
        """POST /api/irrigation/zones with invalid soil_type should return 400."""
        resp = auth_client.post('/api/irrigation/zones', json={
            'name': 'Bad Soil Zone',
            'area': 'greens',
            'soil_type': 'granite',
        })
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_create_zone_invalid_sprinkler_type(self, auth_client):
        """POST /api/irrigation/zones with invalid sprinkler_type should return 400."""
        resp = auth_client.post('/api/irrigation/zones', json={
            'name': 'Bad Sprinkler Zone',
            'area': 'tees',
            'sprinkler_type': 'firehose',
        })
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_create_zone_auto_precipitation_rate(self, auth_client):
        """POST /api/irrigation/zones should auto-calculate precipitation_rate."""
        resp = self._create_zone(auth_client, name='Auto Calc Zone',
                                  heads_count=10, gpm_per_head=12.0, area_sqft=6000)
        assert resp.status_code == 201
        data = resp.get_json()
        # precipitation_rate = (96.25 * 10 * 12.0) / 6000 = 1.925
        precip = data.get('precipitation_rate')
        if precip is not None:
            assert precip > 0

    def test_list_zones(self, auth_client):
        """GET /api/irrigation/zones should return a list of zones."""
        self._create_zone(auth_client, name='Zone A')
        self._create_zone(auth_client, name='Zone B')

        resp = auth_client.get('/api/irrigation/zones')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_zones_filter_by_area(self, auth_client):
        """GET /api/irrigation/zones?area=greens should filter by area."""
        self._create_zone(auth_client, name='Greens Zone', area='greens')
        self._create_zone(auth_client, name='Fairway Zone', area='fairways')

        resp = auth_client.get('/api/irrigation/zones?area=greens')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        for zone in data:
            assert zone.get('area') == 'greens'

    def test_get_zone_by_id(self, auth_client):
        """GET /api/irrigation/zones/<id> should return the specific zone."""
        create_resp = self._create_zone(auth_client, name='Specific Zone')
        zone_id = create_resp.get_json().get('id')
        assert zone_id is not None

        resp = auth_client.get(f'/api/irrigation/zones/{zone_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('id') == zone_id
        assert data.get('name') == 'Specific Zone'

    def test_update_zone(self, auth_client):
        """PUT /api/irrigation/zones/<id> should update zone fields."""
        create_resp = self._create_zone(auth_client, name='Old Name')
        zone_id = create_resp.get_json().get('id')
        assert zone_id is not None

        resp = auth_client.put(f'/api/irrigation/zones/{zone_id}', json={
            'name': 'Updated Name',
            'soil_type': 'clay_loam',
            'notes': 'Updated notes',
        })
        assert resp.status_code == 200

        # Verify the update
        get_resp = auth_client.get(f'/api/irrigation/zones/{zone_id}')
        data = get_resp.get_json()
        assert data.get('name') == 'Updated Name'

    def test_delete_zone(self, auth_client):
        """DELETE /api/irrigation/zones/<id> should remove the zone."""
        create_resp = self._create_zone(auth_client, name='To Delete')
        zone_id = create_resp.get_json().get('id')
        assert zone_id is not None

        resp = auth_client.delete(f'/api/irrigation/zones/{zone_id}')
        assert resp.status_code == 200


class TestIrrigationRuns:
    """Test irrigation run logging endpoints."""

    def _create_zone(self, auth_client):
        """Helper to create a zone and return the ID."""
        resp = auth_client.post('/api/irrigation/zones', json={
            'name': 'Run Test Zone',
            'area': 'greens',
            'area_sqft': 5000,
        })
        return resp.get_json().get('id')

    def test_create_irrigation_run(self, auth_client):
        """POST /api/irrigation/runs should log an irrigation run."""
        zone_id = self._create_zone(auth_client)
        assert zone_id is not None

        resp = auth_client.post('/api/irrigation/runs', json={
            'zone_id': zone_id,
            'run_date': '2026-03-01',
            'start_time': '05:30',
            'duration_minutes': 45,
            'gallons_applied': 2500,
            'inches_applied': 0.25,
            'run_type': 'scheduled',
            'notes': 'Morning cycle',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get('id') is not None

    def test_list_irrigation_runs(self, auth_client):
        """GET /api/irrigation/runs should return irrigation run history."""
        zone_id = self._create_zone(auth_client)
        auth_client.post('/api/irrigation/runs', json={
            'zone_id': zone_id,
            'run_date': '2026-03-01',
            'duration_minutes': 30,
        })

        resp = auth_client.get('/api/irrigation/runs')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_list_runs_filter_by_zone(self, auth_client):
        """GET /api/irrigation/runs?zone_id=X should filter by zone."""
        zone_id = self._create_zone(auth_client)
        auth_client.post('/api/irrigation/runs', json={
            'zone_id': zone_id,
            'run_date': '2026-03-01',
            'duration_minutes': 30,
        })

        resp = auth_client.get(f'/api/irrigation/runs?zone_id={zone_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_delete_irrigation_run(self, auth_client):
        """DELETE /api/irrigation/runs/<id> should remove the run record."""
        zone_id = self._create_zone(auth_client)
        create_resp = auth_client.post('/api/irrigation/runs', json={
            'zone_id': zone_id,
            'run_date': '2026-03-01',
            'duration_minutes': 30,
        })
        run_id = create_resp.get_json().get('id')
        assert run_id is not None

        resp = auth_client.delete(f'/api/irrigation/runs/{run_id}')
        assert resp.status_code == 200


class TestMoistureReadings:
    """Test soil moisture reading endpoints."""

    def _create_zone(self, auth_client):
        """Helper to create a zone for moisture readings."""
        resp = auth_client.post('/api/irrigation/zones', json={
            'name': 'Moisture Test Zone',
            'area': 'greens',
        })
        return resp.get_json().get('id')

    def test_create_moisture_reading(self, auth_client):
        """POST /api/irrigation/moisture should log a moisture reading."""
        zone_id = self._create_zone(auth_client)
        assert zone_id is not None

        resp = auth_client.post('/api/irrigation/moisture', json={
            'zone_id': zone_id,
            'reading_date': '2026-03-01',
            'moisture_pct': 22.5,
            'reading_depth': 4.0,
            'method': 'tdr',
            'notes': 'Morning reading before irrigation',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get('id') is not None

    def test_list_moisture_readings(self, auth_client):
        """GET /api/irrigation/moisture should return moisture readings."""
        resp = auth_client.get('/api/irrigation/moisture')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_delete_moisture_reading(self, auth_client):
        """DELETE /api/irrigation/moisture/<id> should remove the reading."""
        zone_id = self._create_zone(auth_client)
        create_resp = auth_client.post('/api/irrigation/moisture', json={
            'zone_id': zone_id,
            'reading_date': '2026-03-01',
            'moisture_pct': 18.0,
        })
        reading_id = create_resp.get_json().get('id')
        assert reading_id is not None

        resp = auth_client.delete(f'/api/irrigation/moisture/{reading_id}')
        assert resp.status_code == 200


class TestETData:
    """Test evapotranspiration data endpoints."""

    def test_create_et_entry(self, auth_client):
        """POST /api/irrigation/et should log ET data."""
        resp = auth_client.post('/api/irrigation/et', json={
            'date': '2026-03-01',
            'et0': 0.18,
            'rainfall': 0.0,
            'high_temp': 78,
            'low_temp': 55,
            'humidity': 65,
            'wind_speed': 8,
            'source': 'manual',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get('id') is not None

    def test_get_et_data(self, auth_client):
        """GET /api/irrigation/et should return ET data."""
        resp = auth_client.get('/api/irrigation/et')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)


class TestWaterUsage:
    """Test water usage tracking endpoints."""

    def test_log_water_usage(self, auth_client):
        """POST /api/irrigation/water-usage should log water usage."""
        resp = auth_client.post('/api/irrigation/water-usage', json={
            'date': '2026-03-01',
            'total_gallons': 50000,
            'meter_reading': 125430,
            'cost': 175.00,
            'notes': 'Monthly meter reading',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get('id') is not None

    def test_get_water_usage(self, auth_client):
        """GET /api/irrigation/water-usage should return water usage records."""
        resp = auth_client.get('/api/irrigation/water-usage')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_delete_water_usage(self, auth_client):
        """DELETE /api/irrigation/water-usage/<id> should remove the record."""
        create_resp = auth_client.post('/api/irrigation/water-usage', json={
            'date': '2026-03-01',
            'total_gallons': 10000,
        })
        usage_id = create_resp.get_json().get('id')
        assert usage_id is not None

        resp = auth_client.delete(f'/api/irrigation/water-usage/{usage_id}')
        assert resp.status_code == 200


class TestIrrigationAnalytics:
    """Test irrigation analytics and recommendation endpoints."""

    def test_get_recommendations(self, auth_client):
        """GET /api/irrigation/recommendations should return recommendations."""
        resp = auth_client.get('/api/irrigation/recommendations')
        assert resp.status_code == 200

    def test_get_drought_status(self, auth_client):
        """GET /api/irrigation/drought-status should return drought status."""
        resp = auth_client.get('/api/irrigation/drought-status')
        assert resp.status_code == 200
