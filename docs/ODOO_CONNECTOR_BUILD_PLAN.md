# Odoo Connector Build Plan

Date: 2026-05-05

## Summary

This plan describes how to move from the current local Odoo/ERP handoff demo toward a sandbox-only connector without weakening the current safety boundary.

Current default handoff path remains local and dry-run only. In the local
handoff payload and dry-run mapper, these flags must remain false:

- `network_calls_made`
- `live_integration`
- `connector_implemented`
- `external_api_used`

A gated Odoo JSON-2 connector layer now exists for dry-run previews and
sandbox-only probing. It is disabled by default. Sandbox validation has been
completed in a trial sandbox, and production-ready Odoo integration is not
complete.

## Sandbox Validation Status

Sandbox Odoo validation completed against a trial sandbox. The gated JSON-2
connector successfully performed read-only model discovery, sandbox CRM lead
create/verify/cleanup, sandbox project task create/verify/cleanup, sandbox
attachment upload/verify/cleanup, and sandbox internal note posting. No
production Odoo/ERP call was executed.

The validation run kept the API key redacted, used only sandbox-marked test
records, and cleaned up the CRM lead, project task, attachment, and internal
note created during the validation. The integration test result for the
write-enabled sandbox validation path was `2 passed, 4 skipped`.

Production-ready integration remains incomplete pending hardening, idempotency,
audit logging, permission review, secret rotation, retry policy, cleanup
playbooks, and a deployment checklist.

## Architecture Principles

- Keep `odoo_handoff_payload.py` and `odoo_handoff_mapper.py` as the default safe path.
- Add connector code only in isolated modules that are never imported by the Streamlit app by default.
- Fail closed unless live mode is explicitly enabled.
- Require sandbox confirmation before any network call.
- Require a separate write flag before any create/update/attachment operation.
- Keep dry-run outputs available even when connector configuration is missing.
- Never serialize secrets into artifacts.
- Never claim production Odoo/ERP integration until production hardening is complete.

## Implementation Phases

### Phase 0: Research Notes Only

Implemented by documentation only:

- official Odoo JSON-2 research
- legacy RPC deprecation summary
- failure-mode list
- security boundaries
- test matrix

No connector code, dependencies, network calls, or credentials.

### Phase 1: Connector Interface And Stubs

Goal: define connector contracts without live network behavior.

Implemented files:

- `odoo_connector_contract.py`
- `odoo_config.py`
- `tests/test_odoo_config.py`
- `tests/test_odoo_connector_contract.py`

Behavior:

- parse config from injected mappings in tests, not real env by default
- define live-write guard semantics
- define redaction behavior
- define request-shape objects for future JSON-2 calls
- no `requests`, sockets, XML-RPC, JSON-RPC, or default live execution

Acceptance:

- unit tests prove missing config fails closed
- unit tests prove secrets are redacted
- static tests prove no live network imports

### Phase 2: Read-Only Sandbox Introspection

Goal: connect to a sandbox Odoo instance for read-only discovery.

Implemented scaffold files:

- `odoo_json2_client.py`
- `odoo_model_discovery.py`
- `scripts/odoo_sandbox_probe.py`
- `tests/test_odoo_json2_client.py`
- `tests/integration/test_odoo_sandbox_json2.py`

Behavior:

- use JSON-2 for Odoo 19+
- require `ODOO_LIVE_ENABLED=true`
- require sandbox URL marker or explicit sandbox confirmation
- support timeouts
- call only read-only endpoints/methods
- inspect `/doc`, model metadata, or `fields_get` where available
- skip live integration tests by default when sandbox env vars are absent

Acceptance:

- integration tests skipped unless sandbox env is present
- no writes are possible in this phase
- no secrets appear in logs

### Phase 3: Sandbox Review Task Write

Goal: create or update one safe review task or CRM note in sandbox only.

Behavior:

- require `ODOO_LIVE_ENABLED=true`
- require `ODOO_ENABLE_LIVE_WRITES=true`
- require sandbox confirmation
- require target model and field metadata
- write only a test review task or note
- record created IDs for cleanup

Acceptance:

- write test skipped unless all env vars and flags are present
- cleanup or mark-test-only strategy is verified
- no production URL is accepted

### Phase 4: Attachments And Internal Notes

Goal: add report attachments and internal notes after target-model support is proven.

Behavior:

- attach local JSON/report artifact only to verified target records
- use `message_post` only when the target model supports chatter
- never attach files to production
- keep payload non-claims in the note footer

Acceptance:

- tests verify attachment/note targets exist
- failures leave clear cleanup instructions
- no investment advice is sent into Odoo

### Phase 5: Production Hardening

Goal: prepare for a real controlled deployment after sandbox success.

Required before production:

- idempotency keys
- retry policy
- timeout policy
- structured audit logs
- created-record tracking
- rollback/cleanup playbook
- access-right review
- bot user with minimum permissions
- secret rotation process
- explicit user-facing claim update after evidence exists

## Module Layout

Implemented gated connector files:

- `odoo_config.py`: strict config parsing, sandbox guard, secret redaction.
- `odoo_connector_contract.py`: connector request contracts and write guard.
- `odoo_json2_client.py`: JSON-2 client with timeout and request/response handling.
- `odoo_model_discovery.py`: `/doc`, `fields_get`, `ir.model`, and `ir.model.fields` discovery helpers.
- `scripts/odoo_sandbox_probe.py`: dry-run preview and explicitly gated sandbox probe.
- `tests/test_odoo_config.py`
- `tests/test_odoo_connector_contract.py`
- `tests/test_odoo_json2_client.py`
- `tests/test_odoo_model_discovery.py`
- `tests/integration/test_odoo_sandbox_json2.py`

Future files should not be added until their phase is approved.

## Environment Variables For Future Live Stages

Future connector stages may use:

- `ODOO_LIVE_ENABLED=false`
- `ODOO_ENABLE_LIVE_WRITES=false`
- `ODOO_BASE_URL`
- `ODOO_DATABASE`
- `ODOO_API_KEY`
- `ODOO_LOGIN`
- `ODOO_TARGET_MODEL`
- `ODOO_TARGET_RECORD_ID`
- `ODOO_TEST_PROJECT_ID`

Rules:

- Stage 0 and dry-run paths must not require these values.
- Live calls fail closed unless `ODOO_LIVE_ENABLED=true`.
- Live writes fail closed unless `ODOO_ENABLE_LIVE_WRITES=true`.
- Sandbox confirmation is required before any live call.
- Never print the full API key.
- Redact secrets as `****last4`.
- Never write secrets into artifacts, logs, screenshots, or test output.
- Never commit `.env`, tokens, API keys, database credentials, or private Odoo URLs.

## Test Matrix

| Area | Test | Expected Result |
| --- | --- | --- |
| Existing payload | `tests/test_odoo_handoff_payload.py` | Local payload remains deterministic and no live flags become true |
| Existing mapper | `tests/test_odoo_handoff_mapper.py` | Dry-run actions remain deterministic and offline |
| Static dry-run safety | source scan | no network imports in payload or dry-run mapper |
| Config | missing env | fail closed with clear error |
| Config | secret redaction | key-like values are masked |
| Request shape | mocked JSON-2 request builder | endpoint shape is `/json/2/<model>/<method>` |
| Live gate | live flag absent | no network call allowed |
| Write gate | write flag absent | create/update/attach blocked |
| Sandbox gate | production-looking URL | hard abort |
| Integration | env missing | skipped by default |
| Integration | sandbox read-only | metadata/model discovery only |
| Integration | sandbox write | requires explicit write flag and cleanup plan |

## Risk Register

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Production URL used accidentally | P0 | hard abort unless sandbox confirmation is present |
| API key leaked | P0 | env-only secrets, redaction tests, no artifact serialization |
| Wrong database selected | P1 | require `ODOO_DATABASE` when needed and verify target metadata |
| Model unavailable | P1 | `/doc` and metadata discovery before mapping |
| Field mismatch | P1 | `fields_get` and target-specific mapping tests |
| Permission/access failure | P1 | dedicated bot user with minimum permissions |
| Partial write across multiple calls | P1 | avoid multi-step writes until idempotency and cleanup exist |
| Attachment/chatter mismatch | P1 | only enable after target model support is proven |
| Network/rate failure | P2 | timeouts, retry policy, explicit failure reporting |
| Overclaiming | P0 | keep docs and payload non-claims until sandbox evidence exists |

## Hard Abort Conditions

Abort if any of these occur:

- production-looking URL without explicit sandbox confirmation
- missing API key in live mode
- missing target model metadata
- write attempted without `ODOO_ENABLE_LIVE_WRITES=true`
- XML-RPC or JSON-RPC attempted for Odoo 19+
- secrets would be printed or written to an artifact
- `.env` or credentials would be committed
- connector output includes investment advice
- connector output claims production readiness
- connector output claims live Odoo/ERP integration before sandbox evidence exists

## Recommendation

Use Odoo JSON-2 API for future Odoo 19+ connector work.

Do not build legacy XML-RPC or JSON-RPC unless a confirmed older target Odoo version requires it.

Do not build an internal Odoo module unless the product direction changes to an Odoo-native app.

Next safe validation step is a read-only sandbox probe after a sandbox Odoo URL,
database, API key, target model, permissions, and cleanup plan are provided.
