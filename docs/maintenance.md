# Maintaining a Generated Project

[简体中文](maintenance.zh-CN.md)

This guide is for the person who owns a project created by `cpp-foundation init`. It covers
normal code changes, dependency updates and foundation upgrades. Production deployment is
covered separately in [Operations](operations.md).

## Before each pull request

Use this short checklist:

1. Add or update tests for the behavior you changed.
2. Build the affected targets and run `ctest`.
3. Run the fast source checks.
4. Check the manifest if you changed build, release or operation settings.
5. Review `git diff` before pushing.

```bash
cmake --build build/release --parallel
ctest --test-dir build/release --output-on-failure
cpp-foundation quality --root . --mode fast
cpp-foundation validate
git diff --check
```

Run the deep checks when changing CMake files, Docker files, documentation or shared
quality settings:

```bash
cpp-foundation quality --root . --mode deep
```

Do not lower a coverage, performance or warning limit only because a change failed. First
understand the failure. If a limit really needs to change, explain why in the pull request.

## Changing C++ dependencies

The dependency name and requested version live in `conanfile.py`. The lockfile under
`conan/locks/` records the exact version and revision used by the build.

When intentionally changing a dependency:

1. Edit `conanfile.py`.
2. Create a new lockfile using the supported profile.
3. Install from that lockfile and run the full build and tests.
4. Commit `conanfile.py` and the lockfile together.

Example for the GCC profile:

```bash
export CC=gcc-13
export CXX=g++-13
conan lock create . \
  --profile:host conan/profiles/linux-gcc-x64 \
  --profile:build conan/profiles/linux-gcc-x64 \
  --lockfile-out conan/locks/linux-gcc-x64-release.lock
conan install . \
  --profile:host conan/profiles/linux-gcc-x64 \
  --profile:build conan/profiles/linux-gcc-x64 \
  --lockfile conan/locks/linux-gcc-x64-release.lock \
  --output-folder=build/conan \
  --build=missing
```

Never delete the lockfile just to make a dependency error disappear. That would allow a
later build to choose different inputs without review.

## Editing `foundation.toml`

The manifest connects project-specific names and commands to the generic tooling. After
editing it, run:

```bash
cpp-foundation validate
cpp-foundation doctor --root .
```

The main sections are:

| Section | What it controls |
| --- | --- |
| `[project]` | Project name and release version |
| `[build]` | CMake targets, Conan profile and lockfile |
| `[release]` | Programs and extra files placed in a release |
| `[operations]` | Commands used to start, check and stop the service |
| `[observability]` | Health and metrics URLs used by optional checks |

Keep passwords, tokens and private keys out of this file. Operation commands should read
credentials from the host's secret store or environment at runtime.

## Updating the project version

The version appears in `foundation.toml`, `CMakeLists.txt` and `conanfile.py`. Update all
three in the same pull request. `doctor` and the release job catch many mismatches, but a
single reviewed change is easier to understand.

Use normal semantic versions such as `1.4.2`:

- increase the last number for a compatible fix;
- increase the middle number for a compatible feature;
- increase the first number for a breaking change after the project reaches `1.0.0`.

## Upgrading cpp-project-foundation

An upgrade should be a separate pull request. Do not regenerate directly over the working
project.

1. Read the relevant [migration notes](migrations.md).
2. Install the target CLI version with `pipx install --force`.
3. Run `doctor` and `template-diff` in the existing project.
4. Generate a temporary project with the same project name and application version.
5. Copy only the reviewed foundation changes you want to adopt.
6. Change every workflow reference to the same foundation tag.
7. Run fast checks, deep checks and the normal build before merging.

```bash
target_version="0.7.0"
pipx install --force "cpp-project-foundation==$target_version"
cpp-foundation doctor --root .
cpp-foundation template-diff --root .
cpp-foundation init \
  --name order-service \
  --version 0.1.0 \
  --output /tmp/order-service-new-template
```

`template-diff` is read-only. It tells you what differs but never gives permission to
overwrite application code, dependency choices or project-specific limits.

## Keeping GitHub Actions healthy

- Keep all foundation workflow references on one version, such as `v0.6.0`.
- Keep third-party Actions fixed to the full commit shown by the template.
- Review Dependabot pull requests like normal code changes; do not merge all updates at
  once without checking their jobs.
- Investigate a failed job before rerunning it. Repeated reruns can hide a real flaky test.
- Use a stable self-hosted runner only for the optional eight-hour check. Normal checks run
  on GitHub-hosted Ubuntu runners.

## Files that need special care

- Do not hand-edit generated build output under `build/`.
- Do not commit `.venv/`, `.conan2/`, `.tools/`, `runtime/` or secrets.
- Do not place application data or backups under a release directory.
- Do not replace an existing release tag or published package version. Publish a new
  version instead.

## When a check fails

Start with the smallest command that reproduces the problem locally. Read the first useful
error, not only the final summary. Useful diagnostics are:

```bash
cpp-foundation doctor --root . --strict-tools
ctest --test-dir build/release --output-on-failure
cpp-foundation quality --root . --mode fast
git status --short
```

If the issue is in this toolkit rather than your application, include the CLI version,
operating system, failing command and a short sanitized error in the bug report. Never
include credentials or private production details.
