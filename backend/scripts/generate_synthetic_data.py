"""Generates a realistic synthetic appointment-history dataset for bootstrapping
the no-show risk model (docs plan §10.1). Writes a CSV with one row per
appointment, already containing every column app/ml/features.py expects plus
the no_show label, so app/ml/train.py can load it directly with pandas.

Client/staff history stats (client_past_no_show_rate, client_total_visits,
client_tenure_days, staff_no_show_rate_historical) are computed causally —
only from appointments strictly earlier than the current row — so the dataset
has no label leakage (a model scoring ~0.99 AUC on synthetic data usually
means the generator leaked the label into a feature).

Usage:
    python -m scripts.generate_synthetic_data --rows 20000 --out data/synthetic_appointments.csv
"""

import argparse
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

BASE_NO_SHOW_RATE = 0.05


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


BASE_LOGIT = _logit(BASE_NO_SHOW_RATE)
BOOKING_CHANNELS = ["web", "web", "web", "chat", "voice", "admin"]  # weighted toward web
SERVICE_CATALOG = [
    # (category, duration_minutes, price_cents)
    ("Hair", 30, 3000),
    ("Hair", 45, 4500),
    ("Hair", 60, 6000),
    ("Nails", 45, 3500),
    ("Nails", 60, 5000),
    ("Skin", 60, 7000),
    ("Spa", 90, 9000),
    ("Spa", 120, 14000),
]

N_CLIENTS = 3000
N_STAFF = 15
WINDOW_DAYS = 540  # ~18 months, so a chronological train/test split is meaningful


@dataclass
class ClientHistory:
    first_seen: datetime | None = None
    total_visits: int = 0
    no_show_count: int = 0

    @property
    def past_no_show_rate(self) -> float:
        return self.no_show_count / self.total_visits if self.total_visits else 0.0


@dataclass
class StaffHistory:
    total_visits: int = 0
    no_show_count: int = 0

    @property
    def no_show_rate(self) -> float:
        return self.no_show_count / self.total_visits if self.total_visits else BASE_NO_SHOW_RATE


def _sample_lead_time_hours(rng: random.Random) -> float:
    # Lognormal: mostly "a few days out," with a long tail of both last-minute
    # and far-out bookings — enough spread to exercise both of §10.1's lead-time
    # patterns (short AND long lead time each raise risk, for different reasons).
    hours = rng.lognormvariate(mu=3.2, sigma=1.1)
    return max(0.5, min(hours, 90 * 24))


def _no_show_probability(
    *,
    is_first_visit: bool,
    day_of_week: int,
    hour_of_day: int,
    lead_time_hours: float,
    client_past_no_show_rate: float,
    booking_channel: str,
    duration_minutes: int,
    price_cents: int,
    rng: random.Random,
) -> float:
    # Risk factors combine on the log-odds (logit) scale — the standard way to
    # stack independent multiplicative effects — rather than adding raw
    # percentage points, which saturates fast and compresses everything into a
    # narrow, weakly-separable probability band.
    logit = BASE_LOGIT

    if is_first_visit:
        logit += rng.uniform(1.6, 2.0)
    if day_of_week == 0 and hour_of_day < 10:
        logit += rng.uniform(0.8, 1.0)
    if lead_time_hours < 24:
        logit += 1.15
    elif lead_time_hours > 30 * 24:
        logit += 0.55
    if client_past_no_show_rate > 0:
        logit += 2.1
    if booking_channel in ("voice", "chat"):
        logit += 0.2
    if duration_minutes >= 90 or price_cents >= 8000:
        logit -= 0.9

    logit += rng.gauss(0, 0.2)
    return min(max(_sigmoid(logit), 0.01), 0.97)


def generate(rows: int, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    clients: dict[int, ClientHistory] = {i: ClientHistory() for i in range(N_CLIENTS)}
    staff: dict[int, StaffHistory] = {i: StaffHistory() for i in range(N_STAFF)}

    window_start = datetime.now(UTC) - timedelta(days=WINDOW_DAYS)
    offsets = sorted(np_rng.uniform(0, WINDOW_DAYS * 24 * 3600, size=rows))

    records = []
    for offset_seconds in offsets:
        scheduled_start = window_start + timedelta(seconds=float(offset_seconds))

        client_id = rng.randrange(N_CLIENTS)
        staff_id = rng.randrange(N_STAFF)
        category, duration_minutes, price_cents = rng.choice(SERVICE_CATALOG)
        booking_channel = rng.choice(BOOKING_CHANNELS)
        lead_time_hours = _sample_lead_time_hours(rng)

        history = clients[client_id]
        is_first_visit = history.total_visits == 0
        client_past_no_show_rate = history.past_no_show_rate
        client_total_visits = history.total_visits
        client_tenure_days = (scheduled_start - history.first_seen).days if history.first_seen else 0

        staff_history = staff[staff_id]
        staff_no_show_rate_historical = staff_history.no_show_rate

        prob = _no_show_probability(
            is_first_visit=is_first_visit,
            day_of_week=scheduled_start.weekday(),
            hour_of_day=scheduled_start.hour,
            lead_time_hours=lead_time_hours,
            client_past_no_show_rate=client_past_no_show_rate,
            booking_channel=booking_channel,
            duration_minutes=duration_minutes,
            price_cents=price_cents,
            rng=rng,
        )
        no_show = 1 if rng.random() < prob else 0

        records.append(
            {
                "scheduled_start": scheduled_start.isoformat(),
                "day_of_week": scheduled_start.weekday(),
                "hour_of_day": scheduled_start.hour,
                "is_monday_morning": int(scheduled_start.weekday() == 0 and scheduled_start.hour < 10),
                "lead_time_hours": lead_time_hours,
                "is_first_visit": int(is_first_visit),
                "client_past_no_show_rate": client_past_no_show_rate,
                "client_total_visits": client_total_visits,
                "client_tenure_days": client_tenure_days,
                "service_category": category,
                "service_duration_minutes": duration_minutes,
                "service_price_cents": price_cents,
                "booking_channel": booking_channel,
                "staff_no_show_rate_historical": staff_no_show_rate_historical,
                "no_show": no_show,
            }
        )

        # Update running histories AFTER emitting the row — causal, no leakage.
        if history.first_seen is None:
            history.first_seen = scheduled_start
        history.total_visits += 1
        history.no_show_count += no_show
        staff_history.total_visits += 1
        staff_history.no_show_count += no_show

    return pd.DataFrame.from_records(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/synthetic_appointments.csv"))
    args = parser.parse_args()

    df = generate(args.rows, seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows to {args.out} (no_show rate: {df['no_show'].mean():.3f})")


if __name__ == "__main__":
    main()
