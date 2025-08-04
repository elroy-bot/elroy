# Roadmap

## Changelog

| Date | Changes |
|---------|---------|
| 2025-08-04 | Initial version |

## Overview

Elroy is intended to be a scriptable memory and reminder assistant.

The goal thus far has been to make chats with AI more interesting via the addition of goals and memories.

Going forward, the project will focus on being a tool to help its users remember things. This means goal capabilities will be phased out in favor of more detailed reminder behavior.

The intended users are:

1. Users who want to use the project as is
2. Technical users who wish to include Elroy functionality in their own projects.

A good way of making useful APIs is to _use them yourself_. In line with this, I'm developing a mobile app that uses Elroy's APIs.

The APIs powering this app will remain open source in this repo. Users will be free to host their own instances of Elroy for whatever purpose they wish.

## Milestones

### V0 of mobile app

#### 1. Phase out the _goals_ functionality in favor of _reminders_.
This includes more traditional reminder features like timed reminders or location based reminders, but also more nebulous _contextual_reminders.

During this phase **response time optimization will be of low priority**. The goal is to create a usable memory and reminder system, without worrying too much about token use or response times.

#### 2. Optimize token usage / response times
Once basic functionality is robust, further enhancements will:

- Make token usage more efficient
- Improve response times
- Add dynamic model selection depending on task complexity (i.e., strong model / weak model)
- Improve local model support.


## Upcoming refactors

- Convert internal thought / memory retrieval to simulated tool calls, rather than adding recall via system message. This may improve model interoperability, and simplify code
- Remove sqlite-vec integration, to simplify local installation
- Perform vector searches via FAISS


## Supported databases
Elroy will continue to support two databases: Postgres and Sqlite. Any changes to DB schema will come with automatic migration support.

## Supported models
Elroy will support any chat models that support tool calling. Local embeddings calculation will eventually be supported.
