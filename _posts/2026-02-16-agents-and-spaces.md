---
layout: post
title: "Agents and Spaces: A Minimal Architecture for Multi-Agent Coordination"
date: 2026-02-16 16:00:00 +0800
tags: [ai, agents, architecture, llm]
categories: [engineering]
mermaid: true
---

I've been building a local-first personal AI assistant, something in
the vein of [Open Interpreter](https://www.openinterpreter.com/) and
[OpenClaw](https://docs.openclaw.ai), and I hit a wall that I think
a lot of people are hitting right now.

The single-agent loop works surprisingly well. User says something, LLM
reasons, tools execute, repeat. Wrap it in `while true` and you've got
the [Ralph Wiggum loop](https://ghuntley.com/ralph/). You can get a lot
done this way. But a personal assistant that's actually _useful_ needs
to do many things at
once. Research a topic while drafting a document. Process emails while
you're chatting. Run a scheduled task overnight and have the results
ready in the morning. One agent, one context window, one turn at a
time. It doesn't scale.

So, multi-agent. Obviously. But the more I looked at existing
frameworks, the less I liked what I saw.

## What's broken

Here are real problems I ran into:

**Cross-channel continuity.** You mention a project in chat. An email
arrives about the same project. The chat agent and the email agent have
no shared context. In frameworks like
[CrewAI](https://www.crewai.com/) or
[AutoGen](https://microsoft.github.io/autogen/), agents communicate
through prescribed channels, but there's no unified content store where
both can discover they're working on the same thing.

**Background work blocks the conversation.** Ask your assistant to
research something that takes 30 seconds. In a single-agent loop,
you're staring at a spinner. Can't ask a follow-up, can't switch
topics. The context window is busy. Multi-agent helps, but most
frameworks want you to declare the topology upfront. "This is the
research agent, this is the chat agent, here's how they talk." What if
the next question _doesn't_ need research?

**Deferred actions lose their context.** "Remind me tomorrow at 9am" is
easy to _schedule_ but hard to _execute well_. The reminder needs to
carry the conversational context it was created in, like a closure
capturing its environment. But the cron trigger and the chat agent are
separate systems. The deferred action fires in a vacuum.

**Trust is all-or-nothing.** You want a research agent that can browse
the web but can't see your private files. Most frameworks either give
agents full access to everything (YOLO mode), or make you build
separate permission systems per tool.

**Agent roles are premature abstractions.** Frameworks ask you to define
types upfront: Researcher, Writer, Reviewer, Coder. But real tasks
don't decompose neatly into roles. "Plan my trip to Tokyo" needs web
research, calendar access, budget calculations, and document drafting,
in an order that depends on what the research turns up. A fixed role
graph can't adapt.

Any personal assistant that handles more than one thing at a time hits
all of these.

## The bitter lesson, applied

Rich Sutton's
[Bitter Lesson](http://www.incompleteideas.net/IncsightBrief.pdf):
methods that leverage general computation consistently outperform
methods that encode human knowledge. The history of AI is littered with
hand-crafted heuristics that worked until general-purpose approaches
scaled past them.

Multi-agent systems are repeating this mistake. Current frameworks
encode coordination strategies ("this agent is the planner, that one
is the executor, they communicate through this protocol") as if we
know what optimal coordination looks like. We don't. LLMs are improving
fast enough that any fixed topology will be obsolete within a year.

So I went the other direction. Minimal concepts. Zero prescribed
workflows. Coordination that emerges from how agents use the building
blocks.

## The building blocks

The architecture has three concepts.

### Agents

An agent is an LLM with a context window, some tools, and access to
shared content.

| Component | What it is |
|-----------|-----------|
| **Model** | Which LLM (Sonnet, Haiku, Opus, a local model) |
| **Instructions** | How to behave, what to prioritize, what format to use |
| **Tools** | What the agent can do (web search, file access, code execution) |
| **Session** | The context window: working memory and turn history |
| **Connected spaces** | Shared content stores the agent can read from and write to |

No classes, no role enums. What makes an agent a "research agent" vs. a
"writing agent" is the instructions it got and the spaces it can see.

The session _is_ the agent's identity. Creating a session = the agent is born. Wiping
it = the agent is dead. Same instructions, fresh session, different
agent. And spaces outlive agents. Whatever an agent wrote to a space is
still there after it's gone.

Agents can **spawn** other agents, passing along a task, instructions,
and explicit access boundaries. The spawner controls what the new agent
can see and do. Everything else (how to decompose the work, whether to
spawn further, how to coordinate) is the new agent's problem.

### Spaces

A **space** is a shared, access-controlled content store. Agents read
and write **atoms**, small units of content (a task, a message, a
research finding, a document section) that carry metadata and can
reference each other. Content is semantically searchable. Changes
trigger notifications to subscribers.

There is no separate messaging system. A task assignment is an atom
update. A status report is a new atom. A question to a collaborator is
a message in a shared space. All communication is content in spaces.

### Conventions

Everything above the raw mechanics is a **convention**, a usage
pattern taught through instructions, not enforced by code.

A "task list" isn't a special type of space. It's a regular space where
agents follow the task list convention: atoms have `status`/`owner`
metadata, `blocked_by` references encode dependencies, agents scan for
unblocked pending tasks. A "chat" is a space where atoms have `role`
metadata and a UI renders them. A "knowledge base" is a space where
atoms carry `confidence` scores and `supports`/`contradicts` references.

Same spaces, same operations, different conventions.

<pre class="mermaid">
graph TB
    subgraph CON["Conventions (taught, not enforced)"]
        TL["Task Lists"] ~~~ CH["Channels"] ~~~ CT["Chats"] ~~~ DOC["Documents"]
    end

    subgraph CORE["Core"]
        A["Agents<br/><small>LLM + instructions + tools +<br/>session + connected spaces</small>"]
        S["Spaces<br/><small>shared content + permissions +<br/>search + subscriptions</small>"]
    end

    A -->|"spawn"| A
    A <-->|"read / write<br/>atoms"| S
    CON -.-|"patterns built on"| CORE

    style A fill:#4a6fa5,color:#fff
    style S fill:#e8d44d,color:#333
    style CON fill:#6b8cae,color:#fff
    style CORE fill:#f5f5f5,color:#333
    style TL fill:#93afc5,color:#333
    style CH fill:#93afc5,color:#333
    style CT fill:#93afc5,color:#333
    style DOC fill:#93afc5,color:#333
</pre>

An agent that can create other agents and share content stores with them
can express any coordination pattern (pipelines, fan-out, debates,
priority queues) without the architecture prescribing any of them.

## Spawning and trust

When an agent spawns another, it defines the trust boundary:

```
spawn(
    task:         "What to do" (natural language),
    instructions: "How to behave" (reference to an instruction space),
    spaces:       { space_id: permission },
    tools:        [...],
    secrets:      [...],
    model:        "which LLM"
)
```

The spawner says what the new agent can access and gives it a task.
No role assignment, no topology declaration, no workflow step number.

### Trust narrows monotonically

**Privileges can only narrow down the spawn tree, never widen.**
Spaces, tools, secrets all narrow monotonically. No privilege
escalation without going back to a coordinator.

<pre class="mermaid">
graph TD
    C["Coordinator<br/><small>all tools, all spaces, all secrets</small>"]
    R["Research Agent<br/><small>web tools, research space</small>"]
    W["Writer Agent<br/><small>file tools, doc space</small>"]
    S1["Sub-researcher<br/><small>web tools, research space (read only)</small>"]
    S2["Sub-researcher<br/><small>web tools, research space (read only)</small>"]

    C -->|"spawn<br/>(narrows access)"| R
    C -->|"spawn<br/>(narrows access)"| W
    R -->|"spawn<br/>(narrows further)"| S1
    R -->|"spawn<br/>(narrows further)"| S2

    style C fill:#4a6fa5,color:#fff
    style R fill:#6b8cae,color:#fff
    style W fill:#6b8cae,color:#fff
    style S1 fill:#93afc5,color:#333
    style S2 fill:#93afc5,color:#333
</pre>

Every spawn is a trust boundary. Give a research agent web access but no
PII access, a data diode where information flows one direction. The
spawner defines the boundary; the spawned agent operates within it.

### But sometimes a child needs more

Real tasks don't always fit the initial access grant. A research agent
discovers it needs to read a private document. A code agent realizes it
needs database credentials.

The mechanism: ask the coordinator. Every sub-agent has a DM space
shared with its coordinator. It writes a request. The coordinator
evaluates whether the agent's task justifies the access and grants or
denies. Privileges widen only through an explicit grant from an agent
with sufficient permission, like a manager approving an access request.

No special permission API needed. Agents communicating through a space.

### Identity is not a type

Agent identity is shaped by instructions, not declared. The
`instructions` field references a space containing behavioral guidance.
This could be a well-known default ("research-guidelines"), a fork
customized for this task, something created from scratch, or (if the
agent has write access) **refined by the agent itself** over time.

Pre-defined agent templates become seed content, not a locked-in
registry. Fork "research-guidelines," tweak it for biotech, spawn a
specialized agent. All at runtime, no code changes.

## Inside a space

### Atoms

The unit of content is an **atom**: a payload (`content`) with
`metadata` (key-value pairs like status, owner, priority) and typed
`references` to other atoms (`blocked_by`, `supersedes`, `supports`).
Atoms are versioned and semantically searchable. The system stores and
traverses references but doesn't interpret their semantics. That's the
convention layer's job.

Operations are the basics: `put`, `get`, `update`, `search`,
`deprecate`, `history`. Every mutation includes a **comment**, a
semantic description like a git commit message. Comments are what gets
published to subscribers, not atom content. An agent sees "added
findings from 3 review sites" and decides whether to pull the full atom.

### Permissions

Four levels, each implying the ones above it
(`grant` ⊃ `write` ⊃ `append` ⊃ `read`):

- **read**: See content, search, subscribe
- **append**: Add new atoms (can't modify existing)
- **write**: Full mutation (update, replace, refine)
- **grant**: Share access with other agents

New spaces start private. Only `grant` holders can share them.

### Search

Semantic and structured, composable:

```
search(
    query="frontend tasks",                        # semantic
    metadata={"status": "pending"},                # exact match
    references={"blocked_by": {"status": "done"}}  # reference state
)
```

One call: find atoms matching "frontend tasks" where status is pending
and all blockers are done. This is what makes conventions practical.
You can query a task list for available work without multiple round
trips.

### How spaces reach agents

Spaces connect to an agent's session in two ways. **Injected** spaces
are always in context: instructions, personal memories, convention
descriptions. **Queried** spaces are searched on demand: task lists,
knowledge bases, research findings. The distinction matters because
sessions are bounded but spaces are unbounded. You can't inject
everything.

How does an agent _know_ a convention? Each space carries a description
in its metadata: "This is a task list. Atoms have `status`, `owner`,
and `priority`. Use `blocked_by` references for dependencies." When an
agent connects, that description gets injected. The agent learns how to
use the space from the space itself.

## Content is coordination

**There is no separate messaging primitive.** Everything is content in
spaces.

<pre class="mermaid">
graph LR
    subgraph " "
        direction LR
        A1["Research<br/>Agent"] -->|put| S1(["Findings<br/>Space"])
        S1 -->|notification| A2["Writer<br/>Agent"]
        A2 -->|put| S2(["Document<br/>Space"])
        S2 -->|notification| A3["Review<br/>Agent"]
        A3 -->|update| S2
    end

    style S1 fill:#e8d44d,color:#333
    style S2 fill:#e8d44d,color:#333
    style A1 fill:#6b8cae,color:#fff
    style A2 fill:#6b8cae,color:#fff
    style A3 fill:#6b8cae,color:#fff
</pre>

When a research agent writes findings to a shared space, that _is_ the
communication. Other agents subscribed to the space see the update and
react. No separate "hey, I'm done" message. The distinction between
"communication" and "work product" collapses.

Every space change triggers notifications to subscribers. When one
arrives, the system runs an LLM turn. The agent sees the comment and
decides how to react. This is reactive activation from
[blackboard architectures](https://en.wikipedia.org/wiki/Blackboard_(design_pattern))
(Hearsay-II, 1980) without a control shell. The system delivers
events; agents decide what matters.

## Coordinators are topological, not assigned

The system needs entry points, places where external input enters the
agent ecosystem. I call these **coordinators**, but it's misleading if
you think of it as a role.

A coordinator is any agent connected to a space with an external
interface. TUI writes to a chat space? That agent is a coordinator.
Webhook writes to a webhook space? Also a coordinator. The topology
determines it.

<pre class="mermaid">
graph LR
    UI["TUI / Web UI"] --> CS(["Chat Space"])
    WH["Webhook"] --> WS(["Webhook Space"])
    CR["Cron"] --> CRS(["Cron Space"])

    CS --> UA["User Agent"]
    WS --> WA["Webhook Agent"]
    CRS --> CA["Cron Agent"]

    UA <-->|read/write| BUS(["Coordinator Bus"])
    WA <-->|read/write| BUS
    CA <-->|read/write| BUS

    style CS fill:#e8d44d,color:#333
    style WS fill:#e8d44d,color:#333
    style CRS fill:#e8d44d,color:#333
    style BUS fill:#d4a44d,color:#333
    style UA fill:#4a6fa5,color:#fff
    style WA fill:#4a6fa5,color:#fff
    style CA fill:#4a6fa5,color:#fff
    style UI fill:#888,color:#fff
    style WH fill:#888,color:#fff
    style CR fill:#888,color:#fff
</pre>

Coordinators can grant access, share spaces across agent boundaries,
and manage subagent lifecycles. They share a **coordinator bus** for cross-coordinator communication.

### "Remind me tomorrow at 9am"

This sounds trivial but exposes every seam in a multi-agent system. It
crosses coordinator boundaries, requires scheduling, needs shared
context.

1. You type "remind me tomorrow at 9am to review the Q3 report"
2. Chat UI writes to the **chat space**
3. The **user-agent** recognizes a cross-coordinator request, writes to
   the **coordinator bus**: "set reminder: 9am tomorrow, context: Q3
   report review"
4. The **cron-agent** (subscribed to the bus) picks it up, sets the
   trigger, writes back an acknowledgment
5. User-agent confirms: "Done, I'll remind you tomorrow at 9am"
6. Next morning: cron fires, cron-agent writes the reminder to the bus
   with the original context
7. User-agent picks it up: "Time to review the Q3 report"

Two coordinators talking through a space, using the same operations as
everything else.

## Conventions

I mentioned eight conventions so far. Here they are:

| Convention | Analogous to | Key pattern |
|------------|-------------|-------------|
| **Task List** | GitHub Issues | Status/owner metadata + dependency refs |
| **Channel** | Slack channel | Append-only message stream |
| **Chat** | Chat UI | Bidirectional, role-tagged turns |
| **Document** | Google Docs | Progressive refinement with versioning |
| **Scratchpad** | Notepad | Private working memory |
| **Prompt Library** | Template registry | Reusable instruction + convention templates |
| **Knowledge Base** | Team wiki | Curated facts with evidence links |
| **Personal Memory** | mem0 | Auto-extracted facts, injected into context |

New conventions emerge by writing new descriptions, not new code.

## Code as the interaction model

Most agent frameworks give agents a fixed set of named tools like
`search`, `read_file`, `send_email`, and the agent picks which to
call. This works for simple things. But what if you need to search,
filter results, then conditionally update three items based on what you
found? That's three tool calls with branching logic in between. State
management across turns. A new tool for every new operation.

[NanoClaw](https://github.com/qwibitai/nanoclaw) takes one approach:
keep the codebase small enough that the agent can rewrite its own tools.
But there's a more general version of the same insight: let agents write
code as their primary way of acting.

[CodeAct](https://arxiv.org/abs/2402.01030) (Wang et al., 2024) showed
that agents expressing actions as executable Python achieve up to 20%
higher success rates than structured tool calls. Hugging Face's
[smolagents](https://github.com/huggingface/smolagents) makes this
production-grade. [RLMs](https://arxiv.org/abs/2512.24601) (Zhang et
al., 2025) take it further: agents _think_ in code, managing their own
context programmatically and
[scaling to 10M+ tokens](https://www.primeintellect.ai/blog/rlm).

**Spaces are the external environment, and code is how agents interact
with them.** Give agents a `space` capability object in a sandboxed
executor. Convention descriptions include code recipes. Agents adapt
and execute them:

```python
# Fan-out research with dynamic decomposition
findings = space.search(query="initial landscape analysis")
segments = extract_segments(findings[0].content)

for segment in segments:
    coordinator.spawn(
        task=f"Deep research on {segment}",
        instructions="research-guidelines",
        spaces={"findings": "append"},
        tools=["web_search", "web_fetch"]
    )
```

New conventions don't require new tools, only new code recipes. A
framework with fixed tools is limited by what the designers anticipated.
A framework with code and an environment is limited by what the agents
can express. That ceiling rises with every model generation.

## Where this goes

The architecture is designed but not yet implemented. Some scenarios:

A morning briefing, assembled overnight. Cron-agent fires at 6am,
spawns research agents for your calendar, news, overnight emails. Each
writes to a shared briefing space. Synthesis agent compiles. When you
open the chat at 8am, it's waiting.

Or adaptive task decomposition. You ask for a competitive analysis.
The coordinator spawns one research agent, reads the initial findings,
realizes the landscape is broader than expected, spawns three more.
The task graph grew dynamically based on what the first agent found.
Next time, same request might need one researcher. The architecture
doesn't care.

Correctness is almost trivial here. The interesting part starts when
you let agents loose on it.

---

### References

1. Sutton, R. (2019). [The Bitter Lesson](http://www.incompleteideas.net/IncsightBrief.pdf).
2. Wang, X. et al. (2024). [Executable Code Actions Elicit Better LLM Agents](https://arxiv.org/abs/2402.01030). _ICML 2024_.
3. Zhang, T. et al. (2025). [Recursive Language Models](https://arxiv.org/abs/2512.24601). MIT.
4. Prime Intellect. (2026). [The Paradigm of 2026](https://www.primeintellect.ai/blog/rlm).
5. Hugging Face. (2025). [Introducing smolagents](https://huggingface.co/blog/smolagents).
6. Erman, L.D. et al. (1980). The Hearsay-II Speech-Understanding System: Integrating Knowledge to Resolve Uncertainty. _ACM Computing Surveys_, 12(2).
