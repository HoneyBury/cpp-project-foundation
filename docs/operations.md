# Release and Operations Guide

[简体中文](operations.zh-CN.md)

This guide is for packaging and operating a generated service. Try every command in a
test environment before using it on a production host.

Examples use `example` as the service name. Replace paths and names with those from your
project. Commands that change `/opt` or `/var/lib` normally need `sudo`.

## Before the first release

Confirm these items:

- the project builds and all tests pass on Ubuntu 24.04 x86-64 with GCC 13;
- `foundation.toml` contains the correct program path and operation commands;
- the Git working tree is clean and the release commit has been reviewed;
- application data, credentials and backups are outside the release directory;
- the service's `verify` command checks something meaningful and returns a nonzero status
  when the service is unhealthy.

The toolkit will not invent a useful health check for the application. That decision
belongs to the application team.

## Create a release package

Build the Release program first, then package it:

```bash
cmake --build build/release --parallel
ctest --test-dir build/release --output-on-failure
git status --short
cpp-foundation package --output-dir dist
```

`git status --short` must print nothing. Packaging refuses a dirty source tree because the
files would no longer clearly match one reviewed commit.

The `dist/` directory contains:

- a `.tar.gz` release archive;
- a `.sha256` checksum file;
- an SPDX software inventory;
- a JSON file describing the source commit and build environment.

Verify the archive before publishing or copying it:

```bash
cpp-foundation verify-release \
  --archive dist/example-v1.0.0-linux-x64.tar.gz \
  --checksum dist/example-v1.0.0-linux-x64.tar.gz.sha256
```

Keep the archive and checksum as separate files during transport. Verification checks both
the outer archive and every listed file inside it.

## Deployment directories

The deployment commands use two roots:

- `--root /opt/example` stores release files and small deployment records;
- `--state-root /var/lib/example` stores transaction records and the operation lock.

These roots do not hold application data. Put databases, uploads, credentials, backups and
retained evidence in separately managed locations.

## Install a release

Installing checks and extracts the archive but does not start it:

```bash
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  install \
  --archive /tmp/example-v1.0.0-linux-x64.tar.gz \
  --checksum /tmp/example-v1.0.0-linux-x64.tar.gz.sha256
```

The JSON output contains a `deployment_id`. Save that value for the next command. Repeating
the install with the same archive is safe and returns the existing record.

## Start the first release

```bash
deployment_id="paste-the-id-from-install-output"
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  activate \
  --deployment-id "$deployment_id"
```

The tool runs the application's `activate` command followed by its `verify` command. If
either command fails, the new release is cleaned up and the previous release is restored.

Check the result:

```bash
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  status
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  verify
```

## Upgrade and roll back

Install the new archive first. Then use its new deployment ID:

```bash
new_deployment_id="paste-the-new-id-from-install-output"
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  upgrade \
  --deployment-id "$new_deployment_id"
```

To return to the previously active release:

```bash
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  rollback
```

Rollback changes the active release. It does not restore application data. If a new
release changes stored data, the application team needs a separate, tested data migration
and rollback plan.

## Recover an interrupted deployment

A power loss or killed process can leave a transaction marked `started`. In that state,
`status` reports an unfinished transaction and later activation is blocked.

First inspect the status and transaction record under
`/var/lib/example/transactions/<transaction-id>/record.json`. Then run:

```bash
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  recover
```

Recovery stops the candidate release, restores the old `current` and `previous` pointers,
and starts the old release again. If a recovery command fails, the transaction remains
unfinished. Fix the reported host or application problem and retry `recover`; do not delete
the transaction record to bypass the block.

## Check health and metrics URLs

Normal `doctor` runs without network requests. When the service is expected to be running,
explicitly test the URLs from `foundation.toml`:

```bash
cpp-foundation doctor --root . \
  --probe-observability \
  --probe-timeout 5
```

Run this from a machine whose network path represents what you want to test. A check from
the service host does not prove that outside users can reach the service.

## Create and verify an encrypted backup

Production backups require an [`age`](https://age-encryption.org/) recipient. Obtain the
recipient and identity through your organization's key-handling process. Do not store the
private identity in the release directory or Git repository.

Create a backup:

```bash
cpp-foundation backup create \
  --source /var/lib/example/data \
  --output /var/backups/example/data-20260930T120000Z.tar.gz.age \
  --age-recipient age1...
```

The command also creates a `.json` summary beside the archive. Verify both files:

```bash
cpp-foundation backup verify \
  --archive /var/backups/example/data-20260930T120000Z.tar.gz.age \
  --summary /var/backups/example/data-20260930T120000Z.tar.gz.age.json \
  --age-identity /secure/path/backup-identity.txt
```

Copy backups to separate storage and test restoration regularly. A backup stored only on
the service host is not enough.

## Test a restore safely

Restore to a new, empty path that is separate from live data:

```bash
cpp-foundation backup restore \
  --archive /var/backups/example/data-20260930T120000Z.tar.gz.age \
  --summary /var/backups/example/data-20260930T120000Z.tar.gz.age.json \
  --destination /var/tmp/example-restore-test \
  --age-identity /secure/path/backup-identity.txt
```

The destination must not already exist. After restoration, use application-specific checks
to confirm that the data can really be read. Archive verification alone cannot prove that
the application understands the restored data.

## Keep operation records

Commands such as canary, soak and performance checks write JSON summaries. Copy important
summaries into a create-only evidence directory:

```bash
cpp-foundation evidence \
  --root /var/lib/example/evidence \
  record \
  --kind daily \
  --record-id 2026-09-30 \
  --summary runtime/operations/summary.json
cpp-foundation evidence \
  --root /var/lib/example/evidence \
  verify
cpp-foundation evidence \
  --root /var/lib/example/evidence \
  package \
  --output /var/backups/example/evidence-2026-09-30.tar.gz
```

The package output must be outside the evidence root. Copy the package and its checksum to
another host or storage system, then verify the checksum there.

## Simple incident checklist

| Situation | First action |
| --- | --- |
| New release fails during activation | Read the transaction record; automatic rollback should have run |
| `status` lists an unfinished transaction | Inspect it, then run `deploy recover` |
| Current release is unhealthy | Run `verify`, inspect service logs, then consider `rollback` |
| Backup verification fails | Keep the files, stop using that backup and investigate the copy or key |
| Evidence verification fails | Do not overwrite the bad file; preserve it and investigate |

Record the command, time, deployment ID and result during an incident. Remove secrets and
personal data before attaching logs to a ticket.
