# Architecture

## Quality pipeline

The fast path runs deterministic source checks, GCC/Clang compilation, clang-tidy and
coverage on pull requests. The security path builds CodeQL manually with the locked Conan
graph and scans a generated SPDX/PURL dependency inventory. The scheduled deep path runs
IWYU, cppcheck, Dockerfile/documentation checks and build artifact budgets.

All quality settings are repository-owned inputs. Generated projects receive the same
configuration files and may change budgets explicitly; workflows never derive a weaker
threshold from an observed result.

```text
generated C++ project
  foundation.toml
      |
      +-- P0 reusable CI/security workflows
      |     CMake + Conan lock + CTest + sanitizer + fuzz
      |
      +-- P1 release producer
      |     archive + SHA256 + SPDX + provenance + attestation
      |                         |
      |                         v
      |                 deployment manager
      |            install -> activate -> verify
      |                         |
      |                failure -> automatic rollback
      |
      `-- P2 application hooks
            canary + soak + perf + backup + evidence ledger
```

The manifest is the only shared configuration surface. Generic tooling owns state
transitions, digests, safe filesystem handling and evidence formats. The application owns
what constitutes health, business success, performance and protected data.

The deployment tree separates immutable releases, deployment records and mutable state:

```text
/opt/<project>/releases/<deployment-id>/
/opt/<project>/deployments/<deployment-id>/record.json
/opt/<project>/current -> deployments/<deployment-id>
/opt/<project>/previous -> deployments/<deployment-id>
/var/lib/<project>/transactions/<transaction-id>/record.json
```

Deployment commands take an exclusive file lock. Symlink changes are atomic. Failed
candidate activation runs candidate cleanup, restores the previous pointer and invokes
the previous activation hook. Transaction records retain the failure and recovery result.
