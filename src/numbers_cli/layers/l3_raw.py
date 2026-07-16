"""L3: read access to the underlying IWA protobuf objects.

A ``.numbers`` file is a zip of ``Index/*.iwa`` streams; each stream is a Snappy
compressed sequence of protobuf archives, and each archive has a numeric object
identifier and a typed message. This layer surfaces that object graph so an agent
can inspect what the higher layers cannot express - the honest analog of
OfficeCli's raw XPath view.

Writing at this level (``raw-set``) is deliberately not offered yet: patching
undocumented protobuf can produce files Numbers silently repairs or refuses, and
it cannot be verified safely here. The catalog and per object decode below are
read only and safe.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from ..errors import DocumentError


def _iwa_files(path: str) -> zipfile.ZipFile:
    p = Path(path)
    if not p.exists():
        raise DocumentError(f"No such file: {p}", hint="Check the path")
    if not zipfile.is_zipfile(p):
        raise DocumentError(
            f"{p.name} is not a zip based .numbers file",
            hint="Very old or package style documents are not supported by the raw layer",
        )
    return zipfile.ZipFile(p)


def read(file: str, message_id: int | None = None, contains: str | None = None) -> dict[str, Any]:
    """Return a catalog of IWA objects, or one decoded object when ``message_id`` is set."""
    from numbers_parser.iwafile import IWAFile

    zf = _iwa_files(file)
    streams = [n for n in zf.namelist() if n.endswith(".iwa")]
    catalog: list[dict[str, Any]] = []

    for name in streams:
        try:
            iwa = IWAFile.from_buffer(zf.read(name), name)
        except Exception:  # noqa: BLE001 - skip streams the parser cannot decode
            continue
        for chunk in iwa.chunks:
            for archive in chunk.archives:
                obj = archive.objects[0] if archive.objects else None
                type_name = type(obj).__name__ if obj is not None else "?"
                identifier = archive.header.identifier
                if message_id is not None and identifier == message_id:
                    return {
                        "id": identifier,
                        "type": type_name,
                        "stream": name,
                        "message": archive.to_dict(),
                    }
                if contains and contains.lower() not in type_name.lower():
                    continue
                catalog.append({"id": identifier, "type": type_name, "stream": name})

    if message_id is not None:
        raise DocumentError(f"No IWA object with id {message_id}", hint="Run `nmbr raw` with no --id to list ids")

    catalog.sort(key=lambda e: e["id"])
    return {"file": file, "object_count": len(catalog), "objects": catalog}
