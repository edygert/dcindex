from dcindex.core.editions import parse_edition
from dcindex.core.models import MaterialKind, SessionCategory
from dcindex.parsers.mysqldump import parse_dump
from dcindex.parsers.schedule import map_tables


def _map(dump_sql, **kw):
    return map_tables(parse_dump(dump_sql), parse_edition("dc30"), **kw)


def _by_slug(event, slug):
    return next(s for s in event.sessions if s.slug == slug)


def test_event_identity_and_counts(dump_sql):
    res = _map(dump_sql)
    assert res.event.slug == "defcon-30"
    assert res.event.year == 2022
    cats = {s.category for s in res.event.sessions}
    assert cats == {
        SessionCategory.TALK, SessionCategory.DEMOLAB,
        SessionCategory.VILLAGE, SessionCategory.PAGE,
    }
    # 2 talks (continuation row deduped) + 1 demolab + 1 village + 1 page
    assert len(res.event.sessions) == 5


def test_talk_speakers_join_by_hash(dump_sql):
    talk = _by_slug(_map(dump_sql).event, "H1")
    names = sorted(sp.name for sp in talk.speakers)
    assert names == ["Alice Lee", "Carol Diaz"]  # both speaker rows sharing hash H1
    assert talk.title == "Breaking Kernels"  # wrapping quotes stripped
    assert "Track 1 - Main Stage" == talk.room
    assert talk.track == "OS"
    assert talk.starts_at == "Saturday 14:30-15:30"


def test_talk_materials_extracted_from_desc(dump_sql):
    talk = _by_slug(_map(dump_sql).event, "H1")
    urls = {m.url for m in talk.materials}
    assert "https://github.com/acme/kernel-tool" in urls
    assert "https://forum.defcon.org/node/1001" in urls
    assert "https://media.example.org/slides.pdf" in urls
    kinds = {m.url: m.kind for m in talk.materials}
    assert kinds["https://github.com/acme/kernel-tool"] is MaterialKind.TOOL
    assert kinds["https://media.example.org/slides.pdf"] is MaterialKind.PDF
    # forum link is chosen as the representative source URL
    assert talk.source_url == "https://forum.defcon.org/node/1001"


def test_doubled_quote_in_abstract(dump_sql):
    talk = _by_slug(_map(dump_sql).event, "H2")
    assert "It's great fun" in talk.abstract
    assert any(m.url == "https://youtu.be/abc123" for m in talk.materials)


def test_demolab_materials_from_columns_and_html(dump_sql):
    demo = _by_slug(_map(dump_sql).event, "demolab-5")
    urls = {m.url for m in demo.materials}
    assert "https://forum.defcon.org/node/2001" in urls  # ForumPage column
    assert "https://github.com/acme/demo" in urls  # Weblink column
    assert "https://github.com/acme/demo2" in urls  # embedded in Descript
    assert demo.title == "Cool Demo Lab - Dana Smith"


def test_village_and_page_mapping(dump_sql):
    event = _map(dump_sql).event
    village = _by_slug(event, "village-7")
    assert village.title == "IoT Village"
    assert any("github.com/iot/tools" in m.url for m in village.materials)

    page = _by_slug(event, "page-9")
    assert page.title == "Lockpick Village"
    assert page.track == "village"  # pagetype
    assert page.room == "Hall A"
    assert any("lockpickvillage.org" in m.url for m in page.materials)


def test_vendors_and_cms_skipped_unknown_reported(dump_sql):
    res = _map(dump_sql)
    slugs = [s.slug for s in res.event.sessions]
    assert not any("vendor" in s for s in slugs)  # vendors excluded
    # vendors/documents are recognized-but-skipped (not reported); random_extra is unknown
    assert res.skipped_tables == ["random_extra"]


def test_category_filter(dump_sql):
    res = _map(dump_sql, categories={SessionCategory.TALK})
    assert {s.category for s in res.event.sessions} == {SessionCategory.TALK}
    assert len(res.event.sessions) == 2
