# AI Review Guide

Rules for implementation models:

- Stay inside the active slice.
- Report deviations clearly.
- Do not commit or push unless asked.
- Include validation commands.
- Include changed files.
- Include known issues.
- Avoid broad rewrites.
- Preserve local-first deployment assumptions.
- Avoid domain changes before planned slices.

Review priorities:

- Scope control
- Migration safety
- Testability
- Security
- Data model consistency
- Future deployment compatibility

Reviews should focus on actionable risks and preserve the slice boundaries.
