# Odoo Integration Research

Date: 2026-05-05

## Current Repo Boundary

The repository currently has a local Odoo/ERP handoff demo, not a live Odoo integration.

Implemented in the local handoff path:

- `odoo_handoff_payload.py` reshapes the local business-summary export into an Odoo/ERP-style handoff payload.
- `odoo_handoff_mapper.py` converts that payload into dry-run `would_*` action objects.
- The local payload and dry-run action plan intentionally keep these flags false:
  - `network_calls_made`
  - `live_integration`
  - `connector_implemented`
  - `external_api_used`

The public portfolio package should be described as a local Odoo/ERP-style
dry-run handoff workflow only. Sandbox validation evidence may be documented
separately; no live or production Odoo/ERP integration is included.

Not implemented or not production-validated today:

- Odoo SDK dependency
- `requests` client
- XML-RPC or JSON-RPC client code
- default connector execution
- default credential loading
- production record creation
- production attachment upload
- ERP, CRM, SAP, MCP, or hosted API sync
- production deployment

Current safe claim: the repository includes a local Odoo/ERP-style dry-run
handoff payload and mapping notes. It does not include live or production
Odoo/ERP integration.

## Sandbox Validation Status

Sandbox Odoo validation evidence may be documented separately from the public
portfolio package. It should not be presented as live or production Odoo/ERP
integration, and no production Odoo/ERP call is claimed.

Any sandbox validation note must keep API keys redacted, use only sandbox-marked
test records, and keep cleanup evidence separate from the default local demo
path. Production integration remains incomplete pending hardening, idempotency,
audit logging, permission review, secret rotation, retry policy, cleanup
playbooks, and a deployment checklist.

## Official Odoo API Direction

Odoo 19 introduces the External JSON-2 API for external access to Odoo model methods.

Source: <https://www.odoo.com/documentation/19.0/developer/reference/external_api.html>

Key findings:

- Endpoint shape: `POST /json/2/<model>/<method>`.
- `model` is the technical Odoo model name.
- `method` is the model method to execute.
- Request body is JSON.
- The body can include `ids`, `context`, and named method parameters.
- Success returns HTTP 200 with the JSON-serialized method result.
- Errors return 4xx/5xx responses with a structured error object containing fields such as exception name, message, arguments, context, and debug detail.
- Actual available models, fields, and methods are database-specific and should be checked on the target database `/doc` page before mapping fields.

The JSON-2 API should be the default choice for any new Odoo 19+ connector work.

## Authentication And Database Selection

Odoo 19 JSON-2 uses bearer API key authentication.

Required or recommended request headers include:

- `Authorization: bearer <api_key>`
- `Content-Type: application/json; charset=utf-8`
- `User-Agent: <software name>`
- `X-Odoo-Database: <database>` when needed by the deployment

Odoo documents that `X-Odoo-Database` is required when one server hosts multiple databases and database filtering is not configured from the host header.

Odoo API keys must be handled like passwords. Odoo recommends clear key descriptions, limited duration, rotation, immediate deletion of compromised keys, and dedicated bot users for automated integrations with minimum required permissions.

## External API Access And Pricing

Odoo documentation says external API access is available on Custom Odoo pricing plans and is not available on One App Free or Standard plans.

Sources:

- <https://www.odoo.com/documentation/19.0/developer/reference/external_api.html>
- <https://www.odoo.com/pricing>

Before connector implementation, confirm the target account supports external API access.

## Legacy XML-RPC / JSON-RPC Status

Odoo 19 still documents legacy XML-RPC and JSON-RPC external APIs, including record listing, `search_read`, `create`, `write`, `fields_get`, `ir.model`, and `ir.model.fields`.

Source: <https://www.odoo.com/documentation/19.0/developer/reference/external_rpc_api.html>

However, Odoo 19 docs mark `/xmlrpc`, `/xmlrpc/2`, and `/jsonrpc` as scheduled for removal and identify the External JSON-2 API as the replacement. New connector work should avoid legacy RPC unless the confirmed target system is older than Odoo 19 and cannot support JSON-2.

## Model Discovery

Model and field mapping must be target-specific.

Use these discovery paths before write operations:

- Target database `/doc` page for actual models, fields, and methods.
- JSON-2 model calls for read-only metadata where supported by the target instance.
- `fields_get` to inspect fields on a candidate model.
- `ir.model` and `ir.model.fields` metadata if available and permissioned.

Do not assume custom fields exist. Do not write to custom fields until target metadata confirms their technical names and access rights.

## Candidate Workflow Targets

Candidate targets remain future mapping candidates until the target Odoo database is inspected.

Potential workflow concepts:

- CRM opportunity or lead: Odoo CRM tracks leads, opportunities, pipeline activity, and forecasts.
  - Source: <https://www.odoo.com/documentation/19.0/applications/sales/crm.html>
- Project task or review activity: Odoo Project can manage tasks and review workflows.
  - Source: <https://www.odoo.com/documentation/19.0/applications/services/project/tasks/task_creation.html>
- Internal note / chatter message: models with `mail.thread` support can use `message_post` to add messages or internal notes.
  - Source: <https://www.odoo.com/documentation/19.0/developer/reference/backend/mixins.html>
- Document/report attachment: likely through attachment-capable models or `ir.attachment`, but exact target behavior must be verified against the database.
- ORM create/write behavior: field validation and access errors follow Odoo ORM rules.
  - Source: <https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html>

## Failure Modes To Design For

- Missing API key.
- Wrong database or missing `X-Odoo-Database`.
- External API unavailable on the customer’s plan.
- Target model unavailable.
- Target field missing or renamed.
- `fields_get` or `/doc` unavailable because of permissions.
- Access-right or record-rule failure.
- Validation error from invalid field values.
- Network timeout, DNS failure, TLS failure, or transient server error.
- Rate/concurrency pressure.
- Partial write risk across multiple JSON-2 calls because each call is its own transaction.
- Attachment upload mismatch or size/type issue.
- Chatter/message method unavailable on target model.
- Accidental production URL.
- Secret leakage in logs, artifacts, screenshots, or test output.

## Recommendation

Use Odoo JSON-2 for Odoo 19+ connector work.

Avoid legacy XML-RPC/JSON-RPC for new work unless a confirmed older target requires it.

Do not choose an internal Odoo module approach unless the product direction changes from an external Streamlit dashboard to an Odoo-native application.

The next safe implementation step remains a gated connector design and read-only sandbox probe. Do not build live writes until a sandbox Odoo version, URL, database, API key, target models/fields, permissions, and cleanup plan are provided.
