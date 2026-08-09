# Contributing

Changes use pull requests against `main`. A pull request must pass `cpp-ci`, resolve all
conversations, and receive one independent approval. Do not weaken a gate to make an
observed failure pass. Changes to reusable workflows, release provenance, deployment
transactions, backups, or evidence formats require focused tests and a rollback note.

Run locally:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_repository.py
python3 -m foundation --manifest examples/hello-service/foundation.toml validate
```
