def chunk_pages(pages, chunk_size=800, overlap=100):

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size."
        )

    chunks = []
    chunk_id = 0

    step = chunk_size - overlap


    for page in pages:

        text = page.get("text", "") or ""

        page_number = page.get(
            "page",
            chunk_id + 1
        )

        document_name = page.get(
            "document",
            ""
        )

        has_images = page.get(
            "has_images",
            False
        )


        # ==================================================
        # NORMAL TEXT PAGE
        # ==================================================

        if text.strip():

            start = 0

            while start < len(text):

                end = start + chunk_size

                chunk_text = text[
                    start:end
                ].strip()


                if chunk_text:

                    chunks.append({

                        "chunk_id":
                            chunk_id,

                        "type":
                            "text",

                        "text":
                            chunk_text,

                        "page":
                            page_number,

                        "document":
                            document_name

                    })

                    chunk_id += 1


                start += step


        # ==================================================
        # IMAGE / SCANNED / VISUAL PAGE
        # ==================================================

        elif has_images:

            chunks.append({

                "chunk_id":
                    chunk_id,

                "type":
                    "visual",

                "text":
                    (
                        f"Visual content on "
                        f"page {page_number} "
                        f"of document "
                        f"{document_name}. "
                        f"This page may contain "
                        f"images, diagrams, "
                        f"charts, graphs, "
                        f"tables, or scanned text."
                    ),

                "page":
                    page_number,

                "document":
                    document_name

            })

            chunk_id += 1


        # ==================================================
        # COMPLETELY EMPTY PAGE
        # ==================================================

        else:

            chunks.append({

                "chunk_id":
                    chunk_id,

                "type":
                    "page",

                "text":
                    (
                        f"Page {page_number} "
                        f"of document "
                        f"{document_name}."
                    ),

                "page":
                    page_number,

                "document":
                    document_name

            })

            chunk_id += 1


    return chunks