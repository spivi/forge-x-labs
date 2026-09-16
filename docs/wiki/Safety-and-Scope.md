# Safety and Scope

`cloudforge` is a **defensive** security-research tool. It generates scenarios
for **local static analysis, scanner benchmarking, and training**. It never
deploys anything.

## Hard guarantees

- **Local only.** No AWS (or any cloud) credentials are read or required.
- **Never applied.** Terraform is validated statically. `terraform apply` is
  never run. The provider uses `skip_credentials_validation` and mock keys.
- **No real secrets.** No live account IDs. The dummy `000000000000` is
  clearly marked.
- **No offensive content.** The tool models misconfigurations. It does not
  produce exploit or operational attack instructions.

## Forbidden vs allowed permissions

The risk engine **rejects** these destructive actions on any policy node
(validation `FAIL`):

`iam:Delete*` · `s3:DeleteBucket` · `ec2:TerminateInstances` ·
`kms:ScheduleKeyDeletion` · `organizations:*`

Broad **read/list** grants (for example `s3:Get*`, `s3:List*`) *are* allowed.
They are the point of the exercise, but only when they are **explicitly
documented** by an expected finding. An undocumented broad grant is a
validation `FAIL`.

## The report banner

Every generated `report.md` carries this banner verbatim:

> This scenario is generated for local static analysis, scanner benchmarking, and
> defensive security training. It is not deployed and does not require cloud credentials.

## Intended use

Scanner benchmarking, prioritization-engine evaluation, remediation-order
testing, analyst training exercises, and generative-graph research. If you
need to *run* infrastructure to test a control, that is out of scope.
cloudforge stops at validated artifacts.
