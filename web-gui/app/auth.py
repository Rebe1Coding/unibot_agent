"""Google OAuth 2.0 login flow and JWT session cookie for the web GUI."""

from __future__ import annotations

import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import settings

logger = logging.getLogger("web-gui.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_STATE_COOKIE = "unibot_oauth_state"


def _issue_jwt(user: dict) -> str:
    """Sign a session JWT for an authenticated Google user."""
    now = int(time.time())
    payload = {
        "sub": user["sub"],
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "picture": user.get("picture", ""),
        "iat": now,
        "exp": now + settings.jwt_ttl_seconds,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def current_user(request: Request) -> dict | None:
    """Decode the session cookie into a user dict, or None if missing/invalid."""
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.jwt_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect the browser to Google's consent screen."""
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="Google OAuth не настроен")
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    response = RedirectResponse(f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")
    response.set_cookie(
        _STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/google/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None) -> RedirectResponse:
    """Exchange the authorization code for user info and set the session cookie."""
    expected = request.cookies.get(_STATE_COOKIE)
    if not code or not state or state != expected:
        raise HTTPException(status_code=400, detail="Некорректный ответ авторизации")

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.warning("Token exchange failed: %s", token_resp.text)
            raise HTTPException(status_code=502, detail="Не удалось получить токен Google")
        access_token = token_resp.json().get("access_token")

        info_resp = await client.get(_GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if info_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Не удалось получить профиль Google")
        info = info_resp.json()

    if not info.get("sub"):
        raise HTTPException(status_code=502, detail="Профиль Google без идентификатора")

    response = RedirectResponse(settings.post_login_redirect, status_code=303)
    _set_session_cookie(response, _issue_jwt(info))
    response.delete_cookie(_STATE_COOKIE, path="/")
    return response


@router.get("/me")
async def me(request: Request) -> JSONResponse:
    """Return the current user, or 401 if not authenticated."""
    user = current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Не авторизован"})
    return JSONResponse(
        {"user_id": user["sub"], "email": user.get("email"), "name": user.get("name"), "picture": user.get("picture")}
    )


@router.post("/logout")
async def logout() -> JSONResponse:
    """Clear the session cookie."""
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(settings.cookie_name, path="/")
    return response
