# Release process

## Versioning

`hwval` follows [SemVer](https://semver.org/) and pins
`requires-python = ">=3.8"`. Bump the version in `pyproject.toml`:

```toml
[project]
version = "X.Y.Z"
```

- **Patch** — bug fixes, doc fixes, internal refactors with no public
  surface change.
- **Minor** — new public symbols, new optional features (e.g. a new
  `AlertLevel` member).
- **Major** — breaking changes to public API or default behaviour.

## Pre-release checklist

- [ ] `uv run pytest` is green (currently 42 tests, 3 subtests).
- [ ] `uv run python examples/0?_*/example.py` runs cleanly.
- [ ] `docs/generated/` regen'd if the docx generators changed:
      `uv run python docs/generated/generate.py`.
- [ ] README + `docs/` updated for any public-API change.
- [ ] `CHANGELOG.md` updated with the version line.

## Build & publish

```bash
# clean
rm -rf dist/

# build sdist + wheel
uv build

# upload to PyPI (test first)
uv run --with twine python -m twine upload --repository testpypi dist/*
uv run --with twine python -m twine upload dist/*
```

`hatchling` is the build backend (`pyproject.toml`); no extra config
needed.

## Smoke-test on TestPyPI

```bash
python -m venv /tmp/hwval-smoke
source /tmp/hwval-smoke/bin/activate
pip install -i https://test.pypi.org/simple/ hwval==X.Y.Z
pip install hwval[docs]==X.Y.Z  # verify optional extra works

python -c "
from hwval import AlertLevel, check_value, report_test_summary, SegDocument
print('imports OK')
check_value(1, 1, alert_level=AlertLevel.WARNING, msg='smoke')
print('check_value OK:', report_test_summary(file=open('/dev/null', 'w')).total)
```

## Tag & announce

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Add release notes (copy-paste the `CHANGELOG.md` entry).