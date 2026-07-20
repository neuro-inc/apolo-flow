"""Typed, asynchronous programmatic access to apolo-flow.

The command runners predate this module and combine orchestration with Rich output.
The small adapter protocols below are intentional seams: callers may inject quiet
runner adapters, while the supplied adapters never inspect or parse console output.
"""

import dataclasses

import asyncio
import datetime
import re
import secrets
from apolo_sdk import JobStatus, ResourceNotFound
from collections.abc import Awaitable
from pathlib import Path
from time import monotonic
from typing import (
    AbstractSet,
    AsyncIterator,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    cast,
)

from .batch_runner import BatchRunner
from .live_runner import JobInfo, LiveRunner
from .storage.base import Attempt, Bake, ProjectStorage, Task
from .types import TaskStatus


_BAKE_ID_RE = re.compile(
    r"bake-[0-9a-z]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12}"
)

# These caps are part of the public resource-safety contract.  Callers may choose
# smaller values, but cannot accidentally turn facade methods into unbounded work.
MAX_LIST_LIMIT = 1_000
MAX_TASK_LIMIT = 10_000
MAX_LOG_CHUNKS = 10_000
MAX_LOG_BYTES = 16 * 1024 * 1024
MAX_LOG_TIMEOUT = 60 * 60.0
MAX_WAIT_TIMEOUT = 24 * 60 * 60.0
MAX_POLL_INTERVAL = 60.0
MAX_WRITE_TIMEOUT = 60 * 60.0
DEFAULT_WRITE_TIMEOUT = 5 * 60.0

_T = TypeVar("_T")


class PathOutsideWorkspace(ValueError):
    """A user supplied path resolves outside the configured workspace root."""


class BoundError(ValueError):
    """A timeout, item count, or byte bound is not strictly positive."""


class OperationTimeout(TimeoutError):
    """A bounded facade operation did not finish in time."""


class AmbiguousLiveJob(ValueError):
    """A logical live job resolves to more than one raw platform job."""


@dataclasses.dataclass(frozen=True)
class LiveJobState:
    job_id: str
    suffix: Optional[str]
    raw_id: Optional[str]
    status: JobStatus
    tags: tuple[str, ...]
    when: Optional[datetime.datetime]
    terminal_reason: Optional[str]


@dataclasses.dataclass(frozen=True)
class LiveRunResult:
    job_id: str
    suffix: Optional[str]
    jobs: tuple[LiveJobState, ...]


@dataclasses.dataclass(frozen=True)
class LiveListResult:
    jobs: tuple[LiveJobState, ...]
    truncated: bool


@dataclasses.dataclass(frozen=True)
class LogResult:
    raw_id: Optional[str]
    data: bytes
    chunks: int
    truncated: bool


@dataclasses.dataclass(frozen=True)
class TaskState:
    id: str
    raw_id: Optional[str]
    status: TaskStatus
    created_at: datetime.datetime
    finished_at: Optional[datetime.datetime]
    outputs: Optional[Mapping[str, str]]
    state: Optional[Mapping[str, str]]
    terminal_reason: Optional[str]


@dataclasses.dataclass(frozen=True)
class BakeState:
    id: str
    name: Optional[str]
    batch: str
    tags: tuple[str, ...]
    created_at: datetime.datetime
    attempt: Optional[int]
    status: Optional[TaskStatus]
    executor_id: Optional[str]
    tasks: tuple[TaskState, ...]
    tasks_truncated: bool
    terminal_reason: Optional[str]


@dataclasses.dataclass(frozen=True)
class BakeListResult:
    bakes: tuple[BakeState, ...]
    truncated: bool


class LiveRunnerAdapter(Protocol):
    """Structured seam over legacy ``LiveRunner`` console methods."""

    async def list(self) -> Sequence[JobInfo]: ...

    async def get(self, job_id: str, suffix: Optional[str]) -> Sequence[JobInfo]: ...

    async def run(
        self,
        job_id: str,
        suffix: Optional[str],
        args: Optional[tuple[str, ...]],
        params: Mapping[str, str],
    ) -> None: ...

    async def is_multi(self, job_id: str) -> bool: ...

    async def kill(self, job_id: str, suffix: Optional[str]) -> bool: ...

    async def kill_all(self) -> None: ...

    def monitor(self, raw_id: str) -> AsyncIterator[bytes]: ...


class BatchRunnerAdapter(Protocol):
    """Structured seam over legacy ``BatchRunner`` console methods."""

    @property
    def storage(self) -> ProjectStorage: ...

    async def start(
        self,
        batch: str,
        *,
        local_executor: bool,
        params: Optional[Mapping[str, str]],
        name: Optional[str],
        tags: Sequence[str],
    ) -> Bake: ...

    async def cancel(self, bake_id: str, *, attempt_no: int) -> None: ...

    async def restart(
        self,
        bake_id: str,
        *,
        attempt_no: int,
        from_failed: bool,
        local_executor: bool,
    ) -> None: ...

    def monitor(self, raw_id: str) -> AsyncIterator[bytes]: ...


class LogSource(Protocol):
    def monitor(self, raw_id: str) -> AsyncIterator[bytes]: ...


class DefaultLiveRunnerAdapter:
    """Adapter using runner resolution primitives without parsing its output."""

    def __init__(self, runner: LiveRunner) -> None:
        self._runner = runner

    async def list(self) -> Sequence[JobInfo]:
        groups = await asyncio.gather(
            *(self._runner._job_status(job_id) for job_id in self._runner.flow.job_ids)
        )
        return [item for group in groups for item in group]

    async def get(self, job_id: str, suffix: Optional[str]) -> Sequence[JobInfo]:
        if suffix is None:
            return await self._runner._job_status(job_id)
        meta = await self._runner._ensure_meta(job_id, suffix)
        result: list[JobInfo] = []
        try:
            async for descr in self._runner._resolve_jobs(meta, suffix):
                when = (
                    descr.history.created_at
                    if descr.status == JobStatus.PENDING
                    else (
                        descr.history.started_at
                        if descr.status == JobStatus.RUNNING
                        else descr.history.finished_at
                    )
                )
                result.append(
                    JobInfo(
                        f"{job_id} {suffix}", descr.status, descr.id, descr.tags, when
                    )
                )
        except ResourceNotFound:
            result.append(
                JobInfo(f"{job_id} {suffix}", JobStatus.UNKNOWN, None, (), None)
            )
        return result

    async def run(
        self,
        job_id: str,
        suffix: Optional[str],
        args: Optional[tuple[str, ...]],
        params: Mapping[str, str],
    ) -> None:
        # LiveRunner's annotation says a one-item tuple although the CLI and
        # implementation both support an arbitrary argument tuple.
        try:
            await self._runner.run(
                job_id, suffix, cast(Optional[tuple[str]], args), params
            )
        except SystemExit as exc:
            # The legacy runner delegates to the Apolo CLI. A non-zero remote job
            # exit is therefore surfaced as SystemExit even though submission and
            # orchestration succeeded. Convert only a confirmed terminal platform
            # job into normal structured state; local validation/submission exits
            # remain errors.
            infos = await self.get(job_id, suffix)
            if infos and all(info.status.is_finished for info in infos):
                return
            raise RuntimeError(
                f"live runner exited before {job_id!r} reached terminal state"
            ) from exc

    async def is_multi(self, job_id: str) -> bool:
        return await self._runner.flow.is_multi(job_id)

    async def kill(self, job_id: str, suffix: Optional[str]) -> bool:
        return await self._runner.kill_job(job_id, suffix)

    async def kill_all(self) -> None:
        await self._runner.kill_all()

    def monitor(self, raw_id: str) -> AsyncIterator[bytes]:
        return self._runner.client.jobs.monitor(raw_id)


class DefaultBatchRunnerAdapter:
    """Adapter that starts bakes through ``BatchRunner`` orchestration.

    ``BatchRunner.bake`` discards the created bake. Calling its two orchestration
    phases directly is the only safe way to return the ID; this is deliberately
    kept here so the public facade does not infer IDs from formatted output.
    """

    def __init__(self, runner: BatchRunner) -> None:
        self._runner = runner

    @property
    def storage(self) -> ProjectStorage:
        return self._runner.storage

    async def start(
        self,
        batch: str,
        *,
        local_executor: bool,
        params: Optional[Mapping[str, str]],
        name: Optional[str],
        tags: Sequence[str],
    ) -> Bake:
        bake, flow = await self._runner._setup_bake(batch, params, name, tags)
        try:
            await self._runner._run_bake(bake, flow, local_executor)
        except SystemExit as exc:
            # The remote executor CLI exits non-zero when the bake reaches a
            # failed terminal result. Preserve that result as machine-readable
            # bake state, while keeping submission/local failures exceptional.
            attempt = await self.storage.bake(id=bake.id).attempt(number=-1).get()
            if attempt.result.is_finished:
                return bake
            raise RuntimeError(
                f"batch runner exited before bake {bake.id!r} reached terminal state"
            ) from exc
        return bake

    async def cancel(self, bake_id: str, *, attempt_no: int) -> None:
        await self._runner.cancel(bake_id, attempt_no=attempt_no)

    async def restart(
        self,
        bake_id: str,
        *,
        attempt_no: int,
        from_failed: bool,
        local_executor: bool,
    ) -> None:
        await self._runner.restart(
            bake_id,
            attempt_no=attempt_no,
            from_failed=from_failed,
            local_executor=local_executor,
        )

    def monitor(self, raw_id: str) -> AsyncIterator[bytes]:
        return self._runner._client.jobs.monitor(raw_id)


class FlowAPI:
    """A bounded machine-readable facade over initialized flow runners."""

    def __init__(
        self,
        *,
        allowed_workspace_root: Path,
        config_path: Path,
        project_path: Optional[Path] = None,
        live: LiveRunnerAdapter,
        batch: BatchRunnerAdapter,
    ) -> None:
        self.workspace_root = allowed_workspace_root.resolve(strict=True)
        self.config_path = self._safe_path(config_path)
        self.project_path = (
            self._safe_path(project_path) if project_path is not None else None
        )
        self._live = live
        self._batch = batch

    def _safe_path(self, path: Path) -> Path:
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise PathOutsideWorkspace(
                f"{resolved} is outside allowed workspace {self.workspace_root}"
            ) from exc
        return resolved

    @staticmethod
    def _bounded(value: float, name: str, maximum: float) -> None:
        if value <= 0 or value > maximum:
            raise BoundError(
                f"{name} must be greater than zero and at most {maximum:g}"
            )

    @classmethod
    def _log_bounds(cls, timeout: float, max_chunks: int, max_bytes: int) -> None:
        cls._bounded(timeout, "timeout", MAX_LOG_TIMEOUT)
        cls._bounded(max_chunks, "max_chunks", MAX_LOG_CHUNKS)
        cls._bounded(max_bytes, "max_bytes", MAX_LOG_BYTES)

    @classmethod
    async def _write(
        cls, awaitable: Awaitable[_T], timeout: float, operation: str
    ) -> _T:
        cls._bounded(timeout, "timeout", MAX_WRITE_TIMEOUT)
        return await cls._timed(awaitable, timeout, operation)

    @staticmethod
    async def _timed(awaitable: Awaitable[_T], timeout: float, operation: str) -> _T:
        try:
            return await asyncio.wait_for(awaitable, timeout)
        except asyncio.TimeoutError as exc:
            raise OperationTimeout(f"timed out {operation}") from exc

    @staticmethod
    def _live_state(info: JobInfo) -> LiveJobState:
        parts = info.id.split(" ", 1)
        terminal = info.status.value if info.status.is_finished else None
        return LiveJobState(
            parts[0],
            parts[1] if len(parts) == 2 else None,
            info.raw_id,
            info.status,
            tuple(info.tags),
            info.when,
            terminal,
        )

    async def live_list(self, *, limit: int) -> LiveListResult:
        self._bounded(limit, "limit", MAX_LIST_LIMIT)
        infos = (await self._live.list())[: limit + 1]
        return LiveListResult(
            tuple(self._live_state(info) for info in infos[:limit]),
            len(infos) > limit,
        )

    async def live_get(
        self, job_id: str, suffix: Optional[str] = None
    ) -> tuple[LiveJobState, ...]:
        return tuple(self._live_state(i) for i in await self._live.get(job_id, suffix))

    async def live_run(
        self,
        job_id: str,
        *,
        suffix: Optional[str] = None,
        args: Optional[tuple[str, ...]] = None,
        params: Optional[Mapping[str, str]] = None,
        timeout: float = DEFAULT_WRITE_TIMEOUT,
    ) -> LiveRunResult:
        self._bounded(timeout, "timeout", MAX_WRITE_TIMEOUT)

        async def operation() -> LiveRunResult:
            resolved_suffix = suffix
            if resolved_suffix is None and await self._live.is_multi(job_id):
                resolved_suffix = secrets.token_hex(5)
            await self._live.run(
                job_id,
                resolved_suffix,
                args,
                {} if params is None else params,
            )
            jobs = await self.live_get(job_id, resolved_suffix)
            return LiveRunResult(job_id, resolved_suffix, jobs)

        return await self._write(operation(), timeout, f"starting live job {job_id}")

    async def live_logs(
        self,
        job_id: str,
        *,
        suffix: Optional[str] = None,
        timeout: float,
        max_chunks: int,
        max_bytes: int,
    ) -> LogResult:
        self._log_bounds(timeout, max_chunks, max_bytes)
        deadline = monotonic() + timeout
        jobs = await self._timed(
            self.live_get(job_id, suffix), timeout, f"resolving live job {job_id}"
        )
        raw_ids = {job.raw_id for job in jobs if job.raw_id is not None}
        if len(raw_ids) > 1:
            raise AmbiguousLiveJob(
                f"live job {job_id} resolves to multiple raw jobs; provide a suffix"
            )
        raw_id = next(iter(raw_ids), None)
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise OperationTimeout(f"timed out reading logs for live job {job_id}")
        return await self._logs(self._live, raw_id, remaining, max_chunks, max_bytes)

    async def live_wait(
        self,
        job_id: str,
        *,
        suffix: Optional[str] = None,
        timeout: float,
        poll_interval: float,
    ) -> tuple[LiveJobState, ...]:
        self._bounded(timeout, "timeout", MAX_WAIT_TIMEOUT)
        self._bounded(poll_interval, "poll_interval", MAX_POLL_INTERVAL)
        deadline = monotonic() + timeout
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise OperationTimeout(f"timed out waiting for live job {job_id}")
            jobs = await self._timed(
                self.live_get(job_id, suffix),
                remaining,
                f"waiting for live job {job_id}",
            )
            if jobs and all(job.status.is_finished for job in jobs):
                return jobs
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise OperationTimeout(f"timed out waiting for live job {job_id}")
            await asyncio.sleep(min(poll_interval, remaining))

    async def live_kill(
        self,
        job_id: str,
        *,
        suffix: Optional[str] = None,
        timeout: float = DEFAULT_WRITE_TIMEOUT,
    ) -> tuple[LiveJobState, ...]:
        self._bounded(timeout, "timeout", MAX_WRITE_TIMEOUT)

        async def operation() -> tuple[LiveJobState, ...]:
            await self._live.kill(job_id, suffix)
            return await self.live_get(job_id, suffix)

        return await self._write(operation(), timeout, f"killing live job {job_id}")

    async def live_kill_all(
        self, *, limit: int, timeout: float = DEFAULT_WRITE_TIMEOUT
    ) -> LiveListResult:
        self._bounded(limit, "limit", MAX_LIST_LIMIT)
        self._bounded(timeout, "timeout", MAX_WRITE_TIMEOUT)

        async def operation() -> LiveListResult:
            await self._live.kill_all()
            return await self.live_list(limit=limit)

        return await self._write(operation(), timeout, "killing all live jobs")

    async def _resolve_bake(self, id_or_name: str) -> str:
        if _BAKE_ID_RE.fullmatch(id_or_name):
            return id_or_name
        try:
            return (await self._batch.storage.bake(name=id_or_name).get()).id
        except ResourceNotFound:
            return id_or_name

    async def bake_start(
        self,
        batch: str,
        *,
        local_executor: bool = False,
        params: Optional[Mapping[str, str]] = None,
        name: Optional[str] = None,
        tags: Sequence[str] = (),
        task_limit: int,
        timeout: float = DEFAULT_WRITE_TIMEOUT,
    ) -> BakeState:
        self._bounded(task_limit, "task_limit", MAX_TASK_LIMIT)
        self._bounded(timeout, "timeout", MAX_WRITE_TIMEOUT)

        async def operation() -> BakeState:
            bake = await self._batch.start(
                batch,
                local_executor=local_executor,
                params=params,
                name=name,
                tags=tags,
            )
            return await self._bake_state(bake, -1, task_limit)

        return await self._write(operation(), timeout, f"starting bake {batch}")

    async def bake_list(
        self,
        *,
        limit: int,
        task_limit: int,
        tags: AbstractSet[str] = frozenset(),
        since: Optional[datetime.datetime] = None,
        until: Optional[datetime.datetime] = None,
        recent_first: bool = False,
    ) -> BakeListResult:
        self._bounded(limit, "limit", MAX_LIST_LIMIT)
        self._bounded(task_limit, "task_limit", MAX_TASK_LIMIT)
        result: list[BakeState] = []
        truncated = False
        async for bake in self._batch.storage.list_bakes(
            tags=tags, since=since, until=until, recent_first=recent_first
        ):
            if len(result) == limit:
                truncated = True
                break
            result.append(await self._bake_state(bake, -1, task_limit))
        return BakeListResult(tuple(result), truncated)

    async def bake_get(
        self, id_or_name: str, *, attempt_no: int = -1, task_limit: int
    ) -> BakeState:
        self._bounded(task_limit, "task_limit", MAX_TASK_LIMIT)
        bake_id = await self._resolve_bake(id_or_name)
        bake = await self._batch.storage.bake(id=bake_id).get()
        return await self._bake_state(bake, attempt_no, task_limit)

    async def bake_logs(
        self,
        id_or_name: str,
        task_id: str,
        *,
        attempt_no: int = -1,
        timeout: float,
        max_chunks: int,
        max_bytes: int,
    ) -> LogResult:
        self._log_bounds(timeout, max_chunks, max_bytes)
        deadline = monotonic() + timeout

        async def resolve_task() -> Task:
            bake_id = await self._resolve_bake(id_or_name)
            return await (
                self._batch.storage.bake(id=bake_id)
                .attempt(number=attempt_no)
                .task(yaml_id=tuple(task_id.split(".")))
                .get()
            )

        task = await self._timed(
            resolve_task(), timeout, f"resolving task {task_id} of bake {id_or_name}"
        )
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise OperationTimeout(f"timed out reading logs for bake {id_or_name}")
        return await self._logs(
            self._batch, task.raw_id, remaining, max_chunks, max_bytes
        )

    async def bake_wait(
        self,
        id_or_name: str,
        *,
        attempt_no: int = -1,
        timeout: float,
        poll_interval: float,
        task_limit: int,
    ) -> BakeState:
        self._bounded(timeout, "timeout", MAX_WAIT_TIMEOUT)
        self._bounded(poll_interval, "poll_interval", MAX_POLL_INTERVAL)
        deadline = monotonic() + timeout
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise OperationTimeout(f"timed out waiting for bake {id_or_name}")
            state = await self._timed(
                self.bake_get(id_or_name, attempt_no=attempt_no, task_limit=task_limit),
                remaining,
                f"waiting for bake {id_or_name}",
            )
            if state.status is not None and state.status.is_finished:
                return state
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise OperationTimeout(f"timed out waiting for bake {id_or_name}")
            await asyncio.sleep(min(poll_interval, remaining))

    async def bake_cancel(
        self,
        id_or_name: str,
        *,
        attempt_no: int = -1,
        task_limit: int,
        timeout: float = DEFAULT_WRITE_TIMEOUT,
    ) -> BakeState:
        self._bounded(task_limit, "task_limit", MAX_TASK_LIMIT)
        self._bounded(timeout, "timeout", MAX_WRITE_TIMEOUT)

        async def operation() -> BakeState:
            bake_id = await self._resolve_bake(id_or_name)
            await self._batch.cancel(bake_id, attempt_no=attempt_no)
            return await self.bake_get(
                bake_id, attempt_no=attempt_no, task_limit=task_limit
            )

        return await self._write(operation(), timeout, f"cancelling bake {id_or_name}")

    async def bake_restart(
        self,
        id_or_name: str,
        *,
        attempt_no: int = -1,
        from_failed: bool = True,
        local_executor: bool = False,
        task_limit: int,
        timeout: float = DEFAULT_WRITE_TIMEOUT,
    ) -> BakeState:
        self._bounded(task_limit, "task_limit", MAX_TASK_LIMIT)
        self._bounded(timeout, "timeout", MAX_WRITE_TIMEOUT)

        async def operation() -> BakeState:
            bake_id = await self._resolve_bake(id_or_name)
            await self._batch.restart(
                bake_id,
                attempt_no=attempt_no,
                from_failed=from_failed,
                local_executor=local_executor,
            )
            return await self.bake_get(bake_id, attempt_no=-1, task_limit=task_limit)

        return await self._write(operation(), timeout, f"restarting bake {id_or_name}")

    async def _bake_state(
        self, bake: Bake, attempt_no: int, task_limit: int
    ) -> BakeState:
        attempt: Optional[Attempt]
        try:
            attempt = (
                await self._batch.storage.bake(id=bake.id)
                .attempt(number=attempt_no)
                .get()
            )
        except ResourceNotFound:
            attempt = None
        tasks: tuple[TaskState, ...] = ()
        tasks_truncated = False
        if attempt is not None:
            listed = []
            async for task in (
                self._batch.storage.bake(id=bake.id).attempt(id=attempt.id).list_tasks()
            ):
                listed.append(self._task_state(task))
                if len(listed) == task_limit + 1:
                    break
            tasks_truncated = len(listed) > task_limit
            tasks = tuple(listed[:task_limit])
        status = attempt.result if attempt else None
        return BakeState(
            bake.id,
            bake.name,
            bake.batch,
            tuple(bake.tags),
            bake.created_at,
            attempt.number if attempt else None,
            status,
            attempt.executor_id if attempt else None,
            tasks,
            tasks_truncated,
            status.value if status is not None and status.is_finished else None,
        )

    @staticmethod
    def _task_state(task: Task) -> TaskState:
        return TaskState(
            ".".join(task.yaml_id),
            task.raw_id,
            task.status,
            task.created_at,
            task.finished_at,
            task.outputs,
            task.state,
            task.status.value if task.status.is_finished else None,
        )

    async def _logs(
        self,
        source: LogSource,
        raw_id: Optional[str],
        timeout: float,
        max_chunks: int,
        max_bytes: int,
    ) -> LogResult:
        self._log_bounds(timeout, max_chunks, max_bytes)
        if raw_id is None:
            return LogResult(None, b"", 0, False)
        monitor = source.monitor(raw_id)
        deadline = monotonic() + timeout
        chunks = 0
        data = bytearray()
        truncated = False
        while chunks < max_chunks and len(data) < max_bytes:
            remaining = deadline - monotonic()
            if remaining <= 0:
                truncated = True
                break
            try:
                chunk = await asyncio.wait_for(monitor.__anext__(), remaining)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                truncated = True
                break
            chunks += 1
            room = max_bytes - len(data)
            data.extend(chunk[:room])
            if len(chunk) > room:
                truncated = True
                break
        else:
            truncated = True
        return LogResult(raw_id, bytes(data), chunks, truncated)
