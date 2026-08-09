# Contributing

Changes use pull requests against `main`. A pull request must pass `cpp-ci`, resolve all
conversations, and receive one independent approval. Do not weaken a gate to make an
observed failure pass. Changes to reusable workflows, release provenance, deployment
transactions, backups, or evidence formats require focused tests and a rollback note.

Run locally:

```bash
python3 scripts/install_quality_tools.py --venv .venv/quality --tools-dir .tools
export PATH="$PWD/.venv/quality/bin:$PWD/.tools/bin:$PWD/.tools/npm/node_modules/.bin:$PATH"
cpp-foundation quality --root . --mode fast
python3 -m unittest discover -s tests -v
python3 scripts/check_repository.py
python3 -m foundation --manifest examples/hello-service/foundation.toml validate
```

Run `cpp-foundation quality --root . --mode deep` before changing CMake, Docker or
documentation policy. Do not add broad suppressions to make clang-tidy, cppcheck or IWYU
pass; scope an exception to one finding and record its rationale.
