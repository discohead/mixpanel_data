#!/usr/bin/env python3
"""Minimal JQL QA test script.

This script performs a single JQL API call to debug JQL functionality
without triggering rate limits from other API calls.

Usage:
    uv run python scripts/qa_jql.py
"""

from __future__ import annotations

import json
import sys

ACCOUNT_NAME = "sinkapp-website"
FROM_DATE = "2025-11-01"
TO_DATE = "2025-11-30"


def main() -> int:
    """Run minimal JQL test."""
    print("JQL Debug Test")
    print("=" * 70)
    print(f"Account: {ACCOUNT_NAME}")
    print(f"Date range: {FROM_DATE} to {TO_DATE}")
    print()

    # 1. Setup credentials
    print("[1] Loading credentials...")
    from mixpanel_data._internal.config import ConfigManager

    config = ConfigManager()
    try:
        creds = config.resolve_credentials(account=ACCOUNT_NAME)
        print(f"    Username: {creds.username[:15]}...")
        print(f"    Project ID: {creds.project_id}")
        print(f"    Region: {creds.region}")
    except Exception as e:
        print(f"    ERROR: {type(e).__name__}: {e}")
        return 1

    # 2. Create API client
    print("\n[2] Creating API client...")
    from mixpanel_data._internal.api_client import MixpanelAPIClient

    api_client = MixpanelAPIClient(creds)
    api_client.__enter__()
    print("    Client created")

    # 3. Make raw JQL HTTP request
    print("\n[3] Making raw JQL HTTP request...")

    # Test with INVALID JQL to trigger JQLSyntaxError
    # Using .limit() after .groupBy() which is invalid in Mixpanel JQL
    script = f"""function main() {{
  return Events({{
    from_date: "{FROM_DATE}",
    to_date: "{TO_DATE}"
  }})
  .groupBy(["name"], mixpanel.reducer.count())
  .limit(10);
}}"""

    print(f"    Script:\n{script}")
    print()

    url = f"https://mixpanel.com/api/query/jql?project_id={creds.project_id}"
    headers = {
        "Authorization": api_client._get_auth_header(),
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    form_data = {"script": script}

    print(f"    URL: {url}")
    print(
        f"    Headers: {json.dumps({k: v[:20] + '...' if len(v) > 20 else v for k, v in headers.items()}, indent=6)}"
    )
    print(f"    Form data keys: {list(form_data.keys())}")
    print()

    response = api_client._client.post(  # type: ignore[union-attr]
        url,
        data=form_data,
        headers=headers,
        timeout=api_client._timeout,
    )

    # 4. Capture full response
    print("[4] Response details:")
    print(f"    Status code: {response.status_code}")
    print(f"    Status text: {response.reason_phrase}")
    print("    Response headers:")
    for key, value in response.headers.items():
        print(f"        {key}: {value}")
    print()

    print("[5] Response body:")
    try:
        body = response.json()
        print(f"    Type: {type(body).__name__}")
        print(f"    Content:\n{json.dumps(body, indent=4)}")
    except Exception:
        print(f"    Raw text:\n{response.text}")

    # 5. Test JQLSyntaxError via LiveQueryService
    print("\n[6] Testing JQLSyntaxError via LiveQueryService...")
    from mixpanel_data._internal.services.live_query import LiveQueryService
    from mixpanel_data.exceptions import JQLSyntaxError

    live_query = LiveQueryService(api_client)
    try:
        result = live_query.jql(script=script)
        print(f"    JQLResult.raw: {result.raw}")
        print(f"    JQLResult.df:\n{result.df}")
    except JQLSyntaxError as e:
        print("    ✓ JQLSyntaxError raised correctly!")
        print(f"    Error code: {e.code}")
        print(f"    Error type: {e.error_type}")
        print(f"    Error message: {e.error_message}")
        print(f"    Line info: {e.line_info}")
        print(f"    Stack trace: {e.stack_trace}")
        print(f"    Script attached: {e.script is not None}")
        print(f"    Request path: {e.details.get('request_path')}")
        print()
        print("    Full exception message:")
        print(f"    {e}")
    except Exception as e:
        print(f"    ERROR: {type(e).__name__}: {e}")

    # Cleanup
    print("\n[7] Cleanup...")
    api_client.__exit__(None, None, None)
    print("    Done")

    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
