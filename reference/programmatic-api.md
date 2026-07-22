# Programmatic API

`apolo_flow.api.FlowAPI` is the supported machine-readable facade for a Flow project.
It operates on structured values and never parses CLI or Rich output. Application
code should construct it with the `open_flow_api` async context manager:

```python
from pathlib import Path

from apolo_flow.api import open_flow_api

async with open_flow_api(
    cluster="production",
    org="example-org",
    project="example-project",
    allowed_workspace_root=Path("/srv/flow-workspaces"),
    config_path=Path.home() / ".apolo",
    project_path=Path("/srv/flow-workspaces/training"),
) as flow:
    jobs = await flow.live_list(limit=100)
```

`config_path` is the existing Apolo SDK configuration directory. `project_path` is
the Flow workspace, or a directory below it from which the `.apolo` directory can be
found. It must resolve beneath `allowed_workspace_root`.

The factory copies the SDK configuration to a private temporary directory, selects
the explicit cluster, organization, and project on that copy, initializes API
storage and both runners, then closes every resource on exit. It never changes the
context saved in `config_path`. Keep the context manager open for as long as the
facade is in use; the facade must not be used after exit.

The async facade covers:

- live list, get, run, logs, wait, kill, and project-scoped kill-all;
- bake start, list, get, task logs, wait, cancel, and restart;
- typed job, bake, task, log, list, and run results with terminal reasons and truthful
  truncation fields.

All list, task, log, wait, polling, and write parameters have hard upper bounds in
`apolo_flow.api`. Log bytes remain local to the caller. Bake start always uses the
Flow runner's setup and orchestration phases; the facade never creates a bake through
the persistence layer directly.

This facade is intentionally asynchronous and does not perform authorization. A
service or agent boundary must validate the project root, preserve the selected Apolo
context, enforce its own write policy and approval, redact model-facing log data, and
record created resource identifiers before exposing these operations remotely.

The default adapters are compatibility seams over the current Flow runners. The
factory reuses credentials from an existing SDK configuration; it does not add
another authentication mechanism.
