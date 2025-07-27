# Embeddings overhaul

1. Remove dependency on sqlite-vec and pg-vector: for embeddings searches, simply load the user's full cohort of embeddings in memory, then perform similarity searches on it with FAISS.

2. Convert embeddings calculation to a local model, with a second local model performing reranking

# Simplify recall representation.

1. Convert recall to a simulated tool call. This way, memory metadata can be captured in the tool response.

2. (possibly): Convert internal thought to simulated tool call

# Reminders features

1. Add contextual reminders, which can be repeating indefinitely, or completed.

2. Add timing reminders, which should be resurfaced at a specific time.
