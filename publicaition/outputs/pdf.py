"""PDF converter — converts a DOCX to PDF via LibreOffice or docx2pdf."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def convert_to_pdf(docx_path: Path) -> Path:
    """
    Convert a DOCX to PDF. Tries LibreOffice first (headless, no license
    required), then docx2pdf (requires Microsoft Word on macOS/Windows).

    Raises RuntimeError if neither converter is available.
    """
    pdf_path = docx_path.with_suffix(".pdf")

    if _try_libreoffice(docx_path, pdf_path):
        return pdf_path

    if _try_docx2pdf(docx_path, pdf_path):
        return pdf_path

    raise RuntimeError(
        "PDF conversion requires either LibreOffice (install via brew install libreoffice) "
        "or Microsoft Word with docx2pdf (pip install docx2pdf). "
        f"DOCX is available at: {docx_path}"
    )


def _try_libreoffice(docx_path: Path, pdf_path: Path) -> bool:
    lo = shutil.which("soffice") or shutil.which("libreoffice")
    if not lo:
        return False
    try:
        subprocess.run(
            [
                lo, "--headless", "--convert-to", "pdf",
                "--outdir", str(docx_path.parent),
                str(docx_path),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return pdf_path.exists()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _try_docx2pdf(docx_path: Path, pdf_path: Path) -> bool:
    try:
        from docx2pdf import convert  # type: ignore[import]
        convert(str(docx_path), str(pdf_path))
        return pdf_path.exists()
    except ImportError:
        return False
    except Exception:
        return False
