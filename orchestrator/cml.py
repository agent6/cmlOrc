import json
import os
import ssl
import socket
import urllib.request
import urllib.error
from urllib.parse import urlsplit, urlunsplit
from typing import Optional, Tuple, Dict


class CMLClient:
    _TOKEN_CACHE: Dict[Tuple[str, str], str] = {}

    def __init__(self, base_url: str, username: str, password: str, verify_tls: bool = False, timeout: int = 10):
        # Normalize base_url to include API prefix
        parts = urlsplit((base_url or "").strip())
        if not parts.scheme:
            parts = parts._replace(scheme="https")
        path = (parts.path or "").rstrip("/")
        if not path:
            path = "/api/v0"
        elif "/api/" not in path:
            path = f"{path}/api/v0"
        parts = parts._replace(path=path)
        self.base_url = urlunsplit(parts).rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_tls = verify_tls
        self._token: Optional[str] = None
        # Load cached token if any
        try:
            cached = CMLClient._TOKEN_CACHE.get((self.base_url, self.username))
            if cached:
                self._token = cached
        except Exception:
            pass
        self._ctx = None
        if not verify_tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._ctx = ctx

    def _request(self, method: str, path: str, data: Optional[dict] = None, retry_auth: bool = True):
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        payload = None
        if data is not None:
            payload = json.dumps(data).encode()
        req = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                if ctype.startswith("application/json"):
                    return json.loads(raw.decode() or "{}")
                return raw.decode()
        except urllib.error.HTTPError as e:
            if e.code == 401 and retry_auth:
                self.authenticate()
                return self._request(method, path, data, retry_auth=False)
            raise
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            msg = None
            if isinstance(reason, OSError):
                if getattr(reason, "errno", None) in (51, 60, 61, 110, 113):
                    msg = f"Network error ({reason.errno}): {reason.strerror or reason} to {url}"
            elif isinstance(reason, (TimeoutError, socket.timeout)) or str(e.reason).lower() == "timed out":
                msg = f"Network timeout to {url}"
            if msg:
                raise urllib.error.URLError(msg)
            raise

    def authenticate(self):
        payload = {"username": self.username, "password": self.password}
        resp = self._request("POST", "/authenticate", payload, retry_auth=False)
        token = None
        if isinstance(resp, dict):
            token = resp.get("token") or resp.get("jwt")
        if not token and isinstance(resp, str):
            token = resp.strip()
        if not token:
            raise RuntimeError("Authentication failed: no token returned")
        self._token = token
        try:
            CMLClient._TOKEN_CACHE[(self.base_url, self.username)] = token
        except Exception:
            pass
        return token

    # Core endpoints
    def list_labs(self):
        return self._request("GET", "/labs")

    def lab_info(self, lab_uuid: str):
        return self._request("GET", f"/labs/{lab_uuid}")

    def start_lab(self, lab_uuid: str):
        try:
            return self._request("PUT", f"/labs/{lab_uuid}/start")
        except urllib.error.HTTPError as e:
            if e.code in (400, 405):
                return self._request("POST", f"/labs/{lab_uuid}/start")
            raise

    def stop_lab(self, lab_uuid: str):
        try:
            return self._request("PUT", f"/labs/{lab_uuid}/stop")
        except urllib.error.HTTPError as e:
            if e.code in (400, 405):
                return self._request("POST", f"/labs/{lab_uuid}/stop")
            raise

    def wipe_lab(self, lab_uuid: str):
        try:
            return self._request("PUT", f"/labs/{lab_uuid}/wipe")
        except urllib.error.HTTPError as e:
            if e.code in (400, 405):
                return self._request("POST", f"/labs/{lab_uuid}/wipe")
            raise

    # State helpers
    def lab_state(self, lab_uuid: str) -> Optional[str]:
        try:
            info = self.lab_info(lab_uuid)
            if isinstance(info, dict):
                state = info.get("state")
                if isinstance(state, dict):
                    return (state.get("status") or state.get("state") or "").upper()
                if isinstance(state, str):
                    return state.upper()
        except Exception:
            pass
        return None

    def wait_for_lab_not_running(self, lab_uuid: str, timeout: int = 120, interval: float = 2.0) -> bool:
        import time
        end = time.time() + timeout
        while time.time() < end:
            st = self.lab_state(lab_uuid) or ""
            if st not in {"RUNNING", "STARTED", "BOOTED"}:
                return True
            time.sleep(interval)
        return False

    # Lightweight reachability probe (no auth, minimal request)
    def ping(self) -> bool:
        url = f"{self.base_url}"
        for method, path in (("HEAD", ""), ("HEAD", "/labs"), ("GET", "")):
            try:
                u = f"{self.base_url}{path}"
                req = urllib.request.Request(u, headers={}, method=method)
                with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                    _ = resp.status
                    return True
            except urllib.error.HTTPError:
                return True
            except urllib.error.URLError:
                continue
            except Exception:
                continue
        return False

    # Utilities for uploads
    @staticmethod
    def extract_uuids_from_response(obj) -> set[str]:
        import re, json as _json
        uuids: set[str] = set()
        uuid_re = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
        try:
            if isinstance(obj, (bytes, bytearray)):
                text = obj.decode(errors="ignore")
                uuids.update(uuid_re.findall(text))
            elif isinstance(obj, str):
                uuids.update(uuid_re.findall(obj))
            elif isinstance(obj, dict) or isinstance(obj, list):
                text = _json.dumps(obj)
                uuids.update(uuid_re.findall(text))
        except Exception:
            pass
        return uuids

