# Installation

> **⚠️ Pre-release Software**: This package is under active development and not yet published to PyPI. Install directly from GitHub.

!!! tip "Explore on DeepWiki"
    🤖 **[Installation Guide →](https://deepwiki.com/mixpanel/mixpanel-headless/2.1-installation)**

    Ask questions about requirements, dependencies, or troubleshoot installation issues.

## Requirements

- Python 3.10 or higher
- A Mixpanel service account with API access

## Installing with pip

```bash
pip install git+https://github.com/mixpanel/mixpanel-headless.git
```

## Installing with uv

[uv](https://github.com/astral-sh/uv) is a fast Python package installer:

```bash
uv pip install git+https://github.com/mixpanel/mixpanel-headless.git
```

Or add to your project:

```bash
uv add git+https://github.com/mixpanel/mixpanel-headless.git
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
