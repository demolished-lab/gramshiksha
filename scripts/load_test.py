#!/usr/bin/env python3
"""Small, dependency-light async smoke/load test for public API reads.

Example:
  python scripts/load_test.py --base-url http://127.0.0.1:8123 \
    --concurrency 100 --duration 30
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter
from dataclasses import dataclass

import httpx

ENDPOINTS = (
    "/api/health",
    "/api/ready",
    "/api/meta/boards",
    "/api/courses?limit=20&sort=popular",
    "/api/catalog/availability?board=CBSE&class_grade=10",
)


@dataclass
class Result:
    endpoint: str
    status: int | str
    latency_ms: float


async def worker(client: httpx.AsyncClient, deadline: float, results: list[Result]) -> None:
    index = 0
    while time.perf_counter() < deadline:
        endpoint = ENDPOINTS[index % len(ENDPOINTS)]
        index += 1
        started = time.perf_counter()
        try:
            response = await client.get(endpoint)
            status: int | str = response.status_code
        except httpx.TimeoutException:
            status = "timeout"
        except httpx.HTTPError as exc:
            status = type(exc).__name__
        results.append(Result(endpoint, status, (time.perf_counter() - started) * 1000))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    rank = max(0, min(len(values) - 1, round((p / 100) * (len(values) - 1))))
    return values[rank]


async def run(args: argparse.Namespace) -> dict[str, object]:
    base_url = args.base_url.rstrip("/")
    results: list[Result] = []
    started = time.perf_counter()
    deadline = started + args.duration
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(base_url=base_url, limits=limits, timeout=timeout, headers={"User-Agent": "GramShiksha-load-test/1.0"}) as client:
        await asyncio.gather(*(worker(client, deadline, results) for _ in range(args.concurrency)))
    elapsed = time.perf_counter() - started
    latencies = [result.latency_ms for result in results]
    failures = [result for result in results if result.status != 200]
    by_endpoint: dict[str, dict[str, object]] = {}
    for endpoint in ENDPOINTS:
        subset = [result for result in results if result.endpoint == endpoint]
        endpoint_failures = [result for result in subset if result.status != 200]
        endpoint_latencies = [result.latency_ms for result in subset]
        by_endpoint[endpoint] = {
            "requests": len(subset),
            "failures": len(endpoint_failures),
            "p50_ms": round(percentile(endpoint_latencies, 50), 2),
            "p95_ms": round(percentile(endpoint_latencies, 95), 2),
            "p99_ms": round(percentile(endpoint_latencies, 99), 2),
        }
    return {
        "base_url": base_url,
        "duration_s": round(elapsed, 2),
        "concurrency": args.concurrency,
        "requests": len(results),
        "requests_per_second": round(len(results) / elapsed, 2) if elapsed else 0,
        "failures": len(failures),
        "failure_rate_pct": round((len(failures) / len(results)) * 100, 2) if results else 0,
        "status_counts": dict(Counter(str(result.status) for result in results)),
        "latency_ms": {
            "p50": round(percentile(latencies, 50), 2),
            "p95": round(percentile(latencies, 95), 2),
            "p99": round(percentile(latencies, 99), 2),
            "max": round(max(latencies), 2) if latencies else 0,
            "mean": round(statistics.mean(latencies), 2) if latencies else 0,
        },
        "by_endpoint": by_endpoint,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8123")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--json-out")
    args = parser.parse_args()
    if args.concurrency < 1 or args.duration <= 0:
        parser.error("concurrency must be >= 1 and duration must be > 0")
    report = asyncio.run(run(args))
    print(json.dumps(report, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    if report["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
