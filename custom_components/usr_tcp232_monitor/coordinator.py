"""Data coordinator for USR TCP232 diagnostic endpoints."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class UsrAuthError(Exception):
    """Raised when the USR panel rejects the supplied credentials."""


def _bytes(value: Any) -> int | None:
    """Parse a byte counter such as '233226 bytes'."""
    if value is None:
        return None
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else None


def _parse_auth_params(header: str) -> tuple[str, dict[str, str]]:
    """Parse a WWW-Authenticate challenge without logging its contents."""
    match = re.match(r"^\s*(Basic|Digest)\s*(.*)$", header, re.IGNORECASE)
    if not match:
        return "", {}
    scheme, remainder = match.group(1).lower(), match.group(2)
    params: dict[str, str] = {}
    pattern = r'([A-Za-z][A-Za-z0-9_-]*)\s*=\s*(?:"((?:\\.|[^"])*)"|([^,\s]+))'
    for item in re.finditer(pattern, remainder):
        value = item.group(2) if item.group(2) is not None else item.group(3)
        params[item.group(1).lower()] = re.sub(r"\\(.)", r"\1", value)
    return scheme, params


def _hash_digest(value: str, algorithm: str) -> str:
    """Hash an HTTP Digest value for supported algorithms."""
    normalized = algorithm.upper()
    if normalized in ("MD5", "MD5-SESS"):
        return hashlib.md5(value.encode("utf-8"), usedforsecurity=False).hexdigest()
    if normalized in ("SHA-256", "SHA-256-SESS"):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    raise ValueError("Unsupported HTTP Digest algorithm")


def _quote_auth(value: str) -> str:
    """Quote a value for an Authorization header."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class UsrCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch status and device identity from the USR web interface."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.host = config[CONF_HOST]
        self.base_url = f"http://{self.host}"
        self._username = config[CONF_USERNAME]
        self._password = config[CONF_PASSWORD]
        self._auth_scheme: str | None = None
        self._digest_challenge: dict[str, str] | None = None
        self._nonce_count = 0
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def _digest_header(self, method: str, url: str) -> str:
        """Build an HTTP Digest Authorization header from the current challenge."""
        challenge = self._digest_challenge
        if not challenge or not challenge.get("realm") or not challenge.get("nonce"):
            raise UsrAuthError("Incomplete HTTP Digest challenge")

        algorithm = challenge.get("algorithm", "MD5").upper()
        base_algorithm = algorithm.removesuffix("-SESS")
        parsed = urlsplit(url)
        uri = parsed.path or "/"
        if parsed.query:
            uri += f"?{parsed.query}"

        ha1 = _hash_digest(
            f"{self._username}:{challenge['realm']}:{self._password}",
            base_algorithm,
        )
        cnonce = secrets.token_hex(12)
        if algorithm.endswith("-SESS"):
            ha1 = _hash_digest(f"{ha1}:{challenge['nonce']}:{cnonce}", base_algorithm)
        ha2 = _hash_digest(f"{method}:{uri}", base_algorithm)
        qop_options = [part.strip() for part in challenge.get("qop", "").split(",")]
        qop = "auth" if "auth" in qop_options else ""
        self._nonce_count += 1
        nc = f"{self._nonce_count:08x}"

        if qop:
            response = _hash_digest(
                f"{ha1}:{challenge['nonce']}:{nc}:{cnonce}:{qop}:{ha2}",
                base_algorithm,
            )
        else:
            response = _hash_digest(f"{ha1}:{challenge['nonce']}:{ha2}", base_algorithm)

        fields = [
            f"username={_quote_auth(self._username)}",
            f"realm={_quote_auth(challenge['realm'])}",
            f"nonce={_quote_auth(challenge['nonce'])}",
            f"uri={_quote_auth(uri)}",
            f"response={_quote_auth(response)}",
            f"algorithm={algorithm}",
        ]
        if challenge.get("opaque"):
            fields.append(f"opaque={_quote_auth(challenge['opaque'])}")
        if qop:
            fields.extend([f"qop={qop}", f"nc={nc}", f"cnonce={_quote_auth(cnonce)}"])
        return "Digest " + ", ".join(fields)

    async def _request_json(
        self, session: aiohttp.ClientSession, endpoint: str
    ) -> dict[str, Any]:
        """Request JSON, detecting the device's Basic or Digest auth challenge."""
        url = f"{self.base_url}/{endpoint}"
        if self._auth_scheme == "basic":
            context = session.get(
                url, auth=aiohttp.BasicAuth(self._username, self._password), allow_redirects=False
            )
        elif self._auth_scheme == "digest":
            context = session.get(
                url, headers={"Authorization": self._digest_header("GET", url)}, allow_redirects=False
            )
        else:
            context = session.get(url, allow_redirects=False)

        challenge_to_retry: tuple[str, dict[str, str]] | None = None
        async with context as response:
            if response.status == 401:
                parsed = [_parse_auth_params(value) for value in response.headers.getall("WWW-Authenticate", [])]
                digest = next((params for scheme, params in parsed if scheme == "digest"), None)
                basic = next((params for scheme, params in parsed if scheme == "basic"), None)
                if digest is not None:
                    algorithm = digest.get("algorithm", "MD5").upper()
                    if algorithm not in ("MD5", "MD5-SESS", "SHA-256", "SHA-256-SESS"):
                        raise UpdateFailed("USR offered an unsupported Digest algorithm")
                    qop = [part.strip() for part in digest.get("qop", "").split(",")]
                    if digest.get("qop") and "auth" not in qop:
                        raise UpdateFailed("USR Digest challenge does not support qop=auth")
                    challenge_to_retry = ("digest", digest)
                elif basic is not None:
                    challenge_to_retry = ("basic", basic)
                else:
                    raise UsrAuthError("USR returned an unsupported authentication challenge")
            else:
                if 300 <= response.status < 400:
                    raise UpdateFailed(f"Unexpected redirect from {endpoint}")
                response.raise_for_status()
                payload = await response.json(content_type=None)
                if not isinstance(payload, dict):
                    raise UpdateFailed(f"{endpoint} returned non-object JSON")
                return payload

        # The 401 response has now been released before retrying with credentials.
        if challenge_to_retry:
            scheme, challenge = challenge_to_retry
            if scheme == "digest":
                self._auth_scheme = "digest"
                self._digest_challenge = challenge
                self._nonce_count = 0
                auth_header = self._digest_header("GET", url)
                retry_context = session.get(
                    url, headers={"Authorization": auth_header}, allow_redirects=False
                )
            else:
                self._auth_scheme = "basic"
                retry_context = session.get(
                    url, auth=aiohttp.BasicAuth(self._username, self._password), allow_redirects=False
                )
            async with retry_context as response:
                if response.status in (401, 403):
                    raise UsrAuthError("USR rejected the supplied credentials")
                if 300 <= response.status < 400:
                    raise UpdateFailed(f"Unexpected redirect from {endpoint}")
                response.raise_for_status()
                payload = await response.json(content_type=None)
                if not isinstance(payload, dict):
                    raise UpdateFailed(f"{endpoint} returned non-object JSON")
                return payload

        raise UpdateFailed(f"Could not read USR TCP232 endpoint {endpoint}")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch endpoints sequentially with a properly closed HTTP session."""
        endpoint = "temp_status.json"
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                status = await self._request_json(session, endpoint)
                endpoint = "define.json"
                identity = await self._request_json(session, endpoint)
                # This response may contain MQTT credentials. Only retain the enable flag.
                endpoint = "mqttbase.json"
                mqtt = await self._request_json(session, endpoint)
                mqtt_enabled = str(mqtt.get("mqtten", "")) == "1"
                del mqtt

            return {
                "status": status,
                "identity": identity,
                "mqtt_enabled": mqtt_enabled,
                "tx_a": _bytes(status.get("txcounta")),
                "rx_a": _bytes(status.get("rxcounta")),
                "tx_b": _bytes(status.get("txcountb")),
                "rx_b": _bytes(status.get("rxcountb")),
            }
        except UsrAuthError as err:
            _LOGGER.warning(
                "USR TCP232 authentication failed (host=%s, endpoint=%s)", self.host, endpoint
            )
            raise UpdateFailed("USR TCP232 authentication failed") from err
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, UpdateFailed) as err:
            _LOGGER.warning(
                "USR TCP232 request failed (host=%s, endpoint=%s, error=%s)",
                self.host, endpoint, type(err).__name__
            )
            raise UpdateFailed(f"Could not read USR TCP232 endpoint {endpoint}") from err
