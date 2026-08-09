# Hello Service

Generated C++20 service baseline backed by
[`HoneyBury/cpp-project-foundation@v0.2.3`](https://github.com/HoneyBury/cpp-project-foundation/releases/tag/v0.2.3).

The project owns its manifest, Conan profiles and lockfile. Pull requests run the
GitHub-hosted compiler matrix, source quality, static analysis and coverage gates.

Run the native service after building:

```bash
build/release/bin/hello-service --check
build/release/bin/hello-service --benchmark 200000
```
