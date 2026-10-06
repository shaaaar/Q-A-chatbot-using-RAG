import pymupdf


def load_pdf(file_path):

    pages = []

    with pymupdf.open(file_path) as document:

        for page_number, page in enumerate(document):

            text = page.get_text("text") or ""
            text = text.strip()

            image_count = len(
                page.get_images(full=True)
            )

            pages.append({
                "page": page_number + 1,
                "text": text,
                "image_count": image_count,
                "has_images": image_count > 0
            })

    return pages