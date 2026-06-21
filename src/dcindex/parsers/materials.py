"""Classify material links into a MaterialKind. Links only — nothing is ever downloaded here."""

from __future__ import annotations

from urllib.parse import urlparse

from dcindex.core.models import MaterialKind

_EXT_KIND = {
    ".pdf": MaterialKind.PDF,
    ".ppt": MaterialKind.SLIDES,
    ".pptx": MaterialKind.SLIDES,
    ".key": MaterialKind.SLIDES,
    ".mp4": MaterialKind.VIDEO,
    ".m4v": MaterialKind.VIDEO,
    ".mov": MaterialKind.VIDEO,
    ".wmv": MaterialKind.VIDEO,
    ".avi": MaterialKind.VIDEO,
    ".webm": MaterialKind.VIDEO,
    ".mp3": MaterialKind.AUDIO,
    ".m4a": MaterialKind.AUDIO,
    ".zip": MaterialKind.ARCHIVE,
    ".tar": MaterialKind.ARCHIVE,
    ".gz": MaterialKind.ARCHIVE,
    ".tgz": MaterialKind.ARCHIVE,
    ".rar": MaterialKind.ARCHIVE,
    ".7z": MaterialKind.ARCHIVE,
}

# Downloadable file/media assets — never auto-fetched; recorded as links only.
ASSET_EXTENSIONS = tuple(_EXT_KIND.keys())

_HOST_KIND = {
    "github.com": MaterialKind.TOOL,
    "gitlab.com": MaterialKind.TOOL,
    "raw.githubusercontent.com": MaterialKind.TOOL,
    "youtube.com": MaterialKind.VIDEO,
    "www.youtube.com": MaterialKind.VIDEO,
    "youtu.be": MaterialKind.VIDEO,
    "twitch.tv": MaterialKind.VIDEO,
    "www.twitch.tv": MaterialKind.VIDEO,
    "vimeo.com": MaterialKind.VIDEO,
    "forum.defcon.org": MaterialKind.FORUM,
    "twitter.com": MaterialKind.SOCIAL,
    "www.twitter.com": MaterialKind.SOCIAL,
    "x.com": MaterialKind.SOCIAL,
    "discord.com": MaterialKind.SOCIAL,
    "discord.gg": MaterialKind.SOCIAL,
    "www.linkedin.com": MaterialKind.SOCIAL,
    "linkedin.com": MaterialKind.SOCIAL,
    "mastodon.social": MaterialKind.SOCIAL,
    "infosec.exchange": MaterialKind.SOCIAL,
    "www.facebook.com": MaterialKind.SOCIAL,
    "facebook.com": MaterialKind.SOCIAL,
}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def classify(url: str, *, hint: str | None = None) -> MaterialKind:
    """Best-effort kind from a URL (and an optional label hint)."""
    path = urlparse(url).path.lower()
    for ext, kind in _EXT_KIND.items():
        if path.endswith(ext):
            if kind is MaterialKind.PDF and hint:
                h = hint.lower()
                if "white" in h or "paper" in h:
                    return MaterialKind.WHITEPAPER
                if "slide" in h or "presentation" in h or "deck" in h:
                    return MaterialKind.SLIDES
            return kind

    host = _host(url)
    if host in _HOST_KIND:
        return _HOST_KIND[host]

    if hint:
        h = hint.lower()
        if "video" in h or "recording" in h:
            return MaterialKind.VIDEO
        if "audio" in h:
            return MaterialKind.AUDIO
        if "slide" in h or "presentation" in h or "deck" in h:
            return MaterialKind.SLIDES
        if "white" in h or "paper" in h:
            return MaterialKind.WHITEPAPER
        if "code" in h or "tool" in h or "repo" in h or "github" in h:
            return MaterialKind.TOOL
        if "forum" in h:
            return MaterialKind.FORUM

    return MaterialKind.LINK


def is_downloadable_asset(url: str) -> bool:
    """True if the URL points directly at a media/file asset (by extension)."""
    return urlparse(url).path.lower().endswith(ASSET_EXTENSIONS)
