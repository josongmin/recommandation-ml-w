# Code Style & Conventions

## Lint / Format
- **ruff**: line-length 100, target py311
- **basedpyright**: strict mode
- **pre-commit**: ruff, basedpyright, terraform_fmt, commitizen

## Naming & Style
- first-party import: `wine_rec`
- ban relative imports: `ban-relative-imports = "all"`
- quote-style: double
- indent: space
- docstring-code-format: true
- lines-after-imports: 2

## Type Hints
- strict type checking (basedpyright)
- ANN rules enabled (annotations required)
- per-file ignores: tests (ANN, ARG, PLR...), notebooks (T20, ANN), scripts (T20, ANN, S311, RUF002)

## Docstrings
- Pydantic schemas: TC003 runtime field types 허용
- serving/models/cli: TID251 (self-import) 허용

## Per-file Ignores
- tests: S101, ANN, ARG, PLR, TID251, TC003
- notebooks: T20, ANN, E501
- scripts: T20, ANN, S311, RUF002
- schemas: TC003
- serving/models/cli: TID251
