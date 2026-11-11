# Pinned specs

Specs a Desktop probe was built from, kept exactly as they were when the probe ran, so a
replay re-applies what Desktop actually saw. Same idea as `tests/pinned-layouts/`.

- `sales-mix.yaml` — probe 9 (`bp apply` of the then-shipped `examples/sales-mix.yaml`,
  whose third visual was a `pie`). The shipped example uses `bar` now, so the replay reads
  this copy to re-apply what Desktop actually saw. `pie` itself is a core type.

Pin a spec here before changing one a probe used.
