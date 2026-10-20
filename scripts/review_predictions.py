"""Review frozen paper portfolios with final sporting results; keep official ROI separate."""

import argparse
import json
from pathlib import Path

from quantfootball.quiniela.review import write_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("record", "dataset", "probability-evaluation", "market-evaluation", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    review = write_review(args.record, args.dataset, args.probability_evaluation, args.market_evaluation, args.output_dir)
    print(json.dumps({k: review[k] for k in ("completed_fixtures", "pending_fixtures", "strategies")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
