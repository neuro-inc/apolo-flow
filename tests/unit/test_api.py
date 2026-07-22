import asyncio
import datetime
import pytest
from apolo_sdk import JobStatus, ResourceNotFound
from pathlib import Path
from typing import AbstractSet, Any, AsyncIterator, Mapping, Optional, Sequence, cast

from apolo_flow.api import (
    MAX_LIST_LIMIT,
    MAX_LOG_BYTES,
    MAX_LOG_CHUNKS,
    MAX_LOG_TIMEOUT,
    MAX_POLL_INTERVAL,
    MAX_TASK_LIMIT,
    MAX_WAIT_TIMEOUT,
    MAX_WRITE_TIMEOUT,
    AmbiguousLiveJob,
    BatchRunnerAdapter,
    BoundError,
    DefaultBatchRunnerAdapter,
    DefaultLiveRunnerAdapter,
    FlowAPI,
    LiveRunnerAdapter,
    OperationTimeout,
    PathOutsideWorkspace,
    open_flow_api,
)
from apolo_flow.live_runner import JobInfo
from apolo_flow.storage.base import (
    Attempt,
    Bake,
    BakeMeta,
    ConfigsMeta,
    Task,
    TaskStatusItem,
)
from apolo_flow.types import TaskStatus


NOW = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)


class FakeLive:
    def __init__(self) -> None:
        self.run_calls: list[tuple[str, Optional[str]]] = []
        self.run_params: list[Mapping[str, str]] = []
        self.kill_calls: list[tuple[str, Optional[str]]] = []
        self.kill_all_calls = 0
        self.get_count = 0
        self.multi = False
        self.monitor_chunks = [b"abc", b"defgh"]
        self.get_infos: Optional[Sequence[JobInfo]] = None
        self.write_delay = 0.0

    def _info(self, job_id: str, suffix: Optional[str]) -> JobInfo:
        status = JobStatus.RUNNING if self.get_count < 2 else JobStatus.SUCCEEDED
        name = job_id if suffix is None else f"{job_id} {suffix}"
        return JobInfo(name, status, "job-1", ("job:x",), NOW)

    async def list(self) -> Sequence[JobInfo]:
        return [self._info("first", None), self._info("second", None)]

    async def get(self, job_id: str, suffix: Optional[str]) -> Sequence[JobInfo]:
        self.get_count += 1
        if self.get_infos is not None:
            return self.get_infos
        return [self._info(job_id, suffix)]

    async def run(
        self,
        job_id: str,
        suffix: Optional[str],
        params: Mapping[str, str],
    ) -> None:
        await asyncio.sleep(self.write_delay)
        self.run_calls.append((job_id, suffix))
        self.run_params.append(params)

    async def is_multi(self, job_id: str) -> bool:
        return self.multi

    async def kill(self, job_id: str, suffix: Optional[str]) -> bool:
        await asyncio.sleep(self.write_delay)
        self.kill_calls.append((job_id, suffix))
        return True

    async def kill_all(self) -> None:
        await asyncio.sleep(self.write_delay)
        self.kill_all_calls += 1

    async def _monitor(self) -> AsyncIterator[bytes]:
        for chunk in self.monitor_chunks:
            yield chunk

    def monitor(self, raw_id: str) -> AsyncIterator[bytes]:
        return self._monitor()


class FakeAttemptStorage:
    def __init__(self, attempt: Attempt, tasks: Sequence[Task]) -> None:
        self.attempt = attempt
        self.tasks = tasks

    async def get(self) -> Attempt:
        return self.attempt

    async def list_tasks(self) -> AsyncIterator[Task]:
        for task in self.tasks:
            yield task

    def task(
        self, *, id: Optional[str] = None, yaml_id: Optional[tuple[str, ...]] = None
    ) -> "FakeTaskStorage":
        for task in self.tasks:
            if task.id == id or task.yaml_id == yaml_id:
                return FakeTaskStorage(task)
        return FakeTaskStorage(None)


class FakeTaskStorage:
    def __init__(self, task: Optional[Task]) -> None:
        self.task = task

    async def get(self) -> Task:
        if self.task is None:
            raise ResourceNotFound
        return self.task


class FakeBakeStorage:
    def __init__(
        self, bake: Optional[Bake], attempt: Attempt, tasks: Sequence[Task]
    ) -> None:
        self.bake = bake
        self.attempt_storage = FakeAttemptStorage(attempt, tasks)

    async def get(self) -> Bake:
        if self.bake is None:
            raise ResourceNotFound
        return self.bake

    def attempt(
        self, *, id: Optional[str] = None, number: Optional[int] = None
    ) -> FakeAttemptStorage:
        return self.attempt_storage


class FakeProjectStorage:
    def __init__(self, bake: Bake, attempt: Attempt, tasks: Sequence[Task]) -> None:
        self.value = bake
        self.by_id = FakeBakeStorage(bake, attempt, tasks)
        self.list_items = [bake]

    def bake(
        self, *, id: Optional[str] = None, name: Optional[str] = None
    ) -> FakeBakeStorage:
        if id is not None and id != self.value.id:
            return FakeBakeStorage(None, self.by_id.attempt_storage.attempt, ())
        if name is not None and name != self.value.name:
            return FakeBakeStorage(None, self.by_id.attempt_storage.attempt, ())
        return self.by_id

    async def list_bakes(
        self,
        tags: Optional[AbstractSet[str]] = None,
        since: Optional[datetime.datetime] = None,
        until: Optional[datetime.datetime] = None,
        recent_first: bool = False,
    ) -> AsyncIterator[Bake]:
        for bake in self.list_items:
            yield bake


class FakeBatch:
    def __init__(self, storage: FakeProjectStorage) -> None:
        self._storage = storage
        self.start_calls: list[str] = []
        self.cancel_calls: list[tuple[str, int]] = []
        self.restart_calls: list[tuple[str, int, bool, bool]] = []
        self.restart_error: Optional[Exception] = None
        self.write_delay = 0.0

    @property
    def storage(self) -> FakeProjectStorage:
        return self._storage

    async def start(
        self,
        batch: str,
        *,
        local_executor: bool,
        params: Optional[Mapping[str, str]],
        name: Optional[str],
        tags: Sequence[str],
    ) -> Bake:
        await asyncio.sleep(self.write_delay)
        self.start_calls.append(batch)
        return self.storage.value

    async def cancel(self, bake_id: str, *, attempt_no: int) -> None:
        await asyncio.sleep(self.write_delay)
        self.cancel_calls.append((bake_id, attempt_no))
        self.storage.by_id.attempt_storage.attempt = _attempt(TaskStatus.CANCELLED)

    async def restart(
        self,
        bake_id: str,
        *,
        attempt_no: int,
        from_failed: bool,
        local_executor: bool,
    ) -> None:
        await asyncio.sleep(self.write_delay)
        if self.restart_error:
            raise self.restart_error
        self.restart_calls.append((bake_id, attempt_no, from_failed, local_executor))

    async def _monitor(self) -> AsyncIterator[bytes]:
        yield b"task-log"

    def monitor(self, raw_id: str) -> AsyncIterator[bytes]:
        return self._monitor()


def _attempt(result: TaskStatus = TaskStatus.RUNNING) -> Attempt:
    return Attempt(
        "attempt-1",
        "bake-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        1,
        NOW,
        result,
        ConfigsMeta(".", "config-1", None, {}),
        "executor-1",
    )


def _bake(attempt: Attempt) -> Bake:
    return Bake(
        attempt.bake_id,
        "project-1",
        "train",
        "daily",
        ("team:ml",),
        NOW,
        BakeMeta(None),
        {},
        None,
        attempt,
    )


def _task(name: str = "train") -> Task:
    return Task(
        "task-1",
        (name,),
        "attempt-1",
        "job-task",
        {"model": "uri"},
        {"checkpoint": "ok"},
        [TaskStatusItem(NOW, TaskStatus.SUCCEEDED)],
    )


def _api(tmp_path: Path) -> tuple[FlowAPI, FakeLive, FakeBatch]:
    config = tmp_path / "flow.yml"
    config.write_text("kind: live")
    attempt = _attempt()
    live = FakeLive()
    batch = FakeBatch(
        FakeProjectStorage(_bake(attempt), attempt, [_task(), _task("b")])
    )
    api = FlowAPI(
        allowed_workspace_root=tmp_path,
        config_path=config,
        live=cast(LiveRunnerAdapter, live),
        batch=cast(BatchRunnerAdapter, batch),
    )
    return api, live, batch


def test_rejects_path_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.yml"
    outside.write_text("x")
    live = cast(LiveRunnerAdapter, FakeLive())
    attempt = _attempt()
    batch = FakeBatch(FakeProjectStorage(_bake(attempt), attempt, ()))
    with pytest.raises(PathOutsideWorkspace):
        FlowAPI(
            allowed_workspace_root=root,
            config_path=outside,
            live=live,
            batch=cast(BatchRunnerAdapter, batch),
        )


async def test_open_flow_api_initializes_and_closes_without_saving_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    flow_config = workspace / ".apolo"
    flow_config.mkdir(parents=True)
    sdk_config = tmp_path / "sdk"
    sdk_config.mkdir()
    saved_context = sdk_config / "context"
    saved_context.write_text("saved")
    events: list[str] = []
    private_config: Optional[Path] = None

    class Config:
        def __init__(self, path: Path) -> None:
            self.path = path

        async def switch_cluster(self, value: str) -> None:
            events.append(f"cluster:{value}")
            (self.path / "context").write_text(value)

        async def switch_org(self, value: str) -> None:
            events.append(f"org:{value}")

        async def switch_project(self, value: str) -> None:
            events.append(f"project:{value}")

    class Resource:
        def __init__(self, name: str, value: object) -> None:
            self.name = name
            self.value = value

        async def __aenter__(self) -> object:
            events.append(f"enter:{self.name}")
            return self.value

        async def __aexit__(self, *args: object) -> None:
            events.append(f"exit:{self.name}")

    class Client:
        def __init__(self, path: Path) -> None:
            self.config = Config(path)

    class Runner:
        def __init__(self, name: str) -> None:
            self.name = name

        async def __aenter__(self) -> "Runner":
            events.append(f"enter:{self.name}")
            return self

        async def __aexit__(self, *args: object) -> None:
            events.append(f"exit:{self.name}")

    def get(*, path: Path) -> Resource:
        nonlocal private_config
        private_config = path
        assert (path / "context").read_text() == "saved"
        return Resource("client", Client(path))

    monkeypatch.setattr("apolo_flow.api.apolo_sdk.get", get)
    monkeypatch.setattr(
        "apolo_flow.api.ApiStorage", lambda client: Resource("storage", object())
    )
    monkeypatch.setattr("apolo_flow.api.LiveRunner", lambda *args: Runner("live"))
    monkeypatch.setattr("apolo_flow.api.BatchRunner", lambda *args: Runner("batch"))

    async with open_flow_api(
        cluster="cluster-a",
        org="org-a",
        project="project-a",
        allowed_workspace_root=workspace,
        config_path=sdk_config,
        project_path=workspace,
    ) as api:
        assert api.workspace_root == workspace
        assert api.config_path == flow_config
        assert private_config is not None and private_config.exists()
        events.append("yield")

    assert saved_context.read_text() == "saved"
    assert private_config is not None and not private_config.exists()
    assert events == [
        "enter:client",
        "cluster:cluster-a",
        "org:org-a",
        "project:project-a",
        "enter:storage",
        "enter:live",
        "enter:batch",
        "yield",
        "exit:batch",
        "exit:live",
        "exit:storage",
        "exit:client",
    ]


async def test_open_flow_api_rejects_project_outside_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sdk_config = tmp_path / "sdk"
    sdk_config.mkdir()

    with pytest.raises(PathOutsideWorkspace):
        async with open_flow_api(
            cluster="cluster-a",
            org="org-a",
            project="project-a",
            allowed_workspace_root=workspace,
            config_path=sdk_config,
            project_path=outside,
        ):
            pass


async def test_live_resolution_generated_suffix_and_bounds(tmp_path: Path) -> None:
    api, live, _ = _api(tmp_path)
    live.multi = True
    result = await api.live_run("worker")
    assert result.suffix is not None
    assert live.run_calls == [("worker", result.suffix)]
    assert result.jobs[0].suffix == result.suffix
    listed = await api.live_list(limit=1)
    assert len(listed.jobs) == 1
    assert listed.truncated
    with pytest.raises(BoundError):
        await api.live_list(limit=0)
    with pytest.raises(BoundError):
        await api.live_list(limit=MAX_LIST_LIMIT + 1)


async def test_live_run_uses_fresh_immutable_default_handling(tmp_path: Path) -> None:
    api, live, _ = _api(tmp_path)
    await api.live_run("worker")
    await api.live_run("worker")
    assert live.run_params == [{}, {}]
    assert live.run_params[0] is not live.run_params[1]


async def test_default_live_adapter_converts_confirmed_remote_failure() -> None:
    class Runner:
        async def run(
            self,
            job_id: str,
            suffix: Optional[str],
            params: Mapping[str, str],
        ) -> None:
            raise SystemExit(7)

        async def _job_status(self, job_id: str) -> Sequence[JobInfo]:
            return [JobInfo(job_id, JobStatus.FAILED, "job-failed", (), NOW)]

    adapter = DefaultLiveRunnerAdapter(cast(Any, Runner()))
    await adapter.run("worker", None, {})


async def test_default_live_adapter_preserves_unconfirmed_local_exit() -> None:
    class Runner:
        async def run(
            self,
            job_id: str,
            suffix: Optional[str],
            params: Mapping[str, str],
        ) -> None:
            raise SystemExit(2)

        async def _job_status(self, job_id: str) -> Sequence[JobInfo]:
            return [JobInfo(job_id, JobStatus.UNKNOWN, None, (), NOW)]

    adapter = DefaultLiveRunnerAdapter(cast(Any, Runner()))
    with pytest.raises(RuntimeError, match="before 'worker' reached terminal"):
        await adapter.run("worker", None, {})


async def test_default_batch_adapter_converts_confirmed_remote_failure() -> None:
    attempt = _attempt(TaskStatus.FAILED)
    bake = _bake(attempt)

    class Runner:
        storage = FakeProjectStorage(bake, attempt, ())

        async def _setup_bake(
            self,
            batch: str,
            params: Optional[Mapping[str, str]],
            name: Optional[str],
            tags: Sequence[str],
        ) -> tuple[Bake, object]:
            return bake, object()

        async def _run_bake(
            self, bake: Bake, flow: object, local_executor: bool
        ) -> None:
            raise SystemExit(1)

    adapter = DefaultBatchRunnerAdapter(cast(Any, Runner()))
    assert (
        await adapter.start(
            "failure", local_executor=False, params=None, name=None, tags=()
        )
        == bake
    )


async def test_default_batch_adapter_preserves_unconfirmed_local_exit() -> None:
    attempt = _attempt(TaskStatus.RUNNING)
    bake = _bake(attempt)

    class Runner:
        storage = FakeProjectStorage(bake, attempt, ())

        async def _setup_bake(
            self,
            batch: str,
            params: Optional[Mapping[str, str]],
            name: Optional[str],
            tags: Sequence[str],
        ) -> tuple[Bake, object]:
            return bake, object()

        async def _run_bake(
            self, bake: Bake, flow: object, local_executor: bool
        ) -> None:
            raise SystemExit(2)

    adapter = DefaultBatchRunnerAdapter(cast(Any, Runner()))
    with pytest.raises(RuntimeError, match="before bake .* reached terminal"):
        await adapter.start(
            "failure", local_executor=False, params=None, name=None, tags=()
        )


async def test_live_logs_enforce_byte_and_chunk_bounds(tmp_path: Path) -> None:
    api, _, _ = _api(tmp_path)
    result = await api.live_logs("worker", timeout=1, max_chunks=2, max_bytes=5)
    assert result.data == b"abcde"
    assert result.chunks == 2
    assert result.truncated
    for kwargs in (
        {"timeout": MAX_LOG_TIMEOUT + 1, "max_chunks": 1, "max_bytes": 1},
        {"timeout": 1, "max_chunks": MAX_LOG_CHUNKS + 1, "max_bytes": 1},
        {"timeout": 1, "max_chunks": 1, "max_bytes": MAX_LOG_BYTES + 1},
    ):
        with pytest.raises(BoundError):
            await api.live_logs("worker", **kwargs)


async def test_live_logs_reject_ambiguous_raw_jobs(tmp_path: Path) -> None:
    api, live, _ = _api(tmp_path)
    live.get_infos = [
        JobInfo("worker one", JobStatus.RUNNING, "job-1", (), NOW),
        JobInfo("worker two", JobStatus.RUNNING, "job-2", (), NOW),
    ]
    with pytest.raises(AmbiguousLiveJob, match="provide a suffix"):
        await api.live_logs("worker", timeout=1, max_chunks=1, max_bytes=10)


async def test_live_kill_operations_are_structured_and_bounded(tmp_path: Path) -> None:
    api, live, _ = _api(tmp_path)
    killed = await api.live_kill("worker", suffix="one", timeout=1)
    assert killed[0].suffix == "one"
    assert live.kill_calls == [("worker", "one")]
    listed = await api.live_kill_all(limit=1, timeout=1)
    assert len(listed.jobs) == 1
    assert listed.truncated
    assert live.kill_all_calls == 1
    with pytest.raises(BoundError):
        await api.live_run("worker", timeout=MAX_WRITE_TIMEOUT + 1)
    with pytest.raises(BoundError):
        await api.live_kill("worker", timeout=MAX_WRITE_TIMEOUT + 1)
    with pytest.raises(BoundError):
        await api.live_kill_all(limit=1, timeout=MAX_WRITE_TIMEOUT + 1)


async def test_live_wait_and_timeout(tmp_path: Path) -> None:
    api, live, _ = _api(tmp_path)
    state = await api.live_wait("worker", timeout=1, poll_interval=0.001)
    assert state[0].terminal_reason == "succeeded"
    live.get_count = -100
    with pytest.raises(OperationTimeout):
        await api.live_wait("worker", timeout=0.001, poll_interval=0.001)
    with pytest.raises(BoundError):
        await api.live_wait("worker", timeout=MAX_WAIT_TIMEOUT + 1, poll_interval=0.001)
    with pytest.raises(BoundError):
        await api.live_wait("worker", timeout=1, poll_interval=MAX_POLL_INTERVAL + 1)


async def test_bake_start_get_task_bound_and_name_resolution(tmp_path: Path) -> None:
    api, _, batch = _api(tmp_path)
    started = await api.bake_start("train", task_limit=1)
    assert batch.start_calls == ["train"]
    assert started.id == batch.storage.value.id
    assert len(started.tasks) == 1
    assert started.tasks_truncated
    by_name = await api.bake_get("daily", task_limit=2)
    assert by_name.id == started.id
    assert by_name.tasks[0].outputs == {"model": "uri"}
    assert not by_name.tasks_truncated
    with pytest.raises(BoundError):
        await api.bake_get("daily", task_limit=MAX_TASK_LIMIT + 1)


async def test_bake_list_reports_truthful_truncation(tmp_path: Path) -> None:
    api, _, batch = _api(tmp_path)
    first = await api.bake_list(limit=1, task_limit=1)
    assert len(first.bakes) == 1
    assert not first.truncated
    batch.storage.list_items.append(batch.storage.value)
    truncated = await api.bake_list(limit=1, task_limit=1)
    assert len(truncated.bakes) == 1
    assert truncated.truncated
    with pytest.raises(BoundError):
        await api.bake_list(limit=MAX_LIST_LIMIT + 1, task_limit=1)


async def test_bake_logs_cancel_restart_and_controlled_failure(tmp_path: Path) -> None:
    api, _, batch = _api(tmp_path)
    log = await api.bake_logs("daily", "train", timeout=1, max_chunks=1, max_bytes=100)
    assert log.data == b"task-log"
    cancelled = await api.bake_cancel("daily", task_limit=2)
    assert cancelled.terminal_reason == "cancelled"
    assert batch.cancel_calls == [(batch.storage.value.id, -1)]
    await api.bake_restart("daily", from_failed=False, task_limit=2)
    assert batch.restart_calls == [(batch.storage.value.id, -1, False, False)]
    batch.restart_error = RuntimeError("controlled restart failure")
    with pytest.raises(RuntimeError, match="controlled restart failure"):
        await api.bake_restart("daily", task_limit=2)


async def test_bake_write_operations_enforce_timeout_caps(tmp_path: Path) -> None:
    api, _, batch = _api(tmp_path)
    with pytest.raises(BoundError):
        await api.bake_start("train", task_limit=1, timeout=MAX_WRITE_TIMEOUT + 1)
    with pytest.raises(BoundError):
        await api.bake_cancel("daily", task_limit=1, timeout=MAX_WRITE_TIMEOUT + 1)
    with pytest.raises(BoundError):
        await api.bake_restart("daily", task_limit=1, timeout=MAX_WRITE_TIMEOUT + 1)
    batch.write_delay = 0.02
    with pytest.raises(OperationTimeout, match="starting bake"):
        await api.bake_start("train", task_limit=1, timeout=0.001)
    with pytest.raises(OperationTimeout, match="cancelling bake"):
        await api.bake_cancel("daily", task_limit=1, timeout=0.001)
    with pytest.raises(OperationTimeout, match="restarting bake"):
        await api.bake_restart("daily", task_limit=1, timeout=0.001)


async def test_bake_wait_is_bounded(tmp_path: Path) -> None:
    api, _, _ = _api(tmp_path)
    with pytest.raises(OperationTimeout):
        await api.bake_wait("daily", timeout=0.001, poll_interval=0.001, task_limit=1)
