"""The four ratings: what earns each level, and what happens when data is missing."""

import pytest

from housing import ratings


def access(road=None, centre=None, city=None, station=None):
    def part(distance_m):
        return None if distance_m is None else {"distance_m": distance_m, "name": "x"}

    return {
        "road": part(road),
        "centre": part(centre),
        "city": part(city),
        "station": part(station),
    }


def flood(low=0.0, moderate=0.0, high=0.0, max_index=None):
    return {
        "radius_m": 1000,
        "samples": 61,
        "share": {"low": low, "moderate": moderate, "high": high},
        "max_index": max_index,
        "river_share": low + moderate + high,
        "flash_share": 0.0,
    }


def units(available, sold, commercial_available=None, commercial_sold=None):
    return {
        "subsidized_available": available,
        "subsidized_sold": sold,
        "commercial_available": commercial_available,
        "commercial_sold": commercial_sold,
    }


def test_closeness_is_full_up_close_and_falls_to_zero():
    road = ratings.ACCESS_PARTS["road"]
    assert ratings.closeness(100, road) == 100
    assert ratings.closeness(road.full_m, road) == 100
    assert ratings.closeness((road.full_m + road.zero_m) / 2, road) == pytest.approx(50)
    assert ratings.closeness(road.zero_m, road) == 0
    assert ratings.closeness(10_000, road) == 0
    assert ratings.closeness(None, road) == 0


def test_access_next_to_everything_is_five():
    rating = ratings.access_rating(access(road=100, centre=500, city=3_000, station=400))
    assert rating["level"] == 5
    assert rating["score"] == 100
    assert rating["road"] == {"distance_m": 100, "name": "x", "score": 100}


def test_access_far_from_everything_is_one():
    rating = ratings.access_rating(access(road=3_200, centre=9_000, city=40_000))
    assert rating["level"] == 1
    assert rating["score"] == 0
    # No station was found within the search radius: no credit, and no made-up distance.
    assert rating["station"] is None


def test_access_weights_the_road_most():
    by_the_road = ratings.access_rating(access(road=100, centre=9_000, city=40_000))
    by_the_station = ratings.access_rating(
        access(road=3_200, centre=9_000, city=40_000, station=100)
    )
    assert by_the_road["score"] == 40
    assert by_the_station["score"] == 15
    assert by_the_road["level"] > by_the_station["level"]


def test_access_without_measurements_is_unrated():
    assert ratings.access_rating(None) == {"level": None}


@pytest.mark.parametrize(
    ("index", "expected"),
    [(None, None), (0, None), (0.2, "low"), (1 / 3, "low"), (0.5, "moderate"), (0.9, "high")],
)
def test_hazard_classes_follow_bnpb_thirds(index, expected):
    assert ratings.hazard_class(index) == expected


def test_flood_outside_every_zone_is_five():
    rating = ratings.flood_rating(flood())
    assert rating["level"] == 5
    assert rating["exposure"] == 0
    assert rating["max_class"] is None


@pytest.mark.parametrize(
    ("shares", "level"),
    [
        ({"low": 0.2}, 4),  # exposure 0.067
        ({"moderate": 0.3}, 3),  # exposure 0.2
        ({"moderate": 0.7}, 2),  # exposure 0.467
        ({"moderate": 0.4, "high": 0.6}, 1),  # exposure 0.867
    ],
)
def test_flood_level_falls_as_more_of_the_area_is_at_risk(shares, level):
    assert ratings.flood_rating(flood(**shares, max_index=0.5))["level"] == level


def test_flood_reports_how_much_of_the_area_is_in_any_zone():
    rating = ratings.flood_rating(flood(low=0.1, moderate=0.2, high=0.3, max_index=0.8))
    assert rating["hazard_share"] == pytest.approx(0.6)
    assert rating["max_class"] == "high"


def test_sold_share_counts_commercial_units_too():
    assert ratings.sold_share(units(49, 159)) == {"sold": 159, "total": 208, "share": 0.764}
    assert ratings.sold_share(units(10, 30, 10, 50)) == {"sold": 80, "total": 100, "share": 0.8}


@pytest.mark.parametrize(
    "counts",
    [None, {}, units(None, 5), units(23, None), units(0, 0)],
)
def test_sold_share_needs_both_subsidized_counts(counts):
    assert ratings.sold_share(counts) is None
    assert ratings.occupancy_rating(counts) == {"level": None}
    assert ratings.construction_rating(counts) == {"level": None}


@pytest.mark.parametrize(
    ("available", "sold", "occupancy", "construction"),
    [
        (100, 0, 1, 1),  # nothing handed over yet
        (95, 5, 1, 2),  # a first few
        (70, 30, 2, 3),
        (50, 50, 3, 3),
        (25, 75, 4, 4),
        (8, 92, 5, 4),
        (2, 98, 5, 5),  # all but sold out
    ],
)
def test_occupancy_and_construction_levels(available, sold, occupancy, construction):
    assert ratings.occupancy_rating(units(available, sold))["level"] == occupancy
    assert ratings.construction_rating(units(available, sold))["level"] == construction


def test_overall_is_the_mean_of_what_could_be_rated():
    rated = ratings.rate(
        access=access(road=100, centre=500, city=3_000, station=400),  # 5
        flood=flood(moderate=0.3, max_index=0.5),  # 3
        units=None,  # occupancy and construction unknown
        survey={},
    )
    assert rated["occupancy"]["level"] is None
    assert rated["overall"] == 4.0


def test_overall_is_none_when_nothing_could_be_rated():
    assert ratings.rate(access=None, flood=None, units=None, survey={})["overall"] is None


def test_a_site_survey_replaces_the_estimate_and_keeps_it_visible():
    rated = ratings.rate(
        access=None,
        flood=flood(),
        units=units(25, 75),
        survey={
            "occupancy": {"level": 2, "note": "Banyak rumah kosong", "date": "2026-12-01"},
            "unknown": {"level": 5},
            "flood": {"level": 9},  # not a level: ignored
        },
    )
    assert rated["occupancy"]["level"] == 2
    assert rated["occupancy"]["estimated_level"] == 4
    assert rated["occupancy"]["survey"] == {"note": "Banyak rumah kosong", "date": "2026-12-01"}
    assert rated["flood"]["level"] == 5
    assert "survey" not in rated["flood"]
    # flood 5, occupancy 2 (surveyed), construction 4
    assert rated["overall"] == 3.7
