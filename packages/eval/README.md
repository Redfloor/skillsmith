# skillsmith-eval

Evaluation harness for skills:

- **Golden / snapshot** tests.
- **Regression** tests that *block on regression vs a recorded baseline*, not on an
  absolute threshold (which would be brittle as skills legitimately evolve).
- A **determinism harness** that runs a skill N times and reports output-variance
  metrics — because temperature 0 is necessary-but-insufficient.
- A **triggering-accuracy** tester (should-trigger / should-not-trigger query sets,
  run multiple times) with a **train/held-out split** to avoid overfitting
  description tweaks.

Deterministic scorers are ground truth. The optional `promptfoo` wrapper drives
declarative configs; `deepeval` (extra `scored`) provides pytest-native scored
metrics. LLM-as-judge is used only for subjective cases and **never the sole gate**.
