---
name: playtest-pilot
description: Build, test, and verify small Unreal Engine or Unity changes through a repeatable evidence loop. Use when asked to change gameplay, fix a game bug, run engine tests, check a build, verify a feature actually works, or create an Aura-like build-test-fix workflow without a hosted agent.
---

# Playtest Pilot

Close the loop between a game change and observable evidence. Keep the loop small and honest.

## Workflow

1. Turn the request into an observable outcome. Separate compile checks from gameplay checks.
2. Inspect the project and its existing test commands. Save work and avoid disrupting an editor the user is already using.
3. Establish a baseline when failures may already exist. Do not blame pre-existing failures on the new change.
4. Make the smallest coherent change. Do not build a new framework around the task.
5. Find or create `.playtest-pilot.json` in the game project. Read [references/engine-commands.md](references/engine-commands.md) for starting commands. Prefer the project's existing test pipeline over a generic command.
6. Run:

   ```bash
   python scripts/playtest_pilot.py inspect --project /path/to/game
   python scripts/playtest_pilot.py run --project /path/to/game
   ```

   Resolve the script path relative to this skill, not the game project.
7. Read `report.md`, `report.json`, the command log, and any configured evidence. On a relevant failure, make one focused fix and rerun. Stop after three failed attempts, a risky operation, or a problem outside the requested scope.
8. Report the change, the exact checks, and the evidence. State what was not tested.

## Rules

- Never call a change playtested when only compilation or static checks ran.
- Never claim a pass from the command alone; inspect its exit code and evidence.
- Use command arrays, not shell strings. Do not add destructive commands or credentials to the config.
- Ask before taking over a running editor, launching a long build, or installing engine components.
- Keep generated reports out of version control unless the user asks to commit them.
