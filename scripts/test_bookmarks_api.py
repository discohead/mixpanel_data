#!/usr/bin/env python3
"""Quick test of the undocumented Mixpanel bookmarks API."""

from pprint import pprint

import mixpanel_headless as mp


def main():
    # Initialize workspace (uses credentials from config/env)
    ws = mp.Workspace()
    client = ws.api

    print(f"Project ID: {client.project_id}")
    print(f"Region: {client.region}")
    print()

    # Build the bookmarks API URL based on region
    base_url = {
        "us": "https://mixpanel.com",
        "eu": "https://eu.mixpanel.com",
        "in": "https://in.mixpanel.com",  # Assuming India follows same pattern
    }.get(client.region, "https://mixpanel.com")

    url = f"{base_url}/api/app/projects/{client.project_id}/bookmarks"

    print(f"Fetching bookmarks from: {url}")
    print()

    # Fetch Insights bookmarks using API v2
    try:
        response = client.request("GET", url, params={"type": "insights", "v": 2})

        print("=== Raw API Response ===")
        print(f"Response type: {type(response)}")
        print()

        # Extract results
        if isinstance(response, dict):
            results = response.get("results", [])
            print(f"Found {len(results)} Insights bookmarks")
            print()

            # Show first few bookmarks
            for i, bookmark in enumerate(results[:5]):
                print(f"=== Bookmark {i + 1} ===")
                print(f"  ID: {bookmark.get('id')}")
                print(f"  Name: {bookmark.get('name')}")
                print(f"  Type: {bookmark.get('type')}")
                print(f"  Created: {bookmark.get('created')}")
                print(f"  Modified: {bookmark.get('modified')}")
                print()

            # Test the insights() method with the first bookmark
            if results:
                first_bookmark = results[0]
                bookmark_id = first_bookmark.get("id")
                print(f"=== Testing ws.insights(bookmark_id={bookmark_id}) ===")
                print(f"Bookmark name: {first_bookmark.get('name')}")
                print()

                try:
                    insights_result = ws.insights(bookmark_id=bookmark_id)
                    print(f"InsightsResult type: {type(insights_result)}")
                    print(f"InsightsResult: {insights_result}")
                except Exception as e:
                    print(f"Error calling insights(): {type(e).__name__}: {e}")
        else:
            print("Unexpected response format:")
            pprint(response)

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    ws.close()


if __name__ == "__main__":
    main()
