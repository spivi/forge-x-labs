# Review Sheet 01 - `ci_cd_iam_chain--base`

> Sheet auto-assembled from this scenario's real generated artifacts (`report.md` / `graph.json` / `ground_truth_paths.json` / `expected_findings.json`). Score the reviewer view **blind**, then read the reveal. Rubric: [`../review-rubric.md`](../review-rubric.md).

## Reviewer view - score this half BLIND (do not scroll to the reveal)

- **Cloud:** aws
- **Type:** ci_cd_iam_chain
- **Environment:** staging (medium)
- **Company:** b2b_saas, small - app `analytics-exporter`
- **Resource budget:** max 40
- **Size:** 14 resources, 11 edges

**Generated resources**

- `acct-main` - **Account** staging-account (medium)
- `vpc-staging` - **VPC** staging-vpc (low)
- `subnet-public-a` - **Subnet** public-a (medium)
- `sg-web` - **SecurityGroup** web-sg (high)
- `cicd-github` - **CICDIdentity** github-actions-oidc (high)
- `role-deploy` - **IAMRole** DeployRole (high)
- `role-runtime` - **IAMRole** RuntimeRole (critical)
- `pol-deploy-passrole` - **IAMPolicy** DeployPassRolePolicy (high)
- `pol-runtime-s3read` - **IAMPolicy** RuntimeS3ReadPolicy (high)
- `s3-customer-exports` - **S3Bucket** customer-exports (critical)
- `s3-public-assets` - **S3Bucket** public-assets (medium)
- `app-analytics-exporter` - **Application** analytics-exporter (medium)
- `data-customer-exports` - **DataSet** customer-export-data (critical)
- `trail-main` - **LogTrail** main-trail (medium)

**Risk narrative (as an analyst would read it)**

A small b2b saas staging account wired for CI/CD: a GitHub Actions OIDC identity deploys into the account through one or more IAM roles, and there are S3 buckets holding customer export data plus a public-looking assets bucket. The role topology and the S3 grants are where the risk appears to concentrate; a couple of findings look network- or logging-shaped, and at least one bucket is flagged that may be a false positive. Your job blind: decide whether an attacker landing on the CI identity could reach sensitive data, and how much of that a scanner would see.

**Findings surfaced** (family · severity · resources · expected scanner visibility - _the "why" and remediation are withheld until the reveal_)

- **[critical]** `iam_passrole_risk` - `role-deploy`, `role-runtime`, `pol-deploy-passrole` · visibility: **partial**
- **[high]** `iam_excessive_privilege` - `role-runtime`, `pol-runtime-s3read`, `s3-customer-exports` · visibility: **visible**
- **[medium]** `s3_logging_missing` - `s3-customer-exports`, `trail-main` · visibility: **visible**
- **[medium]** `security_group_overexposed` - `sg-web`, `subnet-public-a` · visibility: **visible**
- **[low]** `public_looking_bucket_with_compensating_control` - `s3-public-assets` · visibility: **visible**

**Blind scoring** (anchors in the rubric)

| Realism | Clarity | Training | Scanner-benchmark | Ground-truth trust |
|:-:|:-:|:-:|:-:|:-:|
|   |   |   |   |   |

**Open questions** (answer blind)

- Real SaaS/cloud env? · Risk chain plausible? · Findings too toy-like?
- Remediation order correct? · Benchmark a scanner? · Train an analyst?
- What is missing?

---

## Reveal - read only AFTER scoring the reviewer view

**Ground-truth critical path** (critical)

`cicd-github` → `role-deploy` → `role-runtime` → `s3-customer-exports` → `data-customer-exports`

> GitHub Actions OIDC assumes DeployRole; DeployRole can iam:PassRole RuntimeRole; RuntimeRole holds broad s3:Get*/List* on the sensitive customer-exports bucket -> full read of customer data via CI.

**Expected findings - and why**

- **[critical]** `iam_passrole_risk` - DeployRole can pass RuntimeRole, completing the CI-to-data chain. → *Scope iam:PassRole to the exact RuntimeRole ARN and add a role condition.*
- **[high]** `iam_excessive_privilege` - RuntimeRole has broader S3 read than intended over the exports bucket. → *Replace s3:Get*/List* wildcards with least-privilege object prefixes.*
- **[medium]** `s3_logging_missing` - The sensitive bucket has no access logging / CloudTrail data events. → *Enable S3 access logging and CloudTrail data events for the bucket.*
- **[medium]** `security_group_overexposed` - web-sg allows ingress from 0.0.0.0/0. → *Restrict ingress from 0.0.0.0/0 to known corporate/CI CIDRs.*
- **[low]** `public_looking_bucket_with_compensating_control` - benign → *None needed - public read is intentional; a bucket policy limits it to GetObject.*

**Remediation order (highest risk first)**

1. **[critical]** Scope iam:PassRole to the exact RuntimeRole ARN and add a role condition.
2. **[high]** Replace s3:Get*/List* wildcards with least-privilege object prefixes.
3. **[medium]** Enable S3 access logging and CloudTrail data events for the bucket.
4. **[medium]** Restrict ingress from 0.0.0.0/0 to known corporate/CI CIDRs.
5. **[low]** None needed - public read is intentional; a bucket policy limits it to GetObject.

**Decoy / mutation note**

_Base scenario (no mutation)._ The false-positive here is the `public_looking_bucket_with_compensating_control` finding - a bucket whose name looks public but whose policy restricts access. It should NOT be chased.

**Coherence check**

- Was the scenario coherent (did the reveal match your blind read)?  y / n - why:
