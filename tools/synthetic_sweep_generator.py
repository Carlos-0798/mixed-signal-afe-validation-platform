#!/usr/bin/env python3
"""Generate labeled synthetic DC sweep CSV for host-analysis development."""

from __future__ import annotations

import argparse
import csv
import random
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", type=int, default=21)
    parser.add_argument("--input-max-mv", type=float, default=2000.0)
    parser.add_argument("--gain", type=float, default=2.0)
    parser.add_argument("--offset-mv", type=float, default=12.0)
    parser.add_argument("--noise-sigma-mv", type=float, default=2.0)
    parser.add_argument("--output-min-mv", type=float, default=25.0)
    parser.add_argument("--output-max-mv", type=float, default=3275.0)
    parser.add_argument("--seed", type=int, default=430)
    args = parser.parse_args()
    if args.points < 2:
        parser.error("points must be at least 2")
    if args.input_max_mv <= 0 or args.output_min_mv >= args.output_max_mv:
        parser.error("invalid sweep or output limits")

    rng = random.Random(args.seed)
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(("source", "sequence", "input_mv", "output_mv", "saturated"))
    for index in range(args.points):
        input_mv = args.input_max_mv * index / (args.points - 1)
        unconstrained = args.gain * input_mv + args.offset_mv + rng.gauss(0, args.noise_sigma_mv)
        output_mv = min(args.output_max_mv, max(args.output_min_mv, unconstrained))
        saturated = int(output_mv in {args.output_min_mv, args.output_max_mv})
        writer.writerow(("SYNTHETIC", index, f"{input_mv:.3f}", f"{output_mv:.3f}", saturated))


if __name__ == "__main__":
    main()

