# Changelog

## 1.4.0 (2026-09-17)

- Every story has its own ending. Each core fragment now declares what the
  attacker reaches (`GroundTruthPath.sink_kind` and `target`, both in the
  grade key and the instructor's `ground_truth_paths.json`): the payroll
  escalation ends at the admin-capable role, the cross-account trust at the
  role the external account lands in, the KMS family at the key (the path
  walks role -> encrypted bucket -> key over a new `encrypted_with` edge),
  the Secrets Manager family at the secret, ECR at the repository, SQS at the
  queue, the snapshot family at the snapshot and the RDS family at the
  database; the eight data families are unchanged. Where a role is reached,
  the data it can read is a second, high-severity path; where a resource is
  reached, the data it holds lives elsewhere in the estate with no edge from
  the sink, so the data-set card next to the risky one is not the new tell.
  The validator's critical-sink rule follows the declared target of every
  path rather than only `stores_sensitive_data` edges. The eight prompts, the
  brief and the report say what is reached. Packs written before the fields
  existed still load (`data`, last node).
- Noise, decoys, false positives and compensating controls now match the
  estate's vendor. The composer draws every non-core fragment from a pool
  keyed by `cloud`: `azure` gets storage containers, key vaults, managed
  identities, app services and resource groups; `gcp` gets buckets, service
  accounts, projects, folders and workload identity pools; `k8s` gets
  namespaces, pods, service accounts and a second cluster on top of the AWS
  pool, since that family federates into AWS IAM. Before this an Azure or GCP
  lab was padded with ECR repositories, SQS queues and an IAM decoy role.
  `variation_axes` and `difficulty` count instances per role, whatever the
  vendor. The Azure and GCP emitters render the control attributes the new
  fragments carry (key vault network ACL and private access, storage account
  public-blob flag, bucket uniform access and public access prevention).
- The sink is no longer the only labeled data set. An Azure or GCP estate
  held exactly one `DataSet`, the sink, classified `restricted`; an AWS
  estate's noise data sets were all `internal` while the sink carried no
  classification at all, so the odd data-set card was the answer. Now every
  pool has a noise kind whose container, bucket or pod holds a data set,
  every data set carries a classification drawn from `public` / `internal` /
  `confidential` / `restricted` with the fragment rng, the twelve AWS core
  sinks carry their true `restricted` label, and every compensating control
  guards a `restricted` data set that no identity in the estate can reach.
  The composer's extras guard now counts a kind's real node count, as the
  fill already did. AWS estates change for the same `(spec, seed)` as a
  result (the 1.3.1 byte-identity noted in an earlier draft of this entry
  no longer holds); the id, edge and path contracts are unchanged.
- Nothing a path node carries is rare among its type peers any more. Core
  fragments stamp one fixed tag set (`env=prod`, one owner, one app) while
  padding drew only non-prod values, so filtering on a tag returned the path;
  the path identity was the only `SystemAssigned` one, the path vault the
  only one without purge protection; eight core data sets were CamelCase
  while every pool data set is kebab-case. Now pool nodes draw `env` from a
  distribution where `prod` is the common value and draw the core's own
  owner and app three times as often as any other; the composer plans at
  least two off-path nodes of every path node type its pool can mint, then
  copies each path node's tag values and benign configuration onto seeded
  off-path peers until two of them carry it (`composer_blend.py`). The
  modeled-risk attributes (`imds_version`, `acl`, IAM grants, ...) and
  per-resource identifiers are never copied; that allowlist is printed by
  `tests/cloudforge/lab/test_path_tells.py`. Data set names are kebab-case
  everywhere (`customer-banking-records`, `payroll-financial-records`);
  roles and policies stay CamelCase. Easy difficulty plans one compensating
  control so its guarded restricted data set exists at every difficulty.
- `cloudforge roundtable`: the `identity_federation` track has AWS as its
  fourth dialect (`ci_cd_iam_chain`, a GitHub Actions OIDC identity federating
  into an IAM role), so a four-name roster gets one estate per vendor and the
  facilitator agenda speaks of four clouds.

## 1.3.1 (2026-09-17)

- The student workbench and the demo challenge page show the release version
  again (they still said 1.0.0).
- README: the workbench has seven zones, not five, and its finding checklist
  is the whole catalog rather than a per-vendor list. Two claim badges dropped.
- Student ids and names no longer reveal which nodes are the path, decoys, or
  noise. Every node gets its own `n<k>_<salt>` token from a seeded permutation
  instead of a shared `core0_`/`decoy0_`/`noise13_` prefix, so ids do not
  cluster by fragment, and the non-core fragments draw operator-style names.
  The fragment kind is kept for the instructor in a new optional `origin`
  field on graph nodes, which the student strip never copies.
- `difficulty` (`easy` / `medium` / `hard`, validated, defaults to `medium`)
  now drives the composer: it sets the decoy, false-positive, and
  compensating-control counts and biases the noise fill toward the low or
  high end of the scale profile, unless `variation_axes` overrides a kind.
  It was previously declared, echoed in the report, and used by nothing.
- The two fake workbench tabs (Blue Defense, Forensics) are gone; both were
  static decoration unrelated to the lab's actual findings.
- The finding checklist is filtered to the vendors present in the estate, so
  an Azure or GCP lab no longer lists AWS-only findings such as EC2 or RDS.

## 1.3.0 (2026-09-17)

SOC roundtable pack and multi-cloud labs.

- `cloudforge roundtable`: unique student copies of the same identity-federation
  lesson across Kubernetes (IRSA), Azure (managed identity), and GCP (Workload
  Identity Pool). Writes `facilitator.md` with a 90-minute agenda.
- Those three families emit never-applied Terraform (`k8s.tf`, `azure.tf`,
  `gcp.tf`). AWS-only labs do not pull those providers.

## 1.1.0 (2026-09-17)

Three graph-only labs outside AWS Terraform:

- `k8s_pod_irsa_exfil`: pod IRSA token to an IAM role that reads a sensitive bucket.
- `azure_imds_keyvault_harvest`: App Service managed identity to Key Vault.
- `gcp_workload_identity_federation`: Workload Identity Pool to a GCS bucket.

These families generate a risk graph, workbench, and grade key. Terraform remains
AWS-only. Azure, GCP, and Kubernetes nodes do not emit `.tf` resources yet.

## 1.0.0 (2026-09-16)

Local-first AWS misconfig lab generator.

- 12 scenario families (IAM, S3, KMS, EBS, RDS, ECR, SQS, Lambda, Secrets Manager).
- `generate` / `validate` / `report` pipeline. Graph is source of truth; Terraform is compiled and never applied.
- Trainer loop: `lab`, `grade`, `lab-cohort`, `grade-cohort`, `challenge`.
- Interactive single-file workbench (`estate.html`).
- Variation harness (`cloudforge variation`) with a diversity gate.
- Learning corpus CLI (`cloudforge learn`): fetch, ingest, validate, export. No model training.
- Apache-2.0 license, SECURITY.md, CONTRIBUTING.md.

## 0.1.0

- Deterministic `generate` / `validate` / `report` for AWS misconfig scenarios.
- Families `ci_cd_iam_chain` and `public_data_exposure`.
- Graph composer, mutation engine.
- Fail-soft terraform / checkov / opa. Never `terraform apply`.
