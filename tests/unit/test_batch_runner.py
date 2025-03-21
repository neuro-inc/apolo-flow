import os
import pathlib
import pytest
import sys
import textwrap
from apolo_sdk import Client
from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncIterator, Callable, Mapping

from apolo_flow.batch_runner import (
    ImageRefNotUniqueError,
    build_graphs,
    check_image_refs_unique,
    check_local_deps,
    check_no_cycles,
    iter_flows,
    upload_image_data,
)
from apolo_flow.colored_topo_sorter import CycleError
from apolo_flow.config_loader import BatchLocalCL, ConfigLoader
from apolo_flow.context import EarlyBatchAction, RunningBatchFlow
from apolo_flow.expr import MultiError
from apolo_flow.parser import ConfigDir
from apolo_flow.storage.base import BakeImage, BakeMeta, Storage
from apolo_flow.storage.in_memory import InMemoryStorage


BatchClFactory = Callable[[str], AsyncContextManager[ConfigLoader]]


@pytest.fixture
async def batch_cl_factory(
    assets: pathlib.Path,
    client: Client,
) -> Callable[[str], AsyncContextManager[ConfigLoader]]:
    @asynccontextmanager
    async def _factory(subpath: str = "") -> AsyncIterator[ConfigLoader]:
        config_dir = ConfigDir(
            workspace=assets / subpath,
            config_dir=assets / subpath,
        )
        cl = BatchLocalCL(config_dir, client)
        yield cl
        await cl.close()

    return _factory


@pytest.fixture()
async def batch_storage() -> Storage:
    return InMemoryStorage()


async def test_iter_flows(batch_cl_factory: BatchClFactory) -> None:
    async with batch_cl_factory("early_graph") as cl:
        flow = await RunningBatchFlow.create(cl, "batch", "bake-id")
        prefix2flow = {prefix: flow async for prefix, flow in iter_flows(flow)}

        assert prefix2flow[()] == flow
        action_flow = prefix2flow[("second",)]
        assert isinstance(action_flow, EarlyBatchAction)
        assert action_flow._action == (await flow.get_action_early("second"))._action

        action_flow = prefix2flow[("third",)]
        assert isinstance(action_flow, EarlyBatchAction)
        assert action_flow._action == (await flow.get_action_early("third"))._action


async def test_check_no_cycles(batch_cl_factory: BatchClFactory) -> None:
    async with batch_cl_factory("") as cl:
        flow = await RunningBatchFlow.create(cl, "batch-cycle", "bake-id")
        with pytest.raises(CycleError):
            await check_no_cycles(flow)


async def test_check_cycles(batch_cl_factory: BatchClFactory) -> None:
    async with batch_cl_factory("") as cl:
        flow = await RunningBatchFlow.create(cl, "batch-cycle", "bake-id")
        with pytest.raises(CycleError):
            await check_no_cycles(flow)


async def test_local_deps_on_remote_1(batch_cl_factory: BatchClFactory) -> None:
    async with batch_cl_factory("local_actions") as cl:
        flow = await RunningBatchFlow.create(cl, "bad-order", "bake-id")
        with pytest.raises(
            Exception, match=r"Local action 'local' depends on remote task 'remote'"
        ):
            await check_local_deps(flow)


async def test_local_deps_on_remote_2(batch_cl_factory: BatchClFactory) -> None:
    async with batch_cl_factory("local_actions") as cl:
        flow = await RunningBatchFlow.create(cl, "bad-order-through-action", "bake-id")
        with pytest.raises(
            Exception,
            match=r"Local action 'local' depends on "
            r"remote task 'call_action.remote_task'",
        ):
            await check_local_deps(flow)


async def test_graphs(batch_cl_factory: BatchClFactory) -> None:
    async with batch_cl_factory("") as cl:
        flow = await RunningBatchFlow.create(cl, "batch-action-call", "bake-id")
        graphs = await build_graphs(flow)
        assert graphs == {
            (): {("test",): set()},
            ("test",): {
                ("test", "task_1"): set(),
                ("test", "task_2"): {("test", "task_1")},
            },
        }


async def test_early_graph(batch_cl_factory: BatchClFactory) -> None:
    async with batch_cl_factory("early_graph") as cl:
        flow = await RunningBatchFlow.create(cl, "batch", "bake-id")
        graphs = await build_graphs(flow)
        assert graphs == {
            (): {
                ("first_ac",): set(),
                ("second",): {("first_ac",)},
                ("third",): {("first_ac",)},
            },
            ("first_ac",): {("first_ac", "task_2"): set()},
            ("second",): {
                ("second", "task-1-o3-t3"): set(),
                ("second", "task-1-o1-t1"): set(),
                ("second", "task-1-o2-t1"): set(),
                ("second", "task-1-o2-t2"): set(),
                ("second", "task_2"): {
                    ("second", "task-1-o3-t3"),
                    ("second", "task-1-o1-t1"),
                    ("second", "task-1-o2-t1"),
                    ("second", "task-1-o2-t2"),
                },
            },
            ("third",): {
                ("third", "task-1-o3-t3"): set(),
                ("third", "task-1-o1-t1"): set(),
                ("third", "task-1-o2-t1"): set(),
                ("third", "task-1-o2-t2"): set(),
                ("third", "task_2"): {
                    ("third", "task-1-o3-t3"),
                    ("third", "task-1-o1-t1"),
                    ("third", "task-1-o2-t1"),
                    ("third", "task-1-o2-t2"),
                },
            },
        }


async def test_check_image_refs_unique(batch_cl_factory: BatchClFactory) -> None:
    async with batch_cl_factory("batch_images") as cl:
        flow = await RunningBatchFlow.create(cl, "duplicate_ref", "bake-id")
        with pytest.raises(MultiError) as err_info:
            await check_image_refs_unique(flow)
    err = err_info.value
    assert isinstance(err, MultiError)
    assert len(err.errors) == 1
    inner_err = err.errors[0]

    assert isinstance(inner_err, ImageRefNotUniqueError)
    ws = cl.workspace
    assert str(inner_err) == textwrap.dedent(
        f"""\
        Image with ref 'image:banana1' defined multiple times with different attributes:
        at "{ws / "duplicate_ref.yml"}", line 4, column 5 with params:
          context: {ws / "dir"}
          dockerfile: {ws / "dir/Dockerfile_differ"}
        at "{ws / "subdir/action.yml"}", line 10, column 5 with params:
          context: {ws / "subdir"}
          dockerfile: {ws / "subdir/Dockerfile"}
    """.rstrip()
    )


async def test_check_image_refs_unique_same_defs(
    batch_cl_factory: BatchClFactory,
) -> None:
    async with batch_cl_factory("batch_images") as cl:
        flow = await RunningBatchFlow.create(cl, "duplicate_ref_same", "bake-id")
        # Should not raise an exception
        await check_image_refs_unique(flow)


async def test_upload_image_data(
    batch_cl_factory: BatchClFactory,
    batch_storage: Storage,
    assets: pathlib.Path,
) -> None:
    async with batch_cl_factory("batch_images") as cl:
        flow = await RunningBatchFlow.create(cl, "batch", "bake-id")
        project = await batch_storage.get_or_create_project(
            "test", "test", "test", "test"
        )
        project_storage = batch_storage.project(id=project.id)
        bake = await project_storage.create_bake(
            batch="batch",
            params=None,
            name=None,
            graphs={},
            tags=[],
            meta=BakeMeta(None),
        )
        bake_storage = project_storage.bake(id=bake.id)

        runs = []

        async def _fake_run_cli(*args: str) -> None:
            runs.append(args)

        await upload_image_data(flow, _fake_run_cli, bake_storage)

        ref2img: Mapping[str, BakeImage] = {
            image.ref: image async for image in bake_storage.list_bake_images()
        }
        assert set(ref2img.keys()).issuperset(
            {
                "image:main",
                "image:banana1",
                "image:banana2",
            }
        )
        for ref in {"image:main", "image:banana1"}:
            img = ref2img[ref]
            assert img.context_on_storage
            assert img.dockerfile_rel == "Dockerfile"
            assert any(
                run == ("mkdir", "--parents", str(img.context_on_storage))
                for run in runs
            )
            assert any(
                run
                == (
                    "cp",
                    "--recursive",
                    "--update",
                    "--no-target-directory",
                    (
                        str(assets / "batch_images/dir")
                        if ref == "image:main"
                        else str(assets / "batch_images/subdir")
                    ),
                    str(img.context_on_storage),
                )
                for run in runs
            )


@pytest.mark.xfail(
    condition=sys.platform == "win32" or "GITHUB_ACTOR" in os.environ,
    reason="ssh-agent config action does not properly work on Windows runners, \n"
    "TODO: setup ssh private key for fetching from external github repo",
)
async def test_check_image_refs_unique_gh(
    batch_cl_factory: BatchClFactory,
) -> None:
    async with batch_cl_factory("batch_images/gh") as cl:
        flow = await RunningBatchFlow.create(
            cl, "same-img-reff-same-action-version", "bake-id"
        )
        # Should not raise an exception
        await check_image_refs_unique(flow)

        flow = await RunningBatchFlow.create(
            cl, "same-img-reff-diff-action-version", "bake-id"
        )
        # Should not raise an exception
        await check_image_refs_unique(flow)

        flow = await RunningBatchFlow.create(
            cl, "same-img-reff-diff-image-dockerfile", "bake-id"
        )
        # Should raise an exception
        with pytest.raises(MultiError):
            await check_image_refs_unique(flow)
