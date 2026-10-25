"""
Who may use a server, and by what name.

A request must be addressed (Host) to this Mac (127.0.0.1, localhost, ::1) or a name in
TAILNET_HOSTS (career-kit/.env), port aside. A page on another site can point its own name at
127.0.0.1 (DNS rebinding) to reach a server here as if from this Mac; its requests still carry
its own name, so they are refused.

Over the tailnet, only you may use it. tailscale serve sends a request on with
X-Forwarded-For and the sender's tailnet login in Tailscale-User-Login, which serve sets itself
and never passes on from the sender. A request with either must carry a login in TAILNET_LOGINS
(career-kit/.env); one with neither came from this Mac and is let through.

The writers (app.py) and the read API (api/main.py) both use it.
"""

from collections.abc import Iterable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .env import env_value

LOGIN_HEADER = "Tailscale-User-Login"
FORWARDED_HEADER = "X-Forwarded-For"


def tailnet_logins(env_file: Path | None = None) -> frozenset[str]:
    """TAILNET_LOGINS from the .env file, comma separated."""
    value = env_value("TAILNET_LOGINS", env_file) or ""
    return frozenset(login.strip() for login in value.split(",") if login.strip())


LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def tailnet_hosts(env_file: Path | None = None) -> frozenset[str]:
    """TAILNET_HOSTS from the .env file, comma separated: this Mac's tailnet names."""
    value = env_value("TAILNET_HOSTS", env_file) or ""
    return frozenset(host.strip().lower() for host in value.split(",") if host.strip())


def host_name(host: str) -> str:
    """The name in a Host header, without its port: "[::1]:8100" -> "::1"."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1:].split("]")[0]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def add_identity_check(app: FastAPI, allowed: Iterable[str], only_you: str, hosts: Iterable[str]) -> None:
    """Refuses a request addressed to a name not this Mac's or in hosts, and a request over the
    tailnet from anyone not in allowed. only_you starts the reason: "Changes come only from the owner." """
    allowed = frozenset(allowed)
    names = LOCAL_HOSTS | frozenset(h.lower() for h in hosts)

    @app.middleware("http")
    async def only_owner(request: Request, call_next):
        name = host_name(request.headers.get("host", ""))
        if name not in names:
            return JSONResponse({"detail": f"This only answers to its own names, not {name or 'no name'}."}, 403)
        login = request.headers.get(LOGIN_HEADER)
        if login is not None or FORWARDED_HEADER in request.headers:
            if not allowed:
                return JSONResponse(
                    {"detail": "No one may use this over the tailnet yet. Set TAILNET_LOGINS in career-kit/.env."}, 403
                )
            if login not in allowed:
                return JSONResponse({"detail": f"{only_you} This came from {login or 'a device with no login'}."}, 403)
        return await call_next(request)
