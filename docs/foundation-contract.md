# Responsibilities and Safety Rules

[简体中文](foundation-contract.zh-CN.md)

This document explains the agreement between the generic toolkit and each generated
application. It is mainly useful when adding custom build targets, release files or
operation commands.

## Supported setup

Version 0.7 is tested for this production setup:

- Ubuntu 24.04 on x86-64;
- C++20 with GCC 13;
- Clang 18 for extra compatibility and analysis checks;
- CMake 3.21 or newer, Ninja and Conan 2.8.1;
- GitHub Actions using `ubuntu-24.04` runners;
- Python 3.11 or newer for the command-line tool.

Other systems may work for development, but they need their own build and operation tests
before being treated as production-ready.

## What every project must provide

1. A CMake target for the service program.
2. A CMake target registered with CTest.
3. A Conan profile and a project-owned lockfile.
4. At least one program to place in the release archive.
5. A `verify` command that fails when the service is unhealthy.
6. Application-specific canary and benchmark commands before enabling those optional jobs.

These names and commands are recorded in `foundation.toml`.

## Operation command rules

During deployment, operation commands run from the extracted release directory. They
receive `FOUNDATION_RELEASE_DIR` with that directory's path.

Commands should be safe to retry. In particular, starting an already running service or
stopping an already stopped candidate should not damage data.

Do not put credentials in `foundation.toml`, command arguments, release files or JSON
summaries. Read them from a host-managed secret store or protected environment at runtime.

## Release safety rules

- Packaging uses one clean, reviewed Git commit.
- Every runtime file is listed with its size, executable setting and SHA-256 value.
- The separate archive checksum must be supplied during deployment installation.
- Extra files, missing files, links and unsafe paths are rejected.
- The software inventory must agree with the actual release files.

A stable runtime-payload digest helps compare two builds. The complete archive can still
differ because it records the build time and runner details.

## Operational record rules

- Records are create-only; an existing record is not silently replaced.
- Referenced summaries are copied to names based on their content.
- Verification rejects changed content, unsafe paths, links, special files and unrelated
  files inside the evidence directory.
- A local evidence package is not considered safely retained until another host or storage
  system has copied and verified it.

## What this toolkit does not promise

- It does not implement an application protocol, database or service discovery.
- It does not prove multi-host high availability or disaster recovery.
- It does not decide production capacity or acceptable response time.
- It does not share one dependency lockfile between unrelated projects.
- It does not deploy an unreviewed branch automatically.
- It does not lower a limit or ignore a failed check to make a build pass.
