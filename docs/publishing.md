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

## Publish

Create an API token in the PyPI account settings. For the first upload, the
project does not exist yet, so the token cannot be scoped to this project. After
the first release creates `lsmesher`, replace it with a project-scoped token.

In zsh, read the token without placing it in shell history and publish the exact
artifact:

```console
read -rs "UV_PUBLISH_TOKEN?PyPI token: "; export UV_PUBLISH_TOKEN; echo
uv publish dist/lsmesher-0.1.0.tar.gz
unset UV_PUBLISH_TOKEN
```

Do not publish a wheel from the Nix shell. Portable wheels should later be built
for each supported platform in clean CI environments and checked with the
platform's wheel-repair tooling before upload.
