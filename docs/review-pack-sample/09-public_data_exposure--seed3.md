# Review Sheet 09 — `public_data_exposure--seed3`

> Sheet auto-assembled from this scenario's real generated artifacts (`report.md` / `graph.json` / `ground_truth_paths.json` / `expected_findings.json`). Score the reviewer view **blind**, then read the reveal. Rubric: [`../review-rubric.md`](../review-rubric.md).

## Reviewer view — score this half BLIND (do not scroll to the reveal)

- **Cloud:** aws
- **Type:** public_data_exposure
- **Environment:** prod (medium)
- **Company:** b2b_saas, medium — app `customer-data-lake`
- **Resource budget:** max 30
- **Size:** 8 resources, 6 edges

**Generated resources**

- `acct-main` — **Account** svc-prod-account-r1 (high)
- `vpc-prod` — **VPC** env-prod-vpc-alt (low)
- `s3-public-data` — **S3Bucket** app-customer-pii-b (critical)
- `s3-locked-backups` — **S3Bucket** app-public-looking-backups-r1 (medium)
- `app-data-lake` — **Application** svc-customer-data-lake-v2 (high)
- `data-customer-pii` — **DataSet** customer-pii-records-x (critical)
- `trail-main` — **LogTrail** res-main-trail (medium)
- `subnet-benign-extra` — **Subnet** app-spare-subnet-alt (low)

**Risk narrative (as an analyst would read it)**

A medium b2b saas prod account fronting a customer data lake. There are S3 buckets holding PII, a public-looking backups bucket, and the usual account / VPC / trail scaffolding. One or more buckets appear reachable from the internet. Your job blind: decide which exposure is real customer-PII risk versus a decoy, whether the logging posture matters, and whether a scanner would flag the right bucket.

**Findings surfaced** (family · severity · resources · expected scanner visibility — _the "why" and remediation are withheld until the reveal_)

- **[critical]** `s3_public_exposure` — `s3-public-data`, `data-customer-pii` · visibility: **visible**
- **[medium]** `s3_logging_missing` — `s3-public-data`, `trail-main` · visibility: **visible**
- **[low]** `public_looking_bucket_with_compensating_control` — `s3-locked-backups` · visibility: **visible**

**Blind scoring** (anchors in the rubric)

| Realism | Clarity | Training | Scanner-benchmark | Ground-truth trust |
|:-:|:-:|:-:|:-:|:-:|
|   |   |   |   |   |

**Open questions** (answer blind)

- Real SaaS/cloud env? · Risk chain plausible? · Findings too toy-like?
- Remediation order correct? · Benchmark a scanner? · Train an analyst?
- What is missing?

---

## Reveal — read only AFTER scoring the reviewer view

**Ground-truth critical path** (critical)

`acct-main` → `s3-public-data` → `data-customer-pii`

> The customer-pii bucket has public-read access with no compensating control, so it is reachable directly from the internet -> anonymous read of the sensitive customer-PII dataset it stores.

**Expected findings — and why**

- **[critical]** `s3_public_exposure` — customer-pii allows public read and stores sensitive data. → *Enable S3 Block Public Access and remove the public-read ACL/bucket policy.*
- **[medium]** `s3_logging_missing` — The public bucket has no access logging / CloudTrail data events. → *Enable S3 access logging and CloudTrail data events for the bucket.*
- **[low]** `public_looking_bucket_with_compensating_control` — benign → *None needed — a bucket policy restricts access despite the public-looking name.*

**Remediation order (highest risk first)**

1. **[critical]** Enable S3 Block Public Access and remove the public-read ACL/bucket policy.
2. **[medium]** Enable S3 access logging and CloudTrail data events for the bucket.
3. **[low]** None needed — a bucket policy restricts access despite the public-looking name.

**Decoy / mutation note**

_Seeded mutation (`--mutate-seed 3`) of the base `public_data_exposure`._ The mutation renamed resource **display labels** and added a benign decoy node: `subnet-benign-extra` (app-spare-subnet-alt) — a spare, unconnected subnet with no risk edge. A reviewer should NOT let the renamed labels or the extra resource change the score. Ground-truth critical-path node IDs identical to base: **True**; edges identical: **True** — i.e. the mutation preserved ground truth (12-point definition #12).

**Coherence check**

- Was the scenario coherent (did the reveal match your blind read)?  y / n — why:
