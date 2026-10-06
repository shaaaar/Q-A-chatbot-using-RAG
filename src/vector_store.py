import numpy as np


class VectorStore:

    def __init__(self, dimension):
        self.dimension = dimension
        self.embeddings = np.empty(
            (0, dimension),
            dtype=np.float32
        )

    def add(self, embeddings):

        embeddings = np.asarray(
            embeddings,
            dtype=np.float32
        )

        if embeddings.ndim != 2:
            raise ValueError(
                "Embeddings must be a 2D array."
            )

        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch. "
                f"Expected {self.dimension}, "
                f"got {embeddings.shape[1]}."
            )

        self.embeddings = np.vstack([
            self.embeddings,
            embeddings
        ])

    def size(self):
        return len(self.embeddings)

    def search(self, query_embedding, k=5):

        if self.size() == 0:
            return (
                np.array([]),
                np.array([], dtype=int)
            )

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32
        )

        if query_embedding.ndim != 1:
            raise ValueError(
                "Query embedding must be a 1D array."
            )

        if len(query_embedding) != self.dimension:
            raise ValueError(
                f"Query embedding dimension mismatch. "
                f"Expected {self.dimension}, "
                f"got {len(query_embedding)}."
            )

        # Since embeddings are normalized in
        # EmbeddingModel.encode(), dot product
        # is cosine similarity.
        scores = np.dot(
            self.embeddings,
            query_embedding
        )

        k = min(k, len(scores))

        indices = np.argsort(
            scores
        )[::-1][:k]

        return (
            scores[indices],
            indices
        )