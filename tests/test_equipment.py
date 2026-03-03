"""
Integration tests for Equipment API endpoints.
Tests CRUD operations via Flask test client against /api/equipment routes.
"""

import pytest


class TestEquipmentCRUD:
    """Test equipment create, read, update, delete via API."""

    def _create_equipment(self, auth_client, **overrides):
        """Helper to create an equipment item and return the response."""
        payload = {
            'name': 'Toro Greensmaster 3250-D',
            'equipment_type': 'mower_reel',
            'make': 'Toro',
            'model': 'Greensmaster 3250-D',
            'year': 2022,
            'status': 'active',
            'serial_number': 'TG3250-001',
            'fuel_type': 'diesel',
            'area_assigned': 'greens',
            'current_hours': 350,
            'notes': 'Primary greens mower',
        }
        payload.update(overrides)
        return auth_client.post('/api/equipment', json=payload)

    def test_create_equipment(self, auth_client):
        """POST /api/equipment should create an equipment item and return it."""
        resp = self._create_equipment(auth_client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data is not None
        assert data.get('id') is not None
        assert data.get('name') == 'Toro Greensmaster 3250-D'
        assert data.get('equipment_type') == 'mower_reel'

    def test_create_equipment_minimal(self, auth_client):
        """POST /api/equipment with only required fields should succeed."""
        resp = auth_client.post('/api/equipment', json={
            'name': 'Basic Mower',
            'equipment_type': 'mower_rotary',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get('id') is not None
        assert data.get('name') == 'Basic Mower'

    def test_create_equipment_type_alias(self, auth_client):
        """POST /api/equipment should accept 'type' as alias for 'equipment_type'."""
        resp = auth_client.post('/api/equipment', json={
            'name': 'Sprayer Unit',
            'type': 'sprayer',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get('equipment_type') == 'sprayer'

    def test_list_equipment(self, auth_client):
        """GET /api/equipment should return a list of equipment."""
        # Create two items first
        self._create_equipment(auth_client, name='Mower A')
        self._create_equipment(auth_client, name='Mower B')

        resp = auth_client.get('/api/equipment')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_equipment_filter_by_type(self, auth_client):
        """GET /api/equipment?type=sprayer should filter by equipment type."""
        self._create_equipment(auth_client, name='Sprayer 1', equipment_type='sprayer')
        self._create_equipment(auth_client, name='Mower 1', equipment_type='mower_reel')

        resp = auth_client.get('/api/equipment?type=sprayer')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        for item in data:
            assert item.get('equipment_type') == 'sprayer'

    def test_list_equipment_filter_by_status(self, auth_client):
        """GET /api/equipment?status=active should filter by status."""
        self._create_equipment(auth_client, name='Active Unit', status='active')

        resp = auth_client.get('/api/equipment?status=active')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        for item in data:
            assert item.get('status') == 'active'

    def test_get_equipment_by_id(self, auth_client):
        """GET /api/equipment/<id> should return the specific item."""
        create_resp = self._create_equipment(auth_client, name='Specific Mower')
        equip_id = create_resp.get_json().get('id')
        assert equip_id is not None

        resp = auth_client.get(f'/api/equipment/{equip_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('id') == equip_id
        assert data.get('name') == 'Specific Mower'

    def test_update_equipment(self, auth_client):
        """PUT /api/equipment/<id> should update equipment fields."""
        create_resp = self._create_equipment(auth_client, name='Old Name')
        equip_id = create_resp.get_json().get('id')
        assert equip_id is not None

        resp = auth_client.put(f'/api/equipment/{equip_id}', json={
            'name': 'Updated Name',
            'status': 'maintenance',
            'notes': 'In for service',
        })
        assert resp.status_code == 200

        # Verify the update
        get_resp = auth_client.get(f'/api/equipment/{equip_id}')
        data = get_resp.get_json()
        assert data.get('name') == 'Updated Name'
        assert data.get('status') == 'maintenance'

    def test_update_equipment_type_alias(self, auth_client):
        """PUT /api/equipment/<id> should accept 'type' as alias for 'equipment_type'."""
        create_resp = self._create_equipment(auth_client, equipment_type='mower_reel')
        equip_id = create_resp.get_json().get('id')
        assert equip_id is not None

        resp = auth_client.put(f'/api/equipment/{equip_id}', json={
            'type': 'sprayer',
        })
        assert resp.status_code == 200

    def test_delete_equipment(self, auth_client):
        """DELETE /api/equipment/<id> should remove the equipment item."""
        create_resp = self._create_equipment(auth_client, name='To Delete')
        equip_id = create_resp.get_json().get('id')
        assert equip_id is not None

        resp = auth_client.delete(f'/api/equipment/{equip_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

    def test_delete_nonexistent_equipment(self, auth_client):
        """DELETE /api/equipment/<id> for a nonexistent ID should return 404."""
        resp = auth_client.delete('/api/equipment/999999')
        assert resp.status_code == 404

    def test_get_equipment_summary(self, auth_client):
        """GET /api/equipment/summary should return fleet summary."""
        self._create_equipment(auth_client, name='Summary Test')

        resp = auth_client.get('/api/equipment/summary')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None


class TestEquipmentMaintenance:
    """Test maintenance-related endpoints."""

    def _create_equipment(self, auth_client):
        """Helper to create an equipment item."""
        resp = auth_client.post('/api/equipment', json={
            'name': 'Test Mower',
            'equipment_type': 'mower_reel',
        })
        return resp.get_json().get('id')

    def test_get_maintenance_history(self, auth_client):
        """GET /api/equipment/<id>/maintenance should return maintenance records."""
        equip_id = self._create_equipment(auth_client)
        assert equip_id is not None

        resp = auth_client.get(f'/api/equipment/{equip_id}/maintenance')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_create_maintenance_record(self, auth_client):
        """POST /api/equipment/maintenance should log a maintenance record."""
        equip_id = self._create_equipment(auth_client)
        assert equip_id is not None

        resp = auth_client.post('/api/equipment/maintenance', json={
            'equipment_id': equip_id,
            'maintenance_type': 'routine',
            'description': 'Oil change and blade sharpening',
            'performed_date': '2026-03-01',
            'performed_by': 'Mike',
            'labor_hours': 1.5,
        })
        assert resp.status_code == 201

    def test_get_all_maintenance(self, auth_client):
        """GET /api/equipment/maintenance should return all maintenance records."""
        resp = auth_client.get('/api/equipment/maintenance')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_get_upcoming_maintenance(self, auth_client):
        """GET /api/equipment/maintenance/upcoming should return upcoming tasks."""
        resp = auth_client.get('/api/equipment/maintenance/upcoming')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_get_overdue_maintenance(self, auth_client):
        """GET /api/equipment/maintenance/overdue should return overdue tasks."""
        resp = auth_client.get('/api/equipment/maintenance/overdue')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
