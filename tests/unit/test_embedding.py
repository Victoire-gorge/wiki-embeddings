import pytest

from app.domain.embedding import EmbeddingBackend, FakeEmbeddingBackend


def test_embedding_backend_est_abstraite():
    with pytest.raises(TypeError):
        EmbeddingBackend()


def test_fake_embedding_backend_rend_un_vecteur_par_texte():
    backend = FakeEmbeddingBackend(dimension=4)
    vectors = backend.embed(["un", "deux", "trois"])
    assert len(vectors) == 3
    assert all(len(v) == backend.dimension for v in vectors)


def test_fake_embedding_backend_conserve_l_ordre():
    backend = FakeEmbeddingBackend()
    a, b = backend.embed(["alpha", "beta"])
    beta, alpha = backend.embed(["beta", "alpha"])
    assert a == alpha
    assert b == beta


def test_fake_embedding_backend_est_deterministe():
    backend = FakeEmbeddingBackend()
    assert backend.embed(["même texte"]) == backend.embed(["même texte"])


def test_fake_embedding_backend_distingue_des_textes_differents():
    backend = FakeEmbeddingBackend()
    v1, v2 = backend.embed(["un texte", "un autre texte"])
    assert v1 != v2


def test_fake_embedding_backend_sur_une_liste_vide():
    backend = FakeEmbeddingBackend()
    assert backend.embed([]) == []


def test_fake_embedding_backend_expose_son_nom_et_sa_dimension():
    backend = FakeEmbeddingBackend(dimension=16)
    assert backend.model_name == "fake"
    assert backend.dimension == 16
