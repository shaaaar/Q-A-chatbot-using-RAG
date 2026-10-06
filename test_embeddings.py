from src.embeddings import EmbeddingModel

model = EmbeddingModel()

texts= [
    "What is machine learning?",
    "Machine learning allows computers to learn from data.",
    "The weather is sunny today."

]

embeddings = model.encode(texts)

print("embeddings.shape:", embeddings.shape)