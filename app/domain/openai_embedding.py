import logging
import time

import openai
import tiktoken

from app.domain.embedding import EmbeddingBackend, Vector

logger = logging.getLogger(__name__)

_MODEL_NAME = "text-embedding-3-small"
_DIMENSION = 1536
_TOKENIZER_ENCODING = "cl100k_base"

_MAX_RATE_LIMIT_RETRIES = 5
_INITIAL_BACKOFF_SECONDS = 1.0


def is_quota_exhausted(error: openai.RateLimitError) -> bool:
    """Distingue un quota épuisé (ne réussira jamais, inutile de réessayer)
    d'un débit dépassé (réessayer avec attente croissante).

    Vérifié sur le SDK installé (openai 1.x) : `_should_retry` dans son
    `_base_client.py` retry tout 429 sans lire le corps de la réponse — il
    ne fait pas cette distinction. Le corps, lui, porte `code` =
    `"insufficient_quota"` dans ce cas précis.
    """
    return error.code == "insufficient_quota"


class OpenAIEmbeddingBackend(EmbeddingBackend):
    """Implémentation OpenAI du contrat — non testée unitairement au-delà
    de `is_quota_exhausted` (voir tests/unit/test_openai_embedding.py).
    Le reste (appel réseau réel, lecture de la réponse) est vérifié
    manuellement une fois contre le vrai service avant tout run réel, pas
    par la suite automatisée : voir la discussion dans la PR qui introduit
    ce fichier pour pourquoi un mock de l'appel HTTP n'apporterait rien
    ici.
    """

    def __init__(self, client: openai.OpenAI | None = None):
        # max_retries=0 : le SDK ne distingue pas quota épuisé de débit
        # dépassé (voir is_quota_exhausted), on gère nous-mêmes les 429.
        self._client = client or openai.OpenAI(max_retries=0)
        self._encoding = tiktoken.get_encoding(_TOKENIZER_ENCODING)

    @property
    def model_name(self) -> str:
        return _MODEL_NAME

    @property
    def dimension(self) -> int:
        return _DIMENSION

    def count_tokens(self, text: str) -> int:
        return len(self._encoding.encode_ordinary(text))

    def embed(self, texts: list[str]) -> list[Vector]:
        if not texts:
            return []

        attempt = 0
        backoff = _INITIAL_BACKOFF_SECONDS
        while True:
            try:
                response = self._client.embeddings.create(
                    model=_MODEL_NAME, input=texts
                )
                break
            except openai.RateLimitError as error:
                if is_quota_exhausted(error):
                    raise
                attempt += 1
                if attempt > _MAX_RATE_LIMIT_RETRIES:
                    raise
                logger.warning(
                    "débit OpenAI dépassé, nouvelle tentative dans %.1fs (%d/%d)",
                    backoff,
                    attempt,
                    _MAX_RATE_LIMIT_RETRIES,
                )
                time.sleep(backoff)
                backoff *= 2

        # response.data[i].index correspond à la position dans `texts` —
        # trié explicitement plutôt que supposé déjà dans l'ordre, pour ne
        # pas reposer sur un détail d'implémentation non garanti par écrit.
        ordered = sorted(response.data, key=lambda item: item.index)

        estimated = sum(self.count_tokens(t) for t in texts)
        logger.info(
            "vectorisation : %d textes, estimé %d tokens, facturé %d tokens",
            len(texts),
            estimated,
            response.usage.total_tokens,
        )
        return [item.embedding for item in ordered]
