"""Read + analyze MathType equations stored in OLE objects.

A Word-embedded MathType equation (`oleObject*.bin`) is an OLE compound file
that contains a stream named ``Equation Native``:

    [ EQNOLEFILEHDR : 28 bytes ] [ MTEF data ... ]

The MTEF data starts with a 5-byte header:
    byte 0: MTEF version   (5 for MathType 6/7)
    byte 1: platform       (0 = Mac, 1 = Windows)
    byte 2: product        (0 = MathType, 1 = "Equation Editor")
    byte 3: product version
    byte 4: product subversion

Proving we can reach a valid MTEF v5 stream for every formula means BOTH
conversion routes are viable downstream:
  (A) MTEF -> MathML -> LaTeX   (lossless-ish; e.g. mathtype_to_mathml)
  (B) render the WMF image -> math-OCR -> LaTeX (fallback)

This module does the *analysis* only (no full MTEF->MathML port yet); that is
the next decision point, benchmarked on the GPU box.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

import olefile

EQNOLEFILEHDR_SIZE = 28
RECORD_NAMES = {
    0: "END", 1: "LINE", 2: "CHAR", 3: "TMPL", 4: "PILE", 5: "MATRIX",
    6: "EMBELL", 7: "RULER", 8: "FONT", 9: "SIZE", 10: "FULL", 11: "SUB",
    12: "SUB2", 13: "SYM", 14: "SUBSYM", 15: "COLOR", 16: "COLOR_DEF",
    17: "FONT_DEF", 18: "EQN_PREFS", 19: "ENCODING_DEF",
}


@dataclass
class MtefInfo:
    ok: bool
    reason: str = ""
    has_stream: bool = False
    mtef_version: int | None = None
    platform: int | None = None
    product: int | None = None
    stream_bytes: int = 0
    mtef_bytes: int = 0


def analyze(ole_path: str) -> MtefInfo:
    """Inspect one oleObject*.bin and report whether MTEF is recoverable."""
    try:
        if not olefile.isOleFile(ole_path):
            return MtefInfo(False, "not-an-ole-file")
        with olefile.OleFileIO(ole_path) as ole:
            streams = {"/".join(s).lower(): s for s in ole.listdir()}
            key = next((streams[k] for k in streams if k.endswith("equation native")), None)
            if key is None:
                return MtefInfo(False, "no-equation-native-stream",
                                has_stream=False)
            data = ole.openstream(key).read()
    except Exception as exc:  # noqa: BLE001 - report, don't crash the batch
        return MtefInfo(False, f"ole-error: {exc}")

    if len(data) <= EQNOLEFILEHDR_SIZE + 5:
        return MtefInfo(False, "stream-too-short", has_stream=True,
                        stream_bytes=len(data))

    # EQNOLEFILEHDR: cbHdr should be 0x1C (28).
    (cb_hdr,) = struct.unpack_from("<H", data, 0)
    body = data[EQNOLEFILEHDR_SIZE:] if cb_hdr == EQNOLEFILEHDR_SIZE else data
    ver, platform, product = body[0], body[1], body[2]
    ok = ver in (4, 5)  # MathType MTEF versions seen in the wild
    return MtefInfo(
        ok=ok,
        reason="ok" if ok else f"unexpected-mtef-version-{ver}",
        has_stream=True,
        mtef_version=ver,
        platform=platform,
        product=product,
        stream_bytes=len(data),
        mtef_bytes=len(body),
    )
