"""
publish.py
Reads draft.json and posts it to the Waterloo Business Review LinkedIn page.
Runs only when you manually trigger the publish workflow (human approval gate).
"""

import os
import json
import requests

LINKEDIN_VERSION = "202506"   # set to the current month per LinkedIn's docs


def get_access_token():
    """
    Prefer the refresh-token flow (hands-off, renews forever). If no refresh
    token is set, fall back to a directly stored access token.

    NOTE: a stored access token expires ~60 days after it was issued. Before then,
    enable token rotation on the LinkedIn app, re-run linkedin_auth.py to get a
    real refresh token, add it as LINKEDIN_REFRESH_TOKEN, and this function
    switches to the refresh flow automatically — no code change needed.
    """
    refresh = os.environ.get("LINKEDIN_REFRESH_TOKEN")
    if refresh:
        resp = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": os.environ["LINKEDIN_CLIENT_ID"],
                "client_secret": os.environ["LINKEDIN_CLIENT_SECRET"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise SystemExit(
            "Set LINKEDIN_REFRESH_TOKEN (preferred) or LINKEDIN_ACCESS_TOKEN."
        )
    return token


def post(text):
    token = get_access_token()
    # Personal:  urn:li:person:XXXX   (works today via Share on LinkedIn)
    # WBR page:  urn:li:organization:NNN  (after Community Management approval)
    author_urn = os.environ["LINKEDIN_AUTHOR_URN"]

    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": LINKEDIN_VERSION,
        },
        json={
            "author": author_urn,
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