# Installation

## Requirements

- Python 3.11 or higher
- A Mixpanel service account with API access

## Installing with pip

```bash
pip install mixpanel_data
```

## Installing with uv

[uv](https://github.com/astral-sh/uv) is a fast Python package installer:

```bash
uv pip install mixpanel_data
```

Or add to your project:

```bash
uv add mixpanel_data
```

## Optional Dependencies

### Documentation Tools

If you want to build the documentation locally:

```bash
pip install mixpanel_data[docs]
```

## Verifying Installation

After installation, verify the CLI is available:

```bash
mp --version
```

You should see output like:

```
mixpanel_data 0.1.0
```

Test the Python import:

```python
import mixpanel_data as mp
print(mp.__version__)
```

## Next Steps

- [Quick Start](quickstart.md) — Set up credentials and run your first query
- [Configuration](configuration.md) — Learn about environment variables and config files
