# ADR 0004 - Use LangGraph for ML Triage

* Status: superseded by [ADR-0007](0007-reduce-to-data-pipeline-and-barcode-api.md)
* Deciders: SahiDawa Core Team
* Date: 2026-07-14

Technical Story: [ML Triage Service](../../apps/ml/services/triage_graph.py)

## Context and Problem Statement

SahiDawa implements a voice-first health assistant for rural citizens to speak symptoms in 22 languages and receive primary triage guidance. This requires conducting a multi-turn conversation where the agent extracts symptoms, identifies potential emergencies, cross-references local medicine databases, and provides localized advice.
Managing this conversation flow using simple nested prompts or linear agent execution makes it difficult to maintain state, handle loops (e.g. asking clarifying questions), enforce safety checks (e.g. emergency warnings), and test deterministic paths. We need a framework to manage stateful multi-agent and multi-step conversational triage graphs.

## Decision Drivers

* Clear, visual representation of conversation states and transitions.
* Persistence of derived state (e.g., extracted symptoms, detected emergencies) across session turns.
* Safe routing of emergency vs. non-emergency cases.
* Ease of integration with Google Generative AI models (Gemini) and LangChain components.

## Considered Options

* **Option 1: Custom Session Handlers and Raw Prompts** (Writing custom Python conditional routing and storing state arrays manually in a database).
* **Option 2: LangGraph with LangChain & ChatGoogleGenerativeAI** (Structuring the agent as a stateful graph where nodes perform LLM calls or database lookups, and edges direct the conversation flow).
* **Option 3: Linear Agent Orchestration** (Standard sequential prompt chains without loops or conditional execution graphs).

## Decision Outcome

Chosen option: **Option 2: LangGraph with LangChain & ChatGoogleGenerativeAI**, because it represents the triage process as a StateGraph where states, nodes, and transitions are explicitly defined. The system persists session attributes (language, emergency flags, collected symptom data, and retrieved medicines) in Redis with a 30-minute Time-To-Live (TTL), while leveraging the Google Gemini API for high-quality multilingual LLM reasoning.

### Consequences

* **Good:**
  * Clean separation of concerns (e.g., separate nodes for symptom collection, emergency routing, and pharmacy mapping).
  * Robust multi-turn conversations with automatic state persistence in Redis via session ID keys.
  * Native integration with standard LangChain tools and Google's SDK (`langchain-google-genai`).
  * Simplifies testing and debugging of conversation paths.
* **Bad:**
  * Steeper learning curve for developers unfamiliar with the LangGraph state machine model (nodes, edges, compiled state).
  * Network overhead of calling the external Gemini LLM APIs during agent loops.

## Pros and Cons of the Options

### Option 1: Custom Session Handlers and Raw Prompts

* **Good:** Minimal dependencies, no framework overhead.
* **Bad:** High complexity to write and maintain session loaders, custom condition checks, and error handling for multi-agent loops.

### Option 3: Linear Agent Orchestration

* **Good:** Simple sequential chains.
* **Bad:** Incapable of looping back (e.g., re-asking details if symptoms are unclear) or cleanly routing to different endpoints dynamically (e.g., immediate emergency redirect).
