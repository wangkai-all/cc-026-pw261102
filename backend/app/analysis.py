"""Sample construction and statistics for one experiment analysis."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .data import Scenario, first_exposure_table

GROUPS = ("control", "treatment")
OBSERVATION_DAYS = 7
SRM_ALPHA = 0.01
BOOTSTRAP_SEED = 20261112
BOOTSTRAP_ITERATIONS = 10_000
LIST_LIMIT = 500


def _value(value: Any) -> Any:
    """Convert numpy / pandas scalars to JSON-friendly Python values."""

    if value is None or value is pd.NaT:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        return None if not np.isfinite(result) else result
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _timestamp(value: pd.Timestamp | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def _group_counts(frame: pd.DataFrame) -> dict[str, int]:
    return {
        group: int((frame["first_group"] == group).sum()) for group in GROUPS
    }


def _sample_ratio_mismatch(
    observed: dict[str, int],
    expected_control_pct: float,
    expected_treatment_pct: float,
) -> dict[str, Any]:
    total = sum(observed.values())
    expected_share = {
        "control": expected_control_pct / 100.0,
        "treatment": expected_treatment_pct / 100.0,
    }
    if total == 0:
        return {
            "status": "insufficient",
            "reliable": False,
            "pValue": None,
            "chiSquare": None,
            "alpha": SRM_ALPHA,
            "observed": observed,
            "expected": {"control": 0.0, "treatment": 0.0},
            "observedShare": {group: None for group in GROUPS},
            "expectedShare": expected_share,
            "deviationPp": {group: None for group in GROUPS},
            "note": "所选范围内没有首次曝光用户，无法做分流检查。",
        }

    expected_counts = {group: total * expected_share[group] for group in GROUPS}
    observed_values = [observed[group] for group in GROUPS]
    expected_values = [expected_counts[group] for group in GROUPS]
    result = stats.chisquare(f_obs=observed_values, f_exp=expected_values)
    p_value = float(result.pvalue)
    status = "anomaly" if p_value < SRM_ALPHA else "ok"
    reliable = min(expected_values) >= 5
    observed_share = {group: observed[group] / total for group in GROUPS}
    deviation_pp = {
        group: (observed_share[group] - expected_share[group]) * 100.0
        for group in GROUPS
    }
    note = (
        "样本比例失衡：实际分流比例与预期比例差异显著，效果结论暂停。"
        if status == "anomaly"
        else "未发现样本比例失衡。"
    )
    if not reliable:
        note += " 至少一组的预期人数少于 5，卡方检验仅为近似结果。"
    return {
        "status": status,
        "reliable": reliable,
        "pValue": p_value,
        "chiSquare": float(result.statistic),
        "alpha": SRM_ALPHA,
        "observed": observed,
        "expected": {group: _value(expected_counts[group]) for group in GROUPS},
        "observedShare": {group: _value(observed_share[group]) for group in GROUPS},
        "expectedShare": expected_share,
        "deviationPp": {group: _value(deviation_pp[group]) for group in GROUPS},
        "note": note,
    }


def _empty_conversion(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "method": "双侧 Fisher 精确检验",
        "groups": {
            group: {"n": 0, "converters": 0, "conversionRate": None}
            for group in GROUPS
        },
        "pValue": None,
        "absoluteDifferencePp": None,
        "relativeLiftPct": None,
    }


def _conversion(effect: pd.DataFrame) -> dict[str, Any]:
    groups = {}
    for group in GROUPS:
        subset = effect.loc[effect["first_group"] == group]
        n = int(len(subset))
        converters = int(subset["converted"].sum())
        groups[group] = {
            "n": n,
            "converters": converters,
            "conversionRate": _value(converters / n) if n else None,
        }
    empty_groups = [group for group in GROUPS if groups[group]["n"] == 0]
    if empty_groups:
        labels = "、".join("对照组" if g == "control" else "实验组" for g in empty_groups)
        return _empty_conversion(f"{labels}没有成熟用户，无法计算转化差异。")

    table = [
        [
            groups["control"]["converters"],
            groups["control"]["n"] - groups["control"]["converters"],
        ],
        [
            groups["treatment"]["converters"],
            groups["treatment"]["n"] - groups["treatment"]["converters"],
        ],
    ]
    result = stats.fisher_exact(table, alternative="two-sided")
    p_value = float(result.pvalue)
    # Present the odds ratio in the same direction as the displayed difference:
    # treatment odds divided by control odds.
    denominator = table[1][1] * table[0][0]
    odds_ratio = (
        float((table[1][0] * table[0][1]) / denominator)
        if denominator > 0
        else None
    )

    control_rate = groups["control"]["conversionRate"]
    treatment_rate = groups["treatment"]["conversionRate"]
    absolute_difference_pp = (treatment_rate - control_rate) * 100.0
    if control_rate > 0:
        relative_lift_pct = (treatment_rate - control_rate) / control_rate * 100.0
        relative_note = None
    else:
        relative_lift_pct = None
        relative_note = "对照组转化率为 0，相对提升无法定义。"

    return {
        "available": True,
        "reason": None,
        "method": "双侧 Fisher 精确检验",
        "groups": groups,
        "fisherTable": {
            "control": {"converted": table[0][0], "notConverted": table[0][1]},
            "treatment": {"converted": table[1][0], "notConverted": table[1][1]},
        },
        "oddsRatio": odds_ratio,
        "pValue": p_value,
        "absoluteDifferencePp": _value(absolute_difference_pp),
        "relativeLiftPct": _value(relative_lift_pct),
        "relativeLiftNote": relative_note,
        "direction": "treatment_minus_control",
    }


def _bootstrap_interval(
    control_revenue: np.ndarray, treatment_revenue: np.ndarray
) -> tuple[float, float]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    differences = np.empty(BOOTSTRAP_ITERATIONS, dtype=float)
    for index in range(BOOTSTRAP_ITERATIONS):
        control_sample = rng.choice(
            control_revenue, size=control_revenue.size, replace=True
        )
        treatment_sample = rng.choice(
            treatment_revenue, size=treatment_revenue.size, replace=True
        )
        differences[index] = treatment_sample.mean() - control_sample.mean()
    low, high = np.percentile(differences, [2.5, 97.5])
    return float(low), float(high)


def _empty_revenue(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "groups": {
            group: {"n": 0, "meanRevenue": None, "totalRevenue": None}
            for group in GROUPS
        },
        "difference": None,
        "ciLow": None,
        "ciHigh": None,
        "ciLevel": 0.95,
        "method": "用户级 bootstrap，百分位区间",
        "seed": BOOTSTRAP_SEED,
        "iterations": BOOTSTRAP_ITERATIONS,
    }


def _revenue(effect: pd.DataFrame) -> dict[str, Any]:
    values = {
        group: effect.loc[effect["first_group"] == group, "revenue"].to_numpy(
            dtype=float
        )
        for group in GROUPS
    }
    empty_groups = [group for group in GROUPS if values[group].size == 0]
    if empty_groups:
        labels = "、".join("对照组" if g == "control" else "实验组" for g in empty_groups)
        return _empty_revenue(f"{labels}没有成熟用户，无法计算每用户收入差异。")

    control = values["control"]
    treatment = values["treatment"]
    control_mean = float(control.mean())
    treatment_mean = float(treatment.mean())
    difference = treatment_mean - control_mean
    ci_low, ci_high = _bootstrap_interval(control, treatment)
    notes = []
    if min(control.size, treatment.size) < 30:
        notes.append("至少一组用户数少于 30，bootstrap 区间可能不稳定。")
    if np.all(control == 0) and np.all(treatment == 0):
        notes.append("两组每用户收入均为 0，区间退化为 0。")

    return {
        "available": True,
        "reason": None,
        "groups": {
            "control": {
                "n": int(control.size),
                "meanRevenue": _value(control_mean),
                "totalRevenue": _value(float(control.sum())),
            },
            "treatment": {
                "n": int(treatment.size),
                "meanRevenue": _value(treatment_mean),
                "totalRevenue": _value(float(treatment.sum())),
            },
        },
        "difference": _value(difference),
        "ciLow": _value(ci_low),
        "ciHigh": _value(ci_high),
        "ciLevel": 0.95,
        "method": "用户级 bootstrap，百分位区间",
        "seed": BOOTSTRAP_SEED,
        "iterations": BOOTSTRAP_ITERATIONS,
        "notes": notes,
    }


def analyze_experiment(
    scenario: Scenario,
    start: date,
    end: date,
    expected_control_pct: float,
    expected_treatment_pct: float,
) -> dict[str, Any]:
    exposures = scenario.exposures
    orders = scenario.orders
    first = first_exposure_table(exposures)

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    sample = first.loc[
        (first["first_time"] >= start_ts) & (first["first_time"] <= end_ts)
    ].copy()

    exposure_rows_by_user = exposures.groupby("user_id").size()
    groups_by_user = exposures.groupby("user_id")["group"].nunique()
    sample["group_count"] = sample["user_id"].map(groups_by_user).fillna(0).astype(int)
    cross_mask = sample["group_count"] > 1
    cross_users = sample.loc[cross_mask, "user_id"].tolist()
    non_cross = sample.loc[~cross_mask].copy()

    maturity_cutoff = scenario.data_cutoff - pd.Timedelta(days=OBSERVATION_DAYS)
    non_cross["mature"] = non_cross["first_time"] <= maturity_cutoff
    effect = non_cross.loc[non_cross["mature"]].copy()
    immature = non_cross.loc[~non_cross["mature"]].copy()

    sample_counts = _group_counts(sample)
    cross_counts = _group_counts(sample.loc[cross_mask])
    after_cross_counts = _group_counts(non_cross)
    mature_counts = _group_counts(effect)
    immature_counts = _group_counts(immature)

    repeat_exposure_rows = 0
    if len(sample):
        rows_for_sample_users = int(
            exposure_rows_by_user.reindex(sample["user_id"]).fillna(0).sum()
        )
        repeat_exposure_rows = max(0, rows_for_sample_users - len(sample))

    # ---- order layer, effect sample only --------------------------------
    effect_users = effect[["user_id", "first_group", "first_time"]].copy()
    joined_orders = orders.merge(effect_users, on="user_id", how="inner")
    if len(joined_orders):
        before_mask = joined_orders["order_time"] < joined_orders["first_time"]
        window_end = joined_orders["first_time"] + pd.Timedelta(days=OBSERVATION_DAYS)
        outside_mask = joined_orders["order_time"] >= window_end
        in_window = joined_orders.loc[~before_mask & ~outside_mask].copy()
        deduplicated = in_window.sort_values(
            ["order_id", "order_time"], kind="stable"
        ).drop_duplicates(subset="order_id", keep="first")
        duplicate_rows_removed = int(len(in_window) - len(deduplicated))

        order_agg = (
            deduplicated.groupby("user_id")
            .agg(order_count=("order_id", "size"), revenue=("amount", "sum"))
            .reset_index()
        )
        counted_orders = int(len(deduplicated))
        effect = effect.merge(order_agg, on="user_id", how="left")
        effect["order_count"] = effect["order_count"].fillna(0).astype(int)
        effect["revenue"] = effect["revenue"].fillna(0.0).astype(float)
    else:
        before_mask = pd.Series(False, index=joined_orders.index)
        outside_mask = pd.Series(False, index=joined_orders.index)
        in_window = joined_orders
        duplicate_rows_removed = 0
        counted_orders = 0
        effect["order_count"] = 0
        effect["revenue"] = 0.0

    effect["converted"] = effect["order_count"] > 0
    buyers = int(effect["converted"].sum())

    order_stats = {
        "rawOrderRows": int(len(joined_orders)),
        "beforeFirstExposureRows": int(before_mask.sum()),
        "outsideWindowRows": int(outside_mask.sum()),
        "inWindowRows": int(len(in_window)),
        "duplicateRowsRemoved": int(duplicate_rows_removed),
        "countedOrders": counted_orders,
        "buyers": buyers,
        "zeroRevenueUsers": int(len(effect) - buyers),
        "byGroup": {
            group: {
                "buyers": int(effect.loc[effect["first_group"] == group, "converted"].sum()),
                "zeroRevenueUsers": int(
                    (
                        effect["first_group"].eq(group)
                        & ~effect["converted"]
                    ).sum()
                ),
            }
            for group in GROUPS
        },
    }

    # ---- assignment check (all first-exposure users) --------------------
    srm = _sample_ratio_mismatch(
        sample_counts, expected_control_pct, expected_treatment_pct
    )

    # ---- effect statistics ---------------------------------------------
    conversion = _conversion(effect)
    revenue = _revenue(effect)

    # ---- detail lists ---------------------------------------------------
    cross_matrix: pd.DataFrame | None = None
    if cross_users:
        cross_matrix = (
            exposures.loc[exposures["user_id"].isin(cross_users)]
            .groupby(["user_id", "group"])
            .size()
            .unstack(fill_value=0)
        )

    cross_details = []
    for row in sample.loc[cross_mask].sort_values("user_id").itertuples(index=False):
        counts = {
            group: int(cross_matrix.loc[row.user_id, group])
            if cross_matrix is not None and group in cross_matrix.columns
            else 0
            for group in GROUPS
        }
        cross_details.append(
            {
                "userId": row.user_id,
                "firstGroup": row.first_group,
                "firstExposure": _timestamp(row.first_time),
                "exposureCounts": counts,
                "totalExposureRows": int(sum(counts.values())),
            }
        )

    immature_details = []
    for row in immature.sort_values("user_id").itertuples(index=False):
        observed_days = (
            (scenario.data_cutoff - row.first_time).total_seconds() / 86400.0
        )
        immature_details.append(
            {
                "userId": row.user_id,
                "firstGroup": row.first_group,
                "firstExposure": _timestamp(row.first_time),
                "observedDays": _value(round(observed_days, 2)),
                "daysRemaining": _value(round(max(0.0, OBSERVATION_DAYS - observed_days), 2)),
            }
        )

    # ---- warnings and conclusions --------------------------------------
    warnings = []
    if len(exposures) > int(exposures["user_id"].nunique()):
        warnings.append(
            f"曝光文件有 {len(exposures)} 条事件，去重后为 "
            f"{int(exposures['user_id'].nunique())} 名用户；所有分母均按用户计。"
        )
    if cross_details:
        warnings.append(f"{len(cross_details)} 名跨组用户已另列，并排除出效果分析。")
    if len(immature_details):
        warnings.append(
            f"{len(immature_details)} 名用户观察期不足 7 天，已放入未成熟区，未计为未转化。"
        )
    if order_stats["duplicateRowsRemoved"]:
        warnings.append(
            f"七天窗口内按订单号去除 {order_stats['duplicateRowsRemoved']} 条重复行。"
        )
    if srm["status"] == "anomaly":
        warnings.append(
            f"分流检查 p={srm['pValue']:.4g} < {SRM_ALPHA}，效果结论已暂停。"
        )

    paused = srm["status"] == "anomaly"
    conclusion = {
        "paused": paused,
        "reason": srm["note"] if paused else None,
        "detailsStillVisible": True,
    }

    return {
        "experiment": {
            "experimentId": scenario.experiment_id,
            "title": scenario.meta.get("title", scenario.experiment_id),
            "description": scenario.meta.get("description", ""),
            "groups": scenario.meta.get(
                "groups", {"control": "对照组", "treatment": "实验组"}
            ),
            "dataCutoff": _timestamp(scenario.data_cutoff),
        },
        "query": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "expectedControlPct": expected_control_pct,
            "expectedTreatmentPct": expected_treatment_pct,
        },
        "rules": {
            "observationDays": OBSERVATION_DAYS,
            "grouping": "每人首次曝光决定分组，重复曝光不加人；跨组用户另列并排除。",
            "maturity": "首次曝光时间 <= 数据截止时间 - 7 天，才算拥有完整七天观察期。",
            "orderWindow": "订单时间落在 [首次曝光, 首次曝光 + 7 天)，先按订单号去重，再汇总到用户。",
            "srmAlpha": SRM_ALPHA,
            "bootstrapSeed": BOOTSTRAP_SEED,
            "bootstrapIterations": BOOTSTRAP_ITERATIONS,
            "listLimit": LIST_LIMIT,
        },
        "funnel": {
            "exposureEventRows": int(len(exposures)),
            "uniqueUsersInExperiment": int(exposures["user_id"].nunique()),
            "firstExposureUsers": int(len(sample)),
            "repeatExposureRows": int(repeat_exposure_rows),
            "crossGroupUsers": int(len(cross_details)),
            "afterCrossGroup": int(len(non_cross)),
            "matureUsers": int(len(effect)),
            "immatureUsers": int(len(immature_details)),
            "effectSampleUsers": int(len(effect)),
            "byGroup": {
                group: {
                    "firstExposure": sample_counts[group],
                    "crossGroup": cross_counts[group],
                    "afterCrossGroup": after_cross_counts[group],
                    "mature": mature_counts[group],
                    "immature": immature_counts[group],
                }
                for group in GROUPS
            },
            "steps": [
                {
                    "key": "first_exposure",
                    "label": "首次曝光用户",
                    "count": int(len(sample)),
                    "share": 1.0 if len(sample) else None,
                    "removed": 0,
                    "note": "所选日期范围内，每人只计一次",
                },
                {
                    "key": "after_cross_group",
                    "label": "排除跨组用户",
                    "count": int(len(non_cross)),
                    "share": _value(len(non_cross) / len(sample)) if len(sample) else None,
                    "removed": int(len(cross_details)),
                    "note": "跨组用户不属于任何单一分组",
                },
                {
                    "key": "mature",
                    "label": "观察期成熟（效果样本）",
                    "count": int(len(effect)),
                    "share": _value(len(effect) / len(sample)) if len(sample) else None,
                    "removed": int(len(immature_details)),
                    "note": "未成熟用户留在未成熟区，不算未转化",
                },
            ],
        },
        "orders": order_stats,
        "srm": srm,
        "conversion": conversion,
        "revenue": revenue,
        "crossGroup": {
            "count": int(len(cross_details)),
            "truncated": len(cross_details) > LIST_LIMIT,
            "users": cross_details[:LIST_LIMIT],
        },
        "immature": {
            "count": int(len(immature_details)),
            "truncated": len(immature_details) > LIST_LIMIT,
            "users": immature_details[:LIST_LIMIT],
        },
        "warnings": warnings,
        "conclusion": conclusion,
    }
