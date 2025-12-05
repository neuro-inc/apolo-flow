# Dataclasses
from dataclasses import dataclass, field

import enum
from collections.abc import Mapping, Sequence
from typing import AbstractSet, Optional

from .expr import (
    BaseExpr,
    EnableExpr,
    IdExpr,
    ImageRefStrExpr,
    MappingT,
    OptBoolExpr,
    OptIdExpr,
    OptIntExpr,
    OptLocalPathExpr,
    OptRemotePathExpr,
    OptRestartPolicyExpr,
    OptStrExpr,
    OptTimeDeltaExpr,
    PlatformResourceURIExpr,
    PrimitiveExpr,
    RemotePathExpr,
    SequenceT,
    SimpleIdExpr,
    SimpleOptBoolExpr,
    SimpleOptIdExpr,
    SimpleOptPrimitiveExpr,
    SimpleOptStrExpr,
    SimpleStrExpr,
    StrExpr,
)
from .tokenizer import Pos


@dataclass(frozen=True)
class Base:
    _start: Pos
    _end: Pos


@dataclass(frozen=True)
class WithSpecifiedFields(Base):
    _specified_fields: AbstractSet[str]


class CacheStrategy(enum.Enum):
    NONE = "none"
    DEFAULT = "default"
    INHERIT = "inherit"


@dataclass(frozen=True)
class Cache(Base):
    # 'default' for root BatchFlowDefaults,
    # 'inherit' for task definitions and actions
    strategy: CacheStrategy | None = field(metadata={"allow_none": True})
    life_span: OptTimeDeltaExpr
    # TODO: maybe add extra key->value mapping for additional cache keys later


@dataclass(frozen=True)
class Project(Base):
    id: SimpleIdExpr
    project_name: SimpleOptStrExpr  # project name can contain "-"
    owner: SimpleOptStrExpr  # user name can contain "-"
    role: SimpleOptStrExpr

    images: Mapping[str, "Image"] | None = field(metadata={"allow_none": True})
    volumes: Mapping[str, "Volume"] | None = field(metadata={"allow_none": True})
    defaults: Optional["BatchFlowDefaults"] = field(metadata={"allow_none": True})
    mixins: Mapping[str, "ExecUnitMixin"] | None = field(metadata={"allow_none": True})


# There are 'batch' for pipelined mode and 'live' for interactive one
# (while 'batches' are technically just non-interactive jobs.


class FlowKind(enum.Enum):
    LIVE = "live"  # interactive mode.
    BATCH = "batch"  # pipelined mode


@dataclass(frozen=True)
class Volume(Base):
    remote: PlatformResourceURIExpr  # remote URI, e.g. storage:folder/subfolder
    mount: RemotePathExpr  # mount path inside container
    local: OptLocalPathExpr
    read_only: OptBoolExpr  # True if mounted in read-only mode, False for read-write


@dataclass(frozen=True)
class Image(Base):
    ref: ImageRefStrExpr  # Image reference, e.g. image:my-proj or neuromation/base@v1.6
    context: OptStrExpr
    dockerfile: OptStrExpr
    build_args: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    env: BaseExpr[MappingT] | None = field(metadata={"allow_none": True})
    volumes: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    build_preset: OptStrExpr
    force_rebuild: OptBoolExpr
    extra_kaniko_args: OptStrExpr


@dataclass(frozen=True)
class ExecUnitMixin(WithSpecifiedFields, Base):
    title: OptStrExpr  # Autocalculated if not passed explicitly
    name: OptStrExpr
    image: OptStrExpr
    preset: OptStrExpr
    schedule_timeout: OptTimeDeltaExpr
    entrypoint: OptStrExpr
    cmd: OptStrExpr
    workdir: OptRemotePathExpr
    env: BaseExpr[MappingT] | None = field(metadata={"allow_none": True})
    volumes: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    tags: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    life_span: OptTimeDeltaExpr
    http_port: OptIntExpr
    http_auth: OptBoolExpr
    pass_config: OptBoolExpr
    mixins: Sequence[StrExpr] | None = field(metadata={"allow_none": True})
    restart: OptRestartPolicyExpr


@dataclass(frozen=True)
class ExecUnit(Base):
    title: OptStrExpr  # Autocalculated if not passed explicitly
    name: OptStrExpr
    image: OptStrExpr
    preset: OptStrExpr
    schedule_timeout: OptTimeDeltaExpr
    entrypoint: OptStrExpr
    cmd: OptStrExpr
    workdir: OptRemotePathExpr
    env: BaseExpr[MappingT] | None = field(metadata={"allow_none": True})
    volumes: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    tags: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    life_span: OptTimeDeltaExpr
    http_port: OptIntExpr
    http_auth: OptBoolExpr
    pass_config: OptBoolExpr
    restart: OptRestartPolicyExpr


@dataclass(frozen=True)
class Matrix(Base):
    # AST class is slightly different from YAML representation,
    # in YAML `products` mapping is embedded into the matrix itself.
    products: Mapping[str, BaseExpr[SequenceT]]
    exclude: Sequence[Mapping[str, PrimitiveExpr]]
    include: Sequence[Mapping[str, PrimitiveExpr]]


@dataclass(frozen=True)
class Strategy(Base):
    matrix: Matrix
    fail_fast: OptBoolExpr
    max_parallel: OptIntExpr


@dataclass(frozen=True)
class Param(Base):
    # Possible params in yaml:
    # params:
    #  name: ~
    #  name: value
    #  name:
    #    default: value
    #    descr: description
    default: OptStrExpr
    descr: OptStrExpr


@dataclass(frozen=True)
class JobBase(Base):
    params: Mapping[str, Param] | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class JobMixin(WithSpecifiedFields, Base):
    title: OptStrExpr  # Autocalculated if not passed explicitly
    name: OptStrExpr
    image: OptStrExpr
    preset: OptStrExpr
    schedule_timeout: OptTimeDeltaExpr
    entrypoint: OptStrExpr
    cmd: OptStrExpr
    workdir: OptRemotePathExpr
    env: BaseExpr[MappingT] | None = field(metadata={"allow_none": True})
    volumes: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    tags: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    life_span: OptTimeDeltaExpr
    http_port: OptIntExpr
    http_auth: OptBoolExpr
    pass_config: OptBoolExpr
    detach: OptBoolExpr
    browse: OptBoolExpr
    port_forward: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    multi: SimpleOptBoolExpr
    params: Mapping[str, Param] | None = field(metadata={"allow_none": True})
    mixins: Sequence[StrExpr] | None = field(metadata={"allow_none": True})
    restart: OptRestartPolicyExpr


@dataclass(frozen=True)
class Job(ExecUnit, WithSpecifiedFields, JobBase):
    # Interactive job used by Kind.Live flow

    detach: OptBoolExpr
    browse: OptBoolExpr
    port_forward: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    multi: SimpleOptBoolExpr
    mixins: Sequence[StrExpr] | None = field(metadata={"allow_none": True})


class NeedsLevel(enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"  # pipelined mode


@dataclass(frozen=True)
class TaskBase(Base):
    id: OptIdExpr

    # A set of steps, used in net mode
    # All steps share the same implicit persistent disk volume

    needs: Mapping[IdExpr, NeedsLevel] | None = field(metadata={"allow_none": True})

    # matrix? Do we need a build matrix? Yes probably.

    strategy: Strategy | None = field(metadata={"allow_none": True})

    # continue_on_error: OptBoolExpr
    enable: EnableExpr = field(metadata={"default_expr": "${{ success() }}"})
    cache: Cache | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class Task(ExecUnit, WithSpecifiedFields, TaskBase):
    mixins: Sequence[StrExpr] | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class TaskMixin(WithSpecifiedFields, Base):
    title: OptStrExpr
    name: OptStrExpr
    image: OptStrExpr
    preset: OptStrExpr
    schedule_timeout: OptTimeDeltaExpr
    entrypoint: OptStrExpr
    cmd: OptStrExpr
    workdir: OptRemotePathExpr
    env: BaseExpr[MappingT] | None = field(metadata={"allow_none": True})
    volumes: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    tags: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    life_span: OptTimeDeltaExpr
    http_port: OptIntExpr
    http_auth: OptBoolExpr
    pass_config: OptBoolExpr
    needs: Mapping[IdExpr, NeedsLevel] | None = field(metadata={"allow_none": True})
    strategy: Strategy | None = field(metadata={"allow_none": True})
    enable: EnableExpr = field(metadata={"default_expr": "${{ success() }}"})
    cache: Cache | None = field(metadata={"allow_none": True})
    mixins: Sequence[StrExpr] | None = field(metadata={"allow_none": True})
    restart: OptRestartPolicyExpr


@dataclass(frozen=True)
class BaseActionCall(Base):
    action: SimpleStrExpr  # action ref
    args: Mapping[str, PrimitiveExpr] | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class BaseModuleCall(Base):
    module: SimpleStrExpr  # action ref
    args: Mapping[str, PrimitiveExpr] | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class JobActionCall(BaseActionCall, JobBase):
    pass


@dataclass(frozen=True)
class JobModuleCall(BaseModuleCall, JobBase):
    pass


@dataclass(frozen=True)
class TaskActionCall(BaseActionCall, TaskBase):
    pass


@dataclass(frozen=True)
class TaskModuleCall(BaseModuleCall, TaskBase):
    pass


@dataclass(frozen=True)
class FlowDefaults(WithSpecifiedFields, Base):
    tags: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})

    env: BaseExpr[MappingT] | None = field(metadata={"allow_none": True})
    volumes: BaseExpr[SequenceT] | None = field(metadata={"allow_none": True})
    workdir: OptRemotePathExpr

    life_span: OptTimeDeltaExpr

    preset: OptStrExpr
    schedule_timeout: OptTimeDeltaExpr


@dataclass(frozen=True)
class BatchFlowDefaults(FlowDefaults):
    fail_fast: OptBoolExpr
    max_parallel: OptIntExpr
    cache: Cache | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class BaseFlow(Base):
    kind: FlowKind
    id: SimpleOptIdExpr

    title: SimpleOptStrExpr

    images: Mapping[str, Image] | None = field(metadata={"allow_none": True})
    volumes: Mapping[str, Volume] | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class LiveFlow(BaseFlow):
    # self.kind == Kind.Job
    mixins: Mapping[str, JobMixin] | None = field(metadata={"allow_none": True})
    jobs: Mapping[str, Job | JobActionCall | JobModuleCall]

    defaults: FlowDefaults | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class BatchFlow(BaseFlow):
    # self.kind == Kind.Batch
    life_span: OptTimeDeltaExpr = field(metadata={"allow_none": True})
    params: Mapping[str, Param] | None = field(metadata={"allow_none": True})
    mixins: Mapping[str, TaskMixin] | None = field(metadata={"allow_none": True})
    tasks: Sequence[Task | TaskActionCall | TaskModuleCall]

    defaults: BatchFlowDefaults | None = field(metadata={"allow_none": True})


# Action


class ActionKind(enum.Enum):
    LIVE = "live"  # live composite
    BATCH = "batch"  # batch composite
    STATEFUL = "stateful"  # stateful, can be used in batch flow
    LOCAL = "local"  # runs locally, can be used in batch flow


class InputType(enum.Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STR = "str"

    def to_type(self) -> type[str] | type[float] | type[int] | type[bool]:
        if self.value == "int":
            return int
        elif self.value == "float":
            return float
        elif self.value == "bool":
            return bool
        elif self.value == "str":
            return str
        raise AssertionError("Not reachable")


@dataclass(frozen=True)
class Input(Base):
    descr: SimpleOptStrExpr
    default: SimpleOptPrimitiveExpr
    type: InputType = InputType.STR


@dataclass(frozen=True)
class Output(Base):
    descr: SimpleOptStrExpr
    # TODO: split Output class to BatchOutput with value and an Output without it
    value: OptStrExpr  # valid for BatchAction only


@dataclass(frozen=True)
class BaseAction(Base):
    name: SimpleOptStrExpr
    author: SimpleOptStrExpr
    descr: SimpleOptStrExpr
    inputs: Mapping[str, Input] | None = field(metadata={"allow_none": True})

    kind: ActionKind


@dataclass(frozen=True)
class LiveAction(BaseAction):
    job: Job


@dataclass(frozen=True)
class BatchActionOutputs(Base):
    # AST class is slightly different from YAML representation,
    # in YAML `values` mapping is embedded into the outputs itself.
    values: Mapping[str, Output] | None = field(metadata={"allow_none": True})


@dataclass(frozen=True)
class BatchAction(BaseAction):
    outputs: BatchActionOutputs | None = field(metadata={"allow_none": True})
    cache: Cache | None = field(metadata={"allow_none": True})
    images: Mapping[str, Image] | None = field(metadata={"allow_none": True})

    tasks: Sequence[Task | TaskActionCall | TaskModuleCall]


@dataclass(frozen=True)
class StatefulAction(BaseAction):
    outputs: Mapping[str, Output] | None = field(metadata={"allow_none": True})
    main: ExecUnit
    post: ExecUnit | None = field(metadata={"allow_none": True})
    post_if: EnableExpr = field(metadata={"default_expr": "${{ always() }}"})


@dataclass(frozen=True)
class LocalAction(BaseAction):
    outputs: Mapping[str, Output] | None = field(metadata={"allow_none": True})
    cmd: StrExpr
