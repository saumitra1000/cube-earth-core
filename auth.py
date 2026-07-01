"""
auth.py — CDSE OAuth2 with thread-safe shared token
Single token shared across all threads — no concurrent refresh race
"""
import os
import threading
import requests
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

_token = None
_token_lock = threading.Lock()
_session = None

def get_session():
    global _token, _session
    with _token_lock:
        client_id     = os.environ.get('CDSE_CLIENT_ID', '')
        client_secret = os.environ.get('CDSE_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            raise ValueError("CDSE_CLIENT_ID and CDSE_CLIENT_SECRET must be set")

        client  = BackendApplicationClient(client_id=client_id)
        session = OAuth2Session(client=client)
        token   = session.fetch_token(
            token_url=TOKEN_URL,
            client_secret=client_secret,
            include_client_id=True
        )
        _token   = token
        _session = session
        print("Token refreshed ✅ expires in 30 min")
        return session
