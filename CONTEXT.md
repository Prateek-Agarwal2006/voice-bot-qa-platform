# Voice Bot QA Platform

A unified platform for measuring and evaluating voice bot quality from two complementary angles: (1) how fast the underlying LLMs respond across cloud regions, and (2) how well recorded customer–voice bot conversations actually went. Workers write results to a shared Postgres store; the Orchestrator serves a single React dashboard.

## Language

---

### Shared infrastructure

**Orchestrator**:
The single internal service that serves the API for both latency runs and evaluation jobs. It reads from the Black Box and accepts job submissions from the UI. It never calls workers directly — workers write to the Black Box independently. There is exactly one Orchestrator; it has no external exposure (ClusterIP only, proxied through the UI pod).
_Avoid_: server, controller, coordinator, master

**Black Box**:
Postgres — the shared persistent store that decouples workers from the Orchestrator. Workers write to it; the Orchestrator reads from it. They never communicate directly.

**Probe Worker**:
A deployed pod running the latency Probe in one Source Region. It triggers itself on a schedule (no inbound endpoint), executes each Run's Calls for its Collection Scope, and emits results through the Result Sink. Adding a Source Region means deploying one more Probe Worker.
_Avoid_: agent, node, runner

**Eval Worker**:
A deployed pod that polls the Black Box for pending Jobs and executes the eval pipeline: downloading audio, transcribing via ElevenLabs Scribe, building a Conversation, and scoring it with a Judge. Like the Probe Worker, it has no inbound endpoints — all connections are outbound.
_Avoid_: agent, node, runner, pipeline worker

**Result Sink**:
The path a Probe Worker uses to export finished atomic run rows to the Black Box. The worker does not call into the Orchestrator directly.
_Avoid_: exporter, uploader, publisher, drain

---

### Latency measurement

**Probe**:
The self-contained, location-agnostic logic that issues a Call to a target LLM endpoint and measures its latency. It knows nothing about where it runs — its deployment location is supplied as data.
_Avoid_: client, tester

**Source Region**:
The cloud region where a Probe physically runs — i.e. where a request originates from. Set per worker via `SOURCE_REGION` at deploy time. Recorded as a first-class field on every Sample.
_Avoid_: origin, from-region, location

**Target Region**:
The region hosting the LLM Endpoint being measured — i.e. where the request is sent to.
_Avoid_: destination, to-region

**Endpoint**:
The Sprinklr Gen AI Router URL used for real Calls. Set per deployment via `GEN_AI_ROUTER_URL` (Sprinklr supplies the value).
_Avoid_: URL, host, server

**Router request metadata**:
Sprinklr-specific fields on each Call: `provider`, `model`, `partnerId` (catalog, per model), and pod env `REQUEST_SRC_ENV`, `GEN_AI_CLIENT_IDENTIFIER`, `GEN_AI_ROUTER_URL`. Catalog entries use `??????` until Sprinklr fills them in.
_Avoid_: deployment name, api_base

**Production Environment**:
A named deployment stack (e.g. prod, prod2, prod4) with a specific cloud provider, region, and type (Production, FedRAMP, Self-serve). Maps to Probe Worker placement (source) and target region labels in the catalog.
_Avoid_: prod stack, deployment, cluster

**Model**:
A specific hosted LLM offering being measured (e.g. a named GPT, Claude, or Gemini deployment). Latency varies by Model independently of region because of differing size and current load. Distinct from a Judge — a Model is what is being measured, a Judge is what does the measuring.
_Avoid_: LLM, deployment

**Provider Adapter**:
The implementation behind a single common interface that the Probe uses to issue a Call and observe time-to-first-chunk. Production uses the **Gen AI Router adapter** (streaming `generateWithRequest`); kind sim uses a **Fake adapter** that simulates latency without credentials.
_Avoid_: connector, driver, integration

**Collection Scope**:
The work a single Probe Worker performs each cycle: which Models and which Target Regions it measures, and how often (interval). Supplied per worker through its environment at deploy time, not in the shared catalog.
_Avoid_: plan, config, schedule, matrix

**TTFB**:
Time To First Byte — the latency from sending a request until the first byte/token of the response is received. The primary metric. Requires a streaming request to observe.
_Avoid_: first-token-time, response time, TTFT

**Prompt**:
The fixed, standardized input text sent on every Call, chosen so Runs are comparable across Models and regions. Built in a single place in the Probe.
_Avoid_: input, message, query

**Call**:
A single request to one Endpoint that produces one TTFB observation. The smallest unit of latency measurement.
_Avoid_: request, attempt, hit, phone call

**Run**:
One scheduled collection cycle for a single Model from one Source Region, triggered by the Probe Worker itself on a configurable interval. It issues N Calls to each Target Region in the Collection Scope and emits one Sample per target through the Result Sink. A Run is the unit that gets stored and compared over time.
_Avoid_: test, job, batch, session, on-demand request

**Sample**:
The persisted result for one (Run, Model, Source Region, Target Region): the aggregate of that Run's N Calls (e.g. average TTFB, plus the underlying Calls). One Run produces one Sample per Target Region.
_Avoid_: measurement, record, datapoint, reading

---

### Call evaluation

**Recording**:
A single stereo audio file capturing one customer–voice bot conversation. Channel 0 = Customer, Channel 1 = Voice Bot.
_Avoid_: call, session (unless the conversation spans multiple connected recordings)

**Conversation**:
The structured representation of a Recording after transcription — turns, timestamps, and derived signals. Stored as an artifact after the transcription and structuring stages of the eval pipeline.
_Avoid_: transcript (when you mean the full structured artifact, not just the text)

**Turn**:
A contiguous block of speech by one party until the other party speaks.
_Avoid_: utterance, segment

**Derived Signals**:
Timing and interaction metrics computed from a Conversation's word timestamps — response latency, hesitation, dead air, interruptions. Not provided by the transcription service; computed in-platform.
_Avoid_: metrics (too broad), features (implementation jargon)

**Customer**:
The human caller in a Recording.
_Avoid_: user, caller

**Voice Bot**:
The automated agent handling the spoken conversation in a Recording.
_Avoid_: agent (ambiguous with human QA agents), assistant

**Evaluation**:
The scored output of running a Conversation through all dimensions using a Judge. Stored as an artifact after the evaluation stage of the eval pipeline.
_Avoid_: review, audit (unless referring to human QA workflow)

**Rubric**:
The version-controlled scoring criteria for one evaluation dimension, stored as a Markdown file. The Judge reads the rubric to generate evaluation steps and produce a score.
_Avoid_: prompt, criteria, scorecard

**Judge**:
The LLM instance used to score a Conversation against a Rubric. Distinct from a Model — a Judge measures quality, a Model has its latency measured. Selected at eval time via provider and model ID.
_Avoid_: evaluator, scorer, LLM (when the role is judging)

**Job**:
A unit of eval pipeline work tied to one Recording — from the moment it enters the system (via upload or URL) through to a completed Evaluation. A Job has a status (`pending → downloading → transcribing → structuring → evaluating → done | failed`) and is the unit the Eval Worker polls from the Black Box.
_Avoid_: task, request, run

**Ingestion Source**:
The origin type of a Recording's audio file — how it entered the system. Current values: `upload` (direct browser upload), `https` (URL fetch). Future: `s3`, `gcs`.
_Avoid_: provider (taken by LLM cloud vendor context), source

**Task Success**:
Whether the customer's goal for the call was achieved (e.g. booking confirmed, issue resolved, correct information delivered).
_Avoid_: task completion (too generic), resolution (ambiguous)

**Conversation Quality**:
How well the interaction flowed — turn-taking, conciseness, repetition, pacing, and naturalness — not whether the underlying task succeeded.
_Avoid_: UX, experience (too broad)

**Response Alignment**:
Whether the voice bot answers what the customer asked for — if the customer asks for X, the bot gives X, not unrelated information or a substitute Y.
_Avoid_: intent matching (too vague), answer correctness (use only when you mean factual accuracy alone)

**User Disappointment**:
Detected dissatisfaction, frustration, or negative sentiment from the customer during or by the end of the conversation.
_Avoid_: sentiment (too broad — includes neutral/positive), churn signal
