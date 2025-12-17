# TODO

## Performance Optimizations

1. **Add classifier early in message cycle to help latency of responses**
   - Implement early classification to improve response times
   - Should happen before main processing pipeline

2. **Avoid rewriting context to invalidate prompt caching**
   - Preserve context structure to maintain prompt cache effectiveness
   - User initiative actions excepted from this constraint

3. **Implement strong model / fast model configuration**
   - Allow different models to be used for different tasks
   - Fast model for simple/quick operations (e.g., classification, routing)
   - Strong model for complex reasoning and generation tasks
