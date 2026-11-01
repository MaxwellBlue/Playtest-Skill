<div align="center">

# Playtest Pilot

**Build. Test. Inspect. Fix. Repeat.**

A tiny, local verification skill for **Unreal Engine** and **Unity**.<br>
Give your coding agent a repeatable loop—and proof it can inspect.

[Download the skill](dist/playtest-pilot.skill) · [Quick start](#quick-start) · [Engine commands](skill/playtest-pilot/references/engine-commands.md)

<br>

<img alt="Local first" src="https://img.shields.io/badge/local-first-111827?style=for-the-badge">
<img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
<img alt="Unreal and Unity" src="https://img.shields.io/badge/Unreal_%2B_Unity-supported-5B45FF?style=for-the-badge">
<img alt="MIT license" src="https://img.shields.io/badge/license-MIT-16803A?style=for-the-badge">

</div>

<br>

> **The idea:** stop at evidence, not at “the code is written.”
>
> Playtest Pilot runs your project's real checks, saves the output, and gives an agent a tight verify-and-repair loop. No account, model API, editor plugin, hosted service, or Python dependencies.

## The loop

| Step | What happens |
| --- | --- |
| **1. Inspect** | Detect the Unreal or Unity project and find its existing test pipeline. |
| **2. Run** | Execute configured test or build commands with a timeout. |
| **3. Collect** | Save command logs, expected evidence, and JSON + Markdown reports. |
| **4. Repair** | Let the agent inspect a relevant failure, make one focused fix, and retry. |

## Small by design

| It does | It does not pretend to do |
| --- | --- |
| Detect Unreal and Unity project roots | Magically play every game |
| Run your existing tests, builds, and smoke checks | Record video without editor integration |
| Stop timed-out process trees | Generate gameplay tests from nothing |
| Verify that expected evidence exists | Recover a crashed editor automatically |
| Produce readable pass/fail reports | Call compilation a playtest |
| Work as a Kimi, Claude Code, or Aura-compatible skill | Replace your project's test pipeline |

## Quick start

### 1. Install the skill

Copy [`skill/playtest-pilot`](skill/playtest-pilot) into your agent's skills directory, or import [`playtest-pilot.skill`](dist/playtest-pilot.skill).

For Aura, copy it to:

```text
<GameProject>/Saved/.Aura/Skills/playtest-pilot/
```

### 2. Describe one real check

Create `.playtest-pilot.json` in your game project:

```json
{
  "checks": [
    {
      "name": "gameplay-smoke-test",
      "command": [
        "python",
        "tools/test_gameplay.py",
        "--report",
        "{output}/results.json"
      ],
      "timeoutSeconds": 300,
      "successExitCodes": [0],
      "evidence": ["{output}/results.json"],
      "requiredEvidence": true
    }
  ]
}
```

Prefer the test command your project already trusts. See the [Unity and Unreal examples](skill/playtest-pilot/references/engine-commands.md).

### 3. Run and inspect

```bash
python /path/to/playtest-pilot/scripts/playtest_pilot.py inspect --project /path/to/game
python /path/to/playtest-pilot/scripts/playtest_pilot.py run --project /path/to/game
```

Reports land in:

```text
.playtest-pilot/<timestamp>/
├── report.md
├── report.json
└── <check-name>/
    ├── command.log
    └── your evidence files
```

Add `.playtest-pilot/` to the game project's `.gitignore`.

## Configuration

| Field | Required | Purpose |
| --- | :---: | --- |
| `name` | yes | Display name and evidence folder name |
| `command` | yes | Executable and arguments as an array, never a shell string |
| `timeoutSeconds` | no | Time limit; defaults to `600` |
| `successExitCodes` | no | Accepted exit codes; defaults to `[0]` |
| `evidence` | no | Files to record as present or missing |
| `requiredEvidence` | no | Fail when evidence is missing; defaults to `false` |

Use these placeholders in commands and evidence paths:

| Placeholder | Expands to |
| --- | --- |
| `{project}` | Absolute game project directory |
| `{project_file}` | Absolute `.uproject` path, or an empty string outside Unreal |
| `{output}` | Current check's evidence directory |

## Repository map

```text
skill/playtest-pilot/
├── SKILL.md                     # Agent workflow and guardrails
├── scripts/playtest_pilot.py    # Dependency-free runner
└── references/engine-commands.md

tests/                           # Standard-library unit tests
dist/playtest-pilot.skill        # Importable skill package
```

## Develop

Requires **Python 3.10+** and nothing else.

```bash
python -m unittest discover -s tests -v
```

---

<div align="center">

Inspired by [Aura](https://www.tryaura.dev/)'s verification loop.<br>
Independent and minimal; not affiliated with Aura.

**MIT © 2026 MaxwellBlue**

</div>
