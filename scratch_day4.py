"""Print every stage for all Day 4 scenarios."""

import json
import os

from tests.test_impact_agent import SCENARIOS, run_scenario


def main() -> None:
    print(f"IMPACT_AGENT_MODEL={os.getenv('IMPACT_AGENT_MODEL', 'gpt-5.6-terra')}")
    for scenario in SCENARIOS:
        print(f"\n=== {scenario} ===")
        result = run_scenario(scenario)
        for stage, output in result.items():
            print(f"{stage}:\n{json.dumps(output, indent=2)}")


if __name__ == "__main__":
    main()
