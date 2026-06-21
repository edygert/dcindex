import httpx
import respx

from dcindex.adapters.dump_cache import DumpCache
from dcindex.core.editions import parse_edition

URL = "https://defcon.outel.org/defcon33/dc33_mysqldump.txt"
BODY = "CREATE TABLE `t` (`a` int);\nINSERT INTO `t` VALUES (1);"


@respx.mock
def test_fetch_then_serve_from_cache(temp_settings):
    route = respx.get(URL).mock(return_value=httpx.Response(200, text=BODY))
    cache = DumpCache(temp_settings)
    ed = parse_edition("dc33")

    first = cache.fetch_cached(URL, ed)
    assert first.text == BODY
    assert first.from_cache is False
    assert cache.path_for(ed).is_file()
    assert route.call_count == 1

    # Second call must NOT hit the network.
    second = cache.fetch_cached(URL, ed)
    assert second.text == BODY
    assert second.from_cache is True
    assert route.call_count == 1  # no additional request


@respx.mock
def test_refresh_forces_refetch(temp_settings):
    route = respx.get(URL).mock(return_value=httpx.Response(200, text=BODY))
    cache = DumpCache(temp_settings)
    ed = parse_edition("dc33")

    cache.fetch_cached(URL, ed)
    cache.fetch_cached(URL, ed, refresh=True)
    assert route.call_count == 2
