"""Stage 5E — images (OCR), archives, CAD and .bak detection."""
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from app.pipeline import file_extractors as fx


def _txt_pdf(_path, _hint):
    return [{"page_number": 1, "text": "pdf text " * 20, "method": "fitz"}]


def test_sniff_detects_real_type_regardless_of_extension(tmp_path):
    cases = {
        "a.bak": b"%PDF-1.7 rest",
        "b.bak": b"Rar!\x1a\x07\x00rest",
        "c.bak": b"AC1021\x00\x00rest",
        "d.bak": b"\xff\xd8\xff\xe0 jpeg",
        "e.bak": b"\x89PNG\r\n\x1a\n",
        "f.bak": b"just plain text that is readable\n" * 10,
        "g.bak": bytes(range(256)) * 4,
    }
    for name, data in cases.items():
        (tmp_path / name).write_bytes(data)
    kinds = {n: fx.kind_for(tmp_path / n) for n in cases}
    assert kinds == {"a.bak": "pdf", "b.bak": "rar", "c.bak": "dwg", "d.bak": "image",
                     "e.bak": "image", "f.bak": "text", "g.bak": "unknown"}


def test_upload_type_marks_only_unreadable_files_unsupported(tmp_path, monkeypatch):
    monkeypatch.setattr(fx, "oda_converter", lambda: None)
    (tmp_path / "x.dwg").write_bytes(b"AC1027\x00\x00")
    (tmp_path / "x.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    (tmp_path / "x.rar").write_bytes(b"Rar!\x1a\x07\x00")
    (tmp_path / "x.xyz").write_bytes(bytes(range(256)))
    assert fx.upload_doc_type(tmp_path / "x.dwg") == "UNSUPPORTED"
    assert fx.upload_doc_type(tmp_path / "x.jpg") == "IMAGE"
    assert fx.upload_doc_type(tmp_path / "x.rar") == "ARCHIVE"
    assert fx.upload_doc_type(tmp_path / "x.xyz") == "UNSUPPORTED"
    monkeypatch.setattr(fx, "oda_converter", lambda: "ODAFileConverter")
    assert fx.upload_doc_type(tmp_path / "x.dwg") == "CAD"


def test_nested_zip_keeps_inner_paths_for_provenance(tmp_path):
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("specs/notes.txt", "Tender security EGP 500,000 valid 120 days. " * 5)
    outer = tmp_path / "package.zip"
    with zipfile.ZipFile(outer, "w") as z:
        z.write(inner, "inner.zip")
        z.writestr("vol1.pdf", b"%PDF-1.4 fake")
    got = dict(fx.extract_any(outer, "package.zip", _txt_pdf))
    assert set(got) == {"package.zip/inner.zip/specs/notes.txt", "package.zip/vol1.pdf"}
    assert all(e["status"] == "COMPLETE" for e in got.values())


def test_zip_slip_is_refused(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../../escaped.txt", "pwned " * 20)
    got = fx.extract_any(evil, "evil.zip", _txt_pdf)
    assert got[0][1]["status"] == "FAILED" and "unsafe path" in got[0][1]["error"]
    assert not (tmp_path.parent / "escaped.txt").exists()


def test_archive_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(fx, "MAX_ARCHIVE_FILES", 3)
    many = tmp_path / "many.zip"
    with zipfile.ZipFile(many, "w") as z:
        for i in range(5):
            z.writestr(f"f{i}.txt", "x")
    got = fx.extract_any(many, "many.zip", _txt_pdf)
    assert got[0][1]["status"] == "FAILED" and "limit" in got[0][1]["error"]


def test_nesting_depth_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(fx, "MAX_DEPTH", 1)
    inner = tmp_path / "a.zip"
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("t.txt", "hello " * 20)
    outer = tmp_path / "b.zip"
    with zipfile.ZipFile(outer, "w") as z:
        z.write(inner, "a.zip")
    got = dict(fx.extract_any(outer, "b.zip", _txt_pdf))
    assert got["b.zip/a.zip"]["status"] == "UNSUPPORTED"


def test_dxf_text_entities(tmp_path):
    dxf = tmp_path / "plan.dxf"
    dxf.write_text("\n".join([
        "0", "SECTION", "2", "ENTITIES",
        "0", "TEXT", "8", "0", "1", "220/22 kV GIS BUILDING",
        "0", "MTEXT", "8", "0", "3", "TRANSFORMER 125 MVA ", "1", "\\PFIRE WALL",
        "0", "LINE", "8", "0", "10", "0.0",
        "0", "ENDSEC", "0", "EOF"]))
    pages = fx.extract_dxf(dxf)
    assert "220/22 kV GIS BUILDING" in pages[0]["text"]
    assert "TRANSFORMER 125 MVA" in pages[0]["text"] and "FIRE WALL" in pages[0]["text"]


def test_dwg_without_converter_is_unsupported_with_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(fx, "oda_converter", lambda: None)
    bak = tmp_path / "drawing.bak"
    bak.write_bytes(b"AC1021\x00\x00" + b"\x00" * 100)
    got = fx.extract_any(bak, "drawing.bak", _txt_pdf)
    assert got[0][1]["status"] == "UNSUPPORTED" and "ODA File Converter" in got[0][1]["error"]


def test_dwg_with_converter_reads_text(tmp_path, monkeypatch):
    """The converter is an external program; simulate it writing a DXF."""
    monkeypatch.setattr(fx, "oda_converter", lambda: "ODAFileConverter")

    def fake_run(cmd, **kw):
        out = Path(cmd[2])
        (out / "drawing.dxf").write_text("0\nSECTION\n0\nTEXT\n1\nSWITCHGEAR ROOM\n0\nEOF\n")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(fx.subprocess, "run", fake_run)
    bak = tmp_path / "drawing.bak"
    bak.write_bytes(b"AC1021\x00\x00")
    got = fx.extract_any(bak, "drawing.bak", _txt_pdf)
    assert "SWITCHGEAR ROOM" in got[0][1]["pages"][0]["text"]


@pytest.mark.skipif(shutil.which("tesseract") is None and not Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").exists(),
                    reason="tesseract not installed")
def test_image_ocr_multiframe_tiff(tmp_path):
    from PIL import Image, ImageDraw
    frames = []
    for word in ("PERFORMANCE BOND", "TENDER SECURITY"):
        im = Image.new("RGB", (1400, 300), "white")
        ImageDraw.Draw(im).text((40, 100), word, fill="black", font_size=90)
        frames.append(im)
    tif = tmp_path / "scan.tiff"
    frames[0].save(tif, save_all=True, append_images=frames[1:])
    pages = fx.extract_image(tif)
    assert len(pages) == 2 and pages[0]["ocr_applied"]
    assert "PERFORMANCE" in pages[0]["text"].upper() and "SECURITY" in pages[1]["text"].upper()


@pytest.mark.skipif(fx.unrar_tool() is None, reason="no RAR extractor installed")
def test_rar_extraction_when_tool_available(tmp_path):
    kind, exe = fx.unrar_tool()
    rar_exe = Path(exe).with_name("Rar.exe")
    if not rar_exe.exists():
        pytest.skip("cannot create a RAR fixture without Rar.exe")
    src = tmp_path / "src"
    src.mkdir()
    (src / "notes.txt").write_text("Advance payment 10 percent against bank guarantee. " * 5)
    subprocess.run([str(rar_exe), "a", "-ep1", "-inul", str(tmp_path / "p.rar"), str(src / "notes.txt")], check=True)
    got = dict(fx.extract_any(tmp_path / "p.rar", "p.rar", _txt_pdf))
    assert got["p.rar/notes.txt"]["status"] == "COMPLETE"
