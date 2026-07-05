"""Registry-gated raw fetcher (STUB — implemented in ticket #2).

Fetches every ``enabled`` registry source into a content-addressed cache at
``data/raw/<source_id>/<content_hash>`` plus a ``.metadata.json`` sidecar
(``RawCacheMetadata``). Registry-gated: refuses any unlisted or disabled source — there
is NO broad crawling and NO spider. Idempotent via the content hash. No fetch/ingest
logic lives here in the foundation ticket.

See design §2 (pipeline) and §4 (raw-cache layout, governance rules).
"""

from __future__ import annotations

# Implemented in ticket #2 (Add raw source fetcher and cache).
