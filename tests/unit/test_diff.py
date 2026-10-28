from app.domain.diff import diff_units
from app.domain.units import Unit


def _unit(unit_id, heading, unit_index=0, content_hash=None):
    """Fabrique une Unit minimale pour les tests — seuls unit_id, heading et
    unit_index comptent pour le diff, le reste n'est que de la paperasse."""
    return Unit(
        unit_index=unit_index,
        heading=heading,
        text=f"texte de {unit_id}",
        content_hash=content_hash or f"hash-{unit_id}",
        token_count=10,
        page_id=1,
        unit_id=unit_id,
    )


def test_diff_units_rien_ne_change():
    units = [_unit("a", "Un", unit_index=0), _unit("b", "Deux", unit_index=1)]
    result = diff_units(in_memory=units, in_db=units)
    assert result.unchanged == units
    assert result.new == []
    assert result.deleted == []
    assert result.moved == []
    assert result.modified == []


def test_diff_units_detecte_une_unite_nouvelle():
    in_db = [_unit("a", "Un")]
    in_memory = [_unit("a", "Un"), _unit("b", "Deux")]
    result = diff_units(in_memory, in_db)
    assert result.new == [_unit("b", "Deux")]
    assert result.unchanged == [_unit("a", "Un")]
    assert result.deleted == []
    assert result.modified == []


def test_diff_units_detecte_une_unite_supprimee():
    in_db = [_unit("a", "Un"), _unit("b", "Deux")]
    in_memory = [_unit("a", "Un")]
    result = diff_units(in_memory, in_db)
    assert result.deleted == [_unit("b", "Deux")]
    assert result.new == []


def test_diff_units_detecte_un_deplacement():
    # Même unit_id (contenu identique) mais unit_index différent : aucune
    # écriture de contenu, seulement une mise à jour de position.
    in_db = [_unit("a", "Un", unit_index=0), _unit("b", "Deux", unit_index=1)]
    in_memory = [_unit("b", "Deux", unit_index=0), _unit("a", "Un", unit_index=1)]
    result = diff_units(in_memory, in_db)
    assert {u.unit_id for u in result.moved} == {"a", "b"}
    assert result.new == []
    assert result.deleted == []
    assert result.unchanged == []


def test_diff_units_rapproche_un_nouveau_et_un_supprime_de_meme_titre():
    # Même titre, unit_id différent (le contenu a changé) : rapproché comme
    # "modifié" pour le reporting — jamais pour décider quoi écrire.
    in_db = [_unit("a", "Un")]
    in_memory = [_unit("a-edite", "Un")]
    result = diff_units(in_memory, in_db)
    assert result.modified == [(_unit("a", "Un"), _unit("a-edite", "Un"))]
    assert result.new == []
    assert result.deleted == []


def test_diff_units_ne_rapproche_pas_si_c_est_ambigu():
    # Deux nouveaux et deux supprimés partagent le même titre : impossible
    # de deviner lequel remplace lequel sans se fonder sur la position —
    # donc on ne devine pas, ils restent nouveaux/supprimés tels quels.
    in_db = [_unit("a", "Transcription"), _unit("b", "Transcription")]
    in_memory = [_unit("c", "Transcription"), _unit("d", "Transcription")]
    result = diff_units(in_memory, in_db)
    assert result.modified == []
    assert {u.unit_id for u in result.new} == {"c", "d"}
    assert {u.unit_id for u in result.deleted} == {"a", "b"}
