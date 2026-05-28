---
name: "SonarCloud-Skill-Workflow-Guidance"
description: "GitHub Actions guidance for the SonarCloud skill repository."
applyTo: ".github/workflows/*.yml"
---

# Workflow Guidance

- Keep workflows minimal for a skill repository: dependency review, release packaging, Scorecards, stale issue handling, labeling, and secret scanning.
- Pin third-party actions to immutable SHAs when practical; otherwise use maintained major versions only when the repository convention already does.
- Set explicit `permissions` blocks and grant write scopes only to jobs that need them.
- Add `timeout-minutes` to jobs that run external tools.
- Do not add AI inference workflows that comment on issues or pull requests unless the repository owner explicitly asks for that behavior.
- Validate workflow syntax with `actionlint` when available after editing workflow YAML.
