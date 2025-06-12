title: The problem with tool based memory recall

I wanted to build an LLM assistant with memory abilities. The first solution I turned to, which many people have done, is build an agent loop with access to custom tools I wrote, that manage and read memory.

There's now a handly tool for builders like this: MCP. MCP has taken off among LLM builders, to the point where it almost seems mandatory to support it to get anyone interested in your tool. There are storm clouds on the horizon, though: the _builders_ of MCP servers that far exceeds the number of _users_. I'm not really _that_ interested in using MCP to use _your_ tool, but I sure am eager for you to use MCP to access _mine_. Maybe you'd even pay me!


The problem is that MCP nicely solved a small, cumbersome problem for developers (cross language code execution), at least locally, but the user is left to fix for themselves the hard problem of handing tools to LLM's: how these tools should be used together. This is a task made much more difficult without easy access to edit the tools themselves. With MCP, I've completely delegated not only logic and instructions of my tools, but the execution as well.

footnote:
and not only the _logic_ of the tools, but the _execution on my machine_, and implicity managing my machine's resources (clumsily, at least for now!).



Similar to a well trained monkey given a hammer, an LLM handed a tool can wield a tool and use it on command. This makes for nice demos.



I have a problem when I

What makes a software program useful, however, is the ability to do larger, repeatable tasks _in a consistent way_. If a program's job is not done consistently, I'll still have to think about it, and that's what the computer is for!
Programmers often have this problem, but luckily they have a handy tool at their disposal: code. However, using it lessens the feel of playing god. As soon as we turn to code to fix our LLM problem, the target market of addressable tasks:


spectrum
-
repeatable, rote                repeatable, but involves simple decisions, quick to validate               complex, new every time
just use code                   Current sweet spot                                      antrhopic's ceo is doing everything in his power to reach this, while also trying to persuade everyone that it will end the world. If it's cumbersome to do but also cumbersome to validate, I'm better off doing the task myself.




the "tools" at the LLM's disposal are, just, _code_. the openai spec implies there will soon be more, but they've tellingly not been able to think of any that aren't well described by the word _function_


What I really want is a script that navigates _decision tree_. At key points, have the ability to query for data, synthesize it, and choose between a small number of options.

This could also be described as a _workflow_.

Many pixels have been spilled debating what constitutes an _agent_. Here's my definition:
- long lived, has autonomy
- has multiple use cases

The _agent_ has many degrees of freedom with what changes it can make in your system, and it's discretion will be used to determine what data it reads.

An agent might have _guardrails_, constraining it from doing certain operations, but these are largely for _safety_

For someone like me to be a user of an LLM tool every day for autonmous work, I need the outcome to be _predictable_.


---

Enter building a memory agent. I built what many people have built: a toolset for reading and managing memories. Once I experimented with different models, a problem quickly emerged: the agent's rate of checking memories was very different between different models. Some called the memory tools too infreuently, and wouldn't recall basic details. Other tools called and created memories for simple things, slowing down their response.

The _agentic_ way to solve this problem would be to add more descriptions to the tools, or nudges to use this tool.

My solution was to partially remove recall and memory creation from the agent's control. Upon receiving a message, the memories are automatically searched, with relevant ones being added to context. Every n messages, a memory is created or the token limit is reached, context messages compressed, and a memory created.

This makes even responding to a message in a personified agent way, a _workflow_. (receive message -> incorporate response -> send response -> wait for message)

---

For a piece of software to be useful, I need it to do something I want it to do, _predictably_. Only when a task is done _predictablly_ does it actually relieve me of having to think about it.

I think software maintainers who think about building "agents"  will be outcompeted by those who think about building _workflows_.


The agent approach leads maintainers to _add more prompting_. This can solve some problems, but in the long run what this will create is either unpredictable abstractions, or a predictable one created at very high cost.


The workflow approach leads to lean on the LLM for relatively simple _decisions_, with shifting complexity to code.

(diagram: maximalist approach at one end, increasing "guardrails")


y axi: logic handled by agent
x axies: logic handled by code

top left is fully autonomous LLM
middle is LLM's with guardrails
bottom is workflow

building with workflows is quadratic in how they use code
building with agents in mind is quadratic decining

useful software will land in between here

---

The conclusions here are all free of hard data, other than building a memory tool for myself. Aka., just vibes and personal experience









