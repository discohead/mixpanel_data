# Installation

> **⚠️ Pre-release Software**: This package is under active development. APIs may change between versions before 1.0.

!!! tip "Explore on DeepWiki"
    🤖 **[Installation Guide →](https://deepwiki.com/mixpanel/mixpanel-headless/2.1-installation)**

    Ask questions about requirements, dependencies, or troubleshoot installation issues.

## Requirements

- Python 3.10 or higher
- A Mixpanel service account with API access

## Installing with pip

```bash
pip install mixpanel-headless
```

## Installing with uv

[uv](https://github.com/astral-sh/uv) is a fast Python package installer:

```bash
uv pip install mixpanel-headless
```

Or add to your project:

```bash
uv add mixpanel-headless
```

## Optional Dependencies

### Documentation Tools

If you want to build the documentation locally:

```bash
pip install mixpanel_headless[docs]
```

## Verifying Installation

After installation, verify the CLI is available:

```bash
mp --version
```

You should see the installed version printed.

Test the Python import:

```python
import mixpanel_headless as mp
print(mp.__version__)
```

## Next Steps

- [Quick Start](quickstart.md) — Set up credentials and run your first query
- [Configuration](configuration.md) — Learn about environment variables and config files
