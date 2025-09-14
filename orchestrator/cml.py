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

    def delete_lab(self, lab_uuid: str):
        """Delete a lab via DELETE, with legacy POST fallback."""
        try:
            return self._request("DELETE", f"/labs/{lab_uuid}")
        except urllib.error.HTTPError as e:
            if e.code in (400, 405):
                return self._request("POST", f"/labs/{lab_uuid}/delete")
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

    def import_lab_yaml(self, yaml_text: str):
        """Import/Create a lab from YAML on this controller.
        Tries multiple endpoints and content types for compatibility.
        Returns parsed JSON if available, else response text.
        Raises the last HTTP/URL error if all attempts fail.
        """
        token = self._token or self.authenticate()

        def parse_response(resp):
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if ctype.startswith("application/json"):
                return json.loads(raw.decode() or "{}")
            return raw.decode()

        def send_path(path: str, content_type: str, body: bytes):
            url = f"{self.base_url}{path}"
            headers = {"Content-Type": content_type, "Authorization": f"Bearer {token}"}
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                return parse_response(resp)

        def send_json(path: str, obj: dict):
            return self._request("POST", path, data=obj)

        def send_multipart(path: str, field_name: str, filename: str, content_type: str, content: bytes):
            boundary = f"----cmlorc-{os.urandom(8).hex()}"
            parts = []
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(
                (
                    f"Content-Disposition: form-data; name=\"{field_name}\"; filename=\"{filename}\"\r\n"
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode()
            )
            parts.append(content)
            parts.append(b"\r\n")
            parts.append(f"--{boundary}--\r\n".encode())
            body = b"".join(parts)
            url = f"{self.base_url}{path}"
            headers = {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {token}",
            }
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                return parse_response(resp)

        yaml_bytes = (yaml_text or "").encode()
        last_err = None
        endpoints = ["/labs", "/labs/import", "/import"]
        for path in endpoints:
            try:
                return send_path(path, "text/plain", yaml_bytes)
            except Exception as e:
                last_err = e
            try:
                return send_path(path, "application/x-yaml", yaml_bytes)
            except Exception as e:
                last_err = e
            try:
                return send_json(path, {"yaml": yaml_text})
            except Exception as e:
                last_err = e
            for field in ("file", "upload", "lab", "topology"):
                for fname in ("lab.yaml", "topology.yaml"):
                    for ctype in ("application/x-yaml", "text/plain"):
                        try:
                            return send_multipart(path, field, fname, ctype, yaml_bytes)
                        except Exception as e:
                            last_err = e
                            continue
        if last_err:
            raise last_err
        raise RuntimeError("Import failed: no attempts made")

    @staticmethod
    def extract_lab_title_from_yaml(yaml_text: str) -> Optional[str]:
        """Extract the lab title from a CML lab YAML.
        Prefers lab.title (or lab.lab_title/name). Avoids node label fields.
        """
        text = yaml_text or ""
        # Try PyYAML if available for robust parsing
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(text)
            if isinstance(data, dict):
                lab = data.get("lab")
                if isinstance(lab, dict):
                    for k in ("title", "lab_title", "name"):
                        v = lab.get(k)
                        if isinstance(v, str) and v.strip():
                            return v.strip()
                # fallback: top-level keys if lab block missing
                for k in ("title", "lab_title", "name"):
                    v = data.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
        except Exception:
            pass
        # Regex fallback: locate 'lab:' block then read its title/name lines
        import re

        lines = text.splitlines()
        lab_idx = None
        for i, line in enumerate(lines[:500]):
            if re.match(r"^\s*lab\s*:\s*$", line):
                lab_idx = i
                break
        if lab_idx is not None:
            for line in lines[lab_idx + 1 : lab_idx + 80]:
                m = re.match(r"^\s*(title|lab_title|name)\s*:\s*['\"]?(?P<val>[^'\"]+?)['\"]?\s*$", line)
                if m:
                    val = m.group("val").strip()
                    if val:
                        return val
        # As last resort: first title-like key in the file (avoid 'label')
        for line in lines[:500]:
            m = re.match(r"^\s*(title|lab_title|name)\s*:\s*['\"]?(?P<val>[^'\"]+?)['\"]?\s*$", line)
            if m:
                val = m.group("val").strip()
                if val:
                    return val
        return None

    # Name/UUID helpers
    def resolve_lab_uuid_by_name(self, name_or_uuid: str) -> Optional[str]:
        """Return a lab UUID for a given name or UUID.
        - If the input matches an existing UUID, returns it.
        - Otherwise, searches labs by title/label/name and returns the UUID of an exact (case-insensitive) match.
        """
        target = (name_or_uuid or "").strip()
        if not target:
            return None
        # First, get the list of labs
        labs = self.list_labs()
        # If dict mapping {uuid: name}
        if isinstance(labs, dict):
            # Exact UUID
            if target in labs:
                return target
            # Match by name (case-insensitive)
            lower = target.lower()
            for uuid, nm in labs.items():
                if isinstance(nm, str) and nm.strip().lower() == lower:
                    return uuid
        # If list of UUIDs
        elif isinstance(labs, list):
            # Exact UUID present
            if target in labs:
                return target
            # Need to inspect each lab for its name
            lower = target.lower()
            for uuid in labs:
                try:
                    info = self.lab_info(uuid)
                    nm = None
                    if isinstance(info, dict):
                        nm = (
                            info.get("title")
                            or info.get("lab_title")
                            or info.get("label")
                            or info.get("name")
                        )
                    if isinstance(nm, str) and nm.strip().lower() == lower:
                        return uuid
                except Exception:
                    continue
        return None

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
