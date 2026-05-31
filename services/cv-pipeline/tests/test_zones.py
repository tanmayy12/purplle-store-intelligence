from app.zones import Point, _point_in_polygon


def test_point_in_polygon():
    square = [
        Point(0.0, 0.0),
        Point(1.0, 0.0),
        Point(1.0, 1.0),
        Point(0.0, 1.0),
    ]
    assert _point_in_polygon(0.5, 0.5, square) is True
    assert _point_in_polygon(1.5, 0.5, square) is False
