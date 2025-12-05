---
title: "Make It Easy for Humans First, Then AI"
date: 2025-11-26
---

I recently wrote about [optimizing repos for AI](2025-11-03-optimizing-repos-for-ai.md), but I've not quite settled on the question of, **_should_ you optimize repos for AI?** That is, is there really substantial daylight between what an AI dev needs and what a human needs?

<!-- truncate -->

## Issues with optimizing repos for AI

### Nearly everything I put in agent docs is useful for humans

![info](/img/diagrams/make-it-easy-for-humans/info.png)

Granted, without AI agents I wouldn't go through the trouble of documenting a lot of this. But that doesn't mean the content isn't useful. Even documentation to discourage AI-specific antipatterns is generally useful information for a human dev too.

### AI agent doc organization is fragmented

Each coding agent uses its own configuration file pattern for repo-specific instructions:

![fragmentation](/img/diagrams/make-it-easy-for-humans/fragmentation.png)


This creates a hassle just keeping guidelines between agents consistent, much less making information available for humans.

## Solution: Make it easy for humans

A better way is to organize information for humans and link to relevant artifacts in agent-specific files[^1]:

![easy-for-humans](/img/diagrams/make-it-easy-for-humans/easy-for-humans.png)

This makes keeping information consistent across agent docs much easier, and is much more future-proof for updates to agent file schemes. It also keeps humans in the loop!

For commands/skills, automation can help - for example, I wrote the [just-claude](https://github.com/tombedor/just-claude) utility for automatically synchronizing [Just](https://github.com/casey/just) recipes with [Claude Code Skills](https://www.claude.com/blog/skills).

This also sidesteps dev angst about being left behind. There's really no difference between the goal of economical token use for AI and reducing cognitive overhead for humans - organizing for humans first makes everyone happy.

[^1]: I wrote about what content I put in these files in the (ironically titled) post [Optimizing repos for AI](2025-11-03-optimizing-repos-for-ai.md)
