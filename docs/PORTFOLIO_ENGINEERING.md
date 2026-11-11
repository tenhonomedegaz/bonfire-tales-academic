# Engineering portfolio: Bonfire Tales RPG

This page is a recruiter-oriented technical overview of the **public academic snapshot**, not a claim that the entire production system or every planned capability is complete.

## Problem and approach
Bonfire Tales is a Django/PostgreSQL web platform supporting a tabletop RPG community. The application has character records and progression, rule catalogs, missions and community administration. Its architecture explores declarative rules through tags and generic rule readers rather than hard-coding each class or ability.

## Relevant engineering areas
- **Python and Django:** routes, services, model validation, permissions, migrations and business rules.
- **PostgreSQL and data integrity:** relational models, versioned content, transactional updates and historical records.
- **REST-style APIs and integrations:** scoped administrative access, audited operations and third-party integrations. The public snapshot excludes credentials and real records.
- **Debugging and QA:** issue inventory, reproducible test cases, focused regression suites and known limitations.
- **Development with AI assistance:** the project includes AI-assisted development. A coding agent's output is not proof of correctness: requirements, constraints, review and tests still apply.

## Example architectural challenge
Character progression has to reconcile rule versions, eligibility, UI previews, backend validation and the recorded progression history. A fix in one screen is not sufficient without checking other consumers. The published [maintenance context](docs/academic/CONTEXTO_PARA_ORIENTACAO.md) documents how to trace the relevant code path and minimize regression risk.

## What is deliberately **not** claimed
- The project is **in development**, with tracked pending features and bugs. See [PENDENCIAS.md](PENDENCIAS.md).
- Not every feature is reproducible from this copy: catalogs, production data, the external bot and integrations were deliberately excluded.
- Passing a focused test batch is not equivalent to proving full-system reliability or production readiness.
- Development involved other collaborators and AI assistance; this repository is not evidence that one person wrote every component.

## Technical walkthrough
1. Read the [main README](../README.md) (this document lives under `docs/`).
2. Read [technical orientation](academic/CONTEXTO_PARA_ORIENTACAO.md) and [snapshot provenance](academic/SNAPSHOT.json).
3. Inspect `home/character_engine.py`, `home/gestao/`, `home/db_access_api.py`, and the related tests in the repository.
4. Use synthetic input and isolated tests only; do not connect a public checkout to production systems.

This overview can be used in interview discussions about **problem decomposition, guiding AI coding tools, reviewing generated changes, preserving invariants and validating behavior**. Specific individual contributions should be explained with their actual PRs, commits or work records.
