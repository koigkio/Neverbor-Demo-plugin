---
description: neverbor — savings stats, modes, config and on/off switches
argument-hint: "[stats [today|week|all]|on|off|mode light|normal|aggressive|config [key value]|terse on|off|quiet on|off]"
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/neverbor.py" $ARGUMENTS`

Show the output above to the user in the language they write in: translate the labels, keep all numbers, tool names and line layout unchanged. Add nothing.
