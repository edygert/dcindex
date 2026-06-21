from dcindex.core.models import MaterialKind
from dcindex.parsers.base import clean, strip_html
from dcindex.parsers.materials import classify, is_downloadable_asset


def test_repairs_mojibake_and_strips_control_chars():
    # Double-encoded UTF-8 (as in the Outel dumps) plus a C1 control char that breaks terminals.
    raw = "founding member of â€œThe Diana Initiativeâ€. Iâ€™ll talk"
    out = clean(raw)
    assert '"The Diana Initiative"' in out
    assert "I'll talk" in out
    assert not any(0x80 <= ord(c) <= 0x9F for c in out)  # no C1 controls survive
    # same repair through the HTML path
    assert strip_html(f"<p>{raw}</p>").endswith("I'll talk")


def test_classify_by_extension():
    assert classify("https://x/slides.pdf") is MaterialKind.PDF
    assert classify("https://x/talk.pptx") is MaterialKind.SLIDES
    assert classify("https://x/tool.zip") is MaterialKind.ARCHIVE
    assert classify("https://x/rec.mp4") is MaterialKind.VIDEO


def test_classify_by_host():
    assert classify("https://github.com/acme/tool") is MaterialKind.TOOL
    assert classify("https://youtu.be/abc") is MaterialKind.VIDEO
    assert classify("https://forum.defcon.org/node/1") is MaterialKind.FORUM
    assert classify("https://twitter.com/foo") is MaterialKind.SOCIAL


def test_classify_pdf_hint_promotes_kind():
    assert classify("https://x/doc.pdf", hint="White Paper") is MaterialKind.WHITEPAPER
    assert classify("https://x/doc.pdf", hint="Slides") is MaterialKind.SLIDES


def test_classify_fallback_link():
    assert classify("https://example.org/page") is MaterialKind.LINK


def test_is_downloadable_asset():
    assert is_downloadable_asset("https://x/a.pdf")
    assert is_downloadable_asset("https://x/a.mp4")
    assert not is_downloadable_asset("https://github.com/acme/tool")
    assert not is_downloadable_asset("https://forum.defcon.org/node/1")
