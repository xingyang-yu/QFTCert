"""LLM agent integration for the verifier-in-the-loop interface."""

from dualitycert.agent.client import (
    AnthropicAdapter,
    LLMClient,
    MockLLMClient,
    StructuredLLMResponse,
)
from dualitycert.agent.detection import (
    DETECTION_DECISION_SCHEMA,
    DETECTION_SYSTEM_PROMPT,
    DETECTION_SYSTEM_PROMPT_COMPUTED_R,
    DETECTION_TOOL_NAME,
    DetectionDecision,
    run_detection,
)
from dualitycert.agent.repair_loop import (
    LLMRepairResult,
    RepairIteration,
    run_llm_repair_loop,
)

__all__ = [
    "AnthropicAdapter",
    "DETECTION_DECISION_SCHEMA",
    "DETECTION_SYSTEM_PROMPT",
    "DETECTION_SYSTEM_PROMPT_COMPUTED_R",
    "DETECTION_TOOL_NAME",
    "DetectionDecision",
    "LLMClient",
    "LLMRepairResult",
    "MockLLMClient",
    "RepairIteration",
    "StructuredLLMResponse",
    "run_detection",
    "run_llm_repair_loop",
]
