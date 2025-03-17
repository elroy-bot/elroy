# Memory Configuration

These settings control how Elroy manages and consolidates memories.

## Memory Consolidation Options

* `--memories-between-consolidation INTEGER`: How many memories to create before triggering a memory consolidation operation. [default: 4]
* `--l2-memory-relevance-distance-threshold FLOAT`: L2 distance threshold for memory relevance. [default: 1.24]
* `--memory-cluster-similarity-threshold FLOAT`: Threshold for memory cluster similarity. The lower the parameter is, the less likely memories are to be consolidated. [default: 0.21125]
* `--max-memory-cluster-size INTEGER`: The maximum number of memories that can be consolidated into a single memory at once. [default: 5]
* `--min-memory-cluster-size INTEGER`: The minimum number of memories that can be consolidated into a single memory at once. [default: 3]
* `--reflect / --no-reflect`: If true, the assistant will reflect on memories it recalls. This will lead to slower but richer responses. If false, memories will be less processed when recalled into memory. [default: false]

## Memory Consolidation Process

Elroy automatically consolidates related memories to create higher-level, more abstract memories. This process is triggered after creating a certain number of memories (controlled by `memories-between-consolidation`).

The consolidation process:

1. Groups similar memories based on the `memory-cluster-similarity-threshold`
2. Consolidates groups that have between `min-memory-cluster-size` and `max-memory-cluster-size` memories
3. Creates a new, higher-level memory that summarizes the consolidated memories

## Memory Reflection

When the `reflect` option is enabled, Elroy will spend more time processing and reflecting on memories when they are recalled. This leads to richer, more insightful responses but may increase response time. When disabled, memories are recalled more directly with less processing, resulting in faster responses.
