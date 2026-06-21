from dcindex.core.models import SessionCategory
from dcindex.dto.contracts import EventDTO, MaterialDTO, SessionDTO, SpeakerDTO
from dcindex.services.session_service import SessionService
from dcindex.storage import migrations
from dcindex.storage.db import connect
from dcindex.storage.repositories import Repository


def _setup():
    conn = connect(":memory:")
    migrations.apply(conn)
    repo = Repository(conn)
    ev = EventDTO(
        slug="defcon-30", name="DEF CON 30", number=30, year=2022,
        sessions=[SessionDTO(
            slug="H1", title="Breaking Kernels", category=SessionCategory.TALK,
            abstract="bugs", room="Track 1", starts_at="Saturday 14:30-15:30",
            source_url="https://forum.defcon.org/node/1001",
            speakers=[SpeakerDTO(name="Alice Lee", affiliation="Acme")],
            materials=[
                MaterialDTO(title="tool", url="https://github.com/a/b"),
                MaterialDTO(title="slides", url="https://x/s.pdf"),
            ],
        )],
    )
    repo.save_event(ev, repo.get_or_create_source("dump"))
    repo.commit()
    sid = conn.execute("SELECT id FROM sessions").fetchone()[0]
    return SessionService(repo), sid


def test_get_detail():
    svc, sid = _setup()
    detail = svc.get(sid)
    assert detail.title == "Breaking Kernels"
    assert detail.event_name == "DEF CON 30"
    assert detail.category is SessionCategory.TALK
    assert detail.speakers[0].name == "Alice Lee"
    assert detail.speakers[0].affiliation == "Acme"
    assert {m.url for m in detail.materials} == {"https://github.com/a/b", "https://x/s.pdf"}
    assert svc.get(999_999) is None


def test_get_many_order_and_skips_missing():
    svc, sid = _setup()
    details = svc.get_many([999_999, sid, 888_888])  # missing ids dropped, order preserved
    assert [d.id for d in details] == [sid]
    assert svc.get_many([]) == []


def test_get_many_json_has_full_metadata():
    svc, sid = _setup()
    payload = [d.model_dump(mode="json") for d in svc.get_many([sid])]
    obj = payload[0]
    assert {"id", "title", "category", "abstract", "speakers", "materials", "source_url"} <= obj.keys()
    assert obj["category"] == "talk"  # StrEnum serialized to plain string
    assert obj["speakers"][0]["name"] == "Alice Lee"
    assert {m["url"] for m in obj["materials"]} == {"https://github.com/a/b", "https://x/s.pdf"}
    assert isinstance(obj["materials"][0]["kind"], str)
