FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RMC_API_BUNDLE_ROOT=/tmp/rmc_api_bundles \
    RMC_API_REGISTRY_DB=/tmp/rmc_api_bundles/demo_bundle_runs.sqlite

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /tmp/rmc_api_bundles /app/scripts \
    && chown -R appuser:appuser /tmp/rmc_api_bundles /app

COPY api_app.py \
     demo_presets.py \
     export_contracts.py \
     monte_carlo_model.py \
     risk_flags.py \
     run_registry.py \
     scenario_matrix.py \
     scenario_memo.py \
     ./
COPY scripts/generate_demo_bundle.py ./scripts/generate_demo_bundle.py
COPY demo_presets/ ./demo_presets/
COPY schemas/export_contracts/ ./schemas/export_contracts/

USER appuser

EXPOSE 8000

CMD ["uvicorn", "api_app:app", "--host", "0.0.0.0", "--port", "8000"]
