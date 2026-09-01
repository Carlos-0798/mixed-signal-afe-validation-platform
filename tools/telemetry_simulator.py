#!/usr/bin/env python3
"""Emit valid AFE telemetry using clearly labeled synthetic values."""

from __future__ import annotations

import argparse
import math
import random
import sys
import time
from collections.abc import Iterator

from analog_validation.protocol import AfeTelemetry, encode_afe_message


def generate(count: int, interval_ms: int, seed: int) -> Iterator[AfeTelemetry]:
    """Yield deterministic synthetic AFE v1 messages for one seed."""

    rng = random.Random(seed)
    for index in range(count):
        input_mv = round(800 + 550 * math.sin(index / 7.0) + rng.gauss(0, 2))
        ideal_output = 2.0 * input_mv + 12
        output_mv = round(min(3275, max(25, ideal_output + rng.gauss(0, 3))))
        fault = 0x0001 if output_mv in {25, 3275} else 0
        yield AfeTelemetry(
            seq=index & 0xFFFF,
            time_ms=(index * interval_ms) & 0xFFFFFFFF,
            channel=0,
            input_mv=input_mv,
            output_mv=output_mv,
            gain_milli=2000,
            threshold=int(input_mv >= 1800),
            fault_flags=fault,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--interval-ms", type=int, default=100)
    parser.add_argument("--seed", type=int, default=430)
    parser.add_argument("--realtime", action="store_true", help="sleep between records")
    args = parser.parse_args()
    if args.count < 0 or args.interval_ms < 0:
        parser.error("count and interval must be non-negative")
    print("# source=SYNTHETIC generator=telemetry_simulator", file=sys.stderr)
    for message in generate(args.count, args.interval_ms, args.seed):
        sys.stdout.write(encode_afe_message(message))
        sys.stdout.flush()
        if args.realtime and args.interval_ms:
            time.sleep(args.interval_ms / 1000.0)


if __name__ == "__main__":
    main()
