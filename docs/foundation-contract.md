# Foundation Contract

## Goal

Provide a repeatable C++ service baseline whose build, dependency graph, security gates,
release identity and operations evidence can be independently reproduced. Application
behavior remains outside the foundation and enters only through declared hooks.

## Supported profile

Version 0.2 supports Ubuntu 24.04 x86-64, GCC 13, Clang 18 analysis and compatibility
builds, C++20, CMake 3.21 or newer, Ninja, Conan 2.8.1 and GitHub Actions. Other compilers
and platforms require their own profile, lockfile and native evidence; results are never
substituted across platforms.

Every generated project receives pinned source formatting and analysis configuration.
Pull requests must pass format, Ruff, ShellCheck, actionlint, compiler warning, clang-tidy
and coverage gates. Deep scheduled evidence adds IWYU, cppcheck, Dockerfile/documentation
lint, clean-build time, binary size and repeated-build digest checks. These analysis options
must not be enabled in the production Release configuration.

## Required application contract

Every project supplies:

1. one CMake production target and one CTest target;
2. a Conan host/build profile and project-owned lockfile;
3. at least one release executable;
4. a fail-closed verification command;
5. explicit canary and benchmark commands before enabling P2 gates.

Hooks receive `FOUNDATION_RELEASE_DIR` during deployment and execute with the immutable
release directory as their working directory. Hook credentials remain host-managed and
must not be present in the manifest, release archive, summaries or command arguments.

## Evidence contract

Release evidence binds project/version, exact Git commit, candidate revision, workflow,
run, runner OS/architecture, build configuration and Conan lockfile SHA-256. A candidate
that does not match checkout fails packaging verification.

Operational records are create-only. Referenced summaries are copied into a
content-addressed raw directory before a record is committed. Rewriting a fixed summary
path cannot mutate historical records.

## Non-goals

- no application protocol, database or service discovery implementation;
- no claim of multi-node HA or disaster recovery;
- no shared lockfile between unrelated projects;
- no automatic production deployment from an unreviewed branch;
- no hidden maintenance exclusion or threshold relaxation.
