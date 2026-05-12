---
name: mutation-testing
description: Evaluate Python test suite quality using mutmut to introduce code mutations and verify tests catch them. Use for mutation testing, test quality assessment, mutant detection, and test effectiveness analysis.
---

# Mutation Testing with mutmut

Mutation testing assesses test suite quality by introducing small changes (mutations) to source code and verifying that tests fail. If tests don't catch a mutation, it indicates gaps in test coverage or quality.

## Key Concepts

- **Mutant**: Modified version of code with small change
- **Killed**: Test fails when mutation introduced (good)
- **Survived**: Test passes despite mutation (test gap)
- **Mutation Score**: Percentage of mutants killed

## Quick Start

```bash
# Install
pip install mutmut

# Run mutation testing
mutmut run

# View results
mutmut results

# Inspect specific mutant
mutmut show 1

# Apply mutation to see the change
mutmut apply 1

# Reset applied mutations
mutmut apply 0
```

## Configuration

```ini
# setup.cfg or pyproject.toml [tool.mutmut]
[mutmut]
paths_to_mutate=src/
backup=False
runner=python -m pytest -x
tests_dir=tests/
dict_synonyms=Struct, NamedStruct
```

## Example: Weak vs Strong Tests

```python
# src/validators.py
def is_valid_order(order: dict) -> bool:
    if not order:
        return False
    if not order.get("items"):
        return False
    if order.get("total", 0) <= 0:
        return False
    return True

def calculate_discount(total: float, tier: str) -> float:
    if tier == "gold":
        return total * 0.2
    elif tier == "silver":
        return total * 0.1
    return 0.0
```

```python
# ❌ Weak tests - mutations survive
def test_order_basic():
    order = {"items": ["a"], "total": 10}
    assert is_valid_order(order) == True  # Only tests happy path

# ✅ Strong tests - kill mutations
def test_order_null():
    assert is_valid_order(None) == False
    assert is_valid_order({}) == False

def test_order_empty_items():
    assert is_valid_order({"items": [], "total": 10}) == False

def test_order_zero_total():
    assert is_valid_order({"items": ["a"], "total": 0}) == False

def test_order_negative_total():
    assert is_valid_order({"items": ["a"], "total": -5}) == False

def test_order_valid():
    assert is_valid_order({"items": ["a"], "total": 10}) == True

def test_discount_gold():
    assert calculate_discount(100, "gold") == 20.0

def test_discount_silver():
    assert calculate_discount(100, "silver") == 10.0

def test_discount_none():
    assert calculate_discount(100, "bronze") == 0.0
```

## Common Mutation Operators

| Original | Mutations |
|----------|-----------|
| `>` | `>=`, `<`, `==` |
| `<` | `<=`, `>`, `==` |
| `==` | `!=` |
| `and` | `or` |
| `+` | `-` |
| `return True` | `return False` |
| `return x` | `return x + 1` |

## Improving Mutation Score

When a mutant survives, add tests for:

1. **Boundary conditions**: Test at exact threshold values
2. **Return values**: Verify actual results, not just truthiness
3. **All branches**: Cover each conditional path
4. **Edge cases**: Empty, None, negative, zero

```python
# Mutant survives: >= changed to >
def is_adult(age: int) -> bool:
    return age >= 18

# ❌ Weak: age=25 won't catch >= to > mutation
def test_adult_weak():
    assert is_adult(25) == True

# ✅ Strong: tests boundary
def test_adult_exactly_18():
    assert is_adult(18) == True

def test_not_adult_17():
    assert is_adult(17) == False
```

## CI Integration

```yaml
# .github/workflows/mutation.yml
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
      - run: pip install mutmut pytest
      - run: mutmut run --CI
      - run: mutmut results
```

## Best Practices

- Target critical business logic, not all code
- Aim for 80%+ mutation score on important modules
- Review survived mutants to improve tests
- Test boundaries and edge cases thoroughly
- Verify actual values, not just code execution
