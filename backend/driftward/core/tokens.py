"""Mock security-token service: Ed25519-signed JWTs, RFC 8693 token exchange for narrowing, revocation."""
import time, uuid
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

_KEY = Ed25519PrivateKey.generate()
_PUB = _KEY.public_key()
REVOKED: set[str] = set()
GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"


def public_pem() -> str:
    return _PUB.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def issue(agent: str, scopes: list[str], ttl: int, level: int = 0, contract_version: int = 1, act: str | None = None, sub_jti: str | None = None) -> str:
    now = int(time.time())
    claims = {"iss": "tether-sts", "sub": f"spiffe://tether/agent/{agent}", "aud": "tether-gateway", "iat": now, "exp": now + ttl,
              "jti": uuid.uuid4().hex[:12], "scope": " ".join(scopes), "ctr": contract_version, "lvl": level}
    if act:
        claims["act"] = {"sub": act}
    if sub_jti:
        claims["prev_jti"] = sub_jti
    return jwt.encode(claims, _KEY, algorithm="EdDSA")


def decode(token: str) -> dict:
    return jwt.decode(token, _PUB, algorithms=["EdDSA"], audience="tether-gateway")


def verify(token: str) -> tuple[bool, dict | str]:
    try:
        c = decode(token)
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    if c["jti"] in REVOKED:
        return False, "revoked"
    return True, c


def exchange(subject_token: str, scope: list[str], ttl: int = 300, level: int = 2) -> dict:
    """RFC 8693 token exchange: subject token in, narrowed token out. Scope can only shrink."""
    ok, c = verify(subject_token)
    if not ok:
        raise ValueError(f"subject_token invalid: {c}")
    have = set(c["scope"].split())
    want = [s for s in scope if s in have]  # attenuation: intersection only
    tok = issue(c["sub"].rsplit("/", 1)[-1], want, ttl, level, c.get("ctr", 1), act="spiffe://tether/gateway", sub_jti=c["jti"])
    REVOKED.add(c["jti"])
    return {"access_token": tok, "issued_token_type": "urn:ietf:params:oauth:token-type:access_token", "token_type": "Bearer", "expires_in": ttl, "scope": " ".join(want), "grant_type": GRANT}


def revoke(token: str) -> None:
    ok, c = verify(token)
    if ok:
        REVOKED.add(c["jti"])


def claims_unverified(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})
