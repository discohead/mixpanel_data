# Mutation Testing Implementation Plan

## Executive Summary

Incremental mutation testing plan prioritized by **business value**, **complexity**, and **risk**. Start with high-value, low-complexity modules to establish patterns, then scale to critical infrastructure.

**Target:** 80%+ mutation score on all tested modules

---

## 📋 Complete TODO Checklist

### Setup & Preparation
- [ ] Review this entire plan document
- [ ] Verify mutmut is installed: `mutmut --version`
- [ ] Confirm current test coverage: `just test-cov`
- [ ] Create tracking branch: `git checkout -b mutation-testing`
- [ ] Set up mutation testing directory: `mkdir -p docs/mutation-reports`

---

### Phase 1: Quick Wins (Week 1-2)

#### Week 1, Day 1-2: cli/validators.py
- [ ] **Run baseline tests**: `just test tests/unit/cli/test_validators.py -v`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/cli/validators.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/validators-baseline.txt`
- [ ] **Inspect each survivor**:
  - [ ] Survivor 1: `just mutate-show 1` → analyze → write test
  - [ ] Survivor 2: `just mutate-show 2` → analyze → write test
  - [ ] Survivor 3: `just mutate-show 3` → analyze → write test
  - [ ] (Continue for all survivors)
- [ ] **Re-run mutation testing**: Verify improvements
- [ ] **Achieve 85%+ score**: Iterate until target reached
- [ ] **Document final score**: Record in `docs/mutation-reports/validators-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: achieve 85%+ mutation score for cli/validators.py"`
- [ ] **Update this checklist**: Mark complete ✅

#### Week 1, Day 3-5: exceptions.py
- [ ] **Run baseline tests**: `just test tests/unit/test_exceptions.py -v`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/exceptions.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/exceptions-baseline.txt`
- [ ] **Focus areas**:
  - [ ] Test exception hierarchy: Verify inheritance chain
  - [ ] Test to_dict() serialization: All fields present
  - [ ] Test __repr__ and __str__: Exact output verification
  - [ ] Test HTTP status code logic: Boundary conditions
  - [ ] Test error code matching: Exact string comparisons
- [ ] **Inspect survivors**: `just mutate-show <id>` for each
- [ ] **Write targeted tests**: Focus on survived mutants
- [ ] **Re-run until 80%+ score**
- [ ] **Document final score**: Record in `docs/mutation-reports/exceptions-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: achieve 80%+ mutation score for exceptions.py"`
- [ ] **Update this checklist**: Mark complete ✅

---

### Phase 2: Security & Configuration (Week 2)

#### Week 2: _internal/config.py
- [ ] **Run baseline tests**: `just test tests/unit/test_config.py tests/unit/test_config_pbt.py -v`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/_internal/config.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/config-baseline.txt`
- [ ] **Security-critical checks**:
  - [ ] Verify credential redaction: No secret leakage in repr/str
  - [ ] Test empty string validation: `""` and `"   "` rejected
  - [ ] Test region validation: Invalid regions rejected
  - [ ] Test TOML parsing edge cases: Malformed files handled
  - [ ] Test credential immutability: Cannot modify after creation
- [ ] **Inspect survivors**: Focus on validation logic
- [ ] **Add boundary tests**: Test exact edge cases
- [ ] **Re-run until 85%+ score**
- [ ] **Security review**: Manually verify no credential exposure paths
- [ ] **Document final score**: Record in `docs/mutation-reports/config-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: achieve 85%+ mutation score for config.py (security-critical)"`
- [ ] **Update this checklist**: Mark complete ✅

---

### Phase 3: Data Validation (Week 3)

#### Week 3: types.py
- [ ] **Run baseline tests**: `just test tests/unit/test_types.py tests/unit/test_types_pbt.py -v`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/types.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/types-baseline.txt`
- [ ] **Focus areas**:
  - [ ] Test frozen dataclass immutability
  - [ ] Test lazy DataFrame caching (first access vs subsequent)
  - [ ] Test to_dict() completeness: All fields serialized
  - [ ] Test date parsing edge cases
  - [ ] Test bookmark type validation
  - [ ] Test None vs empty list handling
- [ ] **Inspect survivors**: Large file - prioritize critical paths
- [ ] **Add property-based tests**: Extend existing PBT coverage
- [ ] **Re-run until 80%+ score**
- [ ] **Document final score**: Record in `docs/mutation-reports/types-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: achieve 80%+ mutation score for types.py"`
- [ ] **Update this checklist**: Mark complete ✅

---

### Phase 4: Services Layer (Weeks 4-6)

#### Week 4: services/discovery.py
- [ ] **Run baseline tests**: `just test tests/unit/test_discovery.py tests/unit/test_discovery_pbt.py -v`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/_internal/services/discovery.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/discovery-baseline.txt`
- [ ] **Inspect survivors**: Focus on schema discovery logic
- [ ] **Write targeted tests**: Kill critical path mutants
- [ ] **Re-run until 80%+ score**
- [ ] **Document final score**: Record in `docs/mutation-reports/discovery-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: achieve 80%+ mutation score for discovery.py"`
- [ ] **Update this checklist**: Mark complete ✅

#### Week 5: services/fetcher.py
- [ ] **Run baseline tests**: `just test tests/unit/test_fetcher_service_pbt.py -v`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/_internal/services/fetcher.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/fetcher-baseline.txt`
- [ ] **Focus on streaming logic**: Iterator handling, memory efficiency
- [ ] **Inspect survivors**: Prioritize data integrity paths
- [ ] **Re-run until 80%+ score**
- [ ] **Document final score**: Record in `docs/mutation-reports/fetcher-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: achieve 80%+ mutation score for fetcher.py"`
- [ ] **Update this checklist**: Mark complete ✅

#### Week 6: services/live_query.py
- [ ] **Run baseline tests**: `just test tests/unit/test_live_query.py tests/unit/test_live_query_pbt.py -v`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/_internal/services/live_query.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/live-query-baseline.txt`
- [ ] **Focus on API endpoints**: Each endpoint's logic
- [ ] **Inspect survivors**: Large file - prioritize critical queries
- [ ] **Re-run until 80%+ score**
- [ ] **Document final score**: Record in `docs/mutation-reports/live-query-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: achieve 80%+ mutation score for live_query.py"`
- [ ] **Update this checklist**: Mark complete ✅

---

### Phase 5: Infrastructure (Weeks 7-9)

#### Week 7: _internal/storage.py
- [ ] **FIRST: Improve coverage**: Currently 92%, target 95%+
- [ ] **Identify coverage gaps**: `just test-cov` and review missing lines
- [ ] **Write tests for gaps**: Focus on uncovered branches
- [ ] **Verify improved coverage**: Re-run `just test-cov`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/_internal/storage.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/storage-baseline.txt`
- [ ] **Focus on DuckDB operations**: SQL generation, data persistence
- [ ] **Inspect survivors**: Complex file - timebox at 2 days
- [ ] **Re-run until 80%+ score**
- [ ] **Document final score**: Record in `docs/mutation-reports/storage-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: achieve 80%+ mutation score for storage.py"`
- [ ] **Update this checklist**: Mark complete ✅

#### Week 8: _internal/api_client.py
- [ ] **FIRST: Improve coverage**: Currently 85%, target 90%+
- [ ] **Identify coverage gaps**: Focus on error handling paths
- [ ] **Write tests for gaps**: HTTP retries, timeout handling
- [ ] **Verify improved coverage**: Re-run `just test-cov`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/_internal/api_client.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/api-client-baseline.txt`
- [ ] **Focus on critical paths**: Auth, error handling, retries
- [ ] **Accept lower score**: Integration-heavy code may score 70-75%
- [ ] **Document final score**: Record in `docs/mutation-reports/api-client-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: mutation testing for api_client.py"`
- [ ] **Update this checklist**: Mark complete ✅

#### Week 9: workspace.py
- [ ] **Run baseline tests**: `just test tests/unit/test_workspace.py tests/unit/test_workspace_pbt.py -v`
- [ ] **Run mutation testing**: `just mutate src/mixpanel_data/workspace.py`
- [ ] **Review results**: `just mutate-results`
- [ ] **Document initial score**: Record in `docs/mutation-reports/workspace-baseline.txt`
- [ ] **Focus on error handling**: Edge cases, validation
- [ ] **Accept delegation mutants**: Facade pattern means many delegates
- [ ] **Re-run until 75%+ score**: Lower target due to delegation
- [ ] **Document final score**: Record in `docs/mutation-reports/workspace-final.txt`
- [ ] **Commit changes**: `git commit -m "feat: mutation testing for workspace.py"`
- [ ] **Update this checklist**: Mark complete ✅

---

### Documentation & Reporting

- [ ] **Create summary report**: `docs/mutation-reports/SUMMARY.md`
  - [ ] Include final scores for all modules
  - [ ] Document lessons learned
  - [ ] List common mutation patterns found
  - [ ] Recommend process improvements
- [ ] **Update CLAUDE.md**: Add mutation testing workflow guidance
- [ ] **Update justfile**: Add per-module mutation commands if needed
- [ ] **Create wiki page**: Document mutation testing process for team

---

### CI Integration (Future Phase)

- [ ] **Create workflow file**: `.github/workflows/mutation.yml`
- [ ] **Test locally**: Verify workflow runs successfully
- [ ] **Configure triggers**: Run on PR to critical paths
- [ ] **Set score thresholds**: Fail if score drops below 80%
- [ ] **Add status badge**: Display mutation score in README
- [ ] **Document CI process**: Add to CONTRIBUTING.md

---

### Celebration & Retrospective

- [ ] **Calculate overall mutation score**: Across all tested modules
- [ ] **Document test improvements**: Count new tests added
- [ ] **Share learnings**: Write blog post or internal doc
- [ ] **Team retrospective**: What worked? What didn't?
- [ ] **Plan maintenance**: How to keep scores high?

---

### Quick Reference Commands

```bash
# Start new module
just mutate src/mixpanel_data/<module>.py

# Check results
just mutate-results

# Inspect specific mutant
just mutate-show <id>

# Apply mutation to see change
just mutate-apply <id>

# Reset applied mutation
just mutate-apply 0

# Verify score threshold
just mutate-check

# Run tests with coverage
just test-cov

# Run specific test file
just test tests/unit/test_<module>.py -v

# Run property-based tests
just test-pbt
```

---

## Component Prioritization Matrix

| Rank | Component | Priority | Complexity | Coverage | Value Score | Start Date |
|------|-----------|----------|------------|----------|-------------|------------|
| 1 | **cli/validators.py** | 🔥 HIGH | Low | 100% | ⭐⭐⭐⭐⭐ | Week 1 |
| 2 | **exceptions.py** | 🔥 HIGH | Medium | 97% | ⭐⭐⭐⭐⭐ | Week 1 |
| 3 | **_internal/config.py** | 🔥 HIGH | Medium | 97% | ⭐⭐⭐⭐⭐ | Week 2 |
| 4 | **types.py** | 🟡 MEDIUM | High | 98% | ⭐⭐⭐⭐ | Week 3 |
| 5 | **services/discovery.py** | 🟡 MEDIUM | Medium | 99% | ⭐⭐⭐⭐ | Week 4 |
| 6 | **services/fetcher.py** | 🟡 MEDIUM | Medium | 97% | ⭐⭐⭐ | Week 5 |
| 7 | **services/live_query.py** | 🟡 MEDIUM | High | 100% | ⭐⭐⭐⭐ | Week 6 |
| 8 | **_internal/storage.py** | 🟢 LOW | Very High | 92% | ⭐⭐⭐ | Week 7 |
| 9 | **_internal/api_client.py** | 🟢 LOW | Very High | 85% | ⭐⭐⭐ | Week 8 |
| 10 | **workspace.py** | 🟢 LOW | High | 89% | ⭐⭐ | Week 9 |

---

## Phase 1: Quick Wins (Weeks 1-2)

### Target: Build confidence, establish workflow

#### 1.1 cli/validators.py 🔥
**Why first:** Perfect starter module - simple, well-tested, low complexity

**Characteristics:**
- ✅ 100% line coverage
- ✅ 5 functions, ~20 conditionals
- ✅ Pure validation logic (no I/O)
- ✅ Fast mutation runs (~1-2 minutes)

**Expected mutations:**
```python
# Original: if value not in valid_values:
# Mutant:   if value in valid_values:

# Original: raise typer.Exit(ExitCode.INVALID_ARGS)
# Mutant:   raise typer.Exit(ExitCode.INVALID_ARGS + 1)
```

**Success criteria:**
- 85%+ mutation score
- All boundary conditions tested
- Establish baseline workflow

**Estimated effort:** 2-4 hours

---

#### 1.2 exceptions.py 🔥
**Why second:** Foundational module - error handling must be bulletproof

**Characteristics:**
- ✅ 97% line coverage
- ✅ 14 exception classes
- ✅ 845 lines
- ⚠️ AI agent recovery depends on this
- ⚠️ Serialization logic critical

**Expected mutations:**
```python
# Original: return {"code": self._code, "message": self._message, "details": self._details}
# Mutant:   return {"code": self._code, "message": self._message}

# Original: if status_code >= 500:
# Mutant:   if status_code > 500:
```

**Success criteria:**
- 80%+ mutation score
- Exception hierarchy integrity verified
- Serialization methods fully tested
- HTTP status code logic validated

**Estimated effort:** 4-6 hours

---

## Phase 2: Security & Configuration (Week 2)

#### 2.1 _internal/config.py 🔥
**Why critical:** Security-sensitive credential handling

**Characteristics:**
- ✅ 97% line coverage
- ✅ 16 functions, ~48 conditionals
- ⚠️ **Security-critical:** credential exposure risks
- ⚠️ Validation of regions, empty strings
- ✅ Has property-based tests

**Key risks:**
- Credential leakage via repr/str
- Empty string validation bypasses
- Region validation edge cases
- TOML parsing errors

**Expected mutations:**
```python
# Original: if not v or not v.strip():
# Mutant:   if not v:

# Original: if v_lower not in VALID_REGIONS:
# Mutant:   if v_lower in VALID_REGIONS:

# Original: secret=***
# Mutant:   secret={self.secret}
```

**Success criteria:**
- 85%+ mutation score
- No credential exposure in any code path
- All validators reject invalid inputs
- TOML edge cases handled

**Estimated effort:** 6-8 hours

---

## Phase 3: Data Validation (Week 3)

#### 3.1 types.py 🟡
**Why important:** Complex validation and serialization logic

**Characteristics:**
- ✅ 98% line coverage
- ✅ 1965 lines, extensive validation
- ✅ Has property-based tests (1493 lines!)
- ⚠️ DataFrame conversion logic
- ⚠️ JSON serialization

**Key areas:**
- Frozen dataclass immutability
- Lazy DataFrame caching
- to_dict() serialization
- Date parsing and formatting
- Bookmark type validation

**Expected mutations:**
```python
# Original: if self._df_cache is not None:
# Mutant:   if self._df_cache is None:

# Original: result_df = pd.DataFrame(self._data) if self._data else pd.DataFrame()
# Mutant:   result_df = pd.DataFrame(self._data)
```

**Success criteria:**
- 80%+ mutation score
- Immutability guarantees tested
- All serialization paths validated
- DataFrame caching verified

**Estimated effort:** 8-12 hours

---

## Phase 4: Services Layer (Weeks 4-6)

### 4.1 services/discovery.py 🟡
**Characteristics:**
- 99% coverage, 463 lines
- Schema discovery and introspection
- Moderate complexity

**Estimated effort:** 6-8 hours

---

### 4.2 services/fetcher.py 🟡
**Characteristics:**
- 97% coverage, 276 lines
- Data fetching orchestration
- Streaming ingestion logic

**Estimated effort:** 4-6 hours

---

### 4.3 services/live_query.py 🟡
**Characteristics:**
- 100% coverage, 1154 lines
- Complex query logic
- Multiple API endpoints

**Estimated effort:** 10-12 hours

---

## Phase 5: Infrastructure (Weeks 7-9)

### 5.1 _internal/storage.py 🟢
**Defer reason:** Complex, needs coverage improvement first

**Characteristics:**
- 92% coverage (below target)
- 1209 lines, 303 statements
- DuckDB integration (integration-heavy)

**Strategy:** Fix coverage gaps before mutation testing

**Estimated effort:** 12-16 hours

---

### 5.2 _internal/api_client.py 🟢
**Defer reason:** Integration-heavy, complex HTTP logic

**Characteristics:**
- 85% coverage (below target)
- 1627 lines, 408 statements
- HTTP error handling, retries

**Strategy:** Improve coverage, then mutation test critical paths only

**Estimated effort:** 16-20 hours

---

### 5.3 workspace.py 🟢
**Defer reason:** Facade pattern, mostly delegation

**Characteristics:**
- 89% coverage
- 2041 lines, 357 statements
- Delegates to services

**Strategy:** Focus on error handling and edge cases

**Estimated effort:** 12-16 hours

---

## Mutation Testing Workflow

### Step 1: Run mutation testing
```bash
just mutate src/mixpanel_data/cli/validators.py
```

### Step 2: Review results
```bash
just mutate-results
# Example output:
# Total mutants: 42
# Killed: 35 (83%)
# Survived: 7 (17%)
```

### Step 3: Inspect survived mutants
```bash
just mutate-show 1
just mutate-show 2
# ... review each survivor
```

### Step 4: Write tests to kill survivors
```python
# Example: Mutant changed >= to >
def test_boundary_exactly_at_threshold():
    """Test exact threshold value (kills >= to > mutation)."""
    assert validate_age(18) == True  # Must pass at exactly 18
```

### Step 5: Re-run and verify
```bash
just mutate src/mixpanel_data/cli/validators.py
just mutate-check  # Verify >= 80%
```

---

## Success Metrics

### Per-Module Goals
- **80%+ mutation score** for all tested modules
- **Zero survived mutants** in critical paths (security, data integrity)
- **100% boundary condition coverage**

### Project Goals
- **Week 1-2:** 2 modules complete (validators, exceptions)
- **Week 3:** 1 module complete (config)
- **Month 1:** 3 high-priority modules at 80%+
- **Quarter 1:** All high-priority modules complete

---

## Common Mutation Patterns to Expect

### 1. Conditional Boundaries
```python
# >= changed to >, <=, ==
# < changed to <=, >, ==
# == changed to !=
```
**Fix:** Test exact boundary values

### 2. Boolean Logic
```python
# and changed to or
# not x changed to x
```
**Fix:** Test all boolean combinations

### 3. Return Values
```python
# return True changed to return False
# return x changed to return None
```
**Fix:** Assert exact return values

### 4. Exception Handling
```python
# raise FooError changed to raise BarError
# except Foo: changed to except Bar:
```
**Fix:** Test exception types explicitly

### 5. String/Number Operations
```python
# + changed to -
# * changed to /
# str.upper() changed to str.lower()
```
**Fix:** Verify actual output values

---

## CI Integration (Future)

```yaml
# .github/workflows/mutation.yml
name: Mutation Testing
on:
  pull_request:
    paths:
      - 'src/mixpanel_data/cli/validators.py'
      - 'src/mixpanel_data/exceptions.py'
      - 'src/mixpanel_data/_internal/config.py'

jobs:
  mutation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: uv sync
      - run: just mutate-check
```

---

## Risk Mitigation

### Time Management
- **Quick wins first:** validators.py should take 2-4 hours
- **If stuck:** Move to next module, return later
- **Timebox:** Max 2 days per module

### Scope Control
- **Start small:** Single file at a time
- **Focus on killed mutants:** Don't chase 100%
- **Ignore equivalent mutants:** Some mutations don't change behavior

### Learning Curve
- **Read mutmut docs:** https://mutmut.readthedocs.io/
- **Study survived mutants:** They reveal test gaps
- **Pair with property-based testing:** Already established in this project

---

## Next Steps

1. ✅ Read this plan
2. ⏭️ Run: `just mutate src/mixpanel_data/cli/validators.py`
3. ⏭️ Review results with `just mutate-results`
4. ⏭️ Inspect survivors with `just mutate-show <id>`
5. ⏭️ Write tests to kill survivors
6. ⏭️ Achieve 85%+ mutation score
7. ⏭️ Move to exceptions.py

**Ready to start?** Begin with Phase 1.1 (validators.py)
