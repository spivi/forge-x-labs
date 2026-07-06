"""Fixed benign vocabulary shared by non-core fragments.

Mirrors the pattern in ``generate/mutation_ops.py`` — tag/name values are drawn
from fixed tuples only (never free text), so a fragment can never smuggle a
real secret or an unexpected value into a generated scenario.
"""

from __future__ import annotations

ENV_VALUES = ("staging", "stage", "preprod", "test", "sandbox")
OWNER_VALUES = ("platform-team", "infra-team", "sre-team", "devops-crew", "cloud-eng")
APP_VALUES = ("analytics-exporter", "data-exporter", "report-pipeline", "etl-runner")
