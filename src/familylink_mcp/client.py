import hashlib
import time

import browser_cookie3
import httpx

BASE = "https://kidsmanagement-pa.clients6.google.com/kidsmanagement/v1"
ORIGIN = "https://familylink.google.com"
API_KEY = "AIzaSyAQb1gupaJhY3CXQy2xmTwJMcjmot3M2hw"
PROTOBUF_JSON = "application/json+protobuf"
MAX_AUTHUSER = 5


class FamilyLinkError(RuntimeError):
    pass


def fail(message: str):
    raise FamilyLinkError(message)


def sapisid_hash(sapisid: str, now_ms: int) -> str:
    digest = hashlib.sha1(f"{now_ms} {sapisid} {ORIGIN}".encode()).hexdigest()
    return f"SAPISIDHASH {now_ms}_{digest}"


def find_sapisid(jar) -> str:
    value = next((c.value for c in jar if c.name == "SAPISID" and c.domain == ".google.com"), None)
    return value if value is not None else fail("No Google session in Chrome; sign in to familylink.google.com as the parent")


def is_parent_family(response: httpx.Response) -> bool:
    return response.status_code == 200 and bool(response.json().get("members"))


class Client:
    def __init__(self, jar=None):
        self.jar = jar if jar is not None else browser_cookie3.chrome(domain_name="google.com")
        self.sapisid = find_sapisid(self.jar)
        self.http = httpx.Client(cookies=self.jar, timeout=30)
        self.authuser = self._find_authuser()

    def _headers(self, authuser: int, content_type: str | None) -> dict:
        base = {
            "Origin": ORIGIN,
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-AuthUser": str(authuser),
            "Authorization": sapisid_hash(self.sapisid, int(time.time() * 1000)),
        }
        return base | ({"Content-Type": content_type} if content_type else {})

    def _send(self, authuser: int, method: str, path: str, params=None, body: str | None = None) -> httpx.Response:
        return self.http.request(
            method,
            f"{BASE}/{path}",
            params=params,
            content=body,
            headers=self._headers(authuser, PROTOBUF_JSON if body is not None else None),
        )

    def _find_authuser(self) -> int:
        found = next(
            (n for n in range(MAX_AUTHUSER) if is_parent_family(self._send(n, "GET", "families/mine/members"))),
            None,
        )
        return found if found is not None else fail("No Family Link family found for the signed-in Google accounts")

    def request(self, method: str, path: str, params=None, body: str | None = None):
        response = self._send(self.authuser, method, path, params, body)
        return (
            response.json() if response.status_code == 200
            else fail(f"{method} {path}: HTTP {response.status_code} {response.text[:300]}")
        )

    def get(self, path: str, **params):
        return self.request("GET", path, params=params)
