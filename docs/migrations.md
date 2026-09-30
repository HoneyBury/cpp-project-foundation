# Migration Guide

[简体中文](migrations.zh-CN.md)

This page is only for projects that already use an older foundation version. New projects
can skip it. Perform an upgrade in its own pull request so the template changes are easy to
review and undo.

## Upgrade procedure

1. Read the notes below for every version between the current and target versions.
2. Install the target CLI version with `pipx install --force`.
3. Run `doctor` and `template-diff`; both commands are safe to run before editing files.
4. Generate a temporary project with the same name and application version.
5. Compare the temporary project with the real project. Copy only reviewed changes and do
   not overwrite application code or the Conan lockfile.
6. Change every foundation workflow reference to the same target tag.
7. Run the normal build, fast checks, deep checks and an operations smoke test.
8. Merge through the project's normal review process, then run a release dry-run.

The full procedure and example commands are in
[Maintaining a generated project](maintenance.md#upgrading-cpp-project-foundation).

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

## 0.4.0/0.4.1 to 0.5.0

- Manifest schema version remains 1, but validation is now strict. Remove unknown fields
  and ensure `build.fuzz_targets`, `release.executables`, `release.include` and operation
  commands are arrays of non-empty strings.
- `operations.hook_timeout_seconds` must be positive. Observability URLs must be absolute
  HTTP(S) URLs and `prometheus_retention_days` must be a positive integer.
- Deployment installation now requires `--checksum`. Transport the generated `.sha256`
  file separately from the archive and update host automation before upgrading the CLI.
- Release verification rejects unlisted files, duplicate archive members and executable
  mode drift. Rebuild release archives with 0.5.0 rather than repacking an older archive.
- Update every reusable workflow reference to `v0.5.0`, then run `doctor`,
  `template-diff`, the full PR gates and an operations smoke profile.

## 0.5.0 to 0.6.0

- Manifest and evidence schema versions remain 1; no data rewrite is required.
- Add `deploy recover` to host runbooks. An interrupted `started` transaction now blocks
  activation, upgrade and rollback until recovery restores the pre-transaction release.
- Evidence packaging now accepts only files referenced by its records. Remove unrelated
  files and links from an evidence root, and investigate rather than overwrite a corrupt
  content-addressed file.
- Release manifests now include a deterministic runtime payload digest. Full archive bytes
  may differ when build-run details or the software-list creation time differs.
- `doctor --probe-observability` performs opt-in HTTP checks of configured health and
  metrics URLs; default `doctor` remains network-free.
- Update every reusable workflow reference to `v0.6.0`, then run the full PR gates and an
  operations smoke profile.

## 0.6.0 to 0.7.0

- Manifest schema version remains 1. Project versions are now checked as full Semantic
  Versions, and project names that become C++ keywords are rejected. Existing valid
  projects do not need a manifest rewrite.
- Add `CMakePresets.json`, `CONTRIBUTING.md`, `SECURITY.md`, the CODEOWNERS starter, pull
  request template and `scripts/bootstrap_github.py` from a temporary 0.7.0 project.
- Add the `push` trigger for `main` to generated `ci.yml` and `quality.yml`. Configure branch
  protection separately after GitHub reports the exact required check names.
- Review and adopt the real `--healthcheck` implementation and Docker Compose health check.
  Keep `--check` for an executable-only smoke check and use `--healthcheck` for a running
  service.
- `template-diff` now reports workflow, deployment and governance-file changes. A reported
  change may be an intentional project customization; review it instead of overwriting it.
- Choose and review the project license. Existing projects are not automatically relicensed.
- Update every reusable workflow reference to `v0.7.0`, then run the full PR gates, a
  generated-project build and an operations smoke profile.
