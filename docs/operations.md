# Operations Runbook

## Release

Build on an admitted Linux x64 runner and package the exact checked-out candidate. The
archive verifier rejects checksum mismatch, multiple archive roots, links, absolute paths,
path traversal, missing files and provenance mismatch.

## Deployment

Install is idempotent for the same archive digest. Activation and upgrade are fail-closed:
the candidate must pass both activate and verify hooks before it becomes verified.

```bash
cpp-foundation deploy --root /opt/example --state-root /var/lib/example status
cpp-foundation deploy --root /opt/example --state-root /var/lib/example verify
cpp-foundation deploy --root /opt/example --state-root /var/lib/example rollback
```

Do not place application data, credentials, backups or evidence beneath the immutable
release root. The deployment manager never deletes protected state.

## Backup and restore

Production backup creation requires an age recipient:

```bash
cpp-foundation backup create --source /var/lib/example/data \
  --output /var/backups/example/data-$(date -u +%Y%m%dT%H%M%SZ).tar.gz.age \
  --age-recipient age1...
```

Verification and restore require an identity. Restore refuses an existing destination so
that drills cannot overwrite live state.

## Canary and stability

Schedule canary `run` on a host outside the production service host at each natural UTC
minute. Samples are create-only by minute. Aggregation counts missing minutes as failures,
requires one fixed candidate and reports inclusive availability.

The ordinary CI smoke is not long-run evidence. A 2h gate may run on GitHub-hosted Linux,
but the 8h profile requires a fixed self-hosted runner whose power, network and resource
isolation are controlled. The workflow rejects an 8h request without a `self-hosted`
runner label. Preserve interrupted results as failures rather than combining partial windows.

## Evidence retention

Create daily/weekly/incident/final records from raw summaries, verify the ledger, package
it and copy it off-host. The package result remains incomplete until the destination
verifies the archive checksum and records its independent host/storage identity.
