# Security policy

`cloudforge` **intentionally generates misconfigured AWS Terraform**. That is
the product. Do not file issues titled "this Terraform is insecure."

## What is not a vulnerability

- Generated Terraform that would be dangerous if applied
- Dummy account ids (`000000000000`, `999999999999`)
- Mock AWS keys in `providers.tf` (`skip_credentials_validation = true`)
- Labeled false positives and over-broad read/list IAM grants that are
  documented in `expected_findings.json`

These artifacts are for **local static analysis, tabletop labs, and scanner
benchmarking**. They must never be applied to a real account.

## What to report

Report privately if you find a **tool** bug that could:

- run `terraform apply` (or any deploy path)
- read real cloud credentials
- leak a real secret into generated output
- path-traverse out of the output directory (read or write)
- put the answer key in the student pack (`cloudforge lab`)

Email: alex.spivakovsky@gmail.com

Please include a minimal reproducer (command + spec). Do not attach live
credentials.

## Scope

Local CLI only. No hosted service, no AWS account of ours, no production
URL. Optional tools (terraform, checkov, opa) are invoked locally if present.
