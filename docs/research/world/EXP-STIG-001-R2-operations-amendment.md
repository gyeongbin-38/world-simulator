# EXP-STIG-001: R2 operational deadline amendment

This append-only record is made after the first execution was censored and before
any R2 inference. It does not amend the scientific laws or interpretation in
EXP-STIG-001.md. The original protocol, configuration and evidence remain intact.

The first execution's planned manifest is
`efc8a9c46c0b182aa812af60cb4e337868ac6938e997dc4b0664d9027f97ef1b`.
It returned 12 complete generation responses, then exceeded the 300-second
transport deadline on request 13. The server log recorded ongoing generation
through token 127 of the 128-token limit, not a model or domain exception. The
runner stopped the server and recorded INCOMPLETE_INVALID. Nine initial worlds
exist; zero ticks, events or state transitions were committed. S0–S3 cannot be
assigned. No action scores or raw action contents were inspected to select this
amendment; only runtime metadata and the infrastructure failure were inspected.

One fresh operational replication, EXP-STIG-001-R2, is authorized within this
bounded task. It uses a 900-second request deadline and a 600-second model-load
deadline. The original shorter deadlines remain historical facts. This changes
only operational waiting bounds and the run namespace. It does not change the
models, GGUF hashes, GPU placement, context rendering, sampling, token limit,
seeds, assignments, conditions, horizon, laws, metrics or interpretation rules.
There is no prompt tuning, semantic retry, repair or fallback within either run.

The complete matched cohort is run afresh. No response from the censored run is
substituted into R2, and the censored run is never presented as a completed
replication. The unchanged law suite and new operational-contract tests must
pass before R2. If R2 also fails, stop with a censored result; do not keep changing
execution settings. Operational replication is not evidence for S3.

The exact overlay is owned by
`specs/experiments/EXP-STIG-001-execution-r2.yaml`. It is digest-bound to the
unchanged scientific configuration. R2 is exploratory, not a confirmatory reuse
of the incomplete first execution.
