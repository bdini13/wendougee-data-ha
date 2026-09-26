# Contributing

Start with [the capability map](CAPABILITIES.md) and
[validation plan](docs/VALIDATION_PLAN.md). Keep upstream findings, synthetic
tests and exact-machine observations distinct. Implement protocol facts
independently and record source revisions; see [AI disclosure](AI_DISCLOSURE.md).

## Checks

Use the two environments and commands in [the README](README.md#development-and-checks).
Protocol/package tests use Python 3.13; HA framework tests use a separate pinned
Python 3.14 environment with simulated Bluetooth and network access disabled.
Build the bundled protocol before running HA tests. Tests never require access
to the machine.

## CI policy

`Validate` runs on pushes to `main`, pull requests and manual dispatch. Feature
branches are checked through their PR instead of also running an identical
push workflow. Commits confined to Markdown, `docs/` and `research/` skip both
test environments. Any executable, dependency, dashboard, package artwork,
JSON or workflow change still runs the complete existing checks.

Pip downloads are cached separately by Python version and dependency manifest;
dependencies are still installed on every run. A new commit cancels the older
run for that branch/PR. Ubuntu 24.04 is explicit to avoid an unplanned runner OS
migration. Protocol checks time out after ten minutes and HA checks after fifteen.
No scheduled polling workflow or automatic label-sync job is added.

Use manual dispatch when a documentation change warrants a complete run. If
required branch checks are introduced later, revisit path filtering: a skipped
workflow can leave a required check pending. These choices follow GitHub's
[workflow filter/concurrency documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
and [setup-python cache guidance](https://github.com/actions/setup-python/blob/main/docs/advanced-usage.md#caching-packages).

## Labels

[`.github/labels.json`](.github/labels.json) is the reviewed project label catalog.
Use `area:dashboard` for Espresso layout, graphs and units, and `area:ci` for
workflow efficiency. Keep `area:testing` for test/fixture coverage. Combine area
labels with `type:bug`, `type:enhancement` or `type:research`; add
`needs:hardware-validation` when evidence requires the real machine. Default
GitHub labels are preserved to avoid disrupting existing issue references.

## Privacy and deployment

Keep raw traces, Bluetooth identifiers, auth material and app binaries outside
Git. Published findings should contain reviewed aggregates and provenance.
Before dashboard deployment, compare the live configuration against the prior
source, retain a private backup, save through HA's dashboard API and read back
the saved result. Dashboard-only changes do not require an HA Core restart.
