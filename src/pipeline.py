from pathlib import Path

from src.pdf_loader import load_pdf
from src.chunker import chunk_pages
from src.embeddings import EmbeddingModel
from src.vector_store import VectorStore
from src.retriever import Retriever
from src.generator import Generator


class RAGPipeline:

    def __init__(self):

        self.pages = []
        self.chunks = []

        self.embedding_model = None
        self.vector_store = None
        self.retriever = None
        self.generator = None

        self.pdf_paths = []
        self.documents = []

    # ==================================================
    # INGEST MULTIPLE PDF DOCUMENTS
    # ==================================================

    def ingest(self, pdf_paths):

        print("\n" + "=" * 60)
        print("STARTING MULTI-DOCUMENT INGESTION")
        print("=" * 60)

        if isinstance(pdf_paths, (str, Path)):
            pdf_paths = [pdf_paths]

        if not pdf_paths:
            raise ValueError(
                "No PDF documents were provided."
            )

        all_pages = []

        print("\n[1/5] Loading PDF documents...")

        for pdf_path in pdf_paths:

            pdf_path = Path(pdf_path)

            if not pdf_path.exists():
                raise FileNotFoundError(
                    f"PDF not found: {pdf_path}"
                )

            if pdf_path.suffix.lower() != ".pdf":
                raise ValueError(
                    f"Only PDF files are supported: "
                    f"{pdf_path.name}"
                )

            document_name = pdf_path.name

            print(
                f"\nLoading: {document_name}"
            )

            pages = load_pdf(
                str(pdf_path)
            )

            if not pages:

                print(
                    f"WARNING: {document_name} "
                    "contains no readable pages."
                )

                continue

            for page in pages:

                page["document"] = document_name

                page["source_path"] = str(
                    pdf_path
                )

            all_pages.extend(pages)

            print(
                f"Pages loaded: {len(pages)}"
            )

        if not all_pages:

            raise ValueError(
                "None of the uploaded PDFs "
                "contained readable pages."
            )

        self.pdf_paths = [
            str(Path(path))
            for path in pdf_paths
        ]

        self.documents = [
            Path(path).name
            for path in pdf_paths
        ]

        print(
            "\n[2/5] Creating text chunks..."
        )

        chunks = chunk_pages(
            all_pages,
            chunk_size=800,
            overlap=100
        )

        print(
            f"Text chunks created: {len(chunks)}"
        )

        if chunks:

            print(
                "Text retrieval will be enabled."
            )

        else:

            print(
                "WARNING: No extractable text found.\n"
                "The documents will still be processed "
                "using Ollama's multimodal vision model."
            )

        print(
            "\n[3/5] Initializing Ollama..."
        )

        generator = Generator()

        print(
            "\nRegistering PDF documents "
            "with Ollama..."
        )

        generator.set_documents(
            pdf_paths
        )

        print(
            "PDF documents registered successfully."
        )

        print(
            "\n[4/5] Building vector store..."
        )

        embedding_model = None
        vector_store = None
        retriever = None

        if chunks:

            embedding_model = EmbeddingModel()

            texts = [
                chunk["text"]
                for chunk in chunks
            ]

            embeddings = (
                embedding_model.encode(
                    texts
                )
            )

            dimension = embeddings.shape[1]

            print(
                "Embedding dimension:",
                dimension
            )

            vector_store = VectorStore(
                dimension
            )

            vector_store.add(
                embeddings
            )

            retriever = Retriever(
                embedding_model,
                vector_store,
                chunks
            )

            print(
                "Combined vector store created "
                "successfully."
            )

        else:

            print(
                "No text embeddings created "
                "because the PDFs contain no "
                "extractable text."
            )

        print(
            "\n[5/5] Saving pipeline state..."
        )

        self.pages = all_pages
        self.chunks = chunks
        self.embedding_model = embedding_model
        self.vector_store = vector_store
        self.retriever = retriever
        self.generator = generator

        print(
            "\n" + "=" * 60
        )

        print(
            "MULTI-DOCUMENT INGESTION COMPLETE"
        )

        print(
            "=" * 60
        )

        print(
            "Documents:",
            len(self.documents)
        )

        for document in self.documents:

            print(
                " -",
                document
            )

        print(
            "Total pages:",
            len(self.pages)
        )

        print(
            "Total text chunks:",
            len(self.chunks)
        )

        print(
            "Local text retrieval:",
            "Enabled"
            if self.retriever
            else "Disabled"
        )

        print(
            "Ollama multimodal vision:",
            "Enabled"
        )

        print(
            "=" * 60
        )

        return {
            "documents":
                len(self.documents),

            "filenames":
                self.documents,

            "pages":
                len(self.pages),

            "chunks":
                len(self.chunks),

            "text_retrieval":
                self.retriever is not None,

            "multimodal":
                True
        }

    # ==================================================
    # BUILD VISION PAGES
    # ==================================================

    def build_relevant_pages(
        self,
        results,
        max_pages=3
    ):

        relevant_pages = []
        seen = set()

        # --------------------------------------------------
        # First add retrieved pages
        # --------------------------------------------------

        for result in results:

            document = result.get(
                "document"
            )

            page = result.get(
                "page"
            )

            if not document or not page:
                continue

            key = (
                document,
                page
            )

            if key not in seen:

                seen.add(key)

                relevant_pages.append({
                    "document":
                        document,

                    "page":
                        page
                })

        # --------------------------------------------------
        # Then add neighboring pages.
        #
        # This is important for tables that continue
        # across page boundaries.
        # --------------------------------------------------

        for result in results:

            if len(relevant_pages) >= max_pages:
                break

            document = result.get(
                "document"
            )

            page = result.get(
                "page"
            )

            if not document or not page:
                continue

            try:

                page = int(page)

            except (
                TypeError,
                ValueError
            ):

                continue

            for neighbor in (
                page - 1,
                page + 1
            ):

                if len(relevant_pages) >= max_pages:
                    break

                if neighbor < 1:
                    continue

                key = (
                    document,
                    neighbor
                )

                if key in seen:
                    continue

                # Verify that the neighboring page actually
                # exists in the uploaded document.
                page_exists = any(
                    p.get("document") == document
                    and p.get("page") == neighbor
                    for p in self.pages
                )

                if not page_exists:
                    continue

                seen.add(key)

                relevant_pages.append({
                    "document":
                        document,

                    "page":
                        neighbor
                })

        print(
            "\nVISION PAGE SELECTION"
        )

        for item in relevant_pages:

            print(
                f" - {item['document']} "
                f"| Page {item['page']}"
            )

        return relevant_pages

    # ==================================================
    # ASK QUESTION
    # ==================================================

    def ask(
        self,
        question,
        k=5
    ):

        if self.generator is None:

            raise RuntimeError(
                "No document has been uploaded."
            )

        results = []

        if self.retriever is not None:

            results = self.retriever.search(
                question,
                k=k,
                score_threshold=0.10
            )

        # ==================================================
        # TEXT RETRIEVAL FOUND RESULTS
        # ==================================================

        if results:

            context_parts = []

            for result in results:

                document_name = result.get(
                    "document",
                    "Unknown document"
                )

                page_number = result["page"]

                context_parts.append(

                    f"[Document: {document_name} | "
                    f"Page: {page_number} | "
                    f"Chunk: {result['chunk_id']} | "
                    f"Type: {result.get('type', 'text')}]\n"
                    f"{result['text']}"

                )

            context = "\n\n".join(
                context_parts
            )

            # --------------------------------------------------
            # Build page list including neighboring pages
            # --------------------------------------------------

            relevant_pages = (
                self.build_relevant_pages(
                    results,
                    max_pages=3
                )
            )

            answer = self.generator.generate(
    question=question,
    retrieved_chunks=results,
    relevant_pages=relevant_pages
)

            sources = []

            for result in results:

                sources.append({

                    "document":
                        result.get(
                            "document",
                            "Unknown document"
                        ),

                    "page":
                        result["page"],

                    "chunk_id":
                        result["chunk_id"],

                    "score":
                        round(
                            float(
                                result["score"]
                            ),
                            4
                        ),

                    "type":
                        result.get(
                            "type",
                            "text"
                        )

                })

            return {

                "answer":
                    answer,

                "sources":
                    sources,

                "multimodal":
                    True

            }

        # ==================================================
        # MULTIMODAL FALLBACK
        # ==================================================

        print(
            "\nNo relevant text chunks found."
        )

        print(
            "Switching to multimodal "
            "vision fallback..."
        )

        relevant_pages = []

        MAX_VISION_PAGES = 3

        import fitz

        for document_path in self.pdf_paths:

            document_path = Path(
                document_path
            )

            document_name = (
                document_path.name
            )

            try:

                with fitz.open(
                    str(document_path)
                ) as pdf:

                    total_pages = len(pdf)

                    for page_number in range(
                        1,
                        total_pages + 1
                    ):

                        relevant_pages.append({

                            "document":
                                document_name,

                            "page":
                                page_number

                        })

                        if (
                            len(relevant_pages)
                            >= MAX_VISION_PAGES
                        ):

                            break

            except Exception as e:

                print(
                    f"WARNING: Could not inspect "
                    f"{document_name}: {e}"
                )

            if (
                len(relevant_pages)
                >= MAX_VISION_PAGES
            ):

                break

        context = (

            "No sufficiently relevant text "
            "was retrieved by semantic search.\n\n"

            "Inspect the supplied PDF pages directly.\n\n"

            "Look for text, scanned text, tables, "
            "charts, graphs, diagrams, figures, "
            "images, captions, labels, and layout.\n\n"

            "Use ONLY information actually present "
            "in the uploaded documents."

        )

        answer = self.generator.generate(
    question=question,
    retrieved_chunks=results,
    relevant_pages=relevant_pages
)


        return {

            "answer":
                answer,

            "sources":
                [],

            "multimodal":
                True

        }

    # ==================================================
    # READY CHECK
    # ==================================================

    def is_ready(self):

        return (
            self.generator is not None
        )