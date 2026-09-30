# Documentation

[简体中文](README.zh-CN.md)

Choose the guide that matches what you are doing. You do not need to read every document
before creating a project.

## New users

1. Read [Getting started](getting-started.md) to install the tools, create a project,
   build it and run its test.
2. Keep [Maintaining a project](maintenance.md) nearby for normal development work.
3. Read [Operations](operations.md) only when you are ready to package or deploy a service.

## Project owners

- [Compatibility](compatibility.md) lists the supported operating system and tool versions.
- [Migration guide](migrations.md) explains what to check when moving to a newer foundation
  version.
- [Foundation contract](foundation-contract.md) describes which files the toolkit manages
  and which decisions remain with the application team.

## Production operators

- [Operations](operations.md) covers release checks, deployment, rollback, recovery,
  backups and retained records.
- [Architecture](architecture.md) gives a short picture of how build, release and deployment
  steps connect.

## Foundation repository maintainers

- [Contributing](../CONTRIBUTING.md) explains the local checks and pull-request process.
- [Python publishing](publishing.md) explains the GitHub Release and PyPI publishing flow.
- [Security policy](../SECURITY.md) explains how to report a vulnerability.

## Quick glossary

| Term | Plain meaning |
| --- | --- |
| Manifest | The `foundation.toml` project settings file |
| Lockfile | Exact third-party dependency versions used by the build |
| Workflow | An automated GitHub Actions job |
| Hook | A command supplied by the application, such as its health check |
| Evidence | A saved JSON result or archive showing what a check did |
| SBOM | A list of software included in a release |
