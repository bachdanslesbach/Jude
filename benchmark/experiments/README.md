# Experiments

One-off measurements that informed a decision and are kept so they can
be re-run, not part of the benchmark proper.

* `laya_judge.py` — can a typed-decision model (Laya) act as a
  redact/keep judge on Jude's candidates? Builds nothing itself: it
  reads `decision_set.jsonl` produced by the snippet in
  `docs/decision-models.md` (held-out gold, public mentions, whitelist
  hits and Jude's false positives, each with its sentence). Result:
  AUC 0.64 at best, zero-shot — see the page. Requires `pip install
  laya` (and `laya-mlx` for the `mlx` backend).
