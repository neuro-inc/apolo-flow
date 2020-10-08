from dataclasses import replace

import asyncio
import pytest
from datetime import datetime
from neuromation.api import (
    Client,
    Container,
    JobDescription,
    JobRestartPolicy,
    JobStatus,
    JobStatusHistory,
    RemoteImage,
    ResourceNotFound,
    Resources,
    get as api_get,
)
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    cast,
)
from unittest.mock import ANY
from yarl import URL

from neuro_flow.batch_executor import BatchExecutor, ExecutorData
from neuro_flow.batch_runner import BatchRunner
from neuro_flow.parser import ConfigDir
from neuro_flow.storage import Bake, BatchFSStorage, BatchStorage, LocalFS


MakeBatchRunner = Callable[[Path], Awaitable[BatchRunner]]


def make_descr(
    job_id: str,
    *,
    status: JobStatus = JobStatus.PENDING,
    tags: Iterable[str] = (),
    description: str = "",
    is_preemptible: bool = False,
    created_at: datetime = datetime.now(),
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
    exit_code: Optional[int] = None,
    restart_policy: JobRestartPolicy = JobRestartPolicy.NEVER,
    life_span: float = 3600,
    name: Optional[str] = None,
    container: Optional[Container] = None,
) -> JobDescription:
    if container is None:
        container = Container(RemoteImage("ubuntu"), Resources(100, 0.1))

    return JobDescription(
        id=job_id,
        owner="test-user",
        cluster_name="default",
        status=status,
        history=JobStatusHistory(
            status=status,
            reason="",
            description="",
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            exit_code=exit_code,
        ),
        container=container,
        is_preemptible=is_preemptible,
        uri=URL(f"job://default/test-user/{job_id}"),
        name=name,
        tags=sorted(
            list(set(tags) | {"project:test", "flow:batch-seq", f"task:{job_id}"})
        ),
        description=description,
        restart_policy=restart_policy,
        life_span=life_span,
    )


class JobsMock:
    # Mock for client.jobs subsystem

    _data: Dict[str, JobDescription]
    _outputs: Dict[str, bytes]

    def __init__(self) -> None:
        self.id_counter = 0
        self._data = {}
        self._outputs = {}

    def _make_next_id(self) -> int:
        self.id_counter += 1
        return self.id_counter

    # Method for controlling in tests

    async def _get_task(self, task_name: str) -> JobDescription:
        while True:
            for descr in self._data.values():
                if f"task:{task_name}" in descr.tags:
                    return descr
            await asyncio.sleep(0.01)

    async def get_task(self, task_name: str, timeout: float = 1) -> JobDescription:
        try:
            return await asyncio.wait_for(self._get_task(task_name), timeout=timeout)
        except asyncio.TimeoutError:
            raise AssertionError(
                f'Task "{task_name}" did not appeared in timeout of {timeout}'
            )

    async def mark_started(self, task_name: str) -> None:
        descr = await self.get_task(task_name)
        if descr.status == JobStatus.PENDING:
            descr = replace(descr, status=JobStatus.RUNNING)
            new_history = replace(
                descr.history, status=JobStatus.RUNNING, started_at=datetime.now()
            )
            descr = replace(descr, history=new_history)
            self._data[descr.id] = descr

    async def mark_done(self, task_name: str, output: bytes = b"") -> None:
        await self.mark_started(task_name)
        descr = await self.get_task(task_name)
        if descr.status == JobStatus.RUNNING:
            descr = replace(descr, status=JobStatus.SUCCEEDED)
            new_history = replace(
                descr.history,
                status=JobStatus.SUCCEEDED,
                finished_at=datetime.now(),
                exit_code=0,
            )
            descr = replace(descr, history=new_history)
            self._data[descr.id] = descr
        self._outputs[descr.id] = output

    async def mark_failed(self, task_name: str, output: bytes = b"") -> None:
        await self.mark_started(task_name)
        descr = await self.get_task(task_name)
        if descr.status == JobStatus.RUNNING:
            descr = replace(descr, status=JobStatus.FAILED)
            new_history = replace(
                descr.history,
                status=JobStatus.FAILED,
                finished_at=datetime.now(),
                exit_code=255,
            )
            descr = replace(descr, history=new_history)
            self._data[descr.id] = descr
        self._outputs[descr.id] = output

    # Fake Jobs methods

    async def run(
        self,
        container: Container,
        *,
        name: Optional[str] = None,
        tags: Sequence[str] = (),
        description: Optional[str] = None,
        is_preemptible: bool = False,
        schedule_timeout: Optional[float] = None,
        restart_policy: JobRestartPolicy = JobRestartPolicy.NEVER,
        life_span: Optional[float] = None,
    ) -> JobDescription:
        job_id = f"job-{self._make_next_id()}"
        self._data[job_id] = JobDescription(
            id=job_id,
            owner="test-user",
            cluster_name="default",
            status=JobStatus.PENDING,
            history=JobStatusHistory(
                status=JobStatus.PENDING,
                reason="",
                description="",
                created_at=datetime.now(),
            ),
            container=container,
            is_preemptible=is_preemptible,
            uri=URL(f"job://default/test-user/{job_id}"),
            name=name,
            tags=tags,
            description=description,
            restart_policy=restart_policy,
            life_span=life_span,
        )
        return self._data[job_id]

    async def kill(self, job_id: str) -> None:
        descr = self._data[job_id]
        descr = replace(descr, status=JobStatus.CANCELLED)
        new_history = replace(
            descr.history,
            status=JobStatus.CANCELLED,
            started_at=descr.history.started_at or datetime.now(),
            finished_at=datetime.now(),
            exit_code=0,
        )
        descr = replace(descr, history=new_history)
        self._data[descr.id] = descr

    async def status(self, job_id: str) -> JobDescription:
        try:
            return self._data[job_id]
        except KeyError:
            raise ResourceNotFound

    async def monitor(self, job_id: str) -> AsyncIterator[bytes]:
        yield self._outputs.get(job_id, b"")


@pytest.fixture()
def batch_storage(loop: None) -> Iterator[BatchStorage]:
    with TemporaryDirectory() as tmpdir:
        fs = LocalFS(Path(tmpdir))
        yield BatchFSStorage(fs)


@pytest.fixture()
async def make_batch_runner(
    batch_storage: BatchStorage,
) -> AsyncIterator[MakeBatchRunner]:

    runner: Optional[BatchRunner] = None

    async def create(path: Path) -> BatchRunner:
        config_dir = ConfigDir(
            workspace=path,
            config_dir=path,
        )
        nonlocal runner
        # BatchRunner should not use client in this case
        runner = BatchRunner(config_dir, cast(Client, None), batch_storage)
        await runner.__aenter__()
        return runner

    yield create

    if runner is not None:
        await runner.__aexit__(None, None, None)


@pytest.fixture()
async def batch_runner(
    make_batch_runner: MakeBatchRunner,
    assets: Path,
) -> BatchRunner:
    return await make_batch_runner(assets)


@pytest.fixture()
def jobs_mock() -> JobsMock:
    return JobsMock()


@pytest.fixture()
async def patched_client(
    api_config: Path, jobs_mock: JobsMock
) -> AsyncIterator[Client]:
    async with api_get(path=api_config) as client:
        client._jobs = jobs_mock
        yield client


@pytest.fixture()
def start_executor(
    batch_storage: BatchStorage, patched_client: Client
) -> Callable[[ExecutorData], Awaitable[None]]:
    async def start(data: ExecutorData) -> None:
        await BatchExecutor(
            data, patched_client, batch_storage, polling_timeout=0.01
        ).run()

    return start


@pytest.fixture()
def run_executor(
    make_batch_runner: MakeBatchRunner,
    start_executor: Callable[[ExecutorData], Awaitable[None]],
) -> Callable[[Path, str], Awaitable[None]]:
    async def run(config_loc: Path, batch_name: str) -> None:
        runner = await make_batch_runner(config_loc)
        data = await runner._setup_exc_data(batch_name)
        await start_executor(data)

    return run


def _executor_data_to_bake_id(data: ExecutorData) -> str:
    return Bake(
        project=data.project,
        batch=data.batch,
        when=data.when,
        suffix=data.suffix,
        graphs={},  # not needed for bake_id calculation
    ).bake_id


async def test_simple_batch_ok(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(run_executor(assets, "batch-seq"))
    task_descr = await jobs_mock.get_task("task-1")
    assert task_descr.container.image.name == "ubuntu"
    assert task_descr.container.command
    assert "echo abc" in task_descr.container.command
    await jobs_mock.mark_done("task-1")

    task_descr = await jobs_mock.get_task("task-2")
    assert task_descr.container.image.name == "ubuntu"
    assert task_descr.container.command
    assert "echo def" in task_descr.container.command
    await jobs_mock.mark_done("task-2")
    await executor_task


async def test_batch_with_action_ok(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(run_executor(assets, "batch-action-call"))
    await jobs_mock.get_task("test.task-1")
    await jobs_mock.mark_done(
        "test.task-1", "::set-output name=task1::Task 1 val 1".encode()
    )

    await jobs_mock.get_task("test.task-2")
    await jobs_mock.mark_done(
        "test.task-2", "::set-output name=task2::Task 2 value 2".encode()
    )
    await executor_task


@pytest.mark.parametrize(  # type: ignore
    "batch_name,vars",
    [
        ("batch-matrix-1", [("o1", "t1"), ("o1", "t2"), ("o2", "t1"), ("o2", "t2")]),
        ("batch-matrix-2", [("o1", "t2"), ("o2", "t1"), ("o2", "t2")]),
        (
            "batch-matrix-3",
            [("o1", "t1"), ("o1", "t2"), ("o2", "t1"), ("o2", "t2"), ("o3", "t3")],
        ),
        ("batch-matrix-4", [("o2", "t1"), ("o2", "t2"), ("o3", "t3")]),
    ],
)
async def test_batch_matrix(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
    batch_name: str,
    vars: List[Tuple[str, str]],
) -> None:
    executor_task = asyncio.ensure_future(run_executor(assets, batch_name))
    for var_1, var_2 in vars:
        descr = await jobs_mock.get_task(f"task-1-{var_1}-{var_2}")
        assert descr.container.command
        assert f"{var_1}-{var_2}" in descr.container.command
        await jobs_mock.mark_done(f"task-1-{var_1}-{var_2}")

    await executor_task


@pytest.mark.parametrize(  # type: ignore
    "batch_name,max_parallel,vars",
    [
        pytest.param(
            "batch-matrix-max-parallel",
            2,
            [("o1", "t1"), ("o1", "t2"), ("o2", "t1"), ("o2", "t2")],
            marks=pytest.mark.xfail(reason="Local max_parallel is broken"),
        ),
        (
            "batch-matrix-max-parallel-global",
            2,
            [("o1", "t1"), ("o1", "t2"), ("o2", "t1"), ("o2", "t2")],
        ),
    ],
)
async def test_batch_matrix_max_parallel(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
    batch_name: str,
    max_parallel: int,
    vars: List[Tuple[str, str]],
) -> None:
    executor_task = asyncio.ensure_future(run_executor(assets, batch_name))
    done, pending = await asyncio.wait(
        [jobs_mock.get_task(f"task-1-{var_1}-{var_2}") for var_1, var_2 in vars],
        return_when=asyncio.ALL_COMPLETED,
    )

    alive_cnt = sum(1 for task in done if task.exception() is None)
    assert alive_cnt == max_parallel
    executor_task.cancel()


async def test_enable_cancels_depending_tasks(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    await asyncio.wait_for(run_executor(assets, "batch-first-disabled"), timeout=1)


async def test_disabled_task_is_not_required(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(
        run_executor(assets, "batch-disabled-not-needed")
    )

    await jobs_mock.mark_done("task-1")
    await jobs_mock.mark_done("task-3")
    await jobs_mock.mark_done("task-4")

    await executor_task


async def test_cancellation(
    jobs_mock: JobsMock,
    batch_runner: BatchRunner,
    start_executor: Callable[[ExecutorData], Awaitable[None]],
) -> None:
    data = await batch_runner._setup_exc_data("batch-seq")
    executor_task = asyncio.ensure_future(start_executor(data))
    await jobs_mock.mark_done("task-1")
    descr = await jobs_mock.get_task("task-2")
    assert descr.status == JobStatus.PENDING

    await batch_runner.cancel(_executor_data_to_bake_id(data))
    await executor_task

    descr = await jobs_mock.get_task("task-1")
    assert descr.status == JobStatus.SUCCEEDED

    descr = await jobs_mock.get_task("task-2")
    assert descr.status == JobStatus.CANCELLED


async def test_volumes_parsing(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(run_executor(assets, "batch-volumes-parsing"))

    descr = await jobs_mock.get_task("task-1")

    storage_volume = descr.container.volumes[0]
    assert "folder" in storage_volume.storage_uri.path
    assert storage_volume.container_path == "/mnt/storage"
    assert not storage_volume.read_only

    disk_volume = descr.container.disk_volumes[0]
    assert "disk-name" in disk_volume.disk_uri.path
    assert disk_volume.container_path == "/mnt/disk"
    assert disk_volume.read_only

    secret_file = descr.container.secret_files[0]
    assert "key" in secret_file.secret_uri.path
    assert secret_file.container_path == "/mnt/secret"

    await jobs_mock.mark_done("task-1")
    await executor_task


async def test_graphs(
    batch_storage: BatchStorage,
    batch_runner: BatchRunner,
) -> None:
    data = await batch_runner._setup_exc_data("batch-action-call")
    bake = await batch_storage.fetch_bake(
        data.project, data.batch, data.when, data.suffix
    )
    assert bake.graphs == {
        (): {("test",): set()},
        ("test",): {
            ("test", "task_1"): set(),
            ("test", "task_2"): {("test", "task_1")},
        },
    }


async def test_always_after_disabled(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(
        run_executor(assets, "batch-disabled-but-always")
    )

    await jobs_mock.mark_done("task-2")

    await executor_task


async def test_always_during_cancellation(
    jobs_mock: JobsMock,
    batch_runner: BatchRunner,
    start_executor: Callable[[ExecutorData], Awaitable[None]],
) -> None:
    data = await batch_runner._setup_exc_data("batch-last-always")
    executor_task = asyncio.ensure_future(start_executor(data))
    descr = await jobs_mock.get_task("task-1")
    assert descr.status == JobStatus.PENDING

    await batch_runner.cancel(_executor_data_to_bake_id(data))

    await jobs_mock.mark_done("task-3")

    await executor_task


async def test_stateful_no_post(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(
        run_executor(assets / "stateful_actions", "call-no-post")
    )

    await jobs_mock.mark_done("first")
    await jobs_mock.mark_done("test")
    await jobs_mock.mark_done("last")

    await executor_task


async def test_stateful_with_post(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(
        run_executor(assets / "stateful_actions", "call-with-post")
    )

    await jobs_mock.mark_done("first")
    await jobs_mock.mark_done("test")
    await jobs_mock.mark_done("last")
    await jobs_mock.mark_done("post-test")

    await executor_task


async def test_stateful_with_state(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(
        run_executor(assets / "stateful_actions", "call-with-state")
    )

    await jobs_mock.mark_done("first")
    await jobs_mock.mark_done("test", "::save-state name=const::constant".encode())
    await jobs_mock.mark_done("last")
    await jobs_mock.mark_done("post-test")

    await executor_task


async def test_stateful_post_after_fail(
    jobs_mock: JobsMock,
    assets: Path,
    run_executor: Callable[[Path, str], Awaitable[None]],
) -> None:
    executor_task = asyncio.ensure_future(
        run_executor(assets / "stateful_actions", "call-with-post")
    )

    await jobs_mock.mark_done("first")
    await jobs_mock.mark_done("test")
    await jobs_mock.mark_failed("last")
    await jobs_mock.mark_done("post-test")

    await executor_task


async def test_stateful_post_after_cancellation(
    jobs_mock: JobsMock,
    assets: Path,
    make_batch_runner: MakeBatchRunner,
    start_executor: Callable[[ExecutorData], Awaitable[None]],
) -> None:
    runner = await make_batch_runner(assets / "stateful_actions")
    data = await runner._setup_exc_data("call-with-post")
    executor_task = asyncio.ensure_future(start_executor(data))
    await jobs_mock.mark_done("first")
    await jobs_mock.mark_done("test")

    await runner.cancel(_executor_data_to_bake_id(data))

    await jobs_mock.mark_done("post-test")

    await executor_task


async def test_restart(batch_storage: BatchStorage, batch_runner: BatchRunner) -> None:
    data = await batch_runner._setup_exc_data("batch-seq")
    bake = await batch_storage.fetch_bake(
        data.project, data.batch, data.when, data.suffix
    )
    attempt = await batch_storage.find_attempt(bake)
    job_1 = ("task-1",)
    job_2 = ("task-2",)
    st1 = await batch_storage.start_task(attempt, 1, job_1, make_descr("job:task-1"))
    ft1 = await batch_storage.finish_task(
        attempt,
        2,
        st1,
        make_descr(
            "job:task-1",
            status=JobStatus.SUCCEEDED,
            exit_code=0,
            started_at=datetime.now(),
            finished_at=datetime.now(),
        ),
        {},
        {},
    )
    st2 = await batch_storage.start_task(attempt, 1, job_2, make_descr("job:task-2"))
    await batch_storage.finish_task(
        attempt,
        2,
        st2,
        make_descr(
            "job:task-2",
            status=JobStatus.FAILED,
            exit_code=1,
            started_at=datetime.now(),
            finished_at=datetime.now(),
        ),
        {},
        {},
    )

    await batch_storage.finish_attempt(attempt, JobStatus.FAILED)

    data2 = await batch_runner._restart(bake.bake_id)
    assert data == data2

    attempt2 = await batch_storage.find_attempt(bake)
    assert attempt2.number == 2
    started, finished = await batch_storage.fetch_attempt(attempt2)
    assert list(started.keys()) == [job_1]
    assert list(finished.keys()) == [job_1]
    assert started[job_1] == replace(st1, attempt=attempt2, number=ANY)
    assert finished[job_1] == replace(ft1, attempt=attempt2, number=ANY)
