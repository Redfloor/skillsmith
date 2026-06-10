# skillsmith-core

Shared foundations for skillsmith: Pydantic v2 models, the two-layer config
loader (team ceiling + per-developer), the autonomy policy, the layered sandbox
interface, branch+PR git plumbing, and JSON Schema emission.

This package has no knowledge of any specific ecosystem — adapters depend on it,
not the other way around.
