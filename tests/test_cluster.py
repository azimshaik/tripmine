"""Unit tests for stop clustering — pure Python, no exiftool needed."""

from datetime import datetime, timedelta

from tripmine.track import build_stops, summarize

T0 = datetime(2019, 3, 25, 9, 0, 0)


def rec(minutes: int, lat=None, lon=None, filetype="JPEG"):
    return {
        "path": f"/p/{minutes}.jpg",
        "source": f"{minutes}.jpg",
        "ts": T0 + timedelta(minutes=minutes),
        "lat": lat,
        "lon": lon,
        "model": "iPhone XS",
        "filetype": filetype,
        "duration": None,
    }


def test_single_stop_when_photos_close_together():
    records = [rec(0, 63.9, -22.6), rec(5, 63.9, -22.6), rec(10, 63.9, -22.6)]
    stops = build_stops(records)
    assert len(stops) == 1
    assert stops[0]["photo_count"] == 3
    assert stops[0]["lat"] == 63.9


def test_gap_splits_stops():
    records = [rec(0), rec(5), rec(200), rec(210)]
    stops = build_stops(records)
    assert len(stops) == 2
    assert stops[0]["photo_count"] == 2
    assert stops[1]["photo_count"] == 2
    assert stops[1]["start"] > stops[0]["end"]


def test_video_counted_separately():
    records = [rec(0), rec(2, filetype="MOV"), rec(4)]
    stops = build_stops(records)
    assert len(stops) == 1
    assert stops[0]["photo_count"] == 2
    assert stops[0]["video_count"] == 1


def test_gps_jump_splits_stops():
    # 400km jump in 20 min (e.g. flew between photos) -> new stop
    records = [rec(0, 64.1, -21.9), rec(20, 63.4, -19.0)]
    stops = build_stops(records)
    assert len(stops) == 2


def test_summarize_counts():
    records = [rec(0, 63.9, -22.6), rec(2, filetype="MP4"), rec(600)]
    s = summarize(records)
    assert s["total"] == 3
    assert s["photos"] == 2
    assert s["videos"] == 1
    assert s["with_gps"] == 1
    assert s["first_date"] == T0.isoformat()
