import httpx
import openai

from app.domain.openai_embedding import is_quota_exhausted

_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
_RESPONSE = httpx.Response(429, request=_REQUEST)


def _rate_limit_error(code: str) -> openai.RateLimitError:
    return openai.RateLimitError(
        "erreur de test", response=_RESPONSE, body={"code": code}
    )


def test_is_quota_exhausted_detecte_le_quota_epuise():
    assert is_quota_exhausted(_rate_limit_error("insufficient_quota")) is True


def test_is_quota_exhausted_laisse_passer_un_debit_depasse():
    assert is_quota_exhausted(_rate_limit_error("rate_limit_exceeded")) is False
