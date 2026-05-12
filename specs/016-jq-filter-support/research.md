# Research: JQ Filter Support

**Feature**: 016-jq-filter-support
**Date**: 2026-01-04

## Library Selection

### Decision: jq.py (PyPI: `jq>=1.9.0`)

Selected jq.py as the Python binding for jq functionality.

### Rationale

1. **Maintenance**: Active development (v1.10.0, July 2025)
2. **Community**: 434 GitHub stars, 10 contributors, 220 dependent packages
3. **Python support**: 3.8-3.13 (covers project requirement of 3.10+)
4. **Pre-built wheels**: Available for all target platforms without compilation

### Alternatives Considered

| Library | Why Rejected |
|---------|--------------|
| pyjq | Abandoned (last release 2020), Python 2.7 era code |
| jmespath | Different query syntax (not jq-compatible), less powerful |
| jsonpath-ng | Different query syntax (JSONPath), no jq compatibility |
| Subprocess jq | Requires external binary install, platform-specific |

### Platform Support

Pre-built wheels eliminate compilation requirements:

| Platform | Architecture | Wheel Available |
|----------|--------------|-----------------|
| Linux | x86, x86-64, arm64 | ✅ |
| macOS | Intel (x86-64), Apple Silicon (arm64) | ✅ |
| Windows | x86, x86-64 | ✅ |

## Dependency Strategy

### Decision: Required Dependency (not optional)

Add `jq>=1.9.0` to main dependencies in `pyproject.toml`.

### Rationale

1. **Pre-built wheels**: No compilation needed on any platform
2. **Existing precedent**: Project already includes heavy native deps (pandas, duckdb)
3. **Better UX**: `--jq` works out of the box with `pip install mixpanel_data`
4. **Simpler docs**: No conditional installation instructions

### Alternatives Considered

| Approach | Why Rejected |
|----------|--------------|
| Optional dependency | Extra install step creates "gotcha" moment; documentation complexity |
| Vendored jq binary | Distribution complexity; platform-specific bundling |
| Pure Python parser | No complete jq parser exists; would need maintenance |

## Integration Design

### Decision: Post-Formatter Pipeline

Apply jq filter after JSON formatting, before console output.

### Rationale

1. **Simpler implementation**: Single integration point in `output_result()`
2. **Consistent behavior**: Works identically for all commands
3. **No formatter changes**: Existing formatters remain unchanged
4. **Clear data flow**: `data → format_json() → _apply_jq_filter() → print()`

### Error Handling

| Error Type | Exit Code | Example |
|------------|-----------|---------|
| Invalid jq syntax | 3 (INVALID_ARGS) | `.name |` (incomplete) |
| jq runtime error | 3 (INVALID_ARGS) | `.[0]` on object |
| Incompatible format | 3 (INVALID_ARGS) | `--format table --jq '.'` |

Exit code 3 matches existing patterns for JQL syntax errors and date validation errors.

## Output Format

### Decision: Pretty-Print JSON Results

Always output jq results as formatted JSON:
- Single result → pretty-printed value
- Multiple results → pretty-printed array
- No results → `[]`

### Rationale

1. **Consistency**: Output remains valid JSON for further piping
2. **Readability**: Indentation helps human inspection
3. **Composability**: Can pipe to external jq or other tools if needed

## References

- [jq.py on PyPI](https://pypi.org/project/jq/)
- [jq.py GitHub](https://github.com/mwilliamson/jq.py)
- [jq Manual](https://jqlang.org/manual/)
- [gh CLI --jq reference](https://cli.github.com/manual/gh_help_formatting)
