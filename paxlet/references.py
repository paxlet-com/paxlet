"""Explicit, deliberately small Paxlet address profile (no implicit decoding)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .errors import ResolutionError

NAME = r"[A-Za-z0-9][A-Za-z0-9._-]*"
VERSION = r"[A-Za-z0-9][A-Za-z0-9.+_-]*"
URN = re.compile(rf"urn:paxlet:{NAME}(?::{NAME})*")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
URI_CHARS = re.compile(r"[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")


@dataclass(frozen=True)
class Reference:
    package: str
    action: str | None = None
    version: str | None = None


def validate_uri(value: str) -> None:
    if not isinstance(value, str) or not URI_CHARS.fullmatch(value):
        raise ResolutionError("URI must contain only valid ASCII URI characters")
    if re.search(r"%(?![0-9a-fA-F]{2})", value):
        raise ResolutionError("invalid URI percent encoding")
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not value.split(":", 1)[1]:
            raise ValueError("absolute URI required")
        if value.split(":", 1)[1].startswith("//") and not parsed.netloc and parsed.scheme != "file":
            raise ValueError("URI authority is empty")
        if parsed.netloc:
            parsed.port  # Reject malformed ports/bracketed hosts.
    except ValueError as exc:
        raise ResolutionError(f"invalid URI: {exc}") from exc


def parse_reference(value: str) -> Reference:
    validate_uri(value)
    parsed = urlsplit(value)
    if parsed.scheme == "paxlet":
        # A canonical authority is a registry namespace, never a network endpoint.
        if not value.startswith("paxlet://") or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", parsed.netloc):
            raise ResolutionError("paxlet authority must be a lowercase namespace without credentials or port")
        match = re.fullmatch(rf"/({NAME})(?:/actions/({NAME}))?", parsed.path)
        if not match or "%" in value or "#" in value:
            raise ResolutionError("expected paxlet://authority/package[/actions/action], without encoding or fragment")
        version = None
        if "?" in value:
            query = re.fullmatch(rf"version=({VERSION})", parsed.query)
            if not query:
                raise ResolutionError("only one non-empty version query parameter is supported")
            version = query[1]
        return Reference(f"paxlet://{parsed.netloc}/{match[1]}", match[2], version)
    if "?" in value or "#" in value:
        raise ResolutionError("package references do not accept query or fragment")
    if parsed.scheme == "urn" and not URN.fullmatch(value):
        raise ResolutionError("expected a Paxlet URN")
    return Reference(value)


def validate_binding(value: str) -> None:
    ref = parse_reference(value)
    if ref.action is not None or ref.version is not None:
        raise ResolutionError("bindings identify packages, not actions or version selectors")


def exact_version(value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not re.fullmatch(VERSION, value)):
        raise ResolutionError("version must be an exact label, not a range or URI component")


def exact_digest(value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not DIGEST.fullmatch(value)):
        raise ResolutionError("digest must be sha256 followed by 64 lowercase hexadecimal digits")
