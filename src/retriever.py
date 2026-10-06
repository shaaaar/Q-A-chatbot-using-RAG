class Retriever:

    def __init__(
        self,
        embedding_model,
        vector_store,
        chunks
    ):

        self.embedding_model = embedding_model

        self.vector_store = vector_store

        self.chunks = chunks


    def search(
        self,
        question,
        k=5,
        score_threshold=0.10
    ):

        if not question or not question.strip():

            return []


        if self.vector_store is None:

            return []


        if self.vector_store.size() == 0:

            return []


        k = min(
            k,
            self.vector_store.size()
        )


        if k <= 0:

            return []


        # ==================================================
        # EMBED QUESTION
        # ==================================================

        query_embedding = (
            self.embedding_model
            .encode([question])[0]
        )


        # ==================================================
        # VECTOR SEARCH
        # ==================================================

        scores, indices = (
            self.vector_store.search(
                query_embedding,
                k
            )
        )


        print(
            "\n" + "=" * 60
        )

        print(
            "RETRIEVAL DEBUG"
        )

        print(
            "=" * 60
        )

        print(
            "Question:",
            question
        )


        # ==================================================
        # DEBUG RESULTS
        # ==================================================

        for score, index in zip(
            scores,
            indices
        ):

            index = int(index)

            score = float(score)


            if (
                0 <= index
                < len(self.chunks)
            ):

                chunk = self.chunks[
                    index
                ]


                print(

                    f"Chunk {index} | "

                    f"Score: {score:.4f} | "

                    f"Type: "
                    f"{chunk.get('type', 'text')} | "

                    f"Document: "
                    f"{chunk.get('document', '')} | "

                    f"Page: "
                    f"{chunk.get('page', '?')}"

                )


        print(
            "=" * 60
        )


        # ==================================================
        # BUILD RESULTS
        # ==================================================

        results = []


        for score, index in zip(
            scores,
            indices
        ):

            score = float(score)

            index = int(index)


            if score < score_threshold:

                continue


            if index < 0:

                continue


            if index >= len(
                self.chunks
            ):

                continue


            chunk = self.chunks[
                index
            ].copy()


            chunk["score"] = score


            results.append(
                chunk
            )


        print(

            f"Retrieved "
            f"{len(results)} relevant chunks "
            f"(threshold="
            f"{score_threshold})"

        )


        return results