# Local Container Run

This container setup is for local reproducibility during portfolio review. It runs the local FastAPI evidence-bundle API in a predictable environment.

It is not production deployment, not cloud hosting, not investment advice, and not live ERP/Odoo/MCP/SAP integration.

## Build

```bash
docker build -t rmc-evidence-api .
```

## Run

```bash
docker run --rm -p 8000:8000 rmc-evidence-api
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Generate a local evidence bundle through the API:

```bash
curl -X POST http://127.0.0.1:8000/run-bundle \
  -H "Content-Type: application/json" \
  -d '{"preset":"base","seed":123,"n":2,"sims_per_case":1}'
```

Generated bundles remain inside the container unless a local volume is mounted.

Optional local inspection volume:

```bash
mkdir -p /tmp/rmc_api_bundles
docker run --rm -p 8000:8000 \
  -v /tmp/rmc_api_bundles:/tmp/rmc_api_bundles \
  rmc-evidence-api
```

The mounted folder is for local review artifacts only. Do not mount or commit real secrets, `.env` files, SQLite registries, or generated bundle output.

## Verified Local Container Check

Local container build/run verified for the FastAPI evidence API:

- `docker build -t rmc-evidence-api .` completed successfully.
- `docker run --rm -d -p 8000:8000 --name rmc-evidence-api-check rmc-evidence-api` started successfully.
- `GET /health` returned `200` with `status=ok`, `service=rmc-evidence-api`, and `network_calls_made=false`.
- `POST /run-bundle` returned `200` with a `run_id`, `validation_report.all_valid=true`, `network_calls_made=false`, `generated_files`, and `artifact_endpoints`.
- `GET /bundle/{run_id}`, `GET /risk-flags/{run_id}`, and `GET /memo/{run_id}` returned `200`.
- `GET /bundle/not-a-real-run-id` returned `404`.
- The container stopped successfully, and no repo files were edited during verification.

This verifies local container behavior only. No ERP/Odoo/MCP/SAP connectivity, advisory workflow, hosted service, or security hardening was exercised.
