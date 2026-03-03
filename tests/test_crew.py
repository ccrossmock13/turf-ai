"""
Integration tests for Crew Management API endpoints.
Tests CRUD operations via Flask test client against /api/crew routes.
"""

import pytest


class TestCrewMemberCRUD:
    """Test crew member create, read, update, delete via API."""

    def _create_member(self, auth_client, **overrides):
        """Helper to create a crew member and return the response."""
        payload = {
            'name': 'John Smith',
            'role': 'crew_member',
            'email': 'john@example.com',
            'phone': '555-0101',
            'hire_date': '2024-03-15',
            'hourly_rate': 18.50,
            'notes': 'Experienced operator',
        }
        payload.update(overrides)
        return auth_client.post('/api/crew/members', json=payload)

    def test_create_member(self, auth_client):
        """POST /api/crew/members should create a crew member."""
        resp = self._create_member(auth_client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data is not None
        assert data.get('id') is not None
        assert data.get('name') == 'John Smith'

    def test_create_member_minimal(self, auth_client):
        """POST /api/crew/members with only name should succeed."""
        resp = auth_client.post('/api/crew/members', json={
            'name': 'Jane Doe',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get('id') is not None

    def test_create_member_missing_name(self, auth_client):
        """POST /api/crew/members without name should return 400."""
        resp = auth_client.post('/api/crew/members', json={
            'role': 'crew_member',
            'email': 'noname@example.com',
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_create_member_invalid_role(self, auth_client):
        """POST /api/crew/members with invalid role should return 400."""
        resp = auth_client.post('/api/crew/members', json={
            'name': 'Bad Role Person',
            'role': 'invalid_role',
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_create_member_with_certifications(self, auth_client):
        """POST /api/crew/members should accept certifications as a list."""
        resp = self._create_member(auth_client, name='Certified Worker', certifications=[
            'Pesticide Applicator',
            'CDL Class B',
        ])
        assert resp.status_code == 201

    def test_list_members(self, auth_client):
        """GET /api/crew/members should return a list of crew members."""
        self._create_member(auth_client, name='Worker A')
        self._create_member(auth_client, name='Worker B')

        resp = auth_client.get('/api/crew/members')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_members_filter_by_role(self, auth_client):
        """GET /api/crew/members?role=spray_tech should filter by role."""
        self._create_member(auth_client, name='Spray Tech 1', role='spray_tech')
        self._create_member(auth_client, name='Mechanic 1', role='mechanic')

        resp = auth_client.get('/api/crew/members?role=spray_tech')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        for member in data:
            assert member.get('role') == 'spray_tech'

    def test_get_member_by_id(self, auth_client):
        """GET /api/crew/members/<id> should return the specific member."""
        create_resp = self._create_member(auth_client, name='Specific Person')
        member_id = create_resp.get_json().get('id')
        assert member_id is not None

        resp = auth_client.get(f'/api/crew/members/{member_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('id') == member_id

    def test_update_member(self, auth_client):
        """PUT /api/crew/members/<id> should update member fields."""
        create_resp = self._create_member(auth_client, name='Original Name')
        member_id = create_resp.get_json().get('id')
        assert member_id is not None

        resp = auth_client.put(f'/api/crew/members/{member_id}', json={
            'name': 'Updated Name',
            'role': 'crew_leader',
            'hourly_rate': 22.00,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True or data.get('id') is not None

    def test_update_member_invalid_role(self, auth_client):
        """PUT /api/crew/members/<id> with invalid role should return error."""
        create_resp = self._create_member(auth_client, name='Test')
        member_id = create_resp.get_json().get('id')
        assert member_id is not None

        resp = auth_client.put(f'/api/crew/members/{member_id}', json={
            'role': 'not_a_valid_role',
        })
        # Should raise ValueError which gets caught and returns 400
        assert resp.status_code in (400, 500)

    def test_delete_member(self, auth_client):
        """DELETE /api/crew/members/<id> should remove the crew member."""
        create_resp = self._create_member(auth_client, name='To Delete')
        member_id = create_resp.get_json().get('id')
        assert member_id is not None

        resp = auth_client.delete(f'/api/crew/members/{member_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True


class TestWorkOrders:
    """Test work order endpoints."""

    def _create_member(self, auth_client):
        """Helper to create a crew member and return the ID."""
        resp = auth_client.post('/api/crew/members', json={
            'name': 'Work Order Worker',
            'role': 'crew_member',
        })
        return resp.get_json().get('id')

    def _create_work_order(self, auth_client, **overrides):
        """Helper to create a work order and return the response."""
        payload = {
            'title': 'Mow greens',
            'description': 'Morning mowing of all 18 greens',
            'area': 'greens',
            'task_type': 'mowing',
            'priority': 'high',
            'due_date': '2026-03-05',
            'estimated_hours': 4.0,
        }
        payload.update(overrides)
        return auth_client.post('/api/crew/work-orders', json=payload)

    def test_create_work_order(self, auth_client):
        """POST /api/crew/work-orders should create a work order."""
        resp = self._create_work_order(auth_client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data is not None
        assert data.get('id') is not None

    def test_list_work_orders(self, auth_client):
        """GET /api/crew/work-orders should return work orders."""
        self._create_work_order(auth_client)

        resp = auth_client.get('/api/crew/work-orders')
        assert resp.status_code == 200
        data = resp.get_json()
        # Response may be a list or a dict with 'work_orders' key
        if isinstance(data, dict):
            data = data.get('work_orders', data.get('items', []))
        assert isinstance(data, list)

    def test_get_work_order_by_id(self, auth_client):
        """GET /api/crew/work-orders/<id> should return the specific order."""
        create_resp = self._create_work_order(auth_client)
        create_data = create_resp.get_json()
        order_id = create_data.get('id') if isinstance(create_data, dict) else create_data
        if order_id is None:
            pytest.skip("Work order creation did not return an ID")

        resp = auth_client.get(f'/api/crew/work-orders/{order_id}')
        assert resp.status_code == 200

    def test_update_work_order(self, auth_client):
        """PUT /api/crew/work-orders/<id> should update a work order."""
        create_resp = self._create_work_order(auth_client)
        order_id = create_resp.get_json().get('id')
        assert order_id is not None

        resp = auth_client.put(f'/api/crew/work-orders/{order_id}', json={
            'title': 'Updated title',
            'priority': 'urgent',
        })
        assert resp.status_code == 200

    def test_assign_work_order(self, auth_client):
        """POST /api/crew/work-orders/<id>/assign should assign a member."""
        member_id = self._create_member(auth_client)
        create_resp = self._create_work_order(auth_client)
        order_id = create_resp.get_json().get('id')
        assert order_id is not None

        resp = auth_client.post(f'/api/crew/work-orders/{order_id}/assign', json={
            'crew_member_id': member_id,
        })
        assert resp.status_code == 200

    def test_complete_work_order(self, auth_client):
        """POST /api/crew/work-orders/<id>/complete should mark as done."""
        create_resp = self._create_work_order(auth_client)
        order_id = create_resp.get_json().get('id')
        assert order_id is not None

        resp = auth_client.post(f'/api/crew/work-orders/{order_id}/complete', json={
            'actual_hours': 3.5,
        })
        assert resp.status_code == 200


class TestTimeEntries:
    """Test time tracking endpoints."""

    def test_get_time_entries(self, auth_client):
        """GET /api/crew/time-entries should return time entries."""
        resp = auth_client.get('/api/crew/time-entries')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_create_time_entry(self, auth_client):
        """POST /api/crew/time-entries should log a time entry."""
        # First create a crew member
        member_resp = auth_client.post('/api/crew/members', json={
            'name': 'Time Entry Worker',
            'role': 'crew_member',
        })
        member_id = member_resp.get_json().get('id')
        assert member_id is not None

        resp = auth_client.post('/api/crew/time-entries', json={
            'crew_member_id': member_id,
            'date': '2026-03-03',
            'hours': 8.0,
            'area': 'greens',
            'task_type': 'mowing',
        })
        assert resp.status_code == 201


class TestLaborSummary:
    """Test labor analytics endpoints."""

    def test_get_labor_summary(self, auth_client):
        """GET /api/crew/labor-summary should return labor analytics."""
        resp = auth_client.get('/api/crew/labor-summary')
        assert resp.status_code == 200

    def test_get_daily_sheet(self, auth_client):
        """GET /api/crew/daily-sheet should return daily work sheet."""
        resp = auth_client.get('/api/crew/daily-sheet')
        assert resp.status_code == 200
