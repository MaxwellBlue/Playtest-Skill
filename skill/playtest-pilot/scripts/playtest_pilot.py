#!/usr/bin/env python3
"""Run configured game checks and save a small, inspectable evidence report."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

VERSION = "0.1.0"


class PilotError(Exception):
    """A configuration or project error that should be shown without a traceback."""


def detect_project(project: Path) -> dict[str, Any]:
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise PilotError(f"Project directory does not exist: {project}")

    unreal_files = sorted(project.glob("*.uproject"))
    unity_version_file = project / "ProjectSettings" / "ProjectVersion.txt"
    is_unity = unity_version_file.is_file() and (project / "Assets").is_dir()

    if unreal_files and is_unity:
        raise PilotError("The folder looks like both Unreal and Unity; use separate project roots.")

    result: dict[str, Any] = {
        "root": str(project),
        "name": project.name,
        "engine": "generic",
        "projectFile": None,
        "engineVersion": None,
    }
    if unreal_files:
        result["engine"] = "unreal"
        result["projectFile"] = str(unreal_files[0])
        if len(unreal_files) > 1:
            raise PilotError("Multiple .uproject files found; run from a folder with one project.")
    elif is_unity:
        result["engine"] = "unity"
        first_line = unity_version_file.read_text(encoding="utf-8-sig").splitlines()[0]
        result["engineVersion"] = first_line.split(":", 1)[-1].strip()
    return result


def _string_list(value: Any, label: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PilotError(f"{label} must be an array of strings.")
    if not allow_empty and not value:
        raise PilotError(f"{label} cannot be empty.")
    return value


def load_config(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise PilotError(f"Config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PilotError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("checks"), list):
        raise PilotError("Config must be an object with a 'checks' array.")
    if not data["checks"]:
        raise PilotError("Config must contain at least one check.")

    checks: list[dict[str, Any]] = []
    slugs: set[str] = set()
    for index, raw in enumerate(data["checks"]):
        label = f"checks[{index}]"
        if not isinstance(raw, dict):
            raise PilotError(f"{label} must be an object.")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise PilotError(f"{label}.name must be a non-empty string.")
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not slug:
            raise PilotError(f"{label}.name needs at least one letter or number.")
        if slug in slugs:
            raise PilotError(f"Check names must produce unique folder names: {name}")
        slugs.add(slug)

        command = _string_list(raw.get("command"), f"{label}.command")
        timeout = raw.get("timeoutSeconds", 600)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 86400:
            raise PilotError(f"{label}.timeoutSeconds must be between 1 and 86400.")
        exit_codes = raw.get("successExitCodes", [0])
        if (
            not isinstance(exit_codes, list)
            or not exit_codes
            or not all(isinstance(code, int) and not isinstance(code, bool) for code in exit_codes)
        ):
            raise PilotError(f"{label}.successExitCodes must be a non-empty array of integers.")
        evidence = _string_list(raw.get("evidence", []), f"{label}.evidence", allow_empty=True)
        required = raw.get("requiredEvidence", False)
        if not isinstance(required, bool):
            raise PilotError(f"{label}.requiredEvidence must be true or false.")

        checks.append(
            {
                "name": name.strip(),
                "slug": slug,
                "command": command,
                "timeoutSeconds": timeout,
                "successExitCodes": exit_codes,
                "evidence": evidence,
                "requiredEvidence": required,
            }
        )
    return checks


def _render(value: str, replacements: dict[str, str]) -> str:
    for key, replacement in replacements.items():
        value = value.replace("{" + key + "}", replacement)
    return value


def _stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        process.kill()


def run_check(check: dict[str, Any], project_info: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    project = Path(project_info["root"])
    check_dir = run_dir / check["slug"]
    check_dir.mkdir(parents=True, exist_ok=False)
    replacements = {
        "project": str(project),
        "project_file": project_info.get("projectFile") or "",
        "output": str(check_dir),
    }
    command = [_render(part, replacements) for part in check["command"]]
    started = time.monotonic()
    timed_out = False

    popen_options: dict[str, Any] = {}
    if os.name == "nt":
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_options["start_new_session"] = True

    try:
        process = subprocess.Popen(
            command,
            cwd=project,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **popen_options,
        )
        try:
            output, _ = process.communicate(timeout=check["timeoutSeconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            _stop_process_tree(process)
            output, _ = process.communicate()
        return_code: int | None = process.returncode
        launch_error = None
    except OSError as exc:
        output = ""
        return_code = None
        launch_error = str(exc)

    duration = round(time.monotonic() - started, 3)
    log_path = check_dir / "command.log"
    log_path.write_text(output or "", encoding="utf-8")

    evidence = []
    for pattern in check["evidence"]:
        rendered = Path(_render(pattern, replacements)).expanduser()
        evidence_path = rendered if rendered.is_absolute() else project / rendered
        evidence.append({"path": str(evidence_path.resolve()), "exists": evidence_path.exists()})

    exit_ok = return_code in check["successExitCodes"]
    evidence_ok = all(item["exists"] for item in evidence)
    passed = not timed_out and launch_error is None and exit_ok and (evidence_ok or not check["requiredEvidence"])
    reasons = []
    if launch_error:
        reasons.append(f"Could not launch: {launch_error}")
    if timed_out:
        reasons.append(f"Timed out after {check['timeoutSeconds']} seconds")
    if not exit_ok and launch_error is None:
        reasons.append(f"Exit code {return_code}; expected one of {check['successExitCodes']}")
    if check["requiredEvidence"] and not evidence_ok:
        reasons.append("Required evidence is missing")

    return {
        "name": check["name"],
        "status": "passed" if passed else "failed",
        "command": command,
        "exitCode": return_code,
        "durationSeconds": duration,
        "timedOut": timed_out,
        "log": str(log_path),
        "evidence": evidence,
        "reasons": reasons,
    }


def _new_run_dir(output_root: Path) -> Path:
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = output_root / base
    suffix = 1
    while candidate.exists():
        candidate = output_root / f"{base}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def write_reports(run_dir: Path, report: dict[str, Any]) -> None:
    (run_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Playtest Pilot report",
        "",
        f"**{report['status'].upper()}** ΓÇö {report['project']['name']} ({report['project']['engine']})",
        "",
        f"Started: {report['startedAt']}",
        "",
    ]
    for check in report["checks"]:
        lines.extend(
            [
                f"## {check['name']}: {check['status']}",
                "",
                f"Exit code: {check['exitCode']}  ",
                f"Duration: {check['durationSeconds']} seconds  ",
                f"Log: `{check['log']}`",
                "",
            ]
        )
        for reason in check["reasons"]:
            lines.append(f"- {reason}")
        for evidence in check["evidence"]:
            state = "found" if evidence["exists"] else "missing"
            lines.append(f"- Evidence ({state}): `{evidence['path']}`")
        if check["reasons"] or check["evidence"]:
            lines.append("")
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def run(project_path: Path, config_path: Path | None, output_path: Path | None) -> int:
    project_info = detect_project(project_path)
    project = Path(project_info["root"])
    config = (config_path or project / ".playtest-pilot.json").expanduser().resolve()
    output_root = (output_path or project / ".playtest-pilot").expanduser().resolve()
    checks = load_config(config)
    run_dir = _new_run_dir(output_root)

    report: dict[str, Any] = {
        "version": VERSION,
        "startedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "project": project_info,
        "config": str(config),
        "status": "running",
        "checks": [],
    }
    try:
        for check in checks:
            print(f"Running {check['name']}...", flush=True)
            result = run_check(check, project_info, run_dir)
            report["checks"].append(result)
            print(f"{check['name']}: {result['status']}", flush=True)
    finally:
        report["status"] = "passed" if report["checks"] and all(
            check["status"] == "passed" for check in report["checks"]
        ) else "failed"
        write_reports(run_dir, report)

    print(f"Report: {run_dir / 'report.md'}")
    return 0 if report["status"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="playtest-pilot", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subparsers = parser.add_subparsers(dest="action", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Detect an Unreal or Unity project.")
    inspect_parser.add_argument("--project", type=Path, default=Path("."))
    inspect_parser.add_argument("--json", action="store_true", dest="as_json")

    run_parser = subparsers.add_parser("run", help="Run checks from .playtest-pilot.json.")
    run_parser.add_argument("--project", type=Path, default=Path("."))
    run_parser.add_argument("--config", type=Path)
    run_parser.add_argument("--output", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.action == "inspect":
            info = detect_project(args.project)
            if args.as_json:
                print(json.dumps(info, indent=2))
            else:
                print(f"Project: {info['name']}")
                print(f"Engine: {info['engine']}")
                if info["engineVersion"]:
                    print(f"Engine version: {info['engineVersion']}")
                if info["projectFile"]:
                    print(f"Project file: {info['projectFile']}")
            return 0
        return run(args.project, args.config, args.output)
    except PilotError as exc:
        print(f"playtest-pilot: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
