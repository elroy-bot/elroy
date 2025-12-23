# TODO

## Performance Optimizations

1. **Add classifier early in message cycle to help latency of responses**
   - Implement early classification to improve response times
   - Should happen before main processing pipeline
   - See TODO comment in messenger.py:51 ("Quick classifier on whether recall is necessary")
   - Would work well with fast model configuration to route to appropriate model
