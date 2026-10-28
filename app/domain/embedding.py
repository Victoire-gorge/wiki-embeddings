import hashlib
from abc import ABC, abstractmethod

Vector = list[float]


class EmbeddingBackend(ABC):
    """Tout ce qui change quand on change de modèle, rien d'autre.

    `embed` rend les vecteurs **dans le même ordre que `texts`** —
    correspondance par position, pas par identifiant : à l'appelant de la
    réassocier à ses propres `unit_id` en conservant cet ordre.

    Tout ou rien : soit la liste complète (même longueur que `texts`), soit
    une exception, jamais un résultat partiel — pour ne jamais marquer
    `embedded_at` sur une unité qui n'a pas de vecteur en face.

    Les vecteurs ne sont pas garantis de norme 1 (vrai pour OpenAI, pas
    forcément pour un futur modèle local) : tout calcul de similarité en
    dehors de Qdrant doit utiliser le cosinus, jamais le produit scalaire
    brut.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> list[Vector]:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        ...


class FakeEmbeddingBackend(EmbeddingBackend):
    """Backend déterministe pour les tests — pas de réseau, pas de clé, pas
    de coût. Le vecteur dérive du hash du texte : deux appels sur la même
    entrée rendent le même vecteur, ce qui permet de tester l'idempotence
    sans dépendre d'un aléa."""

    def __init__(self, dimension: int = 8):
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return "fake"

    @property
    def dimension(self) -> int:
        return self._dimension

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def embed(self, texts: list[str]) -> list[Vector]:
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> Vector:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [digest[i % len(digest)] / 255 for i in range(self._dimension)]
