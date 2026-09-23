"""Bounded high-rate read-only sampling through one serialized BLE session."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime

from homeassistant.core import HomeAssistant

from ._protocol.reads import ReadOperation
from ._protocol.session import ReadSession
from ._protocol.state import OperatingState, decode_operating_state
from ._protocol.telemetry import Telemetry, parse_telemetry_response
from .bluetooth import HomeAssistantReadTransport

MIN_CAPTURE_HZ = 1
MAX_CAPTURE_HZ = 10
BENCHMARK_RATES_HZ = (1, 2, 5, 10)
BENCHMARK_STAGE_SECONDS = 3
INTER_REQUEST_DELAY_SECONDS = 0.03
SESSION_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class RuntimeSample:
    """One correlated telemetry/state observation."""

    observed_at_utc: datetime
    offset_seconds: float
    round_trip_ms: float
    telemetry_frame: bytes
    operating_state_frame: bytes
    telemetry: Telemetry
    operating_state: OperatingState


@dataclass(frozen=True)
class RuntimeTrace:
    """A bounded series captured over one connection epoch."""

    started_at_utc: datetime
    ended_at_utc: datetime
    target_hz: float
    elapsed_seconds: float
    achieved_hz: float
    samples: tuple[RuntimeSample, ...]


@dataclass(frozen=True)
class SamplingStage:
    """Privacy-safe result for one requested sampling rate."""

    target_hz: float
    sample_count: int
    elapsed_seconds: float
    achieved_hz: float
    mean_round_trip_ms: float | None
    max_round_trip_ms: float | None
    successful: bool
    failure_kind: str | None = None


@dataclass(frozen=True)
class SamplingBenchmark:
    """Fastest clean stage plus every attempted stage."""

    selected_hz: float | None
    stages: tuple[SamplingStage, ...]


def _validate_capture(duration_seconds: float, target_hz: float) -> None:
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("duration_seconds must be finite and positive")
    if (
        not math.isfinite(target_hz)
        or target_hz < MIN_CAPTURE_HZ
        or target_hz > MAX_CAPTURE_HZ
    ):
        raise ValueError(
            f"target_hz must be between {MIN_CAPTURE_HZ} and {MAX_CAPTURE_HZ}"
        )


async def capture_runtime_trace(
    hass: HomeAssistant,
    address: str,
    *,
    duration_seconds: float,
    target_hz: float,
    sample_limit: int | None = None,
) -> RuntimeTrace:
    """Capture correlated runtime reads; never overlap or retry a transaction."""
    _validate_capture(duration_seconds, target_hz)
    if sample_limit is not None and sample_limit <= 0:
        raise ValueError("sample_limit must be positive")

    transport = HomeAssistantReadTransport(
        hass,
        address,
        allowed_operations=frozenset(
            {ReadOperation.TELEMETRY, ReadOperation.OPERATING_STATE}
        ),
    )
    loop = asyncio.get_running_loop()
    period_seconds = 1 / target_hz
    samples: list[RuntimeSample] = []

    async with ReadSession(transport, timeout=SESSION_TIMEOUT_SECONDS) as session:
        # Establishing a connection through a remote proxy is not sampling time.
        started_monotonic = loop.time()
        started_at_utc = datetime.now(UTC)
        while sample_limit is None or len(samples) < sample_limit:
            target_time = started_monotonic + len(samples) * period_seconds
            remaining = target_time - loop.time()
            if remaining > 0:
                await asyncio.sleep(remaining)
            if samples and loop.time() - started_monotonic >= duration_seconds:
                break

            request_started = loop.time()
            telemetry_frame = await session.read(ReadOperation.TELEMETRY)
            await asyncio.sleep(INTER_REQUEST_DELAY_SECONDS)
            state_frame = await session.read(ReadOperation.OPERATING_STATE)
            completed = loop.time()
            samples.append(
                RuntimeSample(
                    observed_at_utc=datetime.now(UTC),
                    offset_seconds=completed - started_monotonic,
                    round_trip_ms=(completed - request_started) * 1000,
                    telemetry_frame=telemetry_frame,
                    operating_state_frame=state_frame,
                    telemetry=parse_telemetry_response(telemetry_frame),
                    operating_state=decode_operating_state(state_frame),
                )
            )
        ended_monotonic = loop.time()
        ended_at_utc = datetime.now(UTC)

    elapsed_seconds = max(ended_monotonic - started_monotonic, 0.0)
    if len(samples) >= 2:
        sample_span = samples[-1].offset_seconds - samples[0].offset_seconds
        achieved_hz = (len(samples) - 1) / sample_span if sample_span > 0 else 0.0
    elif samples and elapsed_seconds > 0:
        achieved_hz = 1 / elapsed_seconds
    else:
        achieved_hz = 0.0
    return RuntimeTrace(
        started_at_utc=started_at_utc,
        ended_at_utc=ended_at_utc,
        target_hz=target_hz,
        elapsed_seconds=elapsed_seconds,
        achieved_hz=achieved_hz,
        samples=tuple(samples),
    )


async def _run_sampling_stage(
    hass: HomeAssistant, address: str, target_hz: float
) -> SamplingStage:
    """Run one stage without exposing backend exception text or retrying."""
    try:
        trace = await capture_runtime_trace(
            hass,
            address,
            duration_seconds=BENCHMARK_STAGE_SECONDS,
            target_hz=target_hz,
        )
    except Exception:
        return SamplingStage(
            target_hz=target_hz,
            sample_count=0,
            elapsed_seconds=0,
            achieved_hz=0,
            mean_round_trip_ms=None,
            max_round_trip_ms=None,
            successful=False,
            failure_kind="transport_or_protocol_failure",
        )

    round_trips = [sample.round_trip_ms for sample in trace.samples]
    successful = bool(round_trips) and trace.achieved_hz >= target_hz * 0.85
    return SamplingStage(
        target_hz=target_hz,
        sample_count=len(trace.samples),
        elapsed_seconds=trace.elapsed_seconds,
        achieved_hz=trace.achieved_hz,
        mean_round_trip_ms=sum(round_trips) / len(round_trips),
        max_round_trip_ms=max(round_trips),
        successful=successful,
        failure_kind=None if successful else "insufficient_cadence",
    )


async def benchmark_runtime_sampling(
    hass: HomeAssistant, address: str
) -> SamplingBenchmark:
    """Increase within the evidence-backed proxy envelope; stop at first failure."""
    stages: list[SamplingStage] = []
    selected_hz: float | None = None
    for target_hz in BENCHMARK_RATES_HZ:
        stage = await _run_sampling_stage(hass, address, target_hz)
        stages.append(stage)
        if not stage.successful:
            break
        selected_hz = target_hz
    return SamplingBenchmark(selected_hz=selected_hz, stages=tuple(stages))
