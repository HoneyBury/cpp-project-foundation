# Contributing

Thank you for improving C++ Project Foundation. This guide is for changes to this
repository. If you maintain a project created by the tool, use the
[project maintenance guide](docs/maintenance.md) instead.

## Before you start

- Use Python 3.11 or newer.
- Create a branch from the latest `main`.
- Keep one pull request focused on one problem.
- Do not include credentials, private host names or production data.

For a larger behavior change, open an issue first so the expected result can be agreed on
before implementation.

## Set up the repository

From the repository root:

```bash
python3 scripts/bootstrap_dev.py
source .venv/bin/activate
python3 scripts/install_quality_tools.py \
  --venv .venv/quality \
  --tools-dir .tools
export PATH="$PWD/.venv/quality/bin:$PWD/.tools/bin:$PWD/.tools/npm/node_modules/.bin:$PATH"
```

The first script installs this repository in an isolated Python environment. The second
installs the fixed tool versions used by source checks.

## Make a change

- Add or update a focused test when behavior changes.
- Update English and Simplified Chinese docs together when they describe the same feature.
- Keep generated examples and reusable workflows on the same foundation version.
- Add a migration note when a user must change an existing project.
- Include a safe rollback or recovery note for release, deployment, backup or evidence
  changes.

Do not weaken a check simply to make a failure disappear. If a rule genuinely needs to
change, explain the reason in the pull request.

## Run the checks

For every change:

```bash
cpp-foundation quality --root . --mode fast
python3 -m coverage run -m unittest discover -s tests -v
python3 -m coverage report
python3 scripts/check_repository.py
python3 -m foundation \
  --manifest examples/hello-service/foundation.toml \
  validate
```

Run the deep checks after changing CMake, Docker, shell scripts, workflows or documentation:

```bash
cpp-foundation quality --root . --mode deep
```

Before submitting, confirm that `git status --short` contains only the intended files and
that `git diff --check` prints nothing.

## Open the pull request

In the description, state:

- what was confusing or broken;
- what changed;
- how you tested it;
- whether an existing user needs to take action.

All required GitHub checks must pass. Resolve review comments instead of bypassing branch
rules. A maintainer handles version tags, GitHub Releases and PyPI publishing after the
change is merged.
