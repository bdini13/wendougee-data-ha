"""Bounded, local observation journal; never infer a final scale yield.

Only explicit captures retain curves. Routine polls retain sparse summaries.
No addresses, raw frames, profile names, or filenames enter this journal.
"""

from datetime import datetime
from math import isfinite

MAX_RECORDS = 30
MAX_POINTS = 600


def valid_timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


class ShotJournal:
    """Retain summaries independently of lifetime water/shot accounting."""

    def __init__(self):
        self.records = []
        self.latest_curve = []
        self.curve_updated_at = None
        self._current = None
        self._points = []
        self._started = None
        self._last_at = None
        self._last_timer = None
        self._last_volume = None

    def dump(self):
        return {
            "records": self.records,
            "latest_curve": self.latest_curve,
            "curve_updated_at": self.curve_updated_at,
        }

    def restore(self, data):
        """Our versioned private storage is bounded even after an old deployment."""
        if not isinstance(data, dict):
            return
        records = data.get("records", [])
        if isinstance(records, list):
            self.records = []
            for r in records[-MAX_RECORDS:]:
                if not isinstance(r, dict) or not valid_timestamp(r.get("ended_at")):
                    continue
                numeric = (
                    "duration_s",
                    "peak_bar",
                    "pumped_ml",
                    "scale_at_stop_g",
                    "samples",
                )
                if not all(
                    isinstance(r.get(k), int | float) and isfinite(r[k])
                    for k in numeric
                ):
                    continue
                if r.get("source") not in {"poll", "capture"} or r.get(
                    "coverage"
                ) not in {
                    "observed_start",
                    "partial",
                    "sparse",
                    "truncated",
                }:
                    continue
                self.records.append(
                    {
                        **{k: r[k] for k in numeric},
                        "ended_at": r["ended_at"],
                        "source": r["source"],
                        "coverage": r["coverage"],
                        "final_yield_g": None,
                    }
                )
        points = data.get("latest_curve", [])
        if isinstance(points, list):
            self.latest_curve = [
                p
                for p in points
                if isinstance(p, list)
                and len(p) == 4
                and all(isinstance(v, int | float) and isfinite(v) for v in p)
            ][:MAX_POINTS]
        at = data.get("curve_updated_at")
        self.curve_updated_at = at if valid_timestamp(at) else None

    def observe(self, telemetry, state, now, *, source, previous_active, initialized):
        active = state.state in {"profile", "manual", "free_variable"}
        timer = telemetry.elapsed_brew_time_seconds
        volume = telemetry.dispensed_volume_ml
        if active and self._current is None:
            self._current = {
                "ended_at": None,
                "duration_s": timer,
                "peak_bar": 0,
                "pumped_ml": volume,
                "scale_at_stop_g": None,
                "final_yield_g": None,
                "source": source,
                "coverage": "observed_start"
                if initialized and not previous_active
                else "partial",
                "samples": 0,
            }
            self._started = now
            self._points = []
        current = self._current
        gap = (now - self._last_at).total_seconds() if self._last_at else None
        if current is not None:
            if gap is not None and not 0 <= gap <= 2:
                current["coverage"] = "sparse"
            if source != "capture":
                current["source"] = "poll"
        if current is not None and active:
            # Firmware can assert active before resetting old counters. Discard
            # that prefix; do not assign the previous shot's volume to this shot.
            if (
                self._last_timer is not None
                and previous_active
                and (timer < self._last_timer or volume < self._last_volume)
            ):
                self._points = []
                self._started = now
                current.update(peak_bar=0, pumped_ml=0, samples=0)
            current["duration_s"] = timer
            current["peak_bar"] = max(current["peak_bar"], telemetry.pressure_bar)
            current["pumped_ml"] = max(current["pumped_ml"], volume)
            current["samples"] += 1
        if current is not None and (active or state.state == "idle"):
            if source == "capture" and current["source"] == "capture":
                if len(self._points) < MAX_POINTS:
                    self._points.append(
                        [
                            round((now - self._started).total_seconds(), 3),
                            telemetry.pressure_bar,
                            volume,
                            telemetry.scale_weight_grams,
                        ]
                    )
                else:
                    current["coverage"] = "truncated"
            if not active:
                if (
                    gap is not None
                    and 0 <= gap <= 2
                    and self._last_timer is not None
                    and timer >= self._last_timer
                ):
                    current["duration_s"] = timer
                current["ended_at"] = now.isoformat()
                current["scale_at_stop_g"] = telemetry.scale_weight_grams
                # Idle values may already be reset; the tracker separately
                # applies its strict five-second terminal-volume refinement.
                self.records.append(current)
                self.records = self.records[-MAX_RECORDS:]
                self.latest_curve = (
                    self._points if current["source"] == "capture" else []
                )
                self.curve_updated_at = now.isoformat()
                self._current = None
        elif current is not None:
            # Ambiguous state/cleaning is not proof of a completed normal shot.
            self._current = None
            self._points = []
        self._last_at = now
        self._last_timer = timer
        self._last_volume = volume

    def refine_volume(self, ended_at, volume, telemetry, now, source):
        if not self.records or self.records[-1]["ended_at"] != ended_at.isoformat():
            return
        self.records[-1]["pumped_ml"] = volume
        if (
            source == "capture"
            and self.latest_curve
            and len(self.latest_curve) < MAX_POINTS
        ):
            self.latest_curve.append(
                [
                    round((now - self._started).total_seconds(), 3),
                    telemetry.pressure_bar,
                    volume,
                    telemetry.scale_weight_grams,
                ]
            )
            self.curve_updated_at = now.isoformat()
