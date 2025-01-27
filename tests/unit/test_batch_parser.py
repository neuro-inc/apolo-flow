import pathlib
import pytest
from yaml.constructor import ConstructorError

from apolo_flow import ast
from apolo_flow.ast import NeedsLevel
from apolo_flow.expr import (
    EnableExpr,
    IdExpr,
    ImageRefStrExpr,
    MappingItemsExpr,
    OptBashExpr,
    OptBoolExpr,
    OptIdExpr,
    OptImageRefStrExpr,
    OptIntExpr,
    OptLocalPathExpr,
    OptRemotePathExpr,
    OptRestartPolicyExpr,
    OptStrExpr,
    OptTimeDeltaExpr,
    PlatformResourceURIExpr,
    PrimitiveExpr,
    RemotePathExpr,
    SequenceItemsExpr,
    SimpleOptIdExpr,
    SimpleOptStrExpr,
    StrExpr,
)
from apolo_flow.parser import parse_batch
from apolo_flow.tokenizer import Pos


def test_parse_minimal(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-minimal.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(61, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            "Global title",
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params=None,
        images={
            "image_a": ast.Image(
                _start=Pos(4, 4, config_file),
                _end=Pos(16, 0, config_file),
                ref=ImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "image:banana"
                ),
                context=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "dir"
                ),
                dockerfile=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "dir/Dockerfile"
                ),
                build_args=SequenceItemsExpr(
                    [
                        StrExpr(
                            Pos(0, 0, config_file), Pos(0, 0, config_file), "--arg1"
                        ),
                        StrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "val1"),
                        StrExpr(
                            Pos(0, 0, config_file),
                            Pos(0, 0, config_file),
                            "--arg2=val2",
                        ),
                    ]
                ),
                env=None,
                volumes=None,
                build_preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                force_rebuild=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), True
                ),
                extra_kaniko_args=OptStrExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "--reproducible --cache-ttl=1h --single-snapshot",
                ),
            )
        },
        volumes={
            "volume_a": ast.Volume(
                _start=Pos(18, 4, config_file),
                _end=Pos(22, 2, config_file),
                remote=PlatformResourceURIExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "storage:dir"
                ),
                mount=RemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "/var/dir"
                ),
                local=OptLocalPathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "dir"
                ),
                read_only=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), True
                ),
            ),
            "volume_b": ast.Volume(
                _start=Pos(23, 4, config_file),
                _end=Pos(25, 0, config_file),
                remote=PlatformResourceURIExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "storage:other"
                ),
                mount=RemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "/var/other"
                ),
                local=OptLocalPathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                read_only=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
        },
        defaults=ast.BatchFlowDefaults(
            _start=Pos(26, 2, config_file),
            _end=Pos(38, 0, config_file),
            _specified_fields={
                "env",
                "fail_fast",
                "volumes",
                "life_span",
                "schedule_timeout",
                "max_parallel",
                "preset",
                "workdir",
                "tags",
            },
            tags=SequenceItemsExpr(
                [
                    StrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "tag-a"),
                    StrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "tag-b"),
                ]
            ),
            env=MappingItemsExpr(
                {
                    "global_a": StrExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), "val-a"
                    ),
                    "global_b": StrExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), "val-b"
                    ),
                }
            ),
            volumes=SequenceItemsExpr(
                [
                    OptStrExpr(
                        Pos(0, 0, config_file),
                        Pos(0, 0, config_file),
                        "storage:common:/mnt/common:rw",
                    ),
                ]
            ),
            workdir=OptRemotePathExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), "/global/dir"
            ),
            life_span=OptTimeDeltaExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), "1d4h"
            ),
            preset=OptStrExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-large"
            ),
            schedule_timeout=OptTimeDeltaExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), "5d4h3m2s"
            ),
            fail_fast=OptBoolExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), True),
            max_parallel=OptIntExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), 10),
            cache=None,
        ),
        mixins=None,
        tasks=[
            ast.Task(
                _start=Pos(39, 4, config_file),
                _end=Pos(61, 0, config_file),
                _specified_fields={
                    "life_span",
                    "http_auth",
                    "entrypoint",
                    "title",
                    "cmd",
                    "schedule_timeout",
                    "workdir",
                    "env",
                    "tags",
                    "name",
                    "preset",
                    "image",
                    "http_port",
                    "pass_config",
                    "id",
                    "volumes",
                },
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "test_a"),
                title=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "Batch title"
                ),
                needs=None,
                name=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "job-name"
                ),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ images.image_a.ref }}",
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "1d1s"
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "bash"
                ),
                cmd=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "/local/dir"
                ),
                env=MappingItemsExpr(
                    {
                        "local_a": StrExpr(
                            Pos(0, 0, config_file), Pos(0, 0, config_file), "val-1"
                        ),
                        "local_b": StrExpr(
                            Pos(0, 0, config_file), Pos(0, 0, config_file), "val-2"
                        ),
                    }
                ),
                volumes=SequenceItemsExpr(
                    [
                        OptStrExpr(
                            Pos(0, 0, config_file),
                            Pos(0, 0, config_file),
                            "${{ volumes.volume_a.ref }}",
                        ),
                        OptStrExpr(
                            Pos(0, 0, config_file),
                            Pos(0, 0, config_file),
                            "storage:dir:/var/dir:ro",
                        ),
                        OptStrExpr(
                            Pos(0, 0, config_file),
                            Pos(0, 0, config_file),
                            "",
                        ),
                        OptStrExpr(
                            Pos(0, 0, config_file),
                            Pos(0, 0, config_file),
                            None,
                        ),
                    ]
                ),
                tags=SequenceItemsExpr(
                    [
                        StrExpr(
                            Pos(0, 0, config_file), Pos(0, 0, config_file), "tag-1"
                        ),
                        StrExpr(
                            Pos(0, 0, config_file), Pos(0, 0, config_file), "tag-2"
                        ),
                    ]
                ),
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "2h55m"
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), 8080
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), False
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), True
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            )
        ],
    )


def test_parse_seq(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-seq.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(9, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params=None,
        images=None,
        volumes=None,
        defaults=None,
        mixins=None,
        tasks=[
            ast.Task(
                _start=Pos(2, 4, config_file),
                _end=Pos(6, 2, config_file),
                _specified_fields={"preset", "cmd", "image"},
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
            ast.Task(
                _start=Pos(6, 4, config_file),
                _end=Pos(9, 0, config_file),
                _specified_fields={"preset", "cmd", "image"},
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo def"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
        ],
    )


def test_parse_needs(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-needs.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(11, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params=None,
        images=None,
        volumes=None,
        defaults=None,
        mixins=None,
        tasks=[
            ast.Task(
                _start=Pos(2, 4, config_file),
                _end=Pos(7, 2, config_file),
                _specified_fields={"cmd", "image", "id", "preset"},
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "task_a"),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
            ast.Task(
                _start=Pos(7, 4, config_file),
                _end=Pos(11, 0, config_file),
                _specified_fields={"needs", "image", "cmd", "preset"},
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs={
                    IdExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), "task_a"
                    ): NeedsLevel.COMPLETED
                },
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo def"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
        ],
    )


def test_parse_needs_dict(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-needs-dict.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(12, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params=None,
        images=None,
        volumes=None,
        defaults=None,
        mixins=None,
        tasks=[
            ast.Task(
                _start=Pos(2, 4, config_file),
                _end=Pos(7, 2, config_file),
                _specified_fields={"preset", "image", "cmd", "id"},
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "task_a"),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
            ast.Task(
                _start=Pos(7, 4, config_file),
                _end=Pos(12, 0, config_file),
                _specified_fields={"preset", "image", "cmd", "needs"},
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs={
                    IdExpr(
                        Pos(0, 0, config_file),
                        Pos(0, 0, config_file),
                        "${{ 'task_a' }}",
                    ): NeedsLevel.RUNNING
                },
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo def"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
        ],
    )


def test_parse_matrix(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-matrix.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(14, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params=None,
        images=None,
        volumes=None,
        defaults=None,
        mixins=None,
        tasks=[
            ast.Task(
                _start=Pos(2, 4, config_file),
                _end=Pos(14, 0, config_file),
                _specified_fields={"strategy", "image", "cmd"},
                mixins=None,
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                strategy=ast.Strategy(
                    _start=Pos(3, 6, config_file),
                    _end=Pos(12, 4, config_file),
                    matrix=ast.Matrix(
                        _start=Pos(4, 8, config_file),
                        _end=Pos(12, 4, config_file),
                        products={
                            "one": SequenceItemsExpr(
                                [
                                    PrimitiveExpr(
                                        Pos(0, 0, config_file),
                                        Pos(0, 0, config_file),
                                        "o1",
                                    ),
                                    PrimitiveExpr(
                                        Pos(0, 0, config_file),
                                        Pos(0, 0, config_file),
                                        "o2",
                                    ),
                                ]
                            ),
                            "two": SequenceItemsExpr(
                                [
                                    PrimitiveExpr(
                                        Pos(0, 0, config_file),
                                        Pos(0, 0, config_file),
                                        "t1",
                                    ),
                                    PrimitiveExpr(
                                        Pos(0, 0, config_file),
                                        Pos(0, 0, config_file),
                                        "t2",
                                    ),
                                ]
                            ),
                        },
                        exclude=[
                            {
                                "one": PrimitiveExpr(
                                    Pos(0, 0, config_file), Pos(0, 0, config_file), "o1"
                                ),
                                "two": PrimitiveExpr(
                                    Pos(0, 0, config_file), Pos(0, 0, config_file), "t2"
                                ),
                            }
                        ],
                        include=[
                            {
                                "one": PrimitiveExpr(
                                    Pos(0, 0, config_file), Pos(0, 0, config_file), "o3"
                                ),
                                "two": PrimitiveExpr(
                                    Pos(0, 0, config_file), Pos(0, 0, config_file), "t3"
                                ),
                            }
                        ],
                    ),
                    fail_fast=OptBoolExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), None
                    ),
                    max_parallel=OptIntExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), None
                    ),
                ),
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            )
        ],
    )


def test_parse_matrix_with_strategy(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-matrix-with-strategy.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(28, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params=None,
        images=None,
        volumes=None,
        defaults=ast.BatchFlowDefaults(
            Pos(2, 2, config_file),
            Pos(7, 0, config_file),
            _specified_fields={"fail_fast", "cache", "max_parallel"},
            tags=None,
            env=None,
            volumes=None,
            workdir=OptRemotePathExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), None
            ),
            life_span=OptTimeDeltaExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), None
            ),
            preset=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
            schedule_timeout=OptTimeDeltaExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), None
            ),
            fail_fast=OptBoolExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), True),
            max_parallel=OptIntExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), 15),
            cache=ast.Cache(
                Pos(5, 4, config_file),
                Pos(7, 0, config_file),
                strategy=ast.CacheStrategy.NONE,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "2h30m"
                ),
            ),
        ),
        mixins=None,
        tasks=[
            ast.Task(
                _start=Pos(8, 4, config_file),
                _end=Pos(25, 2, config_file),
                _specified_fields={"image", "strategy", "cmd", "cache"},
                mixins=None,
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                strategy=ast.Strategy(
                    Pos(9, 6, config_file),
                    Pos(20, 4, config_file),
                    matrix=ast.Matrix(
                        Pos(10, 8, config_file),
                        Pos(18, 6, config_file),
                        products={
                            "one": SequenceItemsExpr(
                                [
                                    PrimitiveExpr(
                                        Pos(0, 0, config_file),
                                        Pos(0, 0, config_file),
                                        "o1",
                                    ),
                                    PrimitiveExpr(
                                        Pos(0, 0, config_file),
                                        Pos(0, 0, config_file),
                                        "o2",
                                    ),
                                ]
                            ),
                            "two": SequenceItemsExpr(
                                [
                                    PrimitiveExpr(
                                        Pos(0, 0, config_file),
                                        Pos(0, 0, config_file),
                                        "t1",
                                    ),
                                    PrimitiveExpr(
                                        Pos(0, 0, config_file),
                                        Pos(0, 0, config_file),
                                        "t2",
                                    ),
                                ]
                            ),
                        },
                        exclude=[
                            {
                                "one": PrimitiveExpr(
                                    Pos(0, 0, config_file), Pos(0, 0, config_file), "o1"
                                ),
                                "two": PrimitiveExpr(
                                    Pos(0, 0, config_file), Pos(0, 0, config_file), "t2"
                                ),
                            }
                        ],
                        include=[
                            {
                                "one": PrimitiveExpr(
                                    Pos(0, 0, config_file), Pos(0, 0, config_file), "o3"
                                ),
                                "two": PrimitiveExpr(
                                    Pos(0, 0, config_file), Pos(0, 0, config_file), "t3"
                                ),
                            }
                        ],
                    ),
                    fail_fast=OptBoolExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), False
                    ),
                    max_parallel=OptIntExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), 5
                    ),
                ),
                cache=ast.Cache(
                    Pos(21, 6, config_file),
                    Pos(23, 4, config_file),
                    strategy=ast.CacheStrategy.DEFAULT,
                    life_span=OptTimeDeltaExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), "1h30m"
                    ),
                ),
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
            ast.Task(
                Pos(25, 4, config_file),
                Pos(28, 0, config_file),
                _specified_fields={"id", "image", "cmd"},
                mixins=None,
                id=OptIdExpr(
                    Pos(25, 8, config_file), Pos(25, 14, config_file), "simple"
                ),
                needs=None,
                strategy=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "${{ success() }}"
                ),
                cache=None,
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(26, 11, config_file), Pos(26, 17, config_file), "ubuntu"
                ),
                preset=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptStrExpr(
                    Pos(27, 9, config_file), Pos(27, 17, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
        ],
    )


def test_parse_args(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-params.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(13, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params={
            "arg1": ast.Param(
                _start=Pos(2, 8, config_file),
                _end=Pos(
                    2,
                    12,
                    config_file,
                ),
                default=OptStrExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "val1",
                ),
                descr=OptStrExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    None,
                ),
            ),
            "arg2": ast.Param(
                _start=Pos(
                    4,
                    4,
                    config_file,
                ),
                _end=Pos(
                    6,
                    0,
                    config_file,
                ),
                default=OptStrExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "val2",
                ),
                descr=OptStrExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "descr2",
                ),
            ),
        },
        images=None,
        volumes=None,
        defaults=ast.BatchFlowDefaults(
            _start=Pos(7, 2, config_file),
            _end=Pos(10, 0, config_file),
            _specified_fields={"tags"},
            tags=SequenceItemsExpr(
                [
                    StrExpr(
                        Pos(0, 0, config_file),
                        Pos(0, 0, config_file),
                        "${{ params.arg1 }}",
                    ),
                    StrExpr(
                        Pos(0, 0, config_file),
                        Pos(0, 0, config_file),
                        "${{ params.arg2 }}",
                    ),
                ]
            ),
            env=None,
            volumes=None,
            workdir=OptRemotePathExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), None
            ),
            life_span=OptTimeDeltaExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), None
            ),
            preset=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
            schedule_timeout=OptTimeDeltaExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), None
            ),
            fail_fast=OptBoolExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
            max_parallel=OptIntExpr(
                Pos(0, 0, config_file), Pos(0, 0, config_file), None
            ),
            cache=None,
        ),
        mixins=None,
        tasks=[
            ast.Task(
                _start=Pos(
                    11,
                    4,
                    config_file,
                ),
                _end=Pos(
                    13,
                    0,
                    config_file,
                ),
                _specified_fields={"image", "cmd"},
                mixins=None,
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            )
        ],
    )


def test_parse_enable(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-enable.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(11, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params=None,
        images=None,
        volumes=None,
        defaults=None,
        mixins=None,
        tasks=[
            ast.Task(
                _start=Pos(2, 4, config_file),
                _end=Pos(6, 2, config_file),
                _specified_fields={"cmd", "id", "preset", "image"},
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "task_a"),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
            ast.Task(
                _start=Pos(6, 4, config_file),
                _end=Pos(11, 0, config_file),
                _specified_fields={"enable", "image", "needs", "cmd", "preset"},
                mixins=None,
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs={
                    IdExpr(
                        Pos(0, 0, config_file), Pos(0, 0, config_file), "task_a"
                    ): NeedsLevel.COMPLETED
                },
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "ubuntu"
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
        ],
    )


def test_parse_mixin(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "batch-mixin.yml"
    flow = parse_batch(workspace, config_file)
    assert flow == ast.BatchFlow(
        Pos(0, 0, config_file),
        Pos(12, 0, config_file),
        id=SimpleOptIdExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        kind=ast.FlowKind.BATCH,
        title=SimpleOptStrExpr(
            Pos(0, 0, config_file),
            Pos(0, 0, config_file),
            None,
        ),
        life_span=OptTimeDeltaExpr(
            Pos(0, 0, config_file), Pos(0, 0, config_file), None
        ),
        params=None,
        images=None,
        volumes=None,
        defaults=None,
        mixins={
            "basic": ast.TaskMixin(
                Pos(3, 4, config_file),
                Pos(6, 0, config_file),
                _specified_fields={"image", "preset", "restart"},
                mixins=None,
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "ubuntu",
                ),
                preset=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "cpu-micro"
                ),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                needs=None,
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "on-failure"
                ),
            ),
        },
        tasks=[
            ast.Task(
                _start=Pos(7, 4, config_file),
                _end=Pos(10, 2, config_file),
                _specified_fields={"mixins", "cmd"},
                mixins=[
                    StrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "basic")
                ],
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                preset=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo abc"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
            ast.Task(
                _start=Pos(10, 4, config_file),
                _end=Pos(12, 0, config_file),
                _specified_fields={"mixins", "cmd"},
                mixins=[
                    StrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), "basic")
                ],
                id=OptIdExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                title=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                needs=None,
                name=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                image=OptImageRefStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                preset=OptStrExpr(Pos(0, 0, config_file), Pos(0, 0, config_file), None),
                schedule_timeout=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                entrypoint=OptStrExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                cmd=OptBashExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), "echo def"
                ),
                workdir=OptRemotePathExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                env=None,
                volumes=None,
                tags=None,
                life_span=OptTimeDeltaExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_port=OptIntExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                http_auth=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                pass_config=OptBoolExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
                strategy=None,
                cache=None,
                enable=EnableExpr(
                    Pos(0, 0, config_file),
                    Pos(0, 0, config_file),
                    "${{ success() }}",
                ),
                restart=OptRestartPolicyExpr(
                    Pos(0, 0, config_file), Pos(0, 0, config_file), None
                ),
            ),
        ],
    )


def test_batch_job_extra_attrs(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "bad-batch-task-extra-attrs.yml"
    with pytest.raises(ConstructorError):
        parse_batch(workspace, config_file)


def test_batch_action_call_extra_attrs(assets: pathlib.Path) -> None:
    workspace = assets
    config_file = workspace / "bad-batch-action-call-extra-attrs.yml"
    with pytest.raises(ConstructorError):
        parse_batch(workspace, config_file)
