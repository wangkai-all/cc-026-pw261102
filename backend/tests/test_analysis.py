"""Verification tests for the four local scenarios.

These tests double-check the layers the page exposes: user denominators, the
cross-group list, the immature area, order deduplication, SRM, Fisher and the
user-level bootstrap interval.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from scipy import stats

from backend.app.analysis import BOOTSTRAP_SEED, _conversion, _revenue
from backend.app.data import DATA_DIR
from backend.app.main import app

client = TestClient(app)
SCENARIOS = ["normal", "srm", "cross_group", "immature"]


def manifest(slug: str) -> dict:
    return json.loads((DATA_DIR / slug / "manifest.json").read_text(encoding="utf-8"))


def analysis(experiment_id: str, **params) -> dict:
    response = client.get(
        "/api/analysis", params={"experiment_id": experiment_id, **params}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_experiments_are_discovered_in_documented_order() -> None:
    response = client.get("/api/experiments")
    assert response.status_code == 200
    experiments = response.json()["experiments"]
    assert [item["slug"] for item in experiments] == SCENARIOS
    for item in experiments:
        assert item["uniqueUsers"] < item["exposureEventRows"]
        assert item["firstExposureMinDate"] <= item["firstExposureMaxDate"]


@pytest.mark.parametrize("slug", SCENARIOS)
def test_manifest_layer_counts_are_reproduced(slug: str) -> None:
    expected = manifest(slug)
    result = analysis(expected["experiment_id"])

    funnel_keys = {
        "exposure_event_rows": "exposureEventRows",
        "unique_users_in_experiment": "uniqueUsersInExperiment",
        "first_exposure_users": "firstExposureUsers",
        "repeat_exposure_rows": "repeatExposureRows",
        "cross_group_users": "crossGroupUsers",
        "after_cross_group": "afterCrossGroup",
        "mature_users": "matureUsers",
        "immature_users": "immatureUsers",
        "effect_sample_users": "effectSampleUsers",
    }
    order_keys = {
        "raw_order_rows_for_effect_sample": "rawOrderRows",
        "before_first_exposure_rows": "beforeFirstExposureRows",
        "outside_window_rows": "outsideWindowRows",
        "in_window_rows": "inWindowRows",
        "duplicate_rows_removed": "duplicateRowsRemoved",
        "counted_orders": "countedOrders",
        "buyers": "buyers",
        "zero_revenue_users": "zeroRevenueUsers",
    }

    funnel = result["funnel"]
    by_group_keys = {
        "first_exposure": "firstExposure",
        "cross_group": "crossGroup",
        "after_cross_group": "afterCrossGroup",
        "mature": "mature",
        "immature": "immature",
    }
    for key, value in expected["funnel"].items():
        if key == "by_group":
            for group, counts in value.items():
                for layer, count in counts.items():
                    assert funnel["byGroup"][group][by_group_keys[layer]] == count, (
                        group,
                        layer,
                    )
        else:
            assert funnel[funnel_keys[key]] == value, key

    orders = result["orders"]
    for key, value in expected["orders"].items():
        assert orders[order_keys[key]] == value, key

    truth = expected["conversion_truth"]
    assert result["conversion"]["groups"]["control"]["converters"] == truth["control_converters"]
    assert result["conversion"]["groups"]["control"]["n"] == truth["control_n"]
    assert result["conversion"]["groups"]["treatment"]["converters"] == truth["treatment_converters"]
    assert result["conversion"]["groups"]["treatment"]["n"] == truth["treatment_n"]
    assert result["funnel"]["exposureEventRows"] < 4000
    assert result["funnel"]["firstExposureUsers"] == expected["funnel"]["first_exposure_users"]


def test_normal_assignment_has_known_rates_and_fisher_p_value() -> None:
    result = analysis("exp_normal")
    assert result["srm"]["status"] == "ok"
    assert result["srm"]["pValue"] == pytest.approx(1.0)
    assert result["funnel"]["firstExposureUsers"] == 2000
    assert result["funnel"]["matureUsers"] == 1800
    assert result["funnel"]["byGroup"]["control"]["mature"] == 900
    assert result["funnel"]["byGroup"]["treatment"]["mature"] == 900

    conversion = result["conversion"]
    assert conversion["available"] is True
    assert conversion["groups"]["control"]["conversionRate"] == pytest.approx(0.10)
    assert conversion["groups"]["treatment"]["conversionRate"] == pytest.approx(0.16)
    assert conversion["absoluteDifferencePp"] == pytest.approx(6.0)
    assert conversion["relativeLiftPct"] == pytest.approx(60.0)
    expected_p = stats.fisher_exact([[90, 810], [144, 756]], alternative="two-sided").pvalue
    assert conversion["pValue"] == pytest.approx(expected_p)
    assert conversion["oddsRatio"] == pytest.approx((144 * 810) / (756 * 90))

    # 294 counted orders belong to 234 buyers; the page must not use 294 as n.
    assert result["orders"]["countedOrders"] == 294
    assert result["orders"]["buyers"] == 234
    assert result["orders"]["zeroRevenueUsers"] == 1800 - 234


def test_normal_orders_are_trimmed_then_deduplicated_then_aggregated() -> None:
    result = analysis("exp_normal")
    orders = result["orders"]
    assert orders["rawOrderRows"] == 354
    assert orders["beforeFirstExposureRows"] == 24
    assert orders["outsideWindowRows"] == 16
    assert orders["inWindowRows"] == 314
    assert orders["duplicateRowsRemoved"] == 20
    assert orders["countedOrders"] == 294

    # Order 1 belongs to a buyer; the pre-exposure order of that same user must
    # not contribute. We verify the total revenue via the deduplicated unique
    # orders directly from the source files.
    exposures = pd.read_csv(DATA_DIR / "normal" / "exposures.csv", parse_dates=["exposure_time"])
    source_orders = pd.read_csv(DATA_DIR / "normal" / "orders.csv", parse_dates=["order_time"])
    first = (
        exposures.sort_values(["exposure_time", "group", "user_id"])
        .drop_duplicates("user_id", keep="first")
        .set_index("user_id")
    )
    effect_users = [
        user
        for user in first.index
        if first.loc[user, "exposure_time"] <= pd.Timestamp("2026-11-10") - pd.Timedelta(days=7)
    ]
    effective = source_orders[source_orders["user_id"].isin(effect_users)].copy()
    effective["first_time"] = effective["user_id"].map(first["exposure_time"])
    windowed = effective[
        (effective["order_time"] >= effective["first_time"])
        & (effective["order_time"] < effective["first_time"] + pd.Timedelta(days=7))
    ].drop_duplicates("order_id")
    assert len(windowed) == orders["countedOrders"]
    assert windowed["amount"].sum() == pytest.approx(
        result["revenue"]["groups"]["control"]["totalRevenue"]
        + result["revenue"]["groups"]["treatment"]["totalRevenue"]
    )


def test_srm_anomaly_pauses_conclusions_but_keeps_details() -> None:
    result = analysis("exp_srm")
    assert result["srm"]["observed"] == {"control": 700, "treatment": 1200}
    assert result["srm"]["pValue"] < 0.01
    assert result["srm"]["status"] == "anomaly"
    assert result["conclusion"]["paused"] is True
    assert result["conclusion"]["detailsStillVisible"] is True
    # Conversion and revenue details are still computed and visible.
    assert result["conversion"]["available"] is True
    assert result["conversion"]["pValue"] is not None
    assert result["revenue"]["ciLow"] is not None


def test_cross_group_users_are_listed_and_excluded_from_effect_sample() -> None:
    result = analysis("exp_cross_group")
    assert result["funnel"]["firstExposureUsers"] == 1600
    assert result["funnel"]["crossGroupUsers"] == 40
    assert result["funnel"]["afterCrossGroup"] == 1560
    assert result["funnel"]["matureUsers"] == 1520
    assert result["funnel"]["byGroup"]["control"]["mature"] == 760
    assert result["funnel"]["byGroup"]["treatment"]["mature"] == 760
    assert result["srm"]["observed"] == {"control": 800, "treatment": 800}

    cross = result["crossGroup"]["users"]
    assert len(cross) == 40
    assert {row["firstGroup"] for row in cross} == {"control", "treatment"}
    for row in cross:
        assert row["exposureCounts"]["control"] >= 1
        assert row["exposureCounts"]["treatment"] >= 1
        assert row["totalExposureRows"] == sum(row["exposureCounts"].values())
    assert result["orders"]["buyers"] == 198
    assert result["orders"]["rawOrderRows"] == 294  # excludes cross-group orders


def test_immature_users_are_not_counted_as_non_converted() -> None:
    result = analysis("exp_immature")
    assert result["funnel"]["firstExposureUsers"] == 600
    assert result["funnel"]["matureUsers"] == 300
    assert result["funnel"]["immatureUsers"] == 300
    assert result["conversion"]["groups"]["control"]["n"] == 150
    assert result["conversion"]["groups"]["treatment"]["n"] == 150
    assert result["orders"]["rawOrderRows"] == 72
    assert result["orders"]["countedOrders"] == 52
    assert result["orders"]["zeroRevenueUsers"] == 261

    # Every immature user is listed with < 7 observed days.
    immature = result["immature"]["users"]
    assert len(immature) == 300
    assert all(row["observedDays"] < 7 for row in immature)
    assert all(row["daysRemaining"] > 0 for row in immature)


def test_revenue_bootstrap_is_user_level_and_reproducible() -> None:
    first = analysis("exp_normal")
    second = analysis("exp_normal")
    revenue = first["revenue"]
    assert revenue["seed"] == BOOTSTRAP_SEED
    assert revenue["iterations"] == 10_000
    assert revenue["groups"]["control"]["n"] == 900
    assert revenue["groups"]["treatment"]["n"] == 900
    assert revenue["difference"] == pytest.approx(
        revenue["groups"]["treatment"]["meanRevenue"]
        - revenue["groups"]["control"]["meanRevenue"]
    )
    assert revenue["ciLow"] <= revenue["difference"] <= revenue["ciHigh"]
    assert second["revenue"]["ciLow"] == revenue["ciLow"]
    assert second["revenue"]["ciHigh"] == revenue["ciHigh"]


def test_different_date_range_changes_the_sample_but_keeps_users_as_unit() -> None:
    full = analysis("exp_normal")
    narrowed = analysis("exp_normal", start="2026-09-15", end="2026-09-30")
    assert narrowed["funnel"]["firstExposureUsers"] < full["funnel"]["firstExposureUsers"]
    assert narrowed["funnel"]["firstExposureUsers"] == sum(
        narrowed["funnel"]["byGroup"][group]["firstExposure"]
        for group in ("control", "treatment")
    )
    assert narrowed["funnel"]["exposureEventRows"] == full["funnel"]["exposureEventRows"]
    assert narrowed["srm"]["observed"]["control"] + narrowed["srm"]["observed"]["treatment"] == (
        narrowed["funnel"]["firstExposureUsers"]
    )


def test_empty_range_explains_unavailable_results() -> None:
    result = analysis("exp_normal", start="2026-10-29", end="2026-11-04")
    assert result["funnel"]["firstExposureUsers"] == 0
    assert result["srm"]["status"] == "insufficient"
    assert result["srm"]["pValue"] is None
    assert result["conversion"]["available"] is False
    assert "没有" in result["conversion"]["reason"]
    assert result["revenue"]["available"] is False
    assert "没有" in result["revenue"]["reason"]


def test_empty_group_is_explained_not_silently_zero() -> None:
    effect = pd.DataFrame(
        {
            "user_id": ["c1", "c2"],
            "first_group": ["control", "control"],
            "converted": [True, False],
            "revenue": [10.0, 0.0],
        }
    )
    conversion = _conversion(effect)
    assert conversion["available"] is False
    assert "实验组没有成熟用户" in conversion["reason"]
    revenue = _revenue(effect)
    assert revenue["available"] is False
    assert "实验组没有成熟用户" in revenue["reason"]


def test_zero_control_conversion_explains_relative_lift() -> None:
    effect = pd.DataFrame(
        {
            "user_id": ["c1", "c2", "t1", "t2"],
            "first_group": ["control", "control", "treatment", "treatment"],
            "converted": [False, False, True, False],
            "revenue": [0.0, 0.0, 10.0, 0.0],
        }
    )
    conversion = _conversion(effect)
    assert conversion["available"] is True
    assert conversion["groups"]["control"]["conversionRate"] == 0
    assert conversion["relativeLiftPct"] is None
    assert "无法定义" in conversion["relativeLiftNote"]
    assert conversion["absoluteDifferencePp"] == pytest.approx(50.0)


def test_expected_ratio_and_date_validation() -> None:
    bad_ratio = client.get(
        "/api/analysis",
        params={"experiment_id": "exp_normal", "expected_control_pct": 40, "expected_treatment_pct": 40},
    )
    assert bad_ratio.status_code == 400
    assert "100" in bad_ratio.json()["detail"]

    bad_date = client.get(
        "/api/analysis",
        params={"experiment_id": "exp_normal", "start": "2026-10-01", "end": "2026-09-01"},
    )
    assert bad_date.status_code == 400

    missing = client.get("/api/analysis", params={"experiment_id": "nope"})
    assert missing.status_code == 404


def test_expected_ratio_is_checked_against_all_first_exposure_users() -> None:
    # A non-50/50 expectation can turn the same observed split into an anomaly.
    result = analysis(
        "exp_cross_group",
        expected_control_pct=60,
        expected_treatment_pct=40,
    )
    assert result["srm"]["observed"] == {"control": 800, "treatment": 800}
    assert result["srm"]["expected"]["control"] == pytest.approx(960.0)
    assert result["srm"]["expected"]["treatment"] == pytest.approx(640.0)
    assert result["srm"]["status"] == "anomaly"
    assert result["conclusion"]["paused"] is True
