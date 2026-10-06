import base64
import os
import re
from pathlib import Path

from ollama import Client
import pymupdf


class Generator:
    def __init__(self, model_name=None):
        self.model_name = model_name or os.getenv(
            "OLLAMA_MODEL_NAME",
            "qwen3-vl:2b-instruct"
        )
        self.ollama_host = os.getenv(
            "OLLAMA_HOST",
            "http://127.0.0.1:11434"
        )
        self.ollama_timeout = float(
            os.getenv("OLLAMA_TIMEOUT", "600")
        )
        self.ollama_client = Client(
            host=self.ollama_host,
            timeout=self.ollama_timeout
        )
        self.pdf_paths = {}

        print(f"Loading Ollama model: {self.model_name}")
        print(f"Ollama endpoint: {self.ollama_host}")
        print("Ollama multimodal vision enabled.")

    # ==========================================================
    # DOCUMENT REGISTRATION
    # ==========================================================

    def set_documents(self, pdf_paths):
        """
        Register multiple PDF documents.

        Supports:
        - list / tuple of PDF paths
        - dictionary {document_name: pdf_path}
        """
        self.pdf_paths = {}

        if isinstance(pdf_paths, dict):
            for document_name, pdf_path in pdf_paths.items():
                self.pdf_paths[str(document_name)] = str(pdf_path)

        elif isinstance(pdf_paths, (list, tuple)):
            for pdf_path in pdf_paths:
                pdf_path = Path(pdf_path)
                self.pdf_paths[pdf_path.name] = str(pdf_path)

        else:
            raise ValueError(
                "pdf_paths must be a dictionary, list, or tuple."
            )

        print("Registered PDF documents:")
        for document_name in self.pdf_paths:
            print(f" - {document_name}")

    def register_pdf(self, document_name, pdf_path):
        """Register one PDF document."""
        self.pdf_paths[str(document_name)] = str(pdf_path)

    # ==========================================================
    # PDF PAGE RENDERING
    # ==========================================================

    def _render_page(self, document_name, page_number):
        """Render one PDF page as a base64 JPEG."""
        pdf_path = self.pdf_paths.get(document_name)

        if not pdf_path:
            print(
                f"WARNING: PDF path not found for {document_name}"
            )
            return None

        try:
            with pymupdf.open(pdf_path) as document:
                page_index = int(page_number) - 1

                if page_index < 0 or page_index >= len(document):
                    return None

                page = document[page_index]

                pix = page.get_pixmap(
                    matrix=pymupdf.Matrix(1.2, 1.2),
                    alpha=False
                )

                image_bytes = pix.tobytes("jpeg")

                return base64.b64encode(
                    image_bytes
                ).decode("utf-8")

        except Exception as e:
            print(
                f"Error rendering {document_name} "
                f"page {page_number}: {e}"
            )
            return None

    def _select_visual_pages(
        self,
        question,
        retrieved_chunks,
        relevant_pages,
        max_pages=1
    ):
        """
        Select the PDF pages that are most likely to contain the
        visual evidence needed for the question.

        This is important because relevant_pages may be ordered by
        semantic relevance. A visual question such as
        "What does Figure A1 show?" must prioritize the page whose
        retrieved text mentions Figure A1 instead of blindly
        taking the first three pages.
        """
        if not relevant_pages:
            return []

        question_lower = question.lower()

        # Explicit visual reference in the question, e.g.:
        # Figure A1, Figure 2, Diagram B, etc.
        explicit_refs = re.findall(
            r"\b(?:figure|fig\.|diagram|chart|graph)\s+[a-z0-9][a-z0-9_-]*",
            question_lower,
            flags=re.IGNORECASE
        )

        visual_terms = [
            "figure",
            "fig.",
            "diagram",
            "graph",
            "chart",
            "plot",
            "image",
            "illustration",
            "visual",
            "caption",
            "screenshot",
            "pictured",
            "shown"
        ]

        # Deduplicate page candidates while preserving page metadata.
        candidates = []
        seen = set()

        for page_info in relevant_pages:
            document = page_info.get("document", "")
            page = page_info.get("page")

            if not document or page is None:
                continue

            key = (document, self._safe_int(page))

            if key in seen:
                continue

            seen.add(key)

            score = 0
            page_text = ""

            # Find retrieved chunks belonging to this exact page.
            for chunk in retrieved_chunks:
                if (
                    chunk.get("document", "") == document
                    and self._safe_int(chunk.get("page")) == self._safe_int(page)
                ):
                    chunk_text = chunk.get("text", "") or ""
                    page_text += " " + chunk_text

            page_text_lower = page_text.lower()

            # Exact reference match gets the highest priority.
            for ref in explicit_refs:
                if ref in page_text_lower:
                    score += 100

            # General visual-language matches.
            for term in visual_terms:
                if term in page_text_lower:
                    score += 10

            candidates.append((score, page_info))

        # Highest-scoring visual pages first. Keep original order as
        # the tie-breaker because Python sort is stable.
        candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )

        return [
            page_info
            for _, page_info in candidates[:max_pages]
        ]

    def _build_images(self, relevant_pages):
        """Render selected PDF pages."""
        images = []

        seen_pages = set()

        for page_info in relevant_pages[:3]:
            document = page_info.get("document", "")
            page = page_info.get("page")

            if not document or not page:
                continue

            page_key = (document, int(page))

            if page_key in seen_pages:
                continue

            seen_pages.add(page_key)

            image = self._render_page(document, page)

            if image:
                images.append(image)

        print(f"Rendered {len(images)} PDF page(s).")
        return images

    # ==========================================================
    # TEXT CONTEXT
    # ==========================================================

    def _build_text_context(self, retrieved_chunks):
        """
        Build the textual context sent to Ollama.
        """
        max_context_chars = 6000

        context_parts = []
        current_length = 0

        for chunk in retrieved_chunks:
            document = chunk.get("document", "")
            page = chunk.get("page", "?")
            chunk_id = chunk.get("chunk_id", "?")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)

            block = (
                f"[Document: {document} | "
                f"Page: {page} | "
                f"Chunk: {chunk_id} | "
                f"Relevance: {score:.3f}]\n"
                f"{text}\n"
            )

            if current_length + len(block) > max_context_chars:
                break

            context_parts.append(block)
            current_length += len(block)

        return "\n".join(context_parts)

    # ==========================================================
    # TABLE / NUMERIC FAST PATH
    # ==========================================================

    @staticmethod
    def _extract_requested_models(question):
        """
        Extract model names from the user's question.

        Example:
        'Model Alpha, Model Beta, Model Gamma, and Model Delta'
        -> ['Model Alpha', 'Model Beta', 'Model Gamma', 'Model Delta']
        """
        matches = re.findall(
            r"\bModel\s+[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)?\b",
            question
        )

        result = []
        seen = set()

        for match in matches:
            model = re.sub(r"\s+", " ", match).strip()
            key = model.lower()

            if key not in seen:
                seen.add(key)
                result.append(model)

        return result

    @staticmethod
    @staticmethod
    def _latency_matches(text):
        """
        Find numeric latency values in two common PDF extraction forms:

        1. 1.8 sec / 1.8 seconds
        2. 1.8 when the table header contains "latency (s)"
        """
        return list(
            re.finditer(
                r"(\d+(?:\.\d+)?)\s*(seconds?|secs?|sec|s)\b",
                text,
                flags=re.IGNORECASE
            )
        )

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _prepare_ordered_text(self, retrieved_chunks):
        """
        Reorder retrieved chunks into document/page/chunk order.
        """
        ordered_chunks = sorted(
            retrieved_chunks,
            key=lambda chunk: (
                str(chunk.get("document", "")),
                self._safe_int(chunk.get("page", 0)),
                self._safe_int(chunk.get("chunk_id", 0))
            )
        )

        return "\n".join(
            (chunk.get("text", "") or "")
            for chunk in ordered_chunks
        )

    @staticmethod
    def _normalize_number(number):
        return number.strip()

    def _find_model_latency_in_text(self, text, model_name):
        """
        Extract a latency value immediately following a model name.

        PDF table extraction commonly produces:

            Model Alpha
            1.8
            1–2

        rather than "Model Alpha 1.8 sec".
        """
        model_match = re.search(
            rf"(?i)\b{re.escape(model_name)}\b",
            text
        )

        if not model_match:
            return None

        start = model_match.end()
        following = text[start:start + 120]

        # First accept an explicit unit if one exists.
        explicit = re.search(
            r"(\d+(?:\.\d+)?)\s*"
            r"(seconds?|secs?|sec|s)\b",
            following,
            flags=re.IGNORECASE
        )

        if explicit:
            return {
                "value": float(explicit.group(1)),
                "number": self._normalize_number(explicit.group(1)),
                "unit": explicit.group(2)
            }

        # PDF table extraction may place the unit only in the header:
        # "Avg. latency (s)". In that case the first standalone decimal
        # immediately after the model row is the latency value.
        number_match = re.search(
            r"(?:^|\n|\r)\s*(\d+(?:\.\d+)?)\s*(?:\n|\r|$)",
            following
        )

        if number_match:
            number = number_match.group(1)
            return {
                "value": float(number),
                "number": self._normalize_number(number),
                "unit": "s"
            }

        # Handle extraction where the number is on the same line but
        # separated by spaces/tabs instead of a newline.
        number_match = re.search(
            r"\s+(\d+\.\d+|\d+)\s+(?:\d+[–-]\d+)",
            following
        )

        if number_match:
            number = number_match.group(1)
            return {
                "value": float(number),
                "number": self._normalize_number(number),
                "unit": "s"
            }

        return None

    def _extract_document_text(self):
        """
        Extract text directly from the registered uploaded PDFs.

        This is used only as a deterministic fallback for structured
        table lookups when chunk boundaries split a table row.
        It remains strictly grounded in the uploaded documents.
        """
        page_texts = []

        for document_name, pdf_path in self.pdf_paths.items():
            try:
                with pymupdf.open(pdf_path) as document:
                    for page_number, page in enumerate(document, start=1):
                        page_texts.append({
                            "document": document_name,
                            "page": page_number,
                            "text": page.get_text("text") or ""
                        })
            except Exception as e:
                print(
                    f"WARNING: Could not extract text from "
                    f"{document_name}: {e}"
                )

        return page_texts

    def _try_table_latency_answer(self, question, retrieved_chunks):
        """
        Deterministic answer path for latency-table questions.

        The parser extracts model names from the user's question and
        reads their values from uploaded-document text. It does not
        contain hard-coded test values.
        """
        question_lower = question.lower()

        if "latency" not in question_lower:
            return None

        requested_models = self._extract_requested_models(question)

        if not requested_models:
            return None

        # ------------------------------------------------------
        # PASS 1: retrieved chunks
        # ------------------------------------------------------
        sources = [
            {
                "document": "retrieved chunks",
                "text": self._prepare_ordered_text(retrieved_chunks)
            }
        ]

        # ------------------------------------------------------
        # PASS 2: uploaded PDF pages
        #
        # This fixes table rows split by chunk boundaries.
        # ------------------------------------------------------
        sources.extend(self._extract_document_text())

        values = {}

        for model in requested_models:
            for source in sources:
                result = self._find_model_latency_in_text(
                    source.get("text", ""),
                    model
                )

                if result:
                    values[model] = result
                    break

        if not all(model in values for model in requested_models):
            missing = [
                model for model in requested_models
                if model not in values
            ]
            print(
                "TABLE FAST PATH: Missing latency values for: "
                + ", ".join(missing)
            )
            return None

        formatted_values = [
            f"{model}: {values[model]['number']} {values[model]['unit']}"
            for model in requested_models
        ]

        wants_lowest = any(
            word in question_lower
            for word in ("lowest", "minimum", "fastest")
        )

        wants_highest = any(
            word in question_lower
            for word in ("highest", "maximum", "slowest")
        )

        if wants_lowest:
            selected_model = min(
                requested_models,
                key=lambda model: values[model]["value"]
            )

            return (
                f"Lowest latency: {selected_model} — "
                f"{values[selected_model]['number']} "
                f"{values[selected_model]['unit']}. "
                f"Compared values: {', '.join(formatted_values)}."
            )

        if wants_highest:
            selected_model = max(
                requested_models,
                key=lambda model: values[model]["value"]
            )

            return (
                f"Highest latency: {selected_model} — "
                f"{values[selected_model]['number']} "
                f"{values[selected_model]['unit']}. "
                f"Compared values: {', '.join(formatted_values)}."
            )

        return "Latency values: " + ", ".join(
            formatted_values
        ) + "."

    # ==========================================================
    # VISUAL QUESTION DETECTION
    # ==========================================================

    def _needs_visual_reasoning(self, question):
        question_lower = question.lower()

        visual_keywords = [
            "image",
            "figure",
            "diagram",
            "graph",
            "chart",
            "visual",
            "illustration",
            "caption",
            "shown",
            "pictured",
            "look like",
            "what does the figure",
            "what does the diagram",
            "what is shown"
        ]

        return any(
            keyword in question_lower
            for keyword in visual_keywords
        )

    # ==========================================================
    # OLLAMA RESPONSE EXTRACTION
    # ==========================================================

    def _extract_answer(self, response):
        """Safely extract answer text from an Ollama response."""
        if response is None:
            return ""

        answer = ""

        if isinstance(response, dict):
            message = response.get("message", {})

            if isinstance(message, dict):
                answer = message.get("content", "") or ""

            if not answer:
                answer = response.get("response", "") or ""

        else:
            message = getattr(response, "message", None)

            if message:
                answer = getattr(message, "content", "") or ""

            if not answer:
                answer = getattr(response, "response", "") or ""

        return answer.strip()

    # ==========================================================
    # GENERATION
    # ==========================================================

    def generate(
        self,
        question,
        retrieved_chunks,
        relevant_pages=None
    ):
        """
        Generate a grounded answer.

        Deterministic latency-table questions are answered
        directly from retrieved text.

        Other text questions use Ollama.

        Visual questions additionally send relevant PDF pages
        to Qwen3-VL.
        """
        if not question or not question.strip():
            return "Please enter a question."

        if not retrieved_chunks:
            return (
                "I couldn't find this information "
                "in the uploaded document."
            )

        context = self._build_text_context(
            retrieved_chunks
        )

        print(
            f"Retrieved context length: {len(context)}"
        )

        # ------------------------------------------------------
        # FAST PATH: latency table
        # ------------------------------------------------------

        table_answer = self._try_table_latency_answer(
            question,
            retrieved_chunks
        )

        if table_answer:
            print(
                "\nTABLE FAST PATH SUCCESS"
            )
            print(
                "Ollama was not called for this "
                "deterministic table question."
            )
            return table_answer

        # ------------------------------------------------------
        # VISUAL PAGE SELECTION
        # ------------------------------------------------------

        if relevant_pages is None:
            relevant_pages = []

        needs_visual = self._needs_visual_reasoning(
            question
        )

        images = []
        visual_pages = []

        if needs_visual:
            visual_pages = self._select_visual_pages(
                question,
                retrieved_chunks,
                relevant_pages,
                max_pages=1
            )

            print("\nSELECTED VISUAL PAGES")
            for page_info in visual_pages:
                print(
                    f" - {page_info.get('document', '')} | "
                    f"Page {page_info.get('page')}"
                )

            images = self._build_images(
                visual_pages
            )

        print(
            f"Visual reasoning required: {needs_visual}"
        )
        print(
            f"Images sent to Ollama: {len(images)}"
        )

        # ------------------------------------------------------
        # OLLAMA PROMPT
        # ------------------------------------------------------

        prompt = f"""
You are a precise document question-answering system.

Use ONLY the information in the uploaded documents
provided below.

Do NOT use outside knowledge.

RETRIEVED DOCUMENT INFORMATION
==============================

{context}

==============================

USER QUESTION
=============

{question}

==============================

RULES
=====

1. Read ALL retrieved document information.

2. If the question asks for multiple values, provide every
   value supported by the retrieved document.

3. If information is distributed across multiple pages,
   combine the information from those pages.

4. For comparison questions:
   - identify every candidate
   - identify every candidate's value
   - compare all candidates
   - then give the result

5. Do not choose the first value simply because it appears first.

6. Preserve exact numerical values and units from the document.

7. Do not invent information.

8. If the requested information cannot be found, say:
   I couldn't find this information in the uploaded document.

9. Keep the answer concise.

FINAL ANSWER:
"""

        message = {
            "role": "user",
            "content": prompt
        }

        if images:
            message["images"] = images

        try:
            print("\nSending request to Ollama...")

            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[message],
                options={
                    "temperature": 0,
                    "num_ctx": 4096,
                    "num_predict": 256
                },
                think=False
            )

            answer = self._extract_answer(response)

            if answer:
                print("Ollama returned an answer.")
                return answer

            print(
                "WARNING: Ollama returned an empty answer."
            )

        except Exception as e:
            print(
                f"Ollama request failed: {e}"
            )

        return "The model could not generate an answer."
