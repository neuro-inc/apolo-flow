# Programmatic API

`apolo_flow.api.FlowAPI` is the supported machine-readable facade for an initialized
Flow project. It operates on structured values and never parses CLI or Rich output.
Callers supply initialized live and batch runner adapters, an existing Flow config
path, and an allowed workspace root; both the config and optional project path must
resolve beneath that root.

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

The default adapters are compatibility seams over the current Flow runners. Creating
and authenticating those runners remains the responsibility of the existing Flow
configuration/bootstrap path; this API does not add another credential or context
configuration mechanism.
