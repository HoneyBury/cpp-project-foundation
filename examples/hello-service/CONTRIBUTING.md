# Contributing

Create a branch from the latest `main` and keep each pull request focused on one change.
Add or update tests for changed behavior, then run:

```bash
cmake --preset release
cmake --build --preset release
ctest --preset release
cpp-foundation quality --root . --mode fast
cpp-foundation validate
```

Do not commit credentials, production data, build output or local tool environments.
Describe what changed and how it was tested in the pull request.
