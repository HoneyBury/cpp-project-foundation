# Supported Versions

[简体中文](compatibility.zh-CN.md)

This page answers two questions: which setup is regularly tested, and who is responsible
for each part of a generated project.

## Regularly tested setup

The 0.7 release line supports this production setup:

| Part | Supported version |
| --- | --- |
| Host and release files | Ubuntu 24.04, Linux x86-64 |
| C++ | C++20 |
| Build tools | CMake 3.21 or newer and Ninja |
| Compilers | GCC 13; Clang 18 for extra checks |
| C++ dependencies | Conan 2.8.1 with a project-owned lockfile |
| GitHub Actions | GitHub-hosted `ubuntu-24.04` runner |
| Command-line tool | Python 3.11 or newer |
| Source-quality tools | Node.js 22 or newer and npm |

Other versions may work, but this repository does not test them continuously. Before using
a different compiler, operating system or processor in production, run its build, tests,
performance checks and deployment drill on that real platform.

macOS is useful for editing code and running some commands, but it does not create a
supported Linux production release.

## Who owns what?

| Foundation toolkit provides | Your project team decides and maintains |
| --- | --- |
| Reusable GitHub Actions jobs | Which foundation version the project uses |
| Default compiler and source checks | Application code, behavior and tests |
| Starter quality settings and Conan profiles | Dependencies and the lockfile |
| Release and deployment file formats | Application version and release approval |
| Transaction, backup and evidence commands | Health, benchmark and backup commands |
| Example Docker, systemd and monitoring files | Production hosts, credentials and goals |

`cpp-foundation template-diff` only reports changes in foundation-owned starter files. It
does not overwrite application code, `foundation.toml`, lockfiles or project-specific
limits.

## Version policy

- Every release has an immutable version tag. Projects should use an exact tag.
- Before version `1.0.0`, a new middle number may require changes in generated projects.
  Those changes are listed in the [migration guide](migrations.md).
- A change to only the last number is intended to be a compatible fix.
- The newest minor release receives fixes. Older releases remain downloadable but do not
  have separate maintenance branches.
- A feature is normally announced as deprecated for at least one minor release before
  removal. An unsafe behavior may be removed sooner.
- Moving to a new Ubuntu release is a reviewed project change, not an automatic update.

Before changing the version used by an existing project, follow
[Maintaining a generated project](maintenance.md#upgrading-cpp-project-foundation).
