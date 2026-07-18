# Scenario Content Policy v1

Scenario-authored labels, descriptions, telemetry, evidence summaries, and incident titles are untrusted data. They cannot define system messages, change agent roles, add tools, alter allowlists, approve proposals, or become simulator commands.

When scenario strings enter a model prompt, `build_scenario_data_message`:

- emits a canonical `GenerationMessageV1` with role `user`, never `system`;
- serializes scalar fields as deterministic JSON;
- wraps data in a schema-versioned `AEGIS_SCENARIO_DATA` delimiter;
- Unicode-escapes `<`, `>`, and `&`, so content cannot close the delimiter or create prompt-like markup;
- rejects payloads over 32,768 UTF-8 bytes with canonical `VALIDATION_FAILED` behavior.

Delimiting reduces instruction/data ambiguity but is not an authorization boundary. Model output remains untrusted and must pass structured-output validation, evidence grounding, tool authorization, deterministic WARDEN policy, human approval, and final revalidation as applicable.
