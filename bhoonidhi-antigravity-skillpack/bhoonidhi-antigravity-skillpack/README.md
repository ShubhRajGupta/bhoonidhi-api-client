# Bhoonidhi Antigravity Skills Pack

This pack is built to improve Antigravity's ability to **engineer against the Bhoonidhi API**. It is not a user-tutoring course. It gives the agent focused, reusable operating procedures for API integration, STAC search, download pipelines, debugging, tests, and product/collection mapping.

## Install

Copy the `.agents` directory from this archive into the root of your repository, merging it with any existing `.agents` directory. The skill folders should end up at:

```text
your-project/.agents/skills/
```

Antigravity's current documentation identifies `.agents/skills/<skill-folder>/SKILL.md` as the workspace-level location. The older `.agent/skills` path remains supported, but `.agents/skills` is the recommended default.

## Skills included

- `bhoonidhi-api-engineer`: overall API integration and codebase integration; includes the API reference.
- `bhoonidhi-stac-search`: STAC collections/items, search queries, spatial and temporal filters, CQL2, pagination.
- `bhoonidhi-download-pipeline`: online-only downloads, streaming, concurrency, retry policy, and file integrity.
- `bhoonidhi-api-debugger`: diagnose authentication, search, pagination, and download failures from evidence.
- `bhoonidhi-api-test-engineer`: mocks, regression tests, fixtures, and failure-path coverage.
- `bhoonidhi-product-mapping`: resolve user-facing product requests into verified collection IDs / product types, including maintenance of functions such as `resolve_product_types`.

Each skill is independently triggerable. Antigravity can load the focused skill relevant to a task rather than loading one giant instruction file every time.

## Use

After copying the folder, start with a task like:

> Inspect the existing Bhoonidhi fetcher and use the relevant `bhoonidhi-*` skills. Map the current flow, identify concrete gaps, implement the highest-value fixes without rewriting unrelated code, run tests, and report what was verified versus what remains unverified.

No live API test is required for ordinary unit tests. Never commit credentials or tokens. A live end-to-end run requires valid user credentials and should be reported separately from mocked tests.
