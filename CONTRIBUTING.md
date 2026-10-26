# Contributing to TalentGraph

This document describes how work is organized in this repository: branches, commits and pull requests.

## Branches

```
main              stable version (the one that gets cloned and deployed)
  └── develop     integration branch: finished and tested work
        └── feature/<module>-<topic>   one branch per module or task
```

- Always start new work from `develop`:
  ```bash
  git checkout develop
  git pull
  git checkout -b feature/m1-ingestion
  ```
- Branch names: `feature/<module>-<topic>`, lowercase, words separated by `-`.
  Examples: `feature/m0-infra`, `feature/m1-ingestion`, `feature/m4-hybrid-search`.
- Bug fixes on already merged work: `fix/<module>-<topic>`.
- Never commit directly to `main`.

## Commit messages

Format (based on [Conventional Commits](https://www.conventionalcommits.org/)):

```
type(scope): short description
```

### Types

| Type       | Use for                                                        |
| ---------- | -------------------------------------------------------------- |
| `feat`     | a new feature (service, endpoint, agent, model)                |
| `fix`      | a bug fix                                                      |
| `chore`    | configuration and maintenance (gitignore, dependencies, setup) |
| `docs`     | documentation (README, decisions, learning log)                |
| `refactor` | code restructuring without behavior change                     |
| `test`     | adding or updating tests                                       |
| `ci`       | continuous integration (GitHub Actions)                        |

### Scopes

The project module: `m0` to `m8`, or `v2`. The scope can be omitted for cross-cutting changes.

| Scope | Module                              |
| ----- | ----------------------------------- |
| `m0`  | Base infrastructure (Docker Compose)|
| `m1`  | France Travail ingestion            |
| `m2`  | Schema and indexing                 |
| `m3`  | API, form and CV parser             |
| `m4`  | Hybrid search (baseline)            |
| `m5`  | Agents, modes 1 and 2               |
| `m6`  | Model fine-tuning                   |
| `m7`  | Frontend                            |
| `m8`  | Deployment and README               |
| `v2`  | Writing modes, critic agent, MCP    |

### Rules

- Written in English, in the imperative present: "add", not "added" or "adding".
  The message should complete the sentence "This commit will ...".
- Lowercase, no final period, 72 characters maximum.
- One commit = one logical change.
- Reference the GitHub issue when there is one: `(#2)`.

### Examples

```
chore(m0): init project structure and gitignore
feat(m0): add postgres service to docker compose
feat(m0): add elasticsearch service with memory limit
feat(m1): fetch offers from france travail api (#2)
fix(m1): handle expired oauth token
docs(m0): add setup instructions to readme
refactor(m4): extract hybrid query builder
test(m5): add tests for skill gap computation
```

## Pull requests

- `feature/*` → `develop` when a module or task is done.
- `develop` → `main` when `develop` is stable (end of week, before a delivery).
- Title: `M<n>: short summary`, for example `M0: infrastructure (postgres, redis, elasticsearch)`.
- Description: what was done, how to test it, what was learned or decided
  (decisions go in `docs/decisions.md`).
- Before opening a pull request, re-read the diff: every line should be explainable.

## Secrets

- Never commit `.env`. Only `.env.example` (variable names without values) is versioned.
- Check with `git status` before every commit.
