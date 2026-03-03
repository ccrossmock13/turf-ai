"""
Integration tests for Spray Tracker API endpoints.
Tests spray application logging, product inventory, and spray record CRUD
via Flask test client against /api/spray and related routes.
"""

import pytest


class TestSprayApplicationCRUD:
    """Test spray application create, read, delete via API."""

    def _create_custom_product(self, auth_client):
        """Helper to create a custom product and return the product_id."""
        resp = auth_client.post('/api/custom-products', json={
            'product_name': 'Test Fungicide 50WDG',
            'brand': 'TestBrand',
            'product_type': 'fungicide',
            'form_type': 'granular',
            'default_rate': 0.4,
            'rate_unit': 'oz/1000 sq ft',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        return data.get('product_id')

    def _log_spray(self, auth_client, product_id, **overrides):
        """Helper to log a spray application and return the response."""
        payload = {
            'date': '2026-03-01',
            'area': 'greens',
            'product_id': product_id,
            'rate': 0.4,
            'rate_unit': 'oz/1000 sq ft',
            'area_acreage': 3.0,
            'carrier_volume_gpa': 2.0,
            'weather_temp': 72,
            'weather_wind': '5 mph',
            'weather_conditions': 'Clear',
            'notes': 'Test application',
            'application_method': 'spray',
        }
        payload.update(overrides)
        return auth_client.post('/api/spray', json=payload)

    def test_create_spray_application(self, auth_client):
        """POST /api/spray should log a spray application with calculations."""
        product_id = self._create_custom_product(auth_client)
        resp = self._log_spray(auth_client, product_id)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        assert data.get('id') is not None
        assert 'calculations' in data
        calcs = data['calculations']
        assert 'products' in calcs
        # total_carrier_gallons may be None if no carrier volume was specified
        assert 'products' in calcs

    def test_create_spray_missing_date(self, auth_client):
        """POST /api/spray without date should return 400."""
        product_id = self._create_custom_product(auth_client)
        resp = auth_client.post('/api/spray', json={
            'area': 'greens',
            'product_id': product_id,
            'rate': 0.4,
            'rate_unit': 'oz/1000 sq ft',
            'area_acreage': 3.0,
        })
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_create_spray_invalid_area(self, auth_client):
        """POST /api/spray with invalid area should return 400."""
        product_id = self._create_custom_product(auth_client)
        resp = auth_client.post('/api/spray', json={
            'date': '2026-03-01',
            'area': 'invalid_area',
            'product_id': product_id,
            'rate': 0.4,
            'rate_unit': 'oz/1000 sq ft',
            'area_acreage': 3.0,
        })
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_create_spray_missing_product_fields(self, auth_client):
        """POST /api/spray without product_id, rate, rate_unit should return 400."""
        resp = auth_client.post('/api/spray', json={
            'date': '2026-03-01',
            'area': 'greens',
            'area_acreage': 3.0,
        })
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_create_spray_nonexistent_product(self, auth_client):
        """POST /api/spray with a nonexistent product_id should return 404."""
        resp = auth_client.post('/api/spray', json={
            'date': '2026-03-01',
            'area': 'greens',
            'product_id': 'custom:99999',
            'rate': 0.4,
            'rate_unit': 'oz/1000 sq ft',
            'area_acreage': 3.0,
        })
        assert resp.status_code == 404

    def test_list_spray_applications(self, auth_client):
        """GET /api/spray should return a list of spray records."""
        product_id = self._create_custom_product(auth_client)
        self._log_spray(auth_client, product_id)
        self._log_spray(auth_client, product_id, date='2026-03-02')

        resp = auth_client.get('/api/spray')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_spray_filter_by_area(self, auth_client):
        """GET /api/spray?area=greens should filter by area."""
        product_id = self._create_custom_product(auth_client)
        self._log_spray(auth_client, product_id, area='greens')
        self._log_spray(auth_client, product_id, area='fairways', date='2026-03-02')

        resp = auth_client.get('/api/spray?area=greens')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        for record in data:
            assert record.get('area') == 'greens'

    def test_list_spray_filter_by_year(self, auth_client):
        """GET /api/spray?year=2026 should filter by year."""
        resp = auth_client.get('/api/spray?year=2026')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_get_spray_by_id(self, auth_client):
        """GET /api/spray/<id> should return a single spray record."""
        product_id = self._create_custom_product(auth_client)
        create_resp = self._log_spray(auth_client, product_id)
        app_id = create_resp.get_json().get('id')
        assert app_id is not None

        resp = auth_client.get(f'/api/spray/{app_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('id') == app_id
        assert data.get('area') == 'greens'

    def test_get_spray_nonexistent(self, auth_client):
        """GET /api/spray/<id> for nonexistent ID should return 404."""
        resp = auth_client.get('/api/spray/999999')
        assert resp.status_code == 404

    def test_delete_spray(self, auth_client):
        """DELETE /api/spray/<id> should remove the spray record."""
        product_id = self._create_custom_product(auth_client)
        create_resp = self._log_spray(auth_client, product_id)
        app_id = create_resp.get_json().get('id')
        assert app_id is not None

        resp = auth_client.delete(f'/api/spray/{app_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        # Verify it is gone
        get_resp = auth_client.get(f'/api/spray/{app_id}')
        assert get_resp.status_code == 404

    def test_delete_spray_nonexistent(self, auth_client):
        """DELETE /api/spray/<id> for nonexistent ID should return 404."""
        resp = auth_client.delete('/api/spray/999999')
        assert resp.status_code == 404


class TestSprayTankMix:
    """Test tank mix (multi-product) spray applications."""

    def _create_products(self, auth_client):
        """Create two custom products for a tank mix."""
        resp1 = auth_client.post('/api/custom-products', json={
            'product_name': 'Mix Product A',
            'product_type': 'fungicide',
            'form_type': 'granular',
            'default_rate': 0.3,
            'rate_unit': 'oz/1000 sq ft',
        })
        resp2 = auth_client.post('/api/custom-products', json={
            'product_name': 'Mix Product B',
            'product_type': 'insecticide',
            'form_type': 'liquid',
            'default_rate': 1.0,
            'rate_unit': 'fl oz/1000 sq ft',
        })
        return resp1.get_json()['product_id'], resp2.get_json()['product_id']

    def test_create_tank_mix(self, auth_client):
        """POST /api/spray with products array should create a tank mix record."""
        pid_a, pid_b = self._create_products(auth_client)

        resp = auth_client.post('/api/spray', json={
            'date': '2026-03-01',
            'area': 'greens',
            'area_acreage': 3.0,
            'carrier_volume_gpa': 2.0,
            'products': [
                {'product_id': pid_a, 'rate': 0.3, 'rate_unit': 'oz/1000 sq ft'},
                {'product_id': pid_b, 'rate': 1.0, 'rate_unit': 'fl oz/1000 sq ft'},
            ],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        assert len(data['calculations']['products']) == 2


class TestSprayNutrients:
    """Test nutrient summary and monthly breakdown endpoints."""

    def test_get_nutrient_summary(self, auth_client):
        """GET /api/spray/nutrients should return nutrient summary."""
        resp = auth_client.get('/api/spray/nutrients?year=2026')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None

    def test_get_monthly_nutrients(self, auth_client):
        """GET /api/spray/nutrients/monthly should return monthly breakdown."""
        resp = auth_client.get('/api/spray/nutrients/monthly?year=2026')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'primary' in data


class TestSprayInventory:
    """Test product inventory endpoints."""

    def test_get_inventory(self, auth_client):
        """GET /api/inventory should return user inventory."""
        resp = auth_client.get('/api/inventory')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'products' in data

    def test_add_to_inventory(self, auth_client):
        """POST /api/inventory should add a product to inventory."""
        # Create a custom product first
        product_resp = auth_client.post('/api/custom-products', json={
            'product_name': 'Inventory Test Product',
            'product_type': 'fertilizer',
        })
        product_id = product_resp.get_json().get('product_id')

        resp = auth_client.post('/api/inventory', json={
            'product_id': product_id,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

    def test_get_inventory_ids(self, auth_client):
        """GET /api/inventory/ids should return product IDs."""
        resp = auth_client.get('/api/inventory/ids')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_inventory_missing_product_id(self, auth_client):
        """POST /api/inventory without product_id should return 400."""
        resp = auth_client.post('/api/inventory', json={})
        assert resp.status_code == 400


class TestSprayTemplates:
    """Test spray program template endpoints."""

    def test_list_templates(self, auth_client):
        """GET /api/spray-templates should return templates."""
        resp = auth_client.get('/api/spray-templates')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_create_template(self, auth_client):
        """POST /api/spray-templates should save a template."""
        resp = auth_client.post('/api/spray-templates', json={
            'name': 'Spring Fungicide Program',
            'products': [
                {'product_id': 'custom:1', 'rate': 0.4, 'rate_unit': 'oz/1000 sq ft'},
            ],
            'application_method': 'spray',
            'notes': 'Apply every 14 days',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        assert data.get('id') is not None

    def test_create_template_missing_fields(self, auth_client):
        """POST /api/spray-templates without required fields should return 400."""
        resp = auth_client.post('/api/spray-templates', json={
            'name': 'Incomplete Template',
        })
        assert resp.status_code == 400

    def test_delete_template(self, auth_client):
        """DELETE /api/spray-templates/<id> should remove the template."""
        create_resp = auth_client.post('/api/spray-templates', json={
            'name': 'To Delete',
            'products': [{'product_id': 'custom:1', 'rate': 1.0, 'rate_unit': 'oz/1000 sq ft'}],
        })
        template_id = create_resp.get_json().get('id')
        assert template_id is not None

        resp = auth_client.delete(f'/api/spray-templates/{template_id}')
        assert resp.status_code == 200
        assert resp.get_json().get('success') is True
