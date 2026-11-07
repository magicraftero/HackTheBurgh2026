"""BarentsWatch API client: client-credentials token, cached, refreshed on expiry or 401.

Credentials come from .env (BW_CLIENT_ID, BW_CLIENT_SECRET) and are never printed.
Calls are single-threaded, as BarentsWatch asks for bulk pulls.

Run: python -m pipeline.bw_client   (gets a token and reports whether it worked)
"""

from __future__ import annotations

import os
import time

import requests
from dotenv import load_dotenv

from pipeline.common import ROOT

TOKEN_URL = "https://id.barentswatch.no/connect/token"
API = "https://www.barentswatch.no/bwapi"


class BarentsWatch:
    def __init__(self) -> None:
        load_dotenv(ROOT / ".env")
        self.client_id = os.environ.get("BW_CLIENT_ID", "")
        self.client_secret = os.environ.get("BW_CLIENT_SECRET", "")
        if not self.client_id or not self.client_secret:
            raise SystemExit("BW_CLIENT_ID and BW_CLIENT_SECRET must be set in .env")
        self.session = requests.Session()
        self._token: str | None = None
        self._expires = 0.0

    def token(self, force: bool = False) -> str:
        if force or not self._token or time.time() > self._expires - 60:
            resp = requests.post(TOKEN_URL, timeout=30, data={
                "grant_type": "client_credentials",
                "scope": "api",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            if resp.status_code != 200:
                # The body explains the failure (e.g. invalid_client) and holds no secret.
                raise SystemExit(f"token request failed: HTTP {resp.status_code} {resp.text[:300]}")
            body = resp.json()
            self._token = body["access_token"]
            self._expires = time.time() + float(body.get("expires_in", 3600))
        return self._token

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Call API + path; on 401 fetch a new token and retry once."""
        extra = kwargs.pop("headers", {})  # popped once, so a retry keeps them
        for attempt in (0, 1):
            headers = {"Authorization": f"Bearer {self.token(force=attempt == 1)}", **extra}
            resp = self.session.request(method, API + path, headers=headers, timeout=300, **kwargs)
            if resp.status_code != 401:
                break
        resp.raise_for_status()
        return resp

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)


if __name__ == "__main__":
    bw = BarentsWatch()
    bw.token()
    print(f"token OK, valid for about {int(bw._expires - time.time()) // 60} minutes")
