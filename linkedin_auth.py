"""
linkedin_auth.py  —  RUN THIS ONCE, LOCALLY.

Walks you through LinkedIn's OAuth flow and prints a refresh token you paste
into GitHub Secrets. You need this because access tokens expire every 60 days;
publish.py uses the refresh token to mint a fresh access token each run.

Prereqs (see README): a LinkedIn developer app linked to the WBR page, with the
"Share on LinkedIn" product approved, and your account an admin of the page.
"""

import os
import urllib.parse
import requests

CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID") or input("Client ID: ").strip()
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET") or input("Client Secret: ").strip()
REDIRECT_URI = "http://localhost:8000/callback"   # must match the app's Auth tab

# Personal-profile posting (self-serve, works today):
SCOPES = "openid profile w_member_social"
# Later, for the WBR page (after Community Management API approval), swap to:
# SCOPES = "w_organization_social r_organization_social"

auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
    "response_type": "code",
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPES,
    "state": "wbr",
})

print("\n1) Open this URL, approve, then copy the 'code' value from the")
print("   redirected localhost URL (the page itself will fail to load — fine):\n")
print(auth_url)
code = input("\n2) Paste the code here: ").strip()

resp = requests.post(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=30,
)
resp.raise_for_status()
tokens = resp.json()
access_token = tokens.get("access_token", "")

# Look up your personal member id so we can build the author URN.
author_urn = ""
try:
    info = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    ).json()
    if info.get("sub"):
        author_urn = f"urn:li:person:{info['sub']}"
except Exception as e:
    print("  ! couldn't fetch userinfo (only matters for personal posting):", e)

print("\n=== SAVE THESE AS GITHUB SECRETS ===")
print("LINKEDIN_REFRESH_TOKEN =", tokens.get("refresh_token", "<<none returned>>"))
if author_urn:
    print("LINKEDIN_AUTHOR_URN    =", author_urn)
print("\n(access token, for a quick local test only):")
print(access_token[:25] + "...")
print("LINKEDIN_ACCESS_TOKEN =", access_token)