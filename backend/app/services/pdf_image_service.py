from pathlib import Path


def convert_pdf_to_png_images(pdf_bytes: bytes, output_dir: Path, *, zoom: float = 2.0) -> list[tuple[str, bytes, str]]:
    """Render each PDF page as a high-fidelity PNG for vision template analysis."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for vision-based template generation") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[tuple[str, bytes, str]] = []
    try:
        matrix = fitz.Matrix(zoom, zoom)
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = output_dir / f"page-{index:03d}.png"
            pixmap.save(str(image_path))
            images.append((image_path.name, image_path.read_bytes(), "image/png"))
    finally:
        document.close()
    return images
