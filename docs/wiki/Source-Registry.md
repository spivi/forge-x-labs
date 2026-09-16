# Source Registry

`data/source_registry.yaml` is the **allow-list** for the learning corpus. The
fetcher refuses anything not listed, and anything listed with `enabled: false`.
There is no crawler and no spider.

Models: `app/cloudforge/learn/source_models.py`. Loader:
`app/cloudforge/learn/registry.py`.

## Per-entry schema

```yaml
sources:
  - id: checkov-terraform-index
    name: "Checkov Terraform policy index"
    type: scanner_rule_index
    url: "https://www.checkov.io/5.Policy%20Index/terraform.html"
    adapter: checkov_policy_index
    enabled: true
    license: "Apache-2.0"
    reuse_status: metadata_only
    allowed_for_training: false
    notes: "Metadata only: IDs, resource types, summaries. Never copy rule source."
```

A `SourceEntry` must set **exactly one** of `url` (remote) or `path` (local file,
no network).

### `SourceType`

`scanner_rule_index` · `scanner_rule_catalog` · `provider_guidance` ·
`control_framework` · `local_scenario_dir` · `local_rule_catalog` · `iac_repo`

### `ReuseStatus`

`full_reuse` · `attribution` · `metadata_only` · `mappings_only` · `restricted` ·
`unknown`

`mappings_only` covers sources where our-id to external control-id mappings are
allowed, but control body text is not. CSA CCM mappings are training-eligible;
CCM control text is not. CIS Benchmark content stays `metadata_only`.
