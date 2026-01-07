#!/usr/bin/env python3
"""Quick test of duration_mode functionality."""

import scenario_parser

# Test parsing a YAML action with duration_mode
yaml_content = """
- action: cat.run
  duration: 1.5
  duration_mode: truncate
- action: door.open
  duration: 2.0
  duration_mode: stretch
"""

parser = scenario_parser.ScenarioParser()
actions = parser._parse_yaml(yaml_content)

print("Parsed actions:")
for action in actions:
    print(f"  {action.name}: duration={action.duration}s, mode={action.duration_mode}")

# Verify defaults
assert actions[0].duration_mode == "truncate", "First action should be truncate"
assert actions[1].duration_mode == "stretch", "Second action should be stretch"

print("\n✓ Duration mode parsing works correctly!")
