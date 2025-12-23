# TODO

## Performance Optimizations

✅ **Completed**: Add classifier early in message cycle to help latency of responses
   - Implemented two-stage hybrid classifier (heuristics + fast_llm)
   - Integrated at messenger.py:51 (replaced TODO comment)
   - Uses fast_model infrastructure for efficient classification
   - Configurable via `memory_recall_classifier_enabled` and `memory_recall_classifier_window`
   - All tests passing (117 passed, 3 skipped)
