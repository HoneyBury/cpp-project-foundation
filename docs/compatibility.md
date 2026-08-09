# Compatibility and Support Policy

[简体中文](compatibility.zh-CN.md)

## Supported baseline

The following combination is continuously exercised and is the only production baseline
for the 0.3 release line:

| Layer | Supported baseline |
| --- | --- |
| Host and release artifact | Ubuntu 24.04, Linux x86-64 |
| Language | C++20 |
| Build | CMake 3.21 or newer, Ninja |
| Compilers | GCC 13; Clang 18 compatibility and analysis |
| Dependencies | Conan 2.8.1, project-owned profiles and lockfiles |
| Automation | GitHub-hosted `ubuntu-24.04` runners |
| Python CLI | CPython 3.11 or newer |

Other platforms and versions are extension profiles. They require native build,
performance and operations evidence and do not inherit support from this matrix. In
particular, macOS is suitable for development and orchestration but does not produce a
supported Linux release artifact.

## Ownership boundary

| Foundation owns | Consuming project owns |
| --- | --- |
| Reusable workflow contracts and pinned Actions | Workflow tag selected by the project |
| Default compiler, quality and security policy | Application source, behavior and tests |
| Generated quality configuration and Conan profiles | Conan dependency graph and lockfile |
| Archive, provenance, SBOM and deployment formats | Release version and rollout approval |
| Transaction, backup and evidence mechanics | Health, canary, benchmark and backup hooks |
| Reference Compose, systemd and monitoring assets | Production credentials, hosts and SLOs |

`cpp-foundation template-diff` compares only foundation-owned generated files. It never
rewrites application source, the manifest, dependency lockfiles, deployment policy or
performance budgets.

## Version and support lifecycle

- Release tags are immutable and consumers pin an explicit semantic version.
- During `0.x`, a minor release may change a generated or reusable contract; every such
  change must have a migration entry. Patch releases remain backward-compatible fixes.
- The latest minor receives fixes. Older minors remain downloadable but do not receive a
  separate security or maintenance branch.
- Deprecations are documented for at least one minor before removal unless retaining the
  behavior would leave a known security or integrity failure.
- Ubuntu LTS major changes are reviewed as explicit compatibility work and are ignored by
  automated Docker major-version updates.

Consumers should evaluate upgrades with `doctor`, `template-diff`, their required pull
request gates and at least the operations smoke profile before changing the pinned tag.
