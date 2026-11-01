# Engine command starting points

Adapt these to the project. Existing project scripts and CI commands are usually better than these generic examples. Replace engine paths and test filters. Command arrays avoid shell quoting and injection problems.

## Placeholders

- `{project}`: absolute game project directory
- `{project_file}`: absolute `.uproject` path, or an empty string outside Unreal
- `{output}`: the current check's evidence directory

## Unity EditMode tests

```json
{
  "checks": [
    {
      "name": "editmode-tests",
      "command": [
        "C:/Program Files/Unity/Hub/Editor/6000.0.0f1/Editor/Unity.exe",
        "-batchmode",
        "-nographics",
        "-projectPath", "{project}",
        "-runTests",
        "-testPlatform", "EditMode",
        "-testResults", "{output}/results.xml",
        "-logFile", "{output}/unity.log",
        "-quit"
      ],
      "timeoutSeconds": 900,
      "evidence": ["{output}/results.xml", "{output}/unity.log"],
      "requiredEvidence": true
    }
  ]
}
```

Use `-testPlatform PlayMode` for PlayMode tests. A separate PlayMode run is stronger evidence than compilation, but it still only covers what the tests assert.

## Unreal automation tests

```json
{
  "checks": [
    {
      "name": "project-automation-tests",
      "command": [
        "C:/Program Files/Epic Games/UE_5.6/Engine/Binaries/Win64/UnrealEditor-Cmd.exe",
        "{project_file}",
        "-unattended",
        "-nop4",
        "-NullRHI",
        "-ExecCmds=Automation RunTests Project; Quit",
        "-abslog={output}/unreal.log"
      ],
      "timeoutSeconds": 900,
      "successExitCodes": [0],
      "evidence": ["{output}/unreal.log"],
      "requiredEvidence": true
    }
  ]
}
```

Change `Project` to the project's actual automation filter. `-NullRHI` is unsuitable for checks that need rendering, screenshots, or real gameplay presentation. Visual verification needs a project-specific test or editor integration beyond this starter runner.

## A project script

A script already owned by the game repository is the best check when available:

```json
{
  "checks": [
    {
      "name": "gameplay-smoke-test",
      "command": ["python", "tools/test_gameplay.py", "--report", "{output}/results.json"],
      "timeoutSeconds": 300,
      "evidence": ["{output}/results.json"],
      "requiredEvidence": true
    }
  ]
}
```
