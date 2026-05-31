"""Tests for FastAPI endpoints."""

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    """Test health endpoint returns OK status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_ready_endpoint(client: TestClient):
    """Test readiness endpoint includes database status."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "kafka" in data
    assert "consumer_running" in data


def test_metrics_endpoint(client: TestClient, sample_session, sample_pos_transaction):
    """Test metrics endpoint returns metrics data."""
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    
    assert "store_id" in data
    assert "store_name" in data
    assert "date" in data
    assert "footfall" in data
    assert "engagement" in data
    assert "conversion" in data
    assert "revenue" in data
    
    # Check footfall structure
    assert "total_entries" in data["footfall"]
    assert "unique_sessions" in data["footfall"]
    
    # Check engagement structure
    assert "engaged_visits" in data["engagement"]
    assert "engagement_rate" in data["engagement"]
    
    # Check conversion structure
    assert "pos_transactions" in data["conversion"]
    assert "conversion_rate" in data["conversion"]


def test_metrics_with_filters(client: TestClient):
    """Test metrics endpoint with query parameters."""
    response = client.get("/api/v1/metrics?store_id=ST1008&date=2026-04-10")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == "ST1008"


def test_funnel_endpoint(client: TestClient, sample_session):
    """Test funnel endpoint returns funnel data."""
    response = client.get("/api/v1/funnel")
    assert response.status_code == 200
    data = response.json()
    
    assert "store_id" in data
    assert "date" in data
    assert "funnel_type" in data
    assert "stages" in data
    assert isinstance(data["stages"], list)
    
    # Check stage structure
    if data["stages"]:
        stage = data["stages"][0]
        assert "stage" in stage
        assert "stage_order" in stage
        assert "count" in stage


def test_events_endpoint(client: TestClient, sample_session):
    """Test events endpoint returns events list."""
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    data = response.json()
    
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_events_with_type_filter(client: TestClient):
    """Test events endpoint with event type filter."""
    response = client.get("/api/v1/events?event_type=store.entry")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_events_with_limit(client: TestClient):
    """Test events endpoint with limit parameter."""
    response = client.get("/api/v1/events?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 10


def test_sessions_endpoint(client: TestClient, sample_session):
    """Test sessions endpoint returns sessions list."""
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    data = response.json()
    
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_sessions_with_limit(client: TestClient):
    """Test sessions endpoint with limit parameter."""
    response = client.get("/api/v1/sessions?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 5


def test_session_by_id(client: TestClient, sample_session):
    """Test getting a specific session by ID."""
    response = client.get(f"/api/v1/sessions/{sample_session.session_id}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["session_id"] == str(sample_session.session_id)
    assert "person_id" in data
    assert "started_at" in data
    assert "ended_at" in data


def test_session_not_found(client: TestClient):
    """Test getting a non-existent session returns 404."""
    import uuid
    fake_id = uuid.uuid4()
    response = client.get(f"/api/v1/sessions/{fake_id}")
    assert response.status_code == 404


def test_zones_endpoint(client: TestClient):
    """Test zones endpoint returns zones list."""
    response = client.get("/api/v1/zones")
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Check zone structure
    zone = data[0]
    assert "zone_id" in zone
    assert "zone_name" in zone
    assert "zone_type" in zone


def test_anomalies_endpoint(client: TestClient):
    """Test anomalies endpoint returns anomalies list."""
    response = client.get("/api/v1/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_anomalies_with_severity_filter(client: TestClient):
    """Test anomalies endpoint with severity filter."""
    response = client.get("/api/v1/anomalies?severity=high")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_anomalies_summary(client: TestClient):
    """Test anomalies summary endpoint."""
    response = client.get("/api/v1/anomalies/summary")
    assert response.status_code == 200
    data = response.json()
    
    assert "total" in data
    assert "by_type" in data
    assert "by_severity" in data


def test_pos_transactions_endpoint(client: TestClient, sample_pos_transaction):
    """Test POS transactions endpoint."""
    response = client.get("/api/v1/pos/transactions")
    assert response.status_code == 200
    data = response.json()
    
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_metrics_root_redirect(client: TestClient):
    """Test that /metrics root endpoint is removed (Phase 1 fix)."""
    # This should not exist after Phase 1 fix
    response = client.get("/metrics")
    # Should return 404 since the route was removed
    assert response.status_code == 404


def test_funnel_root_redirect(client: TestClient):
    """Test that /funnel root endpoint is removed (Phase 1 fix)."""
    # This should not exist after Phase 1 fix
    response = client.get("/funnel")
    # Should return 404 since the route was removed
    assert response.status_code == 404
