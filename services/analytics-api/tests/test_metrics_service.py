"""Tests for Metrics Service."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.metrics_service import MetricsService


def test_get_metrics_basic(db_session: Session, sample_session, sample_pos_transaction):
    """Test basic metrics retrieval."""
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert metrics is not None
    assert metrics.store_id == "ST1008"
    assert metrics.store_name == "Brigade_Bangalore"
    assert metrics.date == date(2026, 4, 10)


def test_footfall_metrics(db_session: Session, sample_session):
    """Test footfall metrics calculation."""
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert metrics.footfall.total_entries >= 0
    assert metrics.footfall.unique_sessions >= 0
    assert metrics.footfall.staff_excluded >= 0
    assert metrics.footfall.re_entries >= 0


def test_engagement_metrics(db_session: Session, sample_session):
    """Test engagement metrics calculation."""
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert metrics.engagement.engaged_visits >= 0
    assert 0 <= metrics.engagement.engagement_rate <= 100
    assert metrics.engagement.avg_dwell_sec >= 0
    assert metrics.engagement.avg_zones_per_visit >= 0


def test_conversion_metrics(db_session: Session, sample_session, sample_pos_transaction):
    """Test conversion metrics calculation."""
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert metrics.conversion.pos_transactions >= 0
    assert metrics.conversion.matched_conversions >= 0
    assert metrics.conversion.unmatched_pos >= 0
    assert 0 <= metrics.conversion.conversion_rate <= 100


def test_revenue_metrics(db_session: Session, sample_pos_transaction):
    """Test revenue metrics calculation."""
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert metrics.revenue.total_nmv >= 0
    assert metrics.revenue.avg_basket_nmv >= 0
    assert metrics.revenue.avg_items_per_transaction >= 0
    assert metrics.revenue.revenue_per_visitor >= 0


def test_hourly_metrics(db_session: Session, sample_session):
    """Test hourly metrics breakdown."""
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert isinstance(metrics.hourly, list)
    assert len(metrics.hourly) <= 24
    
    for hour in metrics.hourly:
        assert "hour" in hour
        assert "entries" in hour
        assert "transactions" in hour
        assert "nmv" in hour


def test_top_zones(db_session: Session, sample_session):
    """Test top zones calculation."""
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert isinstance(metrics.top_zones, list)
    
    for zone in metrics.top_zones:
        assert "zone_id" in zone
        assert "zone_name" in zone
        assert "visits" in zone
        assert "avg_dwell_sec" in zone


def test_department_mix(db_session: Session, sample_pos_transaction):
    """Test department mix calculation."""
    service = MetricsService(db_session)
    metrics = service.get_metrics()
    
    assert isinstance(metrics.department_mix, list)
    
    for dept in metrics.department_mix:
        assert "department" in dept
        assert "nmv" in dept
        assert "qty" in dept
        assert "share" in dept


def test_metrics_with_store_filter(db_session: Session, sample_session):
    """Test metrics with store ID filter."""
    service = MetricsService(db_session)
    metrics = service.get_metrics(store_id="ST1008")
    
    assert metrics.store_id == "ST1008"


def test_metrics_with_date_filter(db_session: Session, sample_session):
    """Test metrics with date filter."""
    service = MetricsService(db_session)
    metrics = service.get_metrics(metric_date=date(2026, 4, 10))
    
    assert metrics.date == date(2026, 4, 10)


def test_get_funnel(db_session: Session, sample_session):
    """Test funnel metrics retrieval."""
    service = MetricsService(db_session)
    funnel = service.get_funnel()
    
    assert funnel is not None
    assert funnel.store_id == "ST1008"
    assert funnel.date == date(2026, 4, 10)
    assert funnel.funnel_type in ["standard", "engagement"]
    assert isinstance(funnel.stages, list)


def test_funnel_stages_order(db_session: Session, sample_session):
    """Test funnel stages are ordered correctly."""
    service = MetricsService(db_session)
    funnel = service.get_funnel()
    
    if funnel.stages:
        for i in range(len(funnel.stages) - 1):
            assert funnel.stages[i].stage_order < funnel.stages[i + 1].stage_order


def test_funnel_stage_counts(db_session: Session, sample_session):
    """Test funnel stage counts are non-negative."""
    service = MetricsService(db_session)
    funnel = service.get_funnel()
    
    for stage in funnel.stages:
        assert stage.count >= 0
        assert 0 <= stage.pct_of_top <= 100
