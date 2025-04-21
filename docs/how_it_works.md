# How It Works

Elroy is an AI assistant that remembers conversations and helps you achieve your goals. This page explains the core concepts and architecture behind Elroy.

## Core Concepts

### Creating memories

As you chat with Elroy, it creates and stores *memories*. Later, when the text of these memories are semantically similar to your conversation, the assistant is reminded of the memory and prompted to reflect on how it pertains to your conversation.

### Consolidating and updating memories

Over time, memories can become outdated or redundant with other memories.

If Elroy finds that the text of a memory is no longer accurate, it appends an update.

In the background, Elroy's memory consolidation system combines and reorganizes memories, to make sure they are concise and unique as possible.

### Goals

Elroy is designed to help you *DO THINGS*! To help this along, Elroy creates and manages *goals* from your conversation. When a goal is complete, it is copied into memory (where it can be consolidated and reorganized with other knowledge), and the goal is archived.


### Document Awareness

Elroy can ingest documents and perform traditional RAG on their contents. In addition to storing source information, Elroy copies information from documents into memory, where it can be synthesized with other knowledge.

The original documents remain available for times when their exact content is important.
