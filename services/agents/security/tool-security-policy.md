# Agent Tool Security Policy v1

Tool authorization is server-enforced for every model-originated request. Prompt wording and model self-restraint are not controls.

## Three enforcement layers

1. `ToolRegistry.model_visible_tools` exposes only registered, `model_visible` tools permitted for the role. Execution-class tools are never model-visible.
2. `authorize_tool_call` rejects unknown tools, all execution-class tools, role mismatches, and tools absent from the canonical `AgentDefinitionV1.allowed_tools` allowlist.
3. `ToolExecutor.invoke` repeats authorization immediately before dispatch, validates input and output schemas, requires a registered handler, and persists a success/rejected/failed `ToolInvocationV1` audit record.

State-changing simulation execution is not a model tool. BASTION can create a proposal only; WARDEN evaluates deterministic policy; the approval service derives the approver from the authenticated session, revalidates policy and revision immediately before execution, and invokes the internal idempotent command adapter.

Failure is closed with existing canonical error codes such as `TOOL_UNAUTHORIZED` and `TOOL_VALIDATION_FAILED`. This policy introduces no alternate ID, timestamp, trace, or error shapes.
