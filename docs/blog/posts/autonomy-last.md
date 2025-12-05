---
title: Add Autonomy Last
date: 2025-07-07
canonical_url: https://elroy.bot/blog/2025/07/07/add-autonomy-last.html
---

# Add Autonomy Last

A core challenge of using LLM's to build reliable automation is calibrating how much **autonomy** to give to models.

Too much, and the program [loses track of what it's supposed to be doing](https://www.anthropic.com/research/project-vend-1). Too little, and the program feels a bit too, well, _ordinary_[^1].

<!-- truncate -->

## Autonomy first vs autonomy last

An implicit strategy question when building with LLMs is _autonomy first_ or _autonomy last_:

![autonomy_first_vs_last](../../images/blog/autonomy_last/autonomy_first_vs_last.png)

All of the major LLM-specific programming techniques are firmly _autonomy first_ strategies:

- _MCP_ surfaces a wide variety of functionality the program can have, and lets the LLM decide which to use
- _Guardrails_ add some light buffers around the LLM to prevent it from causing too much trouble.
- _Prompt engineering_ describes the alchemy of whispering just the right phrases to your LLM to get the behavior you want.
-  _Context engineering_ begins to stress programming to deliver only relevant information to LLMs at critical points in program execution


All of these:

1. Start with a maximally autonomous program
2. Adjust context, tools, and prompts until you narrow down behavior as desired.

All have similar issues when scaling in size and complexity:

- Program behavior changes too much when switching between models
- The LLM gets confused, and either hallucinates data or misuses tools at its disposal

When problems are encountered, programmers tend to attempt to repair by _adding more prompting_. But this is a duct tape response: a prompt that clarifies for one model might confused another.

_Autonomy last_, on the other hand, maximizes the logic that can be handled by code, then adds autonomous functions. This approach strives to keep the tasks delegated to LLMs [simple](https://en.wikipedia.org/wiki/KISS_principle). As the program grows in size and complexity, the programmer can closely monitor encapsulations and keep behavior consistent.


## Case study: Building Elroy, a chatbot with memory

I wanted to build an LLM assistant with memory abilities, called [Elroy](https://github.com/elroy-bot/elroy). My goal was to make a _program_ that could chat in human text. My ideal users are technical, capable and interested in customizing their software, but not necessarily interested in LLMs for their own sake.

### Approach #1: "Agent" with tools

The first solution I turned to, which many people have done, is build an agent loop with access to custom for creating and reading memories:

![tool_based_agent](../../images/blog/autonomy_last/Agent.png)

### Approach #2: Model Context Protocol (MCP)

There's now a handly tool for builders like this: [MCP](https://modelcontextprotocol.io/introduction). There are many implementations of my memory tools available via MCP, in fact [smithery.ai](https://smithery.ai/) lists one from Mem0 on it's homepage:

![smithery](../../images/blog/autonomy_last/smithery.png)

Now, an (in theory) lightweight abstraction sits between my program and it's tools:

![mcp](../../images/blog/autonomy_last/mcp.png)

This suggests extending my application via picking from a library of MCP's:

![more_mcp](../../images/blog/autonomy_last/more_mcp.png)


### Agentic trouble

I got my memory program working pretty well on gpt-4. At first it wasn't creating or referencing memories enough, but I was able to fix this with careful prompting.

Then, I wanted to see how Sonnet would do, and I had a problem[^2]: the program's behavior completely changed! Now, it was creating a memory on almost every message, and searching memories for even trivial responses:

![tool_usage](../../images/blog/autonomy_last/tool_usage_rate.png)

### Approach #3: Autonomy Last

My solution was to remove the timing of recall and memory creation from the agent's control. Upon receiving a message, the memories are automatically searched, with relevant ones being added to context. Every n messages, a memory is created[^3]:

![tool_usage](../../images/blog/autonomy_last/elroy.png)

This made much more of the behavior of my program deterministic, and made it easier to reason about and optimize.

# Autonomy Last

The "autonomy last" approach trades some of the magic of fully autonomous LLMs for predictable, reliable behavior that scales as your program grows in complexity. While my evidence is, (as I should have stated from the outset), _vibes_, I think this approach will lead to more maintainable and robust applications.

---

[^1]:
    Rather than using _agents_ to describe the genre of program under discussion, I'll be somewhat pointedly referring to them as _programs_.

[^2]:
    One problem I _didn't_ have, thanks to [litellm](https://www.litellm.ai/), was updating a lot of my code to support a different model API.

[^3]:
    Elroy also monitors for the context window being exceeded, and consolidates similar memories in the background.


