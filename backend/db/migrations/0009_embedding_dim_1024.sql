-- NVIDIA NIM nv-embedqa-e5-v5 returns 1024-d vectors (not OpenAI's 1536).
DROP INDEX IF EXISTS idx_conversation_turns_embedding;
ALTER TABLE conversation_turns ALTER COLUMN embedding TYPE vector(1024);
CREATE INDEX idx_conversation_turns_embedding ON conversation_turns USING ivfflat (embedding vector_cosine_ops);
