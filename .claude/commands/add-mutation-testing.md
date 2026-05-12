---
description: Setup mutation testing with mutmut for Python projects
---

# Setup Mutation Testing

Configure mutmut for mutation testing to evaluate Python test suite quality.

## Instructions

### 1. Analyze Test Suite

- Review existing pytest test coverage
- Identify critical modules and business logic to target
- Check current test quality (do tests verify values or just execution?)

### 2. Install and Configure

```bash
pip install mutmut
```

Add to `setup.cfg` or `pyproject.toml`:

```ini
[mutmut]
paths_to_mutate=src/
backup=False
runner=python -m pytest -x --tb=no -q
tests_dir=tests/
```

### 3. Configure Scope

- Set `paths_to_mutate` to target critical code only
- Exclude generated code, migrations, and config files
- Start with a small, important module to validate setup

### 4. Run Mutation Testing

```bash
# Full run
mutmut run

# Target specific module
mutmut run --paths-to-mutate=src/validators.py

# View results
mutmut results

# Inspect survived mutant
mutmut show <id>

# See what changed
mutmut apply <id>
git diff
mutmut apply 0  # reset
```

### 5. Analyze Surviving Mutants

For each survivor:
- Run `mutmut show <id>` to see the mutation
- Determine if it's a test gap or equivalent mutant
- Add tests for boundary conditions and return values
- Re-run to verify mutant is now killed

### 6. CI Integration

Add to `.github/workflows/mutation.yml`:

```yaml
name: Mutation Testing
on:
  pull_request:
    paths: ['src/**']

jobs:
  mutation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install -e ".[dev]" mutmut
      - run: mutmut run --CI
      - run: mutmut results
```

### 7. Set Quality Thresholds

- Target 80%+ mutation score for critical modules
- Add mutation score check to CI:

```bash
# Check mutation score meets threshold
KILLED=$(mutmut results | grep -oP 'Killed: \K\d+')
TOTAL=$(mutmut results | grep -oP 'Total: \K\d+')
SCORE=$((KILLED * 100 / TOTAL))
[ $SCORE -ge 80 ] || exit 1
```

### 8. Document and Maintain

- Add mutation testing to development workflow docs
- Review mutation score trends over time
- Update scope as codebase evolves
