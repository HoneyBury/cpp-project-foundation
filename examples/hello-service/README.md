# Hello Service

This C++20 service was generated with C++ Project Foundation. It includes a small program,
a test, repeatable build settings, GitHub Actions and optional deployment examples.

If this is your first time using the toolkit, follow the full
[getting-started guide](https://github.com/HoneyBury/cpp-project-foundation/blob/v0.7.0/docs/getting-started.md).
The commands below are a short reference for this project.

## Build and test

Use Ubuntu 24.04, GCC 13, Conan 2.8.1, CMake and Ninja:

```bash
export CC=gcc-13
export CXX=g++-13
conan install . \
  --profile:host conan/profiles/linux-gcc-x64 \
  --profile:build conan/profiles/linux-gcc-x64 \
  --lockfile conan/locks/linux-gcc-x64-release.lock \
  --output-folder=build/conan \
  --build=missing
cmake --preset release
cmake --build --preset release --target hello_service hello_service_tests
ctest --preset release
```

## Run the example

```bash
build/release/bin/hello-service --check
build/release/bin/hello-service --healthcheck
build/release/bin/hello-service --benchmark 200000
```

`--check` checks the executable without starting the server. `--healthcheck` connects to a
running server on port 8080 and checks its `/health` response. `--benchmark` prints a JSON
performance result used by the optional operations workflow.

## Important files

| Path | Purpose |
| --- | --- |
| `src/`, `include/` | Example C++ implementation |
| `tests/` | Unit test |
| `CMakePresets.json` | Short, repeatable configure, build and test commands |
| `foundation.toml` | Build, release and operation settings |
| `conanfile.py`, `conan/` | Dependency request, profiles and fixed lockfile |
| `deploy/` | Optional container, systemd and monitoring examples |
| `.github/workflows/` | Automated checks and release jobs |
| `LICENSE`, `SECURITY.md` | Project license and private-reporting guidance |

This example currently uses
[`cpp-project-foundation@v0.7.0`](https://github.com/HoneyBury/cpp-project-foundation/releases/tag/v0.7.0).
Generated projects own their copied files and may change application code normally.
