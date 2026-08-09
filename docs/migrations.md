# Migration Guide

[简体中文](migrations.zh-CN.md)

Consumer upgrades are pull-request changes. Never bulk-replace a workflow tag directly on
the protected default branch.

## Upgrade procedure

1. Install the target foundation tag in an isolated environment.
2. Run `cpp-foundation doctor --root .` and record warnings that are intentional.
3. Run `cpp-foundation template-diff --root .` to identify foundation-owned drift.
4. Generate a temporary project with the same name and version, then selectively apply
   reviewed changes. Do not overwrite application files or the Conan lockfile.
5. Change every foundation workflow reference to the same target tag.
6. Run fast CI and quality gates, deep quality, security and operations smoke.
7. Merge through branch protection. Run a release dry-run before the next production tag.

## 0.2.1 to 0.2.2

- Reusable jobs now set `CONAN_HOME` consistently for setup and build steps.
- The quality workflow separates its Clang analysis profile from the GCC coverage profile.
- Add `coverage-profile: conan/profiles/linux-gcc-x64` to the quality workflow if it is not
  already present.

## 0.2.2 to 0.2.3

- Generated CMake formatting is deterministic even when `cmake-format` is unavailable.
- Regenerate a temporary project and adopt the normalized multiline CMake commands once.
  This is a source-only formatting change and must not alter targets or build behavior.

## 0.2.3 to 0.3.0

- Install the new CLI and run `doctor` before changing workflow references.
- Use `template-diff` to review generated quality-asset drift. A non-zero result is an
  inventory, not permission to overwrite consumer-owned files.
- `bootstrap_github.py` defaults to zero required approvals for a single-maintainer public
  repository. Teams should pass `--required-approvals 1` or higher explicitly.
- `--required-check` is repeatable. Supply the exact check contexts reported by GitHub.
- Ubuntu Docker major updates are intentionally ignored; platform upgrades require a new
  compatibility evidence set.

There is no manifest schema migration in 0.3.0; `schema_version = 1` remains current.

## 0.3.0 to 0.3.1

No generated or manifest migration is required. Version 0.3.1 replaces the non-portable
downloadable wheel checksum from 0.3.0; update foundation workflow and installation tags.

## 0.3.1 to 0.4.0

- Add the generated `.github/dependabot.yml`. It tracks reusable Actions and pinned Python
  tools while keeping Docker updates on the supported Ubuntu 24.04 release line.
- Operations jobs now publish a Markdown summary in addition to the existing JSON evidence;
  no manifest or evidence schema migration is required.
- PyPI publishing is optional and requires the external trusted-publisher configuration in
  [publishing.md](publishing.md). GitHub tag installation remains supported.
