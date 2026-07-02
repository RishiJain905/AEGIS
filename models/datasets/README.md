# Feature datasets

Phase 14 exports content-addressed training datasets from persisted PostgreSQL domain events.

## Layout

```text
models/datasets/<run-id>/
├── features.jsonl    # One FeatureVectorV1 per line (canonical JSON)
└── manifest.json     # DatasetManifestV1 with sha256 checksum and provenance
```

## Generation

```bash
uv run aegis-simulator run-persisted \
  --scenario scenarios/operation-silent-relay --seed 1000 --steps 200

uv run python scripts/build_feature_dataset.py --run-id <run_id>
```

Datasets are deterministic for identical ordered event inputs. Do not commit large generated artifacts to git unless explicitly versioned for evaluation.
