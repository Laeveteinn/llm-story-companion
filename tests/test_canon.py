from pathlib import Path
import pytest

from writing_runtime.canon import CanonLibrary, build_canon_database

ROOT = Path(__file__).parents[1]


def db(tmp_path):
    path = tmp_path / 'canon.sqlite3'
    build_canon_database(ROOT / 'canon_source', path)
    return path


def test_trigger_and_viewpoint_time(tmp_path):
    with CanonLibrary.load(db(tmp_path)) as lib:
        hits = lib.trigger(
            'Mara tried Sable Bind before the door closed.',
            viewpoint='Mara', at='book1/ch05', scope='writer',
        )
        assert hits and hits[0].id == 'ability.sable_bind'
        rev = hits[0].payload['knowledge']['reveals']
        assert len(rev) == 1 and rev[0]['at'] == 'book1/ch03'


def test_pov_scope_does_not_expose_secret_canon(tmp_path):
    with CanonLibrary.load(db(tmp_path)) as lib:
        hit = lib.trigger('black tether', viewpoint='Mara', at='book1/ch05', scope='pov')[0]
        assert 'canon' not in hit.payload
        assert 'mechanics' not in hit.payload
        assert hit.payload['knowledge']['reveals'][0]['fact_key'] == 'effect'


def test_no_false_substring(tmp_path):
    with CanonLibrary.load(db(tmp_path)) as lib:
        assert not lib.trigger('The sablebindingly strange word should not fire.')


def test_typed_timeline_rejects_unknown_point(tmp_path):
    with CanonLibrary.load(db(tmp_path)) as lib:
        with pytest.raises(ValueError, match='unknown timeline point'):
            lib.trigger('Sable Bind', viewpoint='Mara', at='book1/ch999')


def test_fts_search_is_explicit_and_queryable(tmp_path):
    with CanonLibrary.load(db(tmp_path)) as lib:
        rows = lib.search('contested')
        assert rows and rows[0]['entry_id'] == 'ability.sable_bind'


def test_fact_level_disclosure_does_not_confuse_known_entry_with_known_secret(tmp_path):
    with CanonLibrary.load(db(tmp_path)) as lib:
        assert lib.disclosure_audit(
            'The bind restrains a moving target.', viewpoint='Mara', at='book1/ch05'
        ) == []
        leaks = lib.disclosure_audit(
            'Resistance is a contested roll using d20 + 5.', viewpoint='Mara', at='book1/ch05'
        )
        assert {x.get('fact_key') for x in leaks} == {'resistance_model'}
        assert len(leaks[0]['matches']) == 2
        assert lib.disclosure_audit(
            'Resistance is a contested roll using d20 + 5.', viewpoint='Mara', at='book1/ch09'
        ) == []
