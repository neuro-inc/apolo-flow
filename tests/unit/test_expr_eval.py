import pytest
from typing import Dict, List
from typing_extensions import Final

from neuro_flow.context import DepCtx
from neuro_flow.expr import PARSER, RootABC, TypeT
from neuro_flow.tokenizer import Pos, tokenize
from neuro_flow.types import LocalPath, TaskStatus


FNAME = LocalPath("<test>")
START: Final = Pos(0, 0, FNAME)


class DictContext(RootABC):
    def lookup(self, name: str) -> TypeT:
        return self._dct[name]

    def __init__(self, dct: Dict[str, TypeT]) -> None:
        self._dct = dct


@pytest.mark.parametrize(  # type: ignore
    "expr,context,result",
    [
        ('"foo" == "foo"', {}, True),
        ('"foo" == "bar"', {}, False),
        ("4 < 5", {}, True),
        ("4 > 5", {}, False),
        ("(4 > 5) or ((4 <= 5))", {}, True),
        ("len(foo) <= 5", {"foo": [1, 2, 3]}, True),
        ("len(foo) >= 5", {"foo": [1, 2, 3]}, False),
        ("(2 == 3) or True", {}, True),
        ("'sdfdsf' == True", {}, False),
        ("not True", {}, False),
        ("not (42 == 42) or not True", {}, False),
    ],
)
async def test_bool_evals(expr: str, context: Dict[str, TypeT], result: bool) -> None:
    parsed = PARSER.parse(list(tokenize("${{" + expr + "}}", START)))
    assert len(parsed) == 1
    assert result == await parsed[0].eval(DictContext(context))


@pytest.mark.parametrize(  # type: ignore
    "expr,statuses,result",
    [
        ("success()", [], True),
        ("success()", [TaskStatus.SUCCEEDED], True),
        ("success()", [TaskStatus.SUCCEEDED, TaskStatus.SUCCEEDED], True),
        ("success()", [TaskStatus.SUCCEEDED, TaskStatus.FAILED], False),
        ("success()", [TaskStatus.SUCCEEDED, TaskStatus.DISABLED], False),
        ("success('task_1')", [TaskStatus.SUCCEEDED], True),
        (
            "success('task_1', 'task_2')",
            [TaskStatus.SUCCEEDED, TaskStatus.SUCCEEDED],
            True,
        ),
        ("success('task_1')", [TaskStatus.SUCCEEDED, TaskStatus.FAILED], True),
        ("success('task_2')", [TaskStatus.SUCCEEDED, TaskStatus.FAILED], False),
        ("success('task_2')", [TaskStatus.SUCCEEDED, TaskStatus.DISABLED], False),
    ],
)
async def test_success_func(
    expr: str, statuses: List[TaskStatus], result: bool
) -> None:
    context = {
        "needs": {
            f"task_{num}": DepCtx(status, {}) for num, status in enumerate(statuses, 1)
        }
    }
    parsed = PARSER.parse(list(tokenize("${{" + expr + "}}", START)))
    assert len(parsed) == 1
    assert result == await parsed[0].eval(DictContext(context))  # type: ignore


@pytest.mark.parametrize(  # type: ignore
    "expr,statuses,result",
    [
        ("failure()", [], False),
        ("failure()", [TaskStatus.SUCCEEDED], False),
        ("failure()", [TaskStatus.SUCCEEDED, TaskStatus.SUCCEEDED], False),
        ("failure()", [TaskStatus.SUCCEEDED, TaskStatus.FAILED], True),
        ("failure()", [TaskStatus.SUCCEEDED, TaskStatus.DISABLED], False),
        ("failure('task_1')", [TaskStatus.SUCCEEDED], False),
        (
            "failure('task_1', 'task_2')",
            [TaskStatus.SUCCEEDED, TaskStatus.SUCCEEDED],
            False,
        ),
        (
            "failure('task_1', 'task_2')",
            [TaskStatus.SUCCEEDED, TaskStatus.FAILED],
            True,
        ),
        ("failure('task_1')", [TaskStatus.SUCCEEDED, TaskStatus.FAILED], False),
        ("failure('task_2')", [TaskStatus.SUCCEEDED, TaskStatus.FAILED], True),
        ("failure('task_2')", [TaskStatus.SUCCEEDED, TaskStatus.DISABLED], False),
        ("failure('task_1', 'task_2')", [TaskStatus.FAILED, TaskStatus.DISABLED], True),
    ],
)
async def test_failure_func(
    expr: str, statuses: List[TaskStatus], result: bool
) -> None:
    context = {
        "needs": {
            f"task_{num}": DepCtx(status, {}) for num, status in enumerate(statuses, 1)
        }
    }
    parsed = PARSER.parse(list(tokenize("${{" + expr + "}}", START)))
    assert len(parsed) == 1
    assert result == await parsed[0].eval(DictContext(context))  # type: ignore
