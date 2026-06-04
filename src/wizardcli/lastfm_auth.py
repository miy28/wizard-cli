from __future__ import annotations

import hashlib
import json
import webbrowser
from typing import Optional

import requests

LASTFM_ENDPOINT = "https://ws.audioscrobbler.com/2.0/"


def _api_sig(params: dict, secret: str) -> str:
    # build string by alphabetical order of param names, concatenating name+value
    parts = []
    for k in sorted(params.keys()):
        parts.append(f"{k}{params[k]}")
    s = "".join(parts) + secret
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def get_token(api_key: str, secret: str) -> Optional[str]:
    params = {"api_key": api_key, "method": "auth.getToken"}
    sig = _api_sig(params, secret)
    params["api_sig"] = sig
    params["format"] = "json"
    resp = requests.get(LASTFM_ENDPOINT, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("token") or (data.get("error") and None)


def get_session(api_key: str, secret: str, token: str) -> dict:
    params = {"api_key": api_key, "method": "auth.getSession", "token": token}
    params["api_sig"] = _api_sig(params, secret)
    params["format"] = "json"
    resp = requests.get(LASTFM_ENDPOINT, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def do_desktop_auth(api_key: str, secret: str) -> Optional[dict]:
    token = get_token(api_key, secret)
    if not token:
        print("Failed to obtain token from Last.fm")
        return None
    url = f"https://www.last.fm/api/auth/?api_key={api_key}&token={token}"
    print("Opening browser to authorize the application. After you approve it, return here and wait for the session to be stored.")
    print(url)
    webbrowser.open(url)
    input("Press Enter after you have authorized the application...")
    session_resp = get_session(api_key, secret, token)
    # expected: {"session":{"name":"...","key":"..."}, "status":"ok"}
    return session_resp
