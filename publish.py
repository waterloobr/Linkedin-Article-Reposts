"""
publish.py
Reads draft.json and posts it to the Waterloo Business Review LinkedIn page.
Runs only when you manually trigger the publish workflow (human approval gate).
"""

import os
import json
import requests

LINKEDIN_VERSION = "202506"   # set to the current month per LinkedIn's docs


def fresh_access_token():
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "refresh_token",
            "refresh_token": os.environ["LINKEDIN_REFRESH_TOKEN"],
            "client_id": os.environ["LINKEDIN_CLIENT_ID"],
            "client_secret": os.environ["LINKEDIN_CLIENT_SECRET"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def post(text):
    token = fresh_access_token()
    org_urn = f"urn:li:organization:{os.environ['LINKEDIN_ORG_ID']}"

    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": LINKEDIN_VERSION,
        },
        json={
            "author": org_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise SystemExit(f"LinkedIn error {resp.status_code}: {resp.text}")
    print("Posted. URN:", resp.headers.get("x-restli-id", "unknown"))


def main():
    with open("draft.json") as f:
        draft = json.load(f)
    print("Publishing:\n", draft["final_body"], "\n")
    post(draft["final_body"])


if __name__ == "__main__":
    main()
