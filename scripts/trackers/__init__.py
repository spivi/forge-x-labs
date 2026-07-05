"""Tracker abstraction seam.

The CSV store (`.dev-context/kpis/estimates.csv`) is the canonical source of
truth for estimate/model/status. Backends only *mirror* that state to an
external tracker (Linear / GitHub Projects) and read lead-time back. The `none`
backend mirrors nowhere, so the full learning loop works with no tracker at all.
"""
