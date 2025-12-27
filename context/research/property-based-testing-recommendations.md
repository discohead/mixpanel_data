# Property-Based Testing Recommendations

This document outlines recommendations for expanding property-based testing (PBT) coverage in the `mixpanel_data` codebase.

## What is Property-Based Testing?

Property-based testing is a testing methodology where instead of writing individual test cases with specific inputs and expected outputs, you define *properties* that should hold true for *all valid inputs*, and let the testing framework generate hundreds or thousands of random inputs to verify those properties.

### Example: Traditional vs Property-Based

**Traditional (example-based) test:**
```python
def test_sort_specific_cases():
    assert sort([3, 1, 2]) == [1, 2, 3]
    assert sort([]) == []
    assert sort([1]) == [1]
```

**Property-based test:**
```python
@given(st.lists(st.integers()))
def test_sort_properties(xs):
    result = sort(xs)
    # Property 1: Output has same length as input
    assert len(result) == len(xs)
    # Property 2: Output is sorted
    assert all(result[i] <= result[i+1] for i in range(len(result)-1))
    # Property 3: Output is a permutation of input
    assert sorted(result) == sorted(xs)
```

The property-based test will automatically generate edge cases like empty lists, single-element lists, lists with duplicates, negative numbers, and extreme values—many of which a developer might forget to test explicitly.

## Hypothesis Framework

[Hypothesis](https://hypothesis.works/) is Python's premier property-based testing library. Key features:

### Strategies

Strategies generate random test data. Hypothesis provides built-in strategies for all Python types:

```python
from hypothesis import strategies as st

st.integers()                    # Random integers
st.text()                        # Random Unicode strings
st.lists(st.integers())          # Lists of integers
st.dictionaries(st.text(), st.integers())  # Dict[str, int]
st.datetimes()                   # datetime objects
st.from_type(MyPydanticModel)    # Automatic generation from type hints
```

### Shrinking

When Hypothesis finds a failing input, it automatically *shrinks* it to the minimal failing case. If your function fails on a 1000-character string, Hypothesis will find the smallest string that still triggers the failure.

### Reproducibility

Hypothesis stores failing examples in a database (`.hypothesis/`) so they're replayed on every test run. Combined with `derandomize=True` in CI, tests become fully deterministic.

### Profiles

Profiles control how many examples Hypothesis generates:

```python
# conftest.py
from hypothesis import settings, Verbosity

settings.register_profile("dev", max_examples=10)
settings.register_profile("default", max_examples=100)
settings.register_profile("ci", max_examples=200, derandomize=True)
```

## Current PBT Coverage

The `tests/unit/test_types_pbt.py` file provides comprehensive property-based testing for all result types in `types.py`:

- `FetchResult` - Event fetching results
- `SegmentationResult` - Segmentation query results
- `FunnelResult` - Funnel analysis results
- `RetentionResult` - Retention analysis results
- `FlowsResult` - Flow analysis results
- `InsightsResult` - Insights query results
- `SchemaResult` - Schema discovery results
- `ProfileResult` - User profile results

Properties tested include:
- Roundtrip serialization (dict → model → dict)
- DataFrame conversion consistency
- Empty data handling
- Metadata preservation
- Type coercion behavior

---

## Recommended Modules for PBT Expansion

### 1. StorageEngine (Highest Value)

**File:** `src/mixpanel_data/_internal/storage.py`

**Why highest value:**

The `StorageEngine` class is the core persistence layer, handling all DuckDB operations. Bugs here could cause data loss or corruption. Property-based tests would catch edge cases that example-based tests miss:

- Unusual event property names (Unicode, special characters, SQL injection attempts)
- Extreme values (very large integers, very long strings, deeply nested JSON)
- Concurrent access patterns (if applicable)
- Schema evolution edge cases

**Properties to test:**

1. **Roundtrip integrity**: Any event stored can be retrieved unchanged
   ```python
   @given(events=st.lists(event_strategy()))
   def test_store_retrieve_roundtrip(events):
       engine.store_events("test_table", iter(events))
       retrieved = list(engine.query("SELECT * FROM test_table"))
       assert_events_equal(events, retrieved)
   ```

2. **Query result consistency**: Same query always returns same results
   ```python
   @given(query=valid_sql_query_strategy())
   def test_query_determinism(query):
       result1 = list(engine.query(query))
       result2 = list(engine.query(query))
       assert result1 == result2
   ```

3. **JSON property preservation**: Nested JSON survives storage and retrieval
   ```python
   @given(properties=st.dictionaries(
       st.text(min_size=1),
       st.recursive(st.one_of(st.integers(), st.text(), st.booleans()),
                    lambda children: st.lists(children) | st.dictionaries(st.text(), children))
   ))
   def test_json_property_preservation(properties):
       event = {"event": "test", "properties": properties}
       engine.store_events("test", iter([event]))
       result = engine.query("SELECT properties FROM test")[0]
       assert json.loads(result["properties"]) == properties
   ```

4. **Table isolation**: Operations on one table don't affect others
   ```python
   @given(table_a_events=event_list_strategy(), table_b_events=event_list_strategy())
   def test_table_isolation(table_a_events, table_b_events):
       engine.store_events("table_a", iter(table_a_events))
       engine.store_events("table_b", iter(table_b_events))
       count_a = engine.query("SELECT COUNT(*) FROM table_a")[0][0]
       count_b = engine.query("SELECT COUNT(*) FROM table_b")[0][0]
       assert count_a == len(table_a_events)
       assert count_b == len(table_b_events)
   ```

5. **Unicode handling**: All valid Unicode strings survive storage
   ```python
   @given(text=st.text(alphabet=st.characters(categories=("L", "N", "P", "S", "Z"))))
   def test_unicode_preservation(text):
       event = {"event": text, "properties": {"value": text}}
       engine.store_events("test", iter([event]))
       result = engine.query("SELECT event FROM test")[0]
       assert result["event"] == text
   ```

**Estimated complexity:** Medium-high (requires test database setup/teardown)

---

### 2. Formatters (High Value)

**File:** `src/mixpanel_data/cli/formatters.py`

**Why high value:**

Formatters transform data for CLI output. They're pure functions with well-defined inputs and outputs—ideal for PBT. Edge cases in formatting can cause cryptic CLI errors or corrupted output.

**Properties to test:**

1. **JSON roundtrip**: JSON formatter output can be parsed back to original data
   ```python
   @given(data=json_serializable_strategy())
   def test_json_roundtrip(data):
       formatted = json_formatter(data)
       parsed = json.loads(formatted)
       assert parsed == data
   ```

2. **JSONL line count**: JSONL output has one line per record
   ```python
   @given(records=st.lists(json_serializable_strategy()))
   def test_jsonl_line_count(records):
       formatted = jsonl_formatter(records)
       lines = [l for l in formatted.split("\n") if l.strip()]
       assert len(lines) == len(records)
   ```

3. **CSV header consistency**: CSV always has consistent headers across rows
   ```python
   @given(records=st.lists(st.dictionaries(st.text(min_size=1), st.text()), min_size=1))
   def test_csv_header_consistency(records):
       formatted = csv_formatter(records)
       lines = formatted.split("\n")
       header_count = lines[0].count(",") + 1
       for line in lines[1:]:
           if line.strip():
               assert line.count(",") + 1 == header_count
   ```

4. **Table formatter doesn't crash**: Any valid data produces output without exception
   ```python
   @given(data=tabular_data_strategy())
   def test_table_formatter_no_crash(data):
       # Should not raise
       result = table_formatter(data)
       assert isinstance(result, str)
   ```

5. **Empty data handling**: All formatters handle empty input gracefully
   ```python
   @given(formatter=st.sampled_from([json_formatter, jsonl_formatter, csv_formatter, table_formatter]))
   def test_empty_data_handling(formatter):
       result = formatter([])
       assert isinstance(result, str)
   ```

**Estimated complexity:** Low (pure functions, no state)

---

### 3. ConfigManager (Medium Value)

**File:** `src/mixpanel_data/_internal/config.py`

**Why medium value:**

Configuration parsing has many edge cases around file formats, environment variables, and credential resolution. PBT can find unexpected interactions.

**Properties to test:**

1. **Config roundtrip**: Valid config can be written and read back
   ```python
   @given(config=config_strategy())
   def test_config_roundtrip(config):
       config.save(path)
       loaded = ConfigManager.load(path)
       assert loaded == config
   ```

2. **Environment variable precedence**: Env vars always override file config
   ```python
   @given(
       file_value=st.text(min_size=1),
       env_value=st.text(min_size=1)
   )
   def test_env_var_precedence(file_value, env_value, monkeypatch):
       assume(file_value != env_value)
       write_config({"secret": file_value})
       monkeypatch.setenv("MP_SECRET", env_value)
       config = ConfigManager.load()
       assert config.secret == env_value
   ```

3. **TOML special characters**: Config handles special TOML characters
   ```python
   @given(value=st.text(alphabet=st.characters(categories=("L", "N", "P", "S"))))
   def test_toml_special_characters(value):
       config = Config(project_id=value, username="test", secret="test")
       config.save(path)
       loaded = ConfigManager.load(path)
       assert loaded.project_id == value
   ```

4. **Region validation**: Only valid regions are accepted
   ```python
   @given(region=st.text())
   def test_region_validation(region):
       if region not in ("us", "eu", "in"):
           with pytest.raises(ValidationError):
               Credentials(project_id="123", username="u", secret="s", region=region)
   ```

5. **Partial config handling**: Missing optional fields use defaults
   ```python
   @given(partial_config=partial_config_strategy())
   def test_partial_config_defaults(partial_config):
       config = ConfigManager.from_dict(partial_config)
       assert config.region in ("us", "eu", "in")  # Has valid default
   ```

**Estimated complexity:** Medium (requires file system and environment mocking)

---

## Implementation Priority

| Module | Value | Complexity | Priority |
|--------|-------|------------|----------|
| StorageEngine | Highest | Medium-High | 1 |
| Formatters | High | Low | 2 |
| ConfigManager | Medium | Medium | 3 |

**Recommendation:** Start with formatters due to low complexity, then tackle StorageEngine for highest impact, and finally ConfigManager.

## Testing Patterns Established

Based on the existing `test_types_pbt.py`, follow these patterns:

1. **Define reusable strategies** at the top of the test file
2. **Use `st.from_type()` with Pydantic models** when possible
3. **Name PBT test files with `_pbt` suffix** (e.g., `test_storage_pbt.py`)
4. **Use `assume()` to filter invalid inputs** rather than complex strategy constraints
5. **Keep properties focused**—one property per test function
6. **Use descriptive property names** like `test_roundtrip_preserves_data`

## Resources

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Hypothesis Strategies Reference](https://hypothesis.readthedocs.io/en/latest/data.html)
- [Property-Based Testing with Python (RealPython)](https://realpython.com/property-based-testing-python/)
- [Choosing Properties for Property-Based Testing](https://fsharpforfunandprofit.com/posts/property-based-testing-2/)
