# Curriculum: a first week

Who this is for: a SOC team, a cloud security onboarding cohort, or a mixed table of engineers and
managers. Four sessions of ninety minutes and the roundtable. One facilitator holds the instructor
packs; everyone else gets a student pack. Nothing is deployed to any cloud.

Generate the packs once per session with a seed per person (`cloudforge lab-cohort` for a family,
`cloudforge roundtable` for the last session), and keep `instructor/` closed until the share-out.

## Session 1, easy: the resource is the door

Families: `public_data_exposure`, `public_rds_instance`, `public_ebs_snapshot`.

The lesson is exposure without an identity. The misconfiguration sits on the resource (a bucket
policy, a public flag, a shared snapshot), and the path is short. People learn to read attributes
rather than names, and to notice that a resource which looks exposed can be blocked by a control
next to it. Grade the clicked path; the paragraph is optional here.

## Session 2, medium: the identity is the door

Families: `ec2_imds_credential_exfil`, `lambda_public_function_url`, `iam_privesc_policy_version`.

A workload has an identity, and the identity is the attack surface. Instance metadata, a public
function URL, a policy version nobody reviewed. The path now has a hop, and the paragraph is
introduced: where it starts, what opens the access, what is reached. Grade both.

## Session 3, medium: trust across a boundary

Families: `cross_account_trust`, `ci_cd_iam_chain`, `secretsmanager_policy_overbroad`,
`kms_key_overbroad`.

Trust policies, key policies, secret policies, an external principal that should not be there.
The endings differ by family (a role, a secret, a key, data), which is the point of the session:
not every attack ends at a bucket. Ask for the paragraph first and the clicked path second.

## Session 4, hard: the roundtable

Track `identity_federation`, four dialects: a pod federating into AWS (IRSA), an App Service
managed identity into Key Vault, a CI identity through a Workload Identity Pool into GCS, GitHub
Actions through OIDC into an AWS role. Everyone gets a different copy and a different vendor; the
share-out is the same mistake told four ways. Grade the paragraph with the essay sidecar or by
hand; anything in the review band is the facilitator's queue.

Self-study after the week: `ecr_repository_public_read` (what an image carries) and
`sqs_queue_overbroad_policy` (data in flight).

## What difficulty changes

`easy` gives a direct chain and one protected lookalike; `medium` adds decoys, false positives
and a few extra hops drawn per seed; `hard` draws longer chains, adds a dead-end branch from the
same entry, and puts a blocked lookalike next to the exposed resource. Path length is drawn per
seed inside the band, so counting cards is not a strategy.

## What to grade, and how

- The clicked path: a hit needs where it starts, what opens the access, and what is reached, in
  order; the grade also reports how many of the path's nodes were found.
- The paragraph: three yes/no questions with a probability each, a pass at 0.7 on all three, and a
  review band between 0.4 and 0.6 that goes to a human. Completeness is reported as a depth level
  (the triple, the chain, the grants behind the chain) and is feedback, not the pass rule.
- The share-out is where the learning happens; the grades are there so the facilitator knows who to
  ask first.
