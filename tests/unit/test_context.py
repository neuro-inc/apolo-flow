import pathlib
import pytest
from neuromation.api import JobStatus
from textwrap import dedent
from yarl import URL

from neuro_flow.context import BatchContext, DepCtx, LiveContext, NotAvailable
from neuro_flow.expr import EvalError
from neuro_flow.parser import parse_batch, parse_live
from neuro_flow.types import LocalPath, RemotePath


def test_inavailable_context_ctor() -> None:
    err = NotAvailable("job")
    assert err.args == ("Context job is not available",)
    assert str(err) == "Context job is not available"


async def test_ctx_flow(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-minimal.yml"
    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    assert ctx.flow.id == "live-minimal"
    assert ctx.flow.workspace == workspace
    assert ctx.flow.title == "live-minimal"


async def test_env_defaults(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-full.yml"
    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    assert ctx.env == {"global_a": "val-a", "global_b": "val-b"}


async def test_env_from_job(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-full.yml"
    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    ctx = await ctx.with_meta("test_a")
    ctx2 = await ctx.with_job("test_a")
    assert ctx2.env == {
        "global_a": "val-a",
        "global_b": "val-b",
        "local_a": "val-1",
        "local_b": "val-2",
    }


async def test_volumes(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-full.yml"
    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    assert ctx.volumes.keys() == {"volume_a", "volume_b"}

    assert ctx.volumes["volume_a"].id == "volume_a"
    assert ctx.volumes["volume_a"].remote == URL("storage:dir")
    assert ctx.volumes["volume_a"].mount == RemotePath("/var/dir")
    assert ctx.volumes["volume_a"].read_only
    assert ctx.volumes["volume_a"].local == LocalPath("dir")
    assert ctx.volumes["volume_a"].full_local_path == workspace / "dir"
    assert ctx.volumes["volume_a"].ref_ro == "storage:dir:/var/dir:ro"
    assert ctx.volumes["volume_a"].ref_rw == "storage:dir:/var/dir:rw"
    assert ctx.volumes["volume_a"].ref == "storage:dir:/var/dir:ro"

    assert ctx.volumes["volume_b"].id == "volume_b"
    assert ctx.volumes["volume_b"].remote == URL("storage:other")
    assert ctx.volumes["volume_b"].mount == RemotePath("/var/other")
    assert not ctx.volumes["volume_b"].read_only
    assert ctx.volumes["volume_b"].local is None
    assert ctx.volumes["volume_b"].full_local_path is None
    assert ctx.volumes["volume_b"].ref_ro == "storage:other:/var/other:ro"
    assert ctx.volumes["volume_b"].ref_rw == "storage:other:/var/other:rw"
    assert ctx.volumes["volume_b"].ref == "storage:other:/var/other:rw"


async def test_images(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-full.yml"
    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    assert ctx.images.keys() == {"image_a"}

    assert ctx.images["image_a"].id == "image_a"
    assert ctx.images["image_a"].ref == "image:banana"
    assert ctx.images["image_a"].context == LocalPath("dir")
    assert ctx.images["image_a"].full_context_path == workspace / "dir"
    assert ctx.images["image_a"].dockerfile == LocalPath("dir/Dockerfile")
    assert ctx.images["image_a"].full_dockerfile_path == workspace / "dir/Dockerfile"
    assert ctx.images["image_a"].build_args == ["--arg1", "val1", "--arg2=val2"]


async def test_defaults(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-full.yml"
    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    assert ctx.defaults.tags == {"tag-a", "tag-b", "flow:live-full"}
    assert ctx.defaults.workdir == RemotePath("/global/dir")
    assert ctx.defaults.life_span == 100800.0
    assert ctx.defaults.preset == "cpu-large"


async def test_job_root_ctx(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-full.yml"
    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    with pytest.raises(NotAvailable):
        ctx.job


async def test_job(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-full.yml"
    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    ctx = await ctx.with_meta("test_a")

    ctx2 = await ctx.with_job("test_a")
    assert ctx2.job.id == "test_a"
    assert ctx2.job.title == "Job title"
    assert ctx2.job.name == "job-name"
    assert ctx2.job.image == "image:banana"
    assert ctx2.job.preset == "cpu-small"
    assert ctx2.job.http_port == 8080
    assert not ctx2.job.http_auth
    assert ctx2.job.entrypoint == "bash"
    assert ctx2.job.cmd == "echo abc"
    assert ctx2.job.workdir == RemotePath("/local/dir")
    assert ctx2.job.volumes == ["storage:dir:/var/dir:ro", "storage:dir:/var/dir:ro"]
    assert ctx2.job.tags == {
        "tag-1",
        "tag-2",
        "tag-a",
        "tag-b",
        "flow:live-full",
        "job:test-a",
    }
    assert ctx2.job.life_span == 10500.0
    assert ctx2.job.port_forward == ["2211:22"]
    assert ctx2.job.detach
    assert ctx2.job.browse


async def test_bad_expr_type_after_eval(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "live-bad-expr-type-after-eval.yml"

    flow = parse_live(workspace, config_file, id=config_file.stem)
    ctx = await LiveContext.create(flow)
    ctx = await ctx.with_meta("test")

    with pytest.raises(EvalError) as cm:
        await ctx.with_job("test")
    assert str(cm.value) == dedent(
        """\
        'abc def' is not an integer
          in line 5, column 19"""
    )


async def test_pipline_root_ctx(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-minimal.yml"
    flow = parse_batch(workspace, config_file)
    ctx = await BatchContext.create(flow)
    with pytest.raises(NotAvailable):
        ctx.task


async def test_pipeline_minimal_ctx(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-minimal.yml"
    flow = parse_batch(workspace, config_file)
    ctx = await BatchContext.create(flow)

    ctx2 = await ctx.with_task("test_a", needs={})
    assert ctx2.task.id == "test_a"
    assert ctx2.task.real_id == "test_a"
    assert ctx2.task.needs == set()
    assert ctx2.task.title == "Batch title"
    assert ctx2.task.name == "job-name"
    assert ctx2.task.image == "image:banana"
    assert ctx2.task.preset == "cpu-small"
    assert ctx2.task.http_port == 8080
    assert not ctx2.task.http_auth
    assert ctx2.task.entrypoint == "bash"
    assert ctx2.task.cmd == "echo abc"
    assert ctx2.task.workdir == RemotePath("/local/dir")
    assert ctx2.task.volumes == ["storage:dir:/var/dir:ro", "storage:dir:/var/dir:ro"]
    assert ctx2.task.tags == {"tag-1", "tag-2", "tag-a", "tag-b", "flow:batch-minimal"}
    assert ctx2.task.life_span == 10500.0

    assert ctx.graph == {"test_a": set()}
    assert ctx2.matrix == {}
    assert ctx2.strategy.max_parallel == 10
    assert not ctx2.strategy.fail_fast


async def test_pipeline_seq(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-seq.yml"
    flow = parse_batch(workspace, config_file)
    ctx = await BatchContext.create(flow)

    ctx2 = await ctx.with_task(
        "task-2", needs={"task-1": DepCtx(JobStatus.SUCCEEDED, {})}
    )
    assert ctx2.task.id is None
    assert ctx2.task.real_id == "task-2"
    assert ctx2.task.needs == {"task-1"}
    assert ctx2.task.title is None
    assert ctx2.task.name is None
    assert ctx2.task.image == "ubuntu"
    assert ctx2.task.preset == "cpu-small"
    assert ctx2.task.http_port is None
    assert not ctx2.task.http_auth
    assert ctx2.task.entrypoint is None
    assert ctx2.task.cmd == "bash -euxo pipefail -c 'echo def'"
    assert ctx2.task.workdir is None
    assert ctx2.task.volumes == []
    assert ctx2.task.tags == {"flow:batch-seq", "task:task-2"}
    assert ctx2.task.life_span is None

    assert ctx.graph == {"task-2": {"task-1"}, "task-1": set()}
    assert ctx2.matrix == {}
    assert ctx2.strategy.max_parallel == 10
    assert not ctx2.strategy.fail_fast


async def test_pipeline_needs(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-needs.yml"
    flow = parse_batch(workspace, config_file)
    ctx = await BatchContext.create(flow)

    ctx2 = await ctx.with_task(
        "task-2", needs={"task_a": DepCtx(JobStatus.SUCCEEDED, {})}
    )
    assert ctx2.task.id is None
    assert ctx2.task.real_id == "task-2"
    assert ctx2.task.needs == {"task_a"}
    assert ctx2.task.title is None
    assert ctx2.task.name is None
    assert ctx2.task.image == "ubuntu"
    assert ctx2.task.preset == "cpu-small"
    assert ctx2.task.http_port is None
    assert not ctx2.task.http_auth
    assert ctx2.task.entrypoint is None
    assert ctx2.task.cmd == "bash -euxo pipefail -c 'echo def'"
    assert ctx2.task.workdir is None
    assert ctx2.task.volumes == []
    assert ctx2.task.tags == {"flow:batch-needs", "task:task-2"}
    assert ctx2.task.life_span is None

    assert ctx.graph == {"task-2": {"task_a"}, "task_a": set()}
    assert ctx2.matrix == {}
    assert ctx2.strategy.max_parallel == 10
    assert not ctx2.strategy.fail_fast


async def test_pipeline_matrix(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-matrix.yml"
    flow = parse_batch(workspace, config_file)
    ctx = await BatchContext.create(flow)

    assert ctx.graph == {
        "task-1-e3-o3-t3": set(),
        "task-1-o1-t1": set(),
        "task-1-o2-t1": set(),
        "task-1-o2-t2": set(),
    }

    ctx2 = await ctx.with_task("task-1-o2-t2", needs={})
    assert ctx2.task.id is None
    assert ctx2.task.real_id == "task-1-o2-t2"
    assert ctx2.task.needs == set()
    assert ctx2.task.title is None
    assert ctx2.task.name is None
    assert ctx2.task.image == "ubuntu"
    assert ctx2.task.preset is None
    assert ctx2.task.http_port is None
    assert not ctx2.task.http_auth
    assert ctx2.task.entrypoint is None
    assert ctx2.task.cmd == "echo abc"
    assert ctx2.task.workdir is None
    assert ctx2.task.volumes == []
    assert ctx2.task.tags == {"flow:batch-matrix", "task:task-1-o2-t2"}
    assert ctx2.task.life_span is None

    assert ctx2.matrix == {"one": "o2", "two": "t2"}
    assert ctx2.strategy.max_parallel == 10
    assert not ctx2.strategy.fail_fast


async def test_pipeline_matrix_with_strategy(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-matrix-with-strategy.yml"
    flow = parse_batch(workspace, config_file)
    ctx = await BatchContext.create(flow)

    assert ctx.graph == {
        "task-1-e3-o3-t3": set(),
        "task-1-o1-t1": set(),
        "task-1-o2-t1": set(),
        "task-1-o2-t2": set(),
    }

    ctx2 = await ctx.with_task("task-1-e3-o3-t3", needs={})
    assert ctx2.task.id is None
    assert ctx2.task.real_id == "task-1-e3-o3-t3"
    assert ctx2.task.needs == set()
    assert ctx2.task.title is None
    assert ctx2.task.name is None
    assert ctx2.task.image == "ubuntu"
    assert ctx2.task.preset is None
    assert ctx2.task.http_port is None
    assert not ctx2.task.http_auth
    assert ctx2.task.entrypoint is None
    assert ctx2.task.cmd == "echo abc"
    assert ctx2.task.workdir is None
    assert ctx2.task.volumes == []
    assert ctx2.task.tags == {
        "flow:batch-matrix-with-strategy",
        "task:task-1-e3-o3-t3",
    }
    assert ctx2.task.life_span is None

    assert ctx2.matrix == {"extra": "e3", "one": "o3", "two": "t3"}
    assert ctx2.strategy.max_parallel == 5
    assert ctx2.strategy.fail_fast


async def test_pipeline_matrix_2(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-matrix-with-deps.yml"
    flow = parse_batch(workspace, config_file)
    ctx = await BatchContext.create(flow)

    assert ctx.graph == {
        "task-2-a-1": {"task_a"},
        "task-2-a-2": {"task_a"},
        "task-2-b-1": {"task_a"},
        "task-2-b-2": {"task_a"},
        "task-2-c-1": {"task_a"},
        "task-2-c-2": {"task_a"},
        "task_a": set(),
    }

    ctx2 = await ctx.with_task(
        "task-2-a-1", needs={"task_a": DepCtx(JobStatus.SUCCEEDED, {"name": "value"})}
    )
    assert ctx2.task.id is None
    assert ctx2.task.real_id == "task-2-a-1"
    assert ctx2.task.needs == {"task_a"}
    assert ctx2.task.title is None
    assert ctx2.task.name is None
    assert ctx2.task.image == "ubuntu"
    assert ctx2.task.preset == "cpu-small"
    assert ctx2.task.http_port is None
    assert not ctx2.task.http_auth
    assert ctx2.task.entrypoint is None
    assert ctx2.task.cmd == (
        """bash -euxo pipefail -c \'echo "Task B a 1"\necho value\n\'"""
    )
    assert ctx2.task.workdir is None
    assert ctx2.task.volumes == []
    assert ctx2.task.tags == {
        "flow:batch-matrix-with-deps",
        "task:task-2-a-1",
    }
    assert ctx2.task.life_span is None

    assert ctx2.matrix == {"arg1": "a", "arg2": "1"}


async def test_pipeline_args(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-args.yml"
    flow = parse_batch(workspace, config_file)
    ctx = await BatchContext.create(flow)

    assert ctx.args == {"arg1": "val1", "arg2": "val2"}
