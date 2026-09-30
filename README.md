# C++ Project Foundation

[简体中文](https://github.com/HoneyBury/cpp-project-foundation/blob/main/README.zh-CN.md)

Create a ready-to-build C++ service project with one command. The generated project
includes sample code, tests, CMake and Conan settings, GitHub Actions, release packaging,
and optional deployment tools.

This project is a starter kit and command-line tool. It does not decide how your service
should work, choose a database, or deploy anything without an explicit command.

## Is this for me?

Use it when you want:

- a new C++20 service that builds the same way locally and in GitHub Actions;
- tests, formatting and common safety checks set up from the beginning;
- a repeatable release package with a checksum and a software inventory;
- optional commands for deployment, rollback, backup and operational records.

The supported production setup is Ubuntu 24.04 on x86-64 with GCC 13. You can inspect or
generate projects on other systems, but production builds should use the supported setup.

## Quick start

Creating a project requires Python 3.11 or newer and
[`pipx`](https://pipx.pypa.io/stable/). Building it also requires GCC 13, CMake, Ninja and
Conan. The [step-by-step guide](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/getting-started.md) includes the installation commands.

Install the tool from PyPI:

```bash
pipx install "cpp-project-foundation==0.6.0"
cpp-foundation --help
```

Create a project. The output directory must not already exist:

```bash
cpp-foundation init \
  --name order-service \
  --version 0.1.0 \
  --output ../order-service
cd ../order-service
```

Check the generated files:

```bash
cpp-foundation validate
cpp-foundation doctor --root .
```

`validate` checks `foundation.toml`. `doctor` explains which files and tools are ready and
which optional tools are missing. A warning that the service has not been built yet is
normal at this point.

Continue with [Build and run your first project](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/getting-started.md#6-build-and-run).

## What gets created?

| Path | Purpose |
| --- | --- |
| `src/`, `include/` | Example application code to replace with your own code |
| `tests/` | A small test and the place for new tests |
| `CMakeLists.txt` | Build targets and compiler settings |
| `conanfile.py`, `conan/` | Third-party dependencies and their fixed versions |
| `foundation.toml` | Project name, build targets, release files and operation commands |
| `.github/workflows/` | Automated build, test, security and release jobs |
| `deploy/` | Optional Docker Compose and systemd examples |
| `quality/` | Time, size and coverage limits used by checks |

The generated directory is your project. You may edit it normally. The tool never silently
replaces application code or changes a limit after a failed check.

## Commands you will use most

Run these commands from the generated project directory:

| Command | When to use it |
| --- | --- |
| `cpp-foundation validate` | After editing `foundation.toml` |
| `cpp-foundation doctor --root .` | When setting up a machine or diagnosing a project |
| `cpp-foundation quality --root . --mode fast` | Before each pull request |
| `cpp-foundation template-diff --root .` | Before upgrading the foundation version |
| `cpp-foundation package --output-dir dist` | After a successful release build |
| `cpp-foundation verify-release ...` | Before installing or publishing a release archive |

Quality tools have a one-time installation step. Deployment and backup commands also need
some preparation. Follow the linked guide instead of copying an isolated command:

- [First project: install, build, test and run](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/getting-started.md)
- [Maintain a generated project](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/maintenance.md)
- [Release, deploy, recover and back up](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/operations.md)

## A few terms used in the documentation

- **Manifest:** `foundation.toml`, the small file that tells the tool about your project.
- **Lockfile:** a file that records exact dependency versions so later builds use the same
  inputs.
- **Workflow:** an automated GitHub Actions job.
- **Evidence:** a JSON result or package kept to show what a check actually did.
- **SBOM:** a list of the files and third-party packages in a release.

## Documentation

Start at the [documentation index](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/README.md), which separates guides by audience:

- new users;
- people maintaining a generated project;
- production operators;
- contributors maintaining this foundation repository.

For version support and upgrades, see [compatibility](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/compatibility.md) and
[migration notes](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/migrations.md).

## Important limits

- Generated monitoring and deployment files are examples. Review host names, storage,
  credentials and access rules before production use.
- Application data, credentials and backups must stay outside release directories.
- Passing the included checks does not by itself prove high availability, capacity or
  disaster recovery.
- Long eight-hour checks need a reliable self-hosted GitHub Actions runner. Short checks
  use GitHub-hosted runners by default.

To report a security issue, follow [SECURITY.md](https://github.com/HoneyBury/cpp-project-foundation/blob/main/SECURITY.md). To change this repository,
follow [CONTRIBUTING.md](https://github.com/HoneyBury/cpp-project-foundation/blob/main/CONTRIBUTING.md).
