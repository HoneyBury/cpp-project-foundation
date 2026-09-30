# How the Pieces Fit Together

[简体中文](architecture.zh-CN.md)

This page gives maintainers a simple picture of the toolkit. New users can skip it until
they have built the example in [Getting started](getting-started.md).

## The normal path

```text
foundation.toml
      |
      v
build and test -----> release archive + checksum
      |                         |
      v                         v
GitHub checks             install release
                                |
                                v
                         activate and verify
                                |
                       failure: restore old release
                       interruption: run recover
```

`foundation.toml` supplies project-specific names and commands. The Python tool reads that
file and performs the same general steps for every generated project.

## What the toolkit handles

- creating the initial folder and example files;
- checking that project settings refer to valid files and targets;
- running fixed source-quality tools;
- creating and verifying a release archive;
- recording which source commit and dependencies produced a release;
- switching between installed releases and keeping transaction records;
- creating verifiable backup and operation records.

## What the application team handles

- business behavior, APIs and data storage;
- useful tests and a meaningful health check;
- dependency choices and lockfile updates;
- production hosts, credentials and access rules;
- data migration, capacity, availability and disaster-recovery plans;
- the final decision to release or roll back.

The boundary is intentional: a generic tool can check that a health command succeeded,
but only the application team can define what “healthy” really means.

## Automated checks

Pull requests run the common, reasonably fast checks: build, tests, source formatting,
compiler warnings, selected code analysis and coverage. Slower checks run on a schedule or
when requested. They examine areas such as Docker files, documentation and repeat builds.

The settings live in the repository. A workflow does not automatically lower a limit after
a failure.

## Release contents

A release contains only the declared runtime program and files. It also includes:

- a manifest listing every file, size and SHA-256 value;
- the source commit and build information;
- an SPDX software inventory;
- a stable digest of the runtime payload.

The verifier rejects extra files, missing files, changed file modes, unsafe archive paths
and mismatched checksums.

## Deployment state

The default layout separates immutable releases from mutable transaction records:

```text
/opt/<project>/releases/<deployment-id>/
/opt/<project>/deployments/<deployment-id>/record.json
/opt/<project>/current -> deployments/<deployment-id>
/opt/<project>/previous -> deployments/<deployment-id>
/var/lib/<project>/transactions/<transaction-id>/record.json
```

Only one deployment command can change state at a time. Pointer changes are atomic. If a
candidate fails its checks, the old release is restored. If the process stops halfway,
later activation is blocked until an operator runs `deploy recover`.

Application data is deliberately absent from this layout and must be managed separately.
