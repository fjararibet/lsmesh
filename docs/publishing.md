# Publishing to PyPI

The initial PyPI release is source-only. The project builds Triangle and Show
Me while constructing an installation wheel, so a locally built wheel contains
native executables. Uploading a wheel built inside the Nix development shell
would embed Nix runtime paths and would not be portable to ordinary Linux
systems.

## Prepare the release

PyPI does not permit replacing an uploaded artifact or reusing a released
version. Update the version in `pyproject.toml` before every subsequent release,
then run the checks and build a fresh source distribution:

```console
nix develop --command zsh -lc 'uv run pytest -q && uv run ty check'
nix develop --command zsh -lc 'uv build --clear --sdist'
```

Inspect `dist/` before publishing. It should contain only the intended
`lsmesher-<version>.tar.gz` artifact for this release command. The source archive
includes the Triangle sources and their redistribution notice, but no compiled
`src/lsmesher/bin` files.

## Publish with GitHub trusted publishing

The workflow at `.github/workflows/publish.yml` publishes whenever a `v*` tag is
pushed. It uses GitHub's OIDC identity, so it needs no API token. The workflow
checks that the tag exactly matches the version in `pyproject.toml`, builds only
the portable source distribution, and publishes that artifact.

Configure the PyPI trusted publisher with these values:

```text
Owner:       fjararibet
Repository:  lsmesher
Workflow:    publish.yml
Environment: pypi
```

For a project that does not exist on PyPI yet, configure it as a pending trusted
publisher. Release version `0.1.0` with:

```console
git tag v0.1.0
git push origin v0.1.0
```

Do not publish a wheel from the Nix shell. Portable wheels should later be built
for each supported platform in clean CI environments and checked with the
platform's wheel-repair tooling before upload.
