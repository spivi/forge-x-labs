# Source Adapters

Adapters sit between a registry-gated, already-fetched raw source and the
learning corpus. Each one reads a local cache location (never the network)
and emits `RawPatternRecord`s with provenance. They live in
`app/cloudforge/learn/adapters/`.

## Protocol

```python
class PatternAdapter(Protocol):
    adapter_name: str
    adapter_version: str

    def extract(self, source: SourceEntry, raw_path: Path) -> list[RawPatternRecord]: ...
```

`raw_path` is always a local, already-fetched cache location. A
`metadata_only` source must never copy rule source text into a record, only
IDs, resource types, and short summaries.

## Shipped adapters

| Adapter | Module | Source | Default confidence | Training eligible |
|---|---|---|---|---|
| `cloudforge_scenario` | `adapters/cloudforge_scenario.py` | existing scenario dirs | 0.85 | true |
| `rule_catalog_yaml` | `adapters/rule_catalog_yaml.py` | local curated YAML catalog | 0.75 | true |
| `checkov_policy_index` | `adapters/checkov_policy_index.py` | recorded Checkov index HTML | 0.55 | false (metadata only) |
