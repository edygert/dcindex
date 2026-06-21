from dcindex.core.models import MaterialKind, SessionCategory
from dcindex.dto.contracts import EventDTO, MaterialDTO, SessionDTO, SpeakerDTO
from dcindex.storage import migrations
from dcindex.storage.db import connect, fts5_available
from dcindex.storage.repositories import Repository


def _event():
    return EventDTO(
        slug="defcon-30", name="DEF CON 30", number=30, year=2022,
        source_url="https://defcon.outel.org/defcon30/dc30_mysqldump.txt",
        sessions=[SessionDTO(
            slug="H1", title="Breaking Kernels", category=SessionCategory.TALK,
            abstract="A new class of kernel bugs", track="OS", room="Track 1",
            source_url="https://forum.defcon.org/node/1001",
            speakers=[SpeakerDTO(name="Alice Lee")],
            materials=[MaterialDTO(title="tool", url="https://github.com/a/b", kind=MaterialKind.TOOL)],
        )],
    )


def test_fts5_available():
    assert fts5_available(connect(":memory:"))


def test_apply_idempotent():
    conn = connect(":memory:")
    assert migrations.apply(conn) == migrations.SCHEMA_VERSION
    assert migrations.apply(conn) == migrations.SCHEMA_VERSION
    assert migrations.current_version(conn) == migrations.SCHEMA_VERSION


def test_save_event_idempotent_and_category():
    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    src = repo.get_or_create_source("dump")

    c1 = repo.save_event(_event(), src)
    repo.commit()
    c2 = repo.save_event(_event(), src)
    repo.commit()

    assert c1.sessions == 1 and c1.materials == 1
    assert c1.by_category == {"talk": 1}
    assert c2.materials == 0  # same material URL not re-inserted
    assert repo.stats()["sessions"] == 1
    assert [dict(r) for r in repo.stats_by_category()] == [{"category": "talk", "sessions": 1}]


def test_fts_search_hits_title_speaker_and_material():
    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    repo.save_event(_event(), repo.get_or_create_source("dump"))
    repo.commit()

    assert [r["title"] for r in repo.search_sessions('"kernel"')] == ["Breaking Kernels"]
    assert repo.search_sessions('"Alice"')  # speaker indexed
    assert repo.search_sessions('"tool"')  # material title indexed


def test_trigram_substring_search():
    """Trigram tokenizer matches a query anywhere inside a word (prefix/infix/suffix)."""
    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    ev = _event()
    ev.sessions[0].title = "Weaponizing Hypervisors"
    repo.save_event(ev, repo.get_or_create_source("dump"))
    repo.commit()

    assert repo.search_sessions('"hyper"')  # prefix of "Hypervisors"
    assert repo.search_sessions('"visor"')  # infix/suffix of "Hypervisors"
    assert not repo.search_sessions('"zzzz"')


def test_like_fallback_for_short_terms():
    """Terms shorter than the trigram minimum still match via the LIKE fallback."""
    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    ev = _event()
    ev.sessions[0].title = "AI Village: OS internals"
    repo.save_event(ev, repo.get_or_create_source("dump"))
    repo.commit()

    assert [r["title"] for r in repo.search_sessions_like(["os"])] == ["AI Village: OS internals"]
    assert repo.search_sessions_like(["ai", "village"])  # ANDed short + long term
    assert not repo.search_sessions_like(["os", "zzz"])  # AND fails


def test_search_service_routes_short_terms_to_like():
    from dcindex.services.search_service import SearchService

    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    ev = _event()
    ev.sessions[0].title = "RF hacking 101"
    repo.save_event(ev, repo.get_or_create_source("dump"))
    repo.commit()

    svc = SearchService(repo)
    assert [r["title"] for r in svc.search("rf")] == ["RF hacking 101"]  # 2-char term works
    assert svc.search("a") == [] or svc.search("a")  # 1-char doesn't crash


def test_count_and_unlimited_search():
    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    src = repo.get_or_create_source("dump")
    for i in range(5):
        ev = _event()
        ev.sessions[0].slug = f"S{i}"
        ev.sessions[0].title = f"Security topic {i}"
        repo.save_event(ev, src)
    repo.commit()

    # FTS path
    assert repo.count_sessions('"security"') == 5
    assert len(repo.search_sessions('"security"', limit=2)) == 2
    assert len(repo.search_sessions('"security"', limit=None)) == 5  # --all
    # LIKE path (short term)
    assert repo.count_sessions_like(["sec"]) == 5
    assert len(repo.search_sessions_like(["sec"], limit=2)) == 2
    assert len(repo.search_sessions_like(["sec"], limit=None)) == 5


def test_search_service_count_matches_results():
    from dcindex.services.search_service import SearchService

    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    src = repo.get_or_create_source("dump")
    for i in range(3):
        ev = _event()
        ev.sessions[0].slug = f"S{i}"
        ev.sessions[0].title = f"Kernel topic {i}"
        repo.save_event(ev, src)
    repo.commit()

    svc = SearchService(repo)
    assert svc.count("kernel") == 3
    assert len(svc.search("kernel", limit=1)) == 1
    assert len(svc.search("kernel", limit=None)) == 3
    assert svc.count("nomatchxyz") == 0


def test_reingest_replaces_speaker_links_and_prunes():
    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    src = repo.get_or_create_source("dump")

    ev = _event()
    ev.sessions[0].speakers = [SpeakerDTO(name="Alice Lee", affiliation="Acme Inc")]
    repo.save_event(ev, src)
    ev.sessions[0].speakers = [SpeakerDTO(name="Alice Lee", affiliation="Acme")]
    repo.save_event(ev, src)
    repo.commit()

    sid = conn.execute("SELECT id FROM sessions").fetchone()[0]
    links = conn.execute(
        "SELECT COUNT(*) FROM session_speakers WHERE session_id = ?", (sid,)
    ).fetchone()[0]
    assert links == 1
    assert repo.prune_orphan_speakers() == 1
