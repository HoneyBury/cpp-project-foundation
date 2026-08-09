# C++ Project Foundation

[English](README.md) | [简体中文](README.zh-CN.md)

`cpp-project-foundation` is a manifest-driven engineering foundation for C++ services.
It extracts reusable build, dependency, security, release, deployment and operations
contracts without importing any product-specific service topology.

The first supported production profile is deliberately narrow:

- Ubuntu 24.04 x86-64
- GCC 13, C++20, CMake, Ninja and sccache
- Conan 2.8.1 with project-owned profiles and lockfiles
- one independently deployable service per generated project
- GitHub-hosted Actions runners by default, with optional self-hosted runners for long gates

Multi-service orchestration, application protocols, databases, SDK generation and cloud
platform policy are extension points, not hidden assumptions in the foundation core.

## Create a project

Clone this repository and generate a service from the maintained reference template:

```bash
python3 -m venv .venv/foundation
.venv/foundation/bin/pip install -e .
.venv/foundation/bin/cpp-foundation init \
  --name order-service \
  --version 0.1.0 \
  --output ../order-service
```

The generated project owns its `foundation.toml`, Conan graph and lockfile. Review the
manifest, regenerate the lockfile for the approved dependency graph, and then enable the
reusable CI workflow.

## Manifest

`foundation.toml` is the boundary between the generic platform and application code. It
declares build targets, release inputs and fail-closed operation hooks. The toolkit never
guesses service names or rewrites thresholds after observing a failure.

```toml
schema_version = 1

[project]
name = "order-service"
version = "0.1.0"

[build]
target = "order_service"
test_target = "order_service_tests"
profile = "conan/profiles/linux-gcc-x64"
lockfile = "conan/locks/linux-gcc-x64-release.lock"

[release]
executables = ["build/release/bin/order-service"]
include = ["deploy"]

[operations]
activate = ["docker", "compose", "-f", "deploy/docker-compose.yml", "up", "-d"]
verify = ["sh", "deploy/verify.sh"]
deactivate = ["docker", "compose", "-f", "deploy/docker-compose.yml", "down"]
canary = ["bin/order-service", "--check"]
benchmark = ["bin/order-service", "--benchmark", "200000"]
```

## Capability levels

### P0: engineering and supply-chain baseline

- isolated Conan 2.8.1, explicit remotes, profiles and immutable graph lock
- CMake/Ninja/CTest and sccache
- reusable GitHub CI
- OSV, ASan/UBSan, TSan and bounded libFuzzer jobs
- full-SHA Action pinning, least-privilege tokens, CODEOWNERS and branch protection bootstrap
- foundation-owned reusable workflows use an immutable semantic release tag so consumers
  upgrade the platform explicitly; all third-party Actions remain pinned to full SHAs
- candidate/runner/configuration/lockfile provenance
- pinned clang-format, Ruff, ShellCheck and actionlint gates
- Clang 18 clang-tidy with high-confidence findings treated as errors
- zero-warning policy for every project-owned C++ target in CI

### P1: immutable release and deployment

- safe runtime archive, SHA-256, SPDX 2.3 SBOM and candidate provenance
- GitHub artifact attestations and immutable tag release
- archive path traversal and digest verification
- idempotent install, serialized deployment operations, upgrade, rollback, status and verify
- failed candidate cleanup and automatic previous deployment recovery
- runtime-only Dockerfile, hardened Compose, systemd and Prometheus/Grafana reference files
- GCC 13 and Clang 18 compatibility builds, CodeQL and coverage thresholds
- Dependabot policies for Actions, Python tooling and Docker bases

### P2: operations evidence

- create-only evidence records with content-addressed raw summaries
- package verification for off-host retention
- age-encrypted backup creation, verification and isolated restore
- application-defined external canary with fixed-window aggregation
- bounded smoke, 2h and 8h soak profiles
- repeated performance gates with explicit throughput and P99 thresholds
- scheduled IWYU, cppcheck, Hadolint, Markdown and CMake quality checks
- clean-build time, release binary size and repeat-build digest budgets

## Common commands

```bash
cpp-foundation --manifest foundation.toml validate
cpp-foundation quality --root . --mode deep --fix
cpp-foundation quality --root . --mode fast
cpp-foundation quality --root . --mode deep
cpp-foundation --manifest foundation.toml package --output-dir dist
cpp-foundation verify-release --archive dist/project-v0.1.0-linux-x64.tar.gz \
  --checksum dist/project-v0.1.0-linux-x64.tar.gz.sha256

sudo cpp-foundation deploy --root /opt/project --state-root /var/lib/project \
  install --archive /tmp/project-v0.1.0-linux-x64.tar.gz \
  --checksum /tmp/project-v0.1.0-linux-x64.tar.gz.sha256
sudo cpp-foundation deploy --root /opt/project --state-root /var/lib/project \
  activate --deployment-id <deployment-id>
```

Install the repository-pinned quality toolset before running the local quality commands:

```bash
python3 scripts/install_quality_tools.py \
  --venv .venv/quality --tools-dir .tools
export PATH="$PWD/.venv/quality/bin:$PWD/.tools/bin:$PWD/.tools/npm/node_modules/.bin:$PATH"
```

The fast quality gate is required on pull requests. Deep IWYU, cppcheck, documentation,
Dockerfile and reproducibility gates run on schedule or explicit dispatch. Analysis and
coverage options are isolated from the default Release build.

Long operations are opt-in. Ordinary pull requests run a two-second bounded stability
smoke. All generated workflows default to GitHub-hosted `ubuntu-24.04` runners. The 2h
profile can use that default. Before enabling `overnight-8h`, a consuming project must
explicitly configure an authorized self-hosted runner because GitHub-hosted jobs have a
shorter execution limit.

## Production boundaries

- A template cannot configure GitHub branch rules, runner groups, environments or
  secrets. Use `scripts/bootstrap_github.py --apply` after the first `main` commit.
- Consumers reference the public reusable workflows through the immutable
  `HoneyBury/cpp-project-foundation@v0.2.1` release tag.
- GitHub-hosted attestations run automatically for public repositories. Private consumers
  still publish SHA-256, provenance JSON and SPDX; supported enterprise repositories can
  explicitly enable native attestations.
- Conan profiles may be shared; lockfiles are owned by each consuming dependency graph.
- Backup archives require an age recipient by default. Plaintext mode exists only for tests.
- The local evidence package reports `off_host_copy_verified=false`; a separate host must
  verify and record the transfer.
- A successful framework smoke test is not an availability, capacity or HA claim.

See [foundation-contract.md](docs/foundation-contract.md),
[architecture.md](docs/architecture.md) and [operations.md](docs/operations.md).
