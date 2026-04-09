#!/usr/bin/env python3
import logging
import os
import sys
import json
import argparse
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import requests

from common import get_secrets_manager, configure_logging

# Initialize logging
configure_logging()
logger = logging.getLogger(__name__)

# ===================== Config via secrets manager =====================
_secrets = get_secrets_manager()

TOKEN_URL = _secrets.get_secret("MOTUS_TOKEN_URL") or "https://token.motus.com/tokenservice/token/api"
LOGIN_ID  = _secrets.get_secret("MOTUS_LOGIN_ID") or ""
PASSWORD  = _secrets.get_secret("MOTUS_PASSWORD") or ""

# TTL default when no expires_in or exp in JWT (55 min like in Postman)
DEFAULT_TTL_SECONDS = int(_secrets.get_secret("MOTUS_DEFAULT_TTL_SECONDS") or str(55 * 60))

# Cache & refresh window
CACHE_PATH = _secrets.get_secret("MOTUS_TOKEN_CACHE") or ".motus_token.json"
REFRESH_SAFETY = int(_secrets.get_secret("MOTUS_TOKEN_REFRESH_SAFETY") or "60")

DEBUG = (_secrets.get_secret("DEBUG") or "0") == "1"


def dlog(msg: str):
    if DEBUG:
        logger.debug(msg)


def now_ts() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def load_cache() -> Optional[Dict[str, Any]]:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(d: Dict[str, Any]) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)


def cached_ok(c: Dict[str, Any]) -> bool:
    if not c:
        return False
    t, exp = c.get("access_token"), c.get("expires_at")
    return bool(t and exp and (int(exp) - now_ts() > REFRESH_SAFETY))


def token_headers() -> Dict[str, str]:
    # Aceptamos JSON y texto plano, como en Postman
    return {
        "Accept": "application/json, text/plain, */*",
    }


def request_token_form() -> requests.Response:
    """
    Request token using form-urlencoded format.
    Per Motus API docs: only loginId and password are required (no grant_type).
    """
    payload = {
        "loginId": LOGIN_ID,
        "password": PASSWORD,
    }
    return requests.post(
        TOKEN_URL,
        headers={**token_headers(), "Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
        timeout=30,
    )


def request_token_json() -> requests.Response:
    """
    Request token using JSON format (fallback).
    Per Motus API docs: only loginId and password are required (no grant_type).
    """
    payload = {
        "loginId": LOGIN_ID,
        "password": PASSWORD,
    }
    return requests.post(
        TOKEN_URL,
        headers={**token_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )


def request_token() -> Dict[str, Any]:
    # Log MOTUS credentials and URL for token generation
    logger.info(f"MOTUS TOKEN REQUEST | URL: {TOKEN_URL}")
    logger.info(f"MOTUS TOKEN REQUEST | USERNAME (loginId): {LOGIN_ID}")
    logger.info(f"MOTUS TOKEN REQUEST | PASSWORD: {PASSWORD}")

    # 1) intenta como x-www-form-urlencoded
    r = request_token_form()
    logger.info(f"MOTUS TOKEN REQUEST | POST {TOKEN_URL} (form) -> Status: {r.status_code} | Content-Type: {r.headers.get('Content-Type')}")
    if r.status_code < 300:
        try:
            return r.json()
        except Exception:
            return {"raw_text": (r.text or "").strip()}

    # 2) intenta como JSON
    r = request_token_json()
    logger.info(f"MOTUS TOKEN REQUEST | POST {TOKEN_URL} (json) -> Status: {r.status_code} | Content-Type: {r.headers.get('Content-Type')}")
    if r.status_code < 300:
        try:
            return r.json()
        except Exception:
            return {"raw_text": (r.text or "").strip()}

    # error legible
    body = (r.text or "")[:500]
    try:
        body = json.dumps(r.json())[:1000]
    except Exception:
        pass
    raise SystemExit(f"Token request failed {r.status_code}: {body}")


def b64url_decode_to_bytes(s: str) -> bytes:
    # base64url -> bytes (con padding)
    s = s.replace("-", "+").replace("_", "/")
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s + pad)


def infer_exp_from_jwt(jwt_token: str) -> Optional[int]:
    """
    Si el token tiene formato JWT (tres segmentos), decodifica el payload y devuelve exp (epoch segundos).
    """
    parts = jwt_token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload_b = b64url_decode_to_bytes(parts[1])
        payload = json.loads(payload_b.decode("utf-8", errors="ignore"))
        exp = payload.get("exp")
        return int(exp) if exp else None
    except Exception:
        return None


def normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Admite:
      - JSON: { access_token | token | bearerToken, expires_in? }
      - Texto plano en raw['raw_text'] (token directamente)
    Si no hay expires_in, intenta leer exp del JWT; si tampoco, usa DEFAULT_TTL_SECONDS.
    """
    token = raw.get("access_token") or raw.get("token") or raw.get("bearerToken")
    if not token and raw.get("raw_text"):
        token = raw["raw_text"]

    if not token:
        raise SystemExit(f"Token response missing access_token/token. Raw: {json.dumps(raw)[:500]}")

    # Determinar expiración
    expires_in = raw.get("expires_in") or raw.get("expiresIn")
    if expires_in:
        try:
            expires_in = int(expires_in)
        except Exception:
            expires_in = None

    expires_at: Optional[int] = None
    if not expires_in:
        # Probar con exp del JWT
        exp_from_jwt = infer_exp_from_jwt(token)
        if exp_from_jwt:
            expires_at = exp_from_jwt
        else:
            # TTL por defecto (55m desde ahora)
            expires_at = now_ts() + DEFAULT_TTL_SECONDS
    else:
        expires_at = now_ts() + int(expires_in)

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": int(expires_at - now_ts()),
        "expires_at": int(expires_at),
        "raw": raw,
    }


def get_token(force_refresh: bool = False) -> Dict[str, Any]:
    if not LOGIN_ID or not PASSWORD:
        raise SystemExit("Missing MOTUS_LOGIN_ID / MOTUS_PASSWORD")
    cache = load_cache()
    if cache and not force_refresh and cached_ok(cache):
        dlog("Using cached token")
        return cache
    dlog("Requesting new token")
    norm = normalize(request_token())
    save_cache(norm)
    return norm


# =============== helpers .env ===============
def read_env_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    return open(path, "r", encoding="utf-8").read().splitlines()


def write_env(path: str, updates: Dict[str, str]) -> None:
    lines = read_env_lines(path)
    keys = set(updates.keys())
    out, seen = [], set()
    for line in lines:
        if not line.strip() or line.strip().startswith("#"):
            out.append(line)
            continue
        if "=" in line:
            k = line.split("=", 1)[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}")
                seen.add(k)
            else:
                out.append(line)
        else:
            out.append(line)
    for k in (keys - seen):
        out.append(f"{k}={updates[k]}")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, path)


def parse_cli():
    ap = argparse.ArgumentParser(description="Get Motus JWT (grant_type=password) con cache y soporte .env")
    ap.add_argument("--json", action="store_true", help="Imprime JSON normalizado")
    ap.add_argument("--print-export", action="store_true", help='Imprime: export MOTUS_JWT="..."')
    ap.add_argument("--force", action="store_true", help="Ignora el cache y fuerza refresh")
    ap.add_argument("--write-env", action="store_true", help="Escribe MOTUS_JWT y MOTUS_JWT_EXPIRES_AT en .env")
    ap.add_argument("--env-path", default=".env", help="Ruta al .env (default .env)")
    return ap.parse_args()


def main():
    args = parse_cli()
    tok = get_token(force_refresh=args.force)
    exp_iso = datetime.fromtimestamp(tok["expires_at"], tz=timezone.utc).isoformat()

    if args.write_env:
        write_env(args.env_path, {
            "MOTUS_JWT": tok["access_token"],
            "MOTUS_JWT_EXPIRES_AT": str(tok["expires_at"]),
        })
        logger.info(f".env updated at {args.env_path} (expires_at={exp_iso})")
        return

    if args.json:
        print(json.dumps({
            "access_token": tok["access_token"],
            "token_type": tok["token_type"],
            "expires_in": tok["expires_in"],
            "expires_at": tok["expires_at"],
            "expires_at_iso": exp_iso
        }, indent=2))
        return

    if args.print_export:
        print(f'export MOTUS_JWT="{tok["access_token"]}"')
        return

    print(tok["access_token"])


if __name__ == "__main__":
    main()