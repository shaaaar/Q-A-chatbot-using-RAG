# Docker setup for the Flask RAG app

This setup runs two containers with Docker Compose:

- `app`: Flask + your RAG pipeline
- `ollama`: local Ollama server
- `ollama-model-init`: pulls `qwen3-vl:2b-instruct` into the persistent Ollama volume

The Flask container talks to Ollama at `http://ollama:11434`.
