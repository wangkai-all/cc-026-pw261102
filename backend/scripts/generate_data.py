#!/usr/bin/env python3
"""Generate the four local experiment datasets used by the analysis page.

The output is deterministic and intentionally small. Each scenario lives in its
own directory with an exposure file, an order file, a metadata file and a
manifest of the layer counts the UI/API should reproduce.

Run from anywhere:
    python backend/scripts/generate_data.py
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "scenarios"
CUTOFF = datetime(2026, 11, 10, 0, 0, 0)
MATURE_RANGE = (datetime(2026, 9, 15, 0, 0, 0), datetime(2026, 10, 28, 23, 59, 59))
IMMATURE_RANGE = (datetime(2026, 11, 5, 0, 0, 0), datetime(2026, 11, 9, 23, 59, 59))
OBSERVATION_DAYS = 7
RNG_SEED = 20261112


@dataclass
class ScenarioSpec:
    slug: str
    experiment_id: str
    title: str
    description: str
    control_total: int
    control_mature: int
    treatment_total: int
    treatment_mature: int
    control_cross: int
    treatment_cross: int
    control_converters: int
    treatment_converters: int
    control_second_orders: int
    treatment_second_orders: int
    control_duplicate_rows: int
    treatment_duplicate_rows: int
    control_pre_rows: int
    treatment_pre_rows: int
    control_post_rows: int
    treatment_post_rows: int
    control_immature_orders: int
    treatment_immature_orders: int
    repeat_modulus: int
    expected_control_pct: int = 50

    @property
    def control_immature(self) -> int:
        return self.control_total - self.control_mature

    @property
    def treatment_immature(self) -> int:
        return self.treatment_total - self.treatment_mature

    @property
    def control_effect(self) -> int:
        return self.control_mature - self.control_cross

    @property
    def treatment_effect(self) -> int:
        return self.treatment_mature - self.treatment_cross


SPECS = [
    ScenarioSpec(
        slug="normal",
        experiment_id="exp_normal",
        title="正常分流",
        description="50/50 分流，存在重复曝光、少量未成熟用户与应被排除的订单。",
        control_total=1000,
        control_mature=900,
        treatment_total=1000,
        treatment_mature=900,
        control_cross=0,
        treatment_cross=0,
        control_converters=90,
        treatment_converters=144,
        control_second_orders=25,
        treatment_second_orders=35,
        control_duplicate_rows=10,
        treatment_duplicate_rows=10,
        control_pre_rows=12,
        treatment_pre_rows=12,
        control_post_rows=8,
        treatment_post_rows=8,
        control_immature_orders=15,
        treatment_immature_orders=15,
        repeat_modulus=7,
    ),
    ScenarioSpec(
        slug="srm",
        experiment_id="exp_srm",
        title="明显偏流",
        description="标称 50/50，实际首次曝光人数约 700 : 1200，SRM 检验应报警并暂停结论。",
        control_total=700,
        control_mature=600,
        treatment_total=1200,
        treatment_mature=1100,
        control_cross=0,
        treatment_cross=0,
        control_converters=60,
        treatment_converters=165,
        control_second_orders=15,
        treatment_second_orders=30,
        control_duplicate_rows=8,
        treatment_duplicate_rows=8,
        control_pre_rows=8,
        treatment_pre_rows=8,
        control_post_rows=6,
        treatment_post_rows=6,
        control_immature_orders=10,
        treatment_immature_orders=15,
        repeat_modulus=9,
    ),
    ScenarioSpec(
        slug="cross_group",
        experiment_id="exp_cross_group",
        title="跨组曝光",
        description="40 名用户同时出现在两组，另列并从效果分析中排除；其余分流均衡。",
        control_total=800,
        control_mature=780,
        treatment_total=800,
        treatment_mature=780,
        control_cross=20,
        treatment_cross=20,
        control_converters=76,
        treatment_converters=122,
        control_second_orders=20,
        treatment_second_orders=32,
        control_duplicate_rows=8,
        treatment_duplicate_rows=8,
        control_pre_rows=8,
        treatment_pre_rows=8,
        control_post_rows=6,
        treatment_post_rows=6,
        control_immature_orders=10,
        treatment_immature_orders=10,
        repeat_modulus=8,
    ),
    ScenarioSpec(
        slug="immature",
        experiment_id="exp_immature",
        title="观察期不足",
        description="一半用户首次曝光不足 7 天，应进入未成熟区而不是算作未转化。",
        control_total=300,
        control_mature=150,
        treatment_total=300,
        treatment_mature=150,
        control_cross=0,
        treatment_cross=0,
        control_converters=15,
        treatment_converters=24,
        control_second_orders=5,
        treatment_second_orders=8,
        control_duplicate_rows=3,
        treatment_duplicate_rows=3,
        control_pre_rows=4,
        treatment_pre_rows=4,
        control_post_rows=3,
        treatment_post_rows=3,
        control_immature_orders=30,
        treatment_immature_orders=30,
        repeat_modulus=5,
    ),
]


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _pick_times(rng: np.random.Generator, start: datetime, end: datetime, n: int) -> list[datetime]:
    span = int((end - start).total_seconds())
    offsets = rng.integers(0, span + 1, size=n)
    return [start + timedelta(seconds=int(offset)) for offset in offsets]


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate(spec: ScenarioSpec) -> None:
    rng = np.random.default_rng(RNG_SEED + sum(ord(ch) for ch in spec.slug))

    users: list[dict] = []
    exposure_rows: list[dict] = []

    for group, total, mature, cross in (
        ("control", spec.control_total, spec.control_mature, spec.control_cross),
        ("treatment", spec.treatment_total, spec.treatment_mature, spec.treatment_cross),
    ):
        prefix = f"{spec.slug}_{'c' if group == 'control' else 't'}"
        mature_times = _pick_times(rng, *MATURE_RANGE, mature)
        immature_times = _pick_times(rng, *IMMATURE_RANGE, total - mature)
        first_times = [*mature_times, *immature_times]

        for idx, first_time in enumerate(first_times):
            user_id = f"{prefix}_{idx + 1:04d}"
            is_mature = idx < mature
            users.append(
                {
                    "user_id": user_id,
                    "group": group,
                    "first_time": first_time,
                    "mature": is_mature,
                    "cross": is_mature and idx < cross,
                }
            )
            exposure_rows.append(
                {
                    "experiment_id": spec.experiment_id,
                    "user_id": user_id,
                    "group": group,
                    "exposure_time": _fmt(first_time),
                }
            )
            # Re-exposure events deliberately inflate the event row count without
            # adding users. Only mature users get them so they stay before cutoff.
            if is_mature and idx % spec.repeat_modulus == 0:
                repeat_time = first_time + timedelta(hours=8 + (idx % 11))
                exposure_rows.append(
                    {
                        "experiment_id": spec.experiment_id,
                        "user_id": user_id,
                        "group": group,
                        "exposure_time": _fmt(repeat_time),
                    }
                )

    # A cross-group user has at least one exposure in the other arm. The first
    # exposure still determines the group used by the SRM check.
    cross_users = [user for user in users if user["cross"]]
    for user in cross_users:
        other_group = "treatment" if user["group"] == "control" else "control"
        exposure_rows.append(
            {
                "experiment_id": spec.experiment_id,
                "user_id": user["user_id"],
                "group": other_group,
                "exposure_time": _fmt(user["first_time"] + timedelta(days=1, hours=2)),
            }
        )

    # Pin the derived data cutoff to a known instant with a harmless repeat
    # exposure of an existing user.
    anchor_user = next(user for user in users if user["group"] == "control" and user["mature"])
    exposure_rows.append(
        {
            "experiment_id": spec.experiment_id,
            "user_id": anchor_user["user_id"],
            "group": "control",
            "exposure_time": _fmt(CUTOFF),
        }
    )

    exposure_rows.sort(key=lambda row: (row["experiment_id"], row["exposure_time"], row["user_id"]))
    exposure_path = DATA_DIR / spec.slug / "exposures.csv"
    _write_csv(exposure_path, ["experiment_id", "user_id", "group", "exposure_time"], exposure_rows)

    # ---- Orders -----------------------------------------------------------
    order_rows: list[dict] = []
    order_counter = [0]

    def new_order_id() -> str:
        order_counter[0] += 1
        return f"{spec.slug}_o_{order_counter[0]:05d}"

    def add_order(user: dict, when: datetime, amount: int, order_id: str | None = None) -> str:
        oid = order_id or new_order_id()
        order_rows.append(
            {
                "order_id": oid,
                "user_id": user["user_id"],
                "order_time": _fmt(when),
                "amount": f"{amount:.2f}",
            }
        )
        return oid

    for group in ("control", "treatment"):
        group_users = [user for user in users if user["group"] == group]
        effect_users = [user for user in group_users if user["mature"] and not user["cross"]]
        immature_users = [user for user in group_users if not user["mature"]]
        cross_users_group = [user for user in group_users if user["cross"]]

        converters = spec.control_converters if group == "control" else spec.treatment_converters
        second_orders = spec.control_second_orders if group == "control" else spec.treatment_second_orders
        duplicate_rows = spec.control_duplicate_rows if group == "control" else spec.treatment_duplicate_rows
        pre_rows = spec.control_pre_rows if group == "control" else spec.treatment_pre_rows
        post_rows = spec.control_post_rows if group == "control" else spec.treatment_post_rows
        immature_orders = (
            spec.control_immature_orders if group == "control" else spec.treatment_immature_orders
        )

        buyer_users = effect_users[:converters]

        # Base in-window order for every converter.
        base_ids: list[str] = []
        for user in buyer_users:
            amount = int(rng.integers(20, 91))
            base_ids.append(add_order(user, user["first_time"] + timedelta(hours=int(rng.integers(1, 48))), amount))

        # A second, distinct in-window order for a subset of buyers.
        for user in buyer_users[:second_orders]:
            add_order(user, user["first_time"] + timedelta(days=3, hours=int(rng.integers(0, 6))), int(rng.integers(12, 61)))

        # Exact duplicate event rows: same order id, same user, same timestamp,
        # same amount. They must collapse to one order in the analysis.
        for order_id in base_ids[:duplicate_rows]:
            original = next(row for row in order_rows if row["order_id"] == order_id)
            order_rows.append(dict(original))

        # Orders placed before the first exposure must be ignored.
        for user in effect_users[:pre_rows]:
            add_order(user, user["first_time"] - timedelta(hours=6), int(rng.integers(15, 51)))

        # Orders outside the 7-day window must be ignored.
        for user in effect_users[:post_rows]:
            add_order(user, user["first_time"] + timedelta(days=8), int(rng.integers(18, 66)))

        # Immature users can have orders, but they are not part of the effect
        # sample yet: no mature observation, no denominator.
        for user in immature_users[:immature_orders]:
            remaining_seconds = int((CUTOFF - user["first_time"]).total_seconds())
            if remaining_seconds <= 2:
                continue
            delay_seconds = int(rng.integers(1, remaining_seconds))
            amount = int(rng.integers(20, 81))
            add_order(
                user,
                user["first_time"] + timedelta(seconds=delay_seconds),
                amount,
            )

        # Cross-group users keep their orders, but the user is excluded from
        # every effect denominator.
        for user in cross_users_group[:10]:
            add_order(user, user["first_time"] + timedelta(hours=12), int(rng.integers(20, 81)))

    order_rows.sort(key=lambda row: (row["order_time"], row["order_id"], row["user_id"]))
    order_path = DATA_DIR / spec.slug / "orders.csv"
    _write_csv(order_path, ["order_id", "user_id", "order_time", "amount"], order_rows)

    # ---- Manifest ---------------------------------------------------------
    first_exposure_users = len(users)
    cross_group_users = len(cross_users)
    after_cross = first_exposure_users - cross_group_users
    mature_effect = spec.control_effect + spec.treatment_effect
    immature_after_cross = after_cross - mature_effect
    in_window_rows = (
        spec.control_converters
        + spec.treatment_converters
        + spec.control_second_orders
        + spec.treatment_second_orders
        + spec.control_duplicate_rows
        + spec.treatment_duplicate_rows
    )
    raw_order_rows = (
        in_window_rows
        + spec.control_pre_rows
        + spec.treatment_pre_rows
        + spec.control_post_rows
        + spec.treatment_post_rows
    )
    manifest = {
        "experiment_id": spec.experiment_id,
        "slug": spec.slug,
        "data_cutoff": _fmt(CUTOFF),
        "observation_days": OBSERVATION_DAYS,
        "expected_control_pct": spec.expected_control_pct,
        "expected_treatment_pct": 100 - spec.expected_control_pct,
        "funnel": {
            "exposure_event_rows": len(exposure_rows),
            "unique_users_in_experiment": first_exposure_users,
            "first_exposure_users": first_exposure_users,
            "repeat_exposure_rows": len(exposure_rows) - first_exposure_users,
            "cross_group_users": cross_group_users,
            "after_cross_group": after_cross,
            "mature_users": mature_effect,
            "immature_users": immature_after_cross,
            "effect_sample_users": mature_effect,
            "by_group": {
                "control": {
                    "first_exposure": spec.control_total,
                    "after_cross_group": spec.control_total - spec.control_cross,
                    "mature": spec.control_effect,
                    "immature": spec.control_total - spec.control_cross - spec.control_effect,
                    "cross_group": spec.control_cross,
                },
                "treatment": {
                    "first_exposure": spec.treatment_total,
                    "after_cross_group": spec.treatment_total - spec.treatment_cross,
                    "mature": spec.treatment_effect,
                    "immature": spec.treatment_total - spec.treatment_cross - spec.treatment_effect,
                    "cross_group": spec.treatment_cross,
                },
            },
        },
        "orders": {
            "raw_order_rows_for_effect_sample": raw_order_rows,
            "before_first_exposure_rows": spec.control_pre_rows + spec.treatment_pre_rows,
            "outside_window_rows": spec.control_post_rows + spec.treatment_post_rows,
            "in_window_rows": in_window_rows,
            "duplicate_rows_removed": spec.control_duplicate_rows + spec.treatment_duplicate_rows,
            "counted_orders": (
                spec.control_converters
                + spec.treatment_converters
                + spec.control_second_orders
                + spec.treatment_second_orders
            ),
            "buyers": spec.control_converters + spec.treatment_converters,
            "zero_revenue_users": mature_effect
            - spec.control_converters
            - spec.treatment_converters,
        },
        "conversion_truth": {
            "control_converters": spec.control_converters,
            "control_n": spec.control_effect,
            "treatment_converters": spec.treatment_converters,
            "treatment_n": spec.treatment_effect,
        },
        "universe_counts": {
            "control_total_users": spec.control_total,
            "treatment_total_users": spec.treatment_total,
            "control_immature_in_total": spec.control_immature,
            "treatment_immature_in_total": spec.treatment_immature,
        },
    }
    meta = {
        "experiment_id": spec.experiment_id,
        "title": spec.title,
        "description": spec.description,
        "sort_order": SPECS.index(spec) + 1,
        "expected_control_pct": spec.expected_control_pct,
        "expected_treatment_pct": 100 - spec.expected_control_pct,
        "groups": {
            "control": "对照组",
            "treatment": "实验组",
        },
    }
    scenario_dir = DATA_DIR / spec.slug
    (scenario_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (scenario_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{spec.slug:12s} exposures={len(exposure_rows):4d} users={first_exposure_users:4d} "
        f"orders={len(order_rows):4d} mature={mature_effect:4d} cross={cross_group_users:3d}"
    )


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for spec in SPECS:
        generate(spec)
