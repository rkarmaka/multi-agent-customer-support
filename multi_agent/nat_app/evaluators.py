"""Custom NAT evaluator: agent-routing / trajectory check.

Goal: verify the coordinator *delegated to the right specialist* for each shopper
turn — the behavior the pytest suite never exercises (it tests tools directly,
not whether the LLM routes correctly).

This is a non-LLM evaluator: instead of a judge model, it inspects the trajectory
NAT recorded for the turn (the tool/agent calls) and compares the agents that
were actually invoked against the `expected_tools` list on each dataset row.

Registration happens because `register.py` imports this module, and `register.py`
is the entry-point NAT loads (see pyproject.toml).
"""
import logging

from nat.builder.evaluator import EvaluatorInfo
from nat.cli.register_workflow import register_evaluator
from nat.data_models.evaluator import EvalInputItem, EvaluatorBaseConfig
from nat.data_models.intermediate_step import IntermediateStepType
from nat.plugins.eval.data_models.evaluator_io import EvalOutputItem
from nat.plugins.eval.evaluator.base_evaluator import BaseEvaluator

logger = logging.getLogger(__name__)


class AgentRoutingEvaluatorConfig(EvaluatorBaseConfig, name="agent_routing"):
    """Config for the routing evaluator.

    `llm_name` is required by the base class but unused here (no judge), so we
    override it to be optional.
    """

    llm_name: str | None = None


def _tools_called(trajectory) -> set[str]:
    """Names of every tool/agent invoked in the turn (TOOL_START events)."""
    return {
        step.name
        for step in trajectory
        if step.event_type == IntermediateStepType.TOOL_START and step.name
    }


class AgentRoutingEvaluator(BaseEvaluator):
    """Item-level routing check. BaseEvaluator handles concurrency + averaging."""

    def __init__(self, max_concurrency: int = 4):
        super().__init__(max_concurrency=max_concurrency, tqdm_desc="Agent routing")

    async def evaluate_item(self, item: EvalInputItem) -> EvalOutputItem:
        entry = item.full_dataset_entry or {}
        expected = set(entry.get("expected_tools", []))
        called = _tools_called(item.trajectory or [])

        if not expected:
            # An empty expectation means "the coordinator should answer this
            # itself" (greetings, how-does-this-work) — so any delegation fails.
            score = 1.0 if not called else 0.0
        else:
            # Fraction of expected specialists that were actually called.
            score = len(expected & called) / len(expected)

        return EvalOutputItem(
            id=item.id,
            score=score,
            reasoning={
                "expected_tools": sorted(expected),
                "tools_called": sorted(called),
            },
        )


@register_evaluator(config_type=AgentRoutingEvaluatorConfig)
async def register_agent_routing_evaluator(config: AgentRoutingEvaluatorConfig, builder):
    evaluator = AgentRoutingEvaluator()
    yield EvaluatorInfo(
        config=config,
        evaluate_fn=evaluator.evaluate,
        description="Checks the coordinator delegated to the expected agents/tools.",
    )
