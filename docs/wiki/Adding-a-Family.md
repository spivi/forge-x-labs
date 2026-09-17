# Adding a family

Since v1.4.0, a family is one core fragment module and one example spec. The
`fragments` package auto-imports every `core_*.py` file it finds
(`generate/fragments/__init__.py`), and every other hand-maintained map (the
composer's `scenario_type -> kind` map, the student brief prompt, the
workbench checklist row, the README teaching-point table) is derived from the
class attributes that module declares (`generate/fragments/base.py`,
`register_core`). Dropping the fragment file in `fragments/` and adding an
example spec is the whole registration path; there is nothing else to edit.

This page walks through adding one real, small family with the scaffold:
`public_lambda_layer_read`.

## The story

Teams often publish a Lambda layer's `.zip` archive to an S3 bucket first
(`aws lambda publish-layer-version --content S3Bucket=...`), then reference
that bucket from the `publish-layer-version` call. If the bucket is left
public, anyone can download the raw archive directly, without ever calling
the Lambda API — and a layer built by a CI pipeline sometimes bundles a
vendored `.env` file the build step forgot to strip. The direct exposure (the
bucket) is the critical risk; what it hands over (the dataset the leaked file
represents) is the point of the finding.

## 1. Run the scaffold

```bash
cloudforge new-family public_lambda_layer_read --cloud aws --title "Public Lambda layer read"
```

This writes two files and refuses to run if either already exists:

- `app/cloudforge/generate/fragments/core_public_lambda_layer_read.py`
- `examples/public_lambda_layer_read.yaml`

The fragment is a real, importable three-node path (entry exposes resource,
resource stores the sink dataset) with one critical finding, already
registered with `@register_core` — it passes the composer integrity net
before you change a line. The next steps replace the placeholder story with
the real one.

## 2. Edit the fragment

Open `core_public_lambda_layer_read.py`. The generated class looks like this:

```python
@register_core
class PublicLambdaLayerRead:
    scenario_type = "public_lambda_layer_read"
    cloud = "aws"
    prompt = (
        "Public Lambda layer read. Can it be reached from outside the "
        "boundary, and what sensitive data does it hold?"
    )
    checklist = ("public_lambda_layer_read", "Public Lambda layer read")
    teaching_point = "Public Lambda layer read"
```

Replace the placeholder text with the real story. The class attributes are
the whole declarative surface every other file used to duplicate by hand:

```python
    prompt = (
        "A Lambda layer's build archive is stored in S3. Can it be downloaded "
        "directly, and what does the archive bundle?"
    )
    checklist = ("lambda_layer_archive_public_read", "Serverless: Public Lambda Layer Archive")
    teaching_point = "Public S3 layer-archive bucket; the zip bundles a vendored secret"
```

Then rename the generated node ids and names in `_nodes`/`_edges` to match:
the entry stays an `Account`, the resource becomes the layer-archive bucket
(`S3Bucket`, `public_access="enabled"`), and the sink becomes the dataset the
bundled `.env` represents. Update `_findings` with a real
`FindingFamily` (`S3_PUBLIC_EXPOSURE` fits here), a real `ground_truth`
sentence, and a real `remediation`. Rewrite the module docstring and the
`GroundTruthPath.explanation` to match. Keep the shape the scaffold gave you
(entry → resource → sink, `sink_kind=SinkKind.DATA`, `target` on the last
node) — that shape is what the graph-risk engine's critical-sink check reads.

## 3. Fill in the example spec

`examples/public_lambda_layer_read.yaml` was scaffolded with a working
`company_profile`, `requirements` and `constraints` block already valid
against `ScenarioSpec`. Adjust `company_profile.app_name` and `environment`
to fit the story; leave `requirements.critical_chains: 1` unless you add a
second path.

## 4. Run it

```bash
cloudforge lab examples/public_lambda_layer_read.yaml --seed 17 --out out/demo
cloudforge validate out/demo/instructor    # or generate + validate directly
```

`cloudforge lab` writes `out/demo/student/` (no answer key) and
`out/demo/instructor/` (the grade key). Re-run with `--seed 0` too — every
family must generate the same shape deterministically per seed and pass at
every difficulty (`--seed 17 -- ` twice must be byte-identical).

## 5. Check the student tree has no key

The strip contract (the 1.3.1 tests) says the student pack never carries
`expected_findings.json`, the ground-truth paths, or a `security.risk` /
`criticality` field. Check it by hand:

```bash
grep -rl "criticality\|expected_finding\|ground_truth" out/demo/student/ && echo LEAK || echo clean
```

and by running the real suite, which checks every family, not just this one:

```bash
PYTHONPATH=. pytest tests/cloudforge/lab/test_id_leak.py -q
```

## 6. Run the tests

```bash
ruff check --fix app tests && ruff format app tests
mypy --strict app/
PYTHONPATH=. pytest tests/cloudforge tests/unit tests/property -q
```

The composer integrity net (`tests/integration/test_composer_integrity.py`)
does not know about your new family by name; add it to that test's `_FAMILIES`
list so seeds `{0, 1, 2, 17, 99}` and all three difficulties run against it.
The README table and the workbench checklist need no edit: both derive from
the registry, so run `PYTHONPATH=. python scripts/render_family_table.py` to
regenerate the README table and commit the diff.

## 7. Open the PR

```bash
git checkout -b feat/public-lambda-layer-read
git add app/cloudforge/generate/fragments/core_public_lambda_layer_read.py examples/public_lambda_layer_read.yaml
git commit --signoff -m "feat: add public_lambda_layer_read family"
git push -u origin feat/public-lambda-layer-read
gh pr create --title "feat: public Lambda layer archive read" --body "..."
```

Never commit to `master`. See CONTRIBUTING.md for the checks a PR must pass.
