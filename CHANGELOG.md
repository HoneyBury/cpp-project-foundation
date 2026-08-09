# Changelog

All notable changes are recorded here. Release tags follow Semantic Versioning while the
project remains in the `0.x` development lifecycle.

## 0.3.0 - 2026-08-09

### Added

- `cpp-foundation doctor` for project, toolchain and workflow compatibility diagnostics.
- `cpp-foundation template-diff` for read-only foundation-owned template drift reports.
- Installable wheels containing the complete scaffold and pinned quality assets.
- English and Simplified Chinese compatibility, lifecycle and migration documentation.

### Changed

- Branch protection bootstrap supports multiple exact check contexts and defaults to zero
  approvals for single-maintainer repositories.
- Dependabot no longer proposes an unsupported Ubuntu major-version Docker migration.

## 0.2.3 - 2026-08-09

- Made generated CMake formatting independent of locally installed formatting tools.

## 0.2.2 - 2026-08-09

- Isolated reusable Conan state and separated Clang analysis from GCC coverage profiles.
- Added generated README and ignore rules and updated artifact attestation tooling.

## 0.2.1 - 2026-08-09

- Corrected exact SBOM attestation paths in the release workflow.

## 0.2.0 - 2026-08-09

- Established the P0-P2 build, quality, supply-chain, release, deployment and operations
  foundation.
