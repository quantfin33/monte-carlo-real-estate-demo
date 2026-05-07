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
