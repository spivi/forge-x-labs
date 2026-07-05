"""Pure HCL string builders — one per Terraform file.

Terraform is a *compiled artifact* of the graph. It must be valid enough for
``terraform validate`` and for static scanners (checkov/opa) to have real
resources to flag, but it is never applied. All values are safe fakes; the dummy
account id is clearly marked.

The intentional misconfigurations (broad S3 read, missing bucket logging, a
0.0.0.0/0 security group) are deliberate — they are the modeled risks. No
destructive permissions appear here.
"""

from __future__ import annotations

from app.cloudforge import constants

_DUMMY = constants.DUMMY_ACCOUNT_ID
_REGION = constants.DEFAULT_REGION


def build_providers_tf() -> str:
    return """terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.region
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}
"""


def build_variables_tf() -> str:
    return f"""variable "region" {{
  type    = string
  default = "{_REGION}"
}}

# DUMMY / non-routable fake account id — this scenario is never deployed.
variable "account_id" {{
  type    = string
  default = "{_DUMMY}"
}}
"""


def build_main_tf() -> str:
    return f"""locals {{
  fake_account_id = "{_DUMMY}"
  common_tags = {{
    env   = "staging"
    owner = "platform-team"
    app   = "analytics-exporter"
  }}
}}
"""


def build_iam_tf() -> str:
    return """# DeployRole: assumed by the GitHub Actions OIDC identity.
resource "aws_iam_role" "deploy_role" {
  name               = "DeployRole"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = "arn:aws:iam::${local.fake_account_id}:oidc-provider/token.actions.githubusercontent.com" }
      Action    = "sts:AssumeRoleWithWebIdentity"
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role" "runtime_role" {
  name               = "RuntimeRole"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = aws_iam_role.deploy_role.arn }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.common_tags
}

# INTENDED MISCONFIG: iam:PassRole (the privilege-chain link). Not destructive.
resource "aws_iam_role_policy" "deploy_passrole" {
  name   = "DeployPassRolePolicy"
  role   = aws_iam_role.deploy_role.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "iam:PassRole"
      Resource = aws_iam_role.runtime_role.arn
    }]
  })
}

# INTENDED MISCONFIG: broad S3 read over the sensitive bucket.
resource "aws_iam_role_policy" "runtime_s3read" {
  name   = "RuntimeS3ReadPolicy"
  role   = aws_iam_role.runtime_role.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:Get*", "s3:List*"]
      Resource = ["${aws_s3_bucket.customer_exports.arn}", "${aws_s3_bucket.customer_exports.arn}/*"]
    }]
  })
}
"""


def build_s3_tf() -> str:
    return """# Sensitive bucket. INTENDED MISCONFIG: no logging / no CloudTrail data events.
resource "aws_s3_bucket" "customer_exports" {
  bucket = "customer-exports-staging-000000000000"
  tags   = local.common_tags
}

# Public-looking bucket WITH a compensating control (the false-positive case).
resource "aws_s3_bucket" "public_assets" {
  bucket = "public-assets-staging-000000000000"
  tags   = local.common_tags
}

# Compensating control: policy limits public access to GetObject on a public prefix.
resource "aws_s3_bucket_policy" "public_assets" {
  bucket = aws_s3_bucket.public_assets.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.public_assets.arn}/public/*"
    }]
  })
}
"""


def build_network_tf() -> str:
    return """resource "aws_vpc" "staging" {
  cidr_block = "10.0.0.0/16"
  tags       = local.common_tags
}

resource "aws_subnet" "public_a" {
  vpc_id     = aws_vpc.staging.id
  cidr_block = "10.0.1.0/24"
  tags       = local.common_tags
}

# INTENDED MISCONFIG: ingress open to the whole internet.
resource "aws_security_group" "web" {
  name   = "web-sg"
  vpc_id = aws_vpc.staging.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}
"""
