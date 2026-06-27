"""
auth.py — CDSE OAuth authentication
Handles token retrieval and refresh for Copernicus Data Space Ecosystem
"""
import os
import time
import requests
from dotenv import load_dotenv
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

load_dotenv()

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

_session = None
_token_expiry = 0

def get_session() -> OAuth2Session:
    """Get authenticated OAuth2 session. Refreshes token if expired."""
    global _session, _token_expiry

    CLIENT_ID = os.environ['CDSE_CLIENT_ID']
    CLIENT_SECRET = os.environ['CDSE_CLIENT_SECRET']

    if _session is None or time.time() > _token_expiry - 60:
        client = BackendApplicationClient(client_id=CLIENT_ID)
        _session = OAuth2Session(client=client)
        token = _session.fetch_token(
            token_url=TOKEN_URL,
            client_secret=CLIENT_SECRET,
            include_client_id=True
        )
        _token_expiry = token['expires_at']
        print(f"Token refreshed ✅ expires in {int(token['expires_in']//60)} min")

    return _session

if __name__ == '__main__':
    session = get_session()
    print(f"Session ready: {session}")
    # Test with simple catalog ping
    r = session.get(
        "https://sh.dataspace.copernicus.eu/configuration/v1/wms/instances",
        timeout=10
    )
    print(f"API ping: {r.status_code}")
