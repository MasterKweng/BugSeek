"""Table name normalization utilities."""
import re

try:
    import inflect  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    inflect = None

_inflect_engine = inflect.engine() if inflect else None


def _singularize_token(token: str) -> str:
    if not token:
        return token

    if _inflect_engine:
        singular = _inflect_engine.singular_noun(token)
        return singular if singular else token

    # Fallback singularization for environments where inflect is unavailable/incompatible.
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("ses") and len(token) > 3:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 1:
        return token[:-1]
    return token


def normalize_name(name: str) -> str:
    """
    Normalize ERP-style table names.

    Rules:
    1. lower case
    2. remove common prefixes: t_, sys_, erp_
    3. singularize underscore-separated tokens
    """
    if not name:
        return ""

    normalized = name.strip().lower()
    normalized = re.sub(r"^(t_|sys_|erp_)", "", normalized)
    normalized = re.sub(r"[^a-z0-9_]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    if not normalized:
        return ""

    tokens = [token for token in normalized.split("_") if token]
    singular_tokens = [_singularize_token(token) for token in tokens]

    return "_".join(singular_tokens)
