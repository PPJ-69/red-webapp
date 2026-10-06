Claude Incremental Web App Build Playbook
A reusable process for turning requirements into architecture, an implementation manifest, and a working project in bounded LLM chunks.
Purpose: Use this playbook to avoid asking Claude to generate an entire web application in one response. The process creates a stable architecture, decomposes the work into small implementation chunks, keeps project state in repository files, and makes it easy to resume in a new conversation.
# 1. Core Strategy
Requirements
    ↓
Architecture
    ↓
Component Trees
    ↓
5–7 Milestones
    ↓
Implementation Manifest
    ↓
Project Skeleton
    ↓
One Chunk at a Time
    ↓
Tests + State + Handoff
    ↓
Milestone Review
    ↓
Next Milestone
    ↓
Release
The key rule: architecture is created once; implementation is decomposed into bounded chunks; Claude is instructed to implement exactly one chunk at a time.
# 2. Create These Project-Control Files
REQUIREMENTS.md — authoritative product requirements.
ARCHITECTURE.md — approved high-level architecture and boundaries.
IMPLEMENTATION_PLAN.md — milestone/chunk manifest.
PROJECT_STATE.md — current implementation state and checkpoint.
DECISIONS.md — durable architecture decisions that should not be silently changed.
Keep these files at the repository root unless there is a strong reason not to.
# 3. Step 1 — Requirements → Architecture
Do not request source code yet. Give Claude the requirements and ask only for architecture.
## Prompt A — Architecture
You are a senior software architect reviewing a product requirements document for a new web application.

Read the requirements document completely before responding. The requirements document is the product source of truth.

Produce a high-level system architecture and implementation roadmap.

Do NOT write implementation code.
Do NOT redesign the product or add major features.
Where a detail is unspecified, make a reasonable recommendation and label it Architectural Inference.

Return, in this exact order:
1. Architecture Summary
2. Requirements → Architecture Implications
3. High-Level System Architecture Map
4. Runtime Data Flow
5. Frontend Component Tree
6. Backend Component Tree
7. Frontend/Backend API Boundary
8. State Ownership Map
9. Security & Privacy Boundaries
10. External Integration Architecture
11. 5–7 Development Milestones
12. Milestone Dependency Graph
13. Architecture Decision Summary
14. Open Architectural Questions
15. Recommended Implementation Order

Use Mermaid for diagrams.

Distinguish Requirement, Architectural Inference, and Open Decision.

Favor clear boundaries, minimal coupling, explicit APIs, testability, privacy/security by design, incremental development, replaceable external integrations, and simple infrastructure.

Do not generate source code, detailed implementation tickets, engineering-hour estimates, or unnecessary database schemas.

Now read the attached requirements document and produce the architecture.
Save Claude's response as ARCHITECTURE.md. Review only decisions that could materially affect implementation.
# 4. Step 2 — Architecture → Implementation Manifest
## Prompt B — Implementation Manifest
Using REQUIREMENTS.md and ARCHITECTURE.md as the source of truth, create an incremental implementation manifest.

Do NOT write implementation code.

Break the project into 5–7 logical, self-contained milestones. Prefer 6 unless the architecture strongly suggests otherwise.

Within each milestone, create coherent implementation chunks. A chunk should normally be small enough to implement and review in one LLM response.

For every chunk provide:
- Chunk ID: M1-C01, M1-C02, etc.
- Milestone
- Name
- Purpose
- Files to create
- Files to modify
- Dependencies
- Interfaces/API contracts introduced
- Tests required
- Acceptance criteria
- Explicit out-of-scope items

Rules:
1. Each chunk must produce a meaningful, testable increment.
2. Put technically risky foundations early.
3. Avoid artificial chunks for trivial folder creation or renaming.
4. Minimize cross-milestone dependencies.
5. Do not invent product requirements.
6. Identify independent chunks and the critical path.
7. Identify technically risky chunks that should be validated early.

End with a PROJECT MANIFEST showing every milestone and chunk.

Do not write source code.
Save the result as IMPLEMENTATION_PLAN.md.
# 5. Step 3 — Initialize Project State
## Prompt C — Initial State
Create PROJECT_STATE.md using REQUIREMENTS.md, ARCHITECTURE.md, and IMPLEMENTATION_PLAN.md.

Include:
# Project State
## Architecture Version
## Current Milestone
## Current Chunk
## Completed Chunks
## Upcoming Chunks
## Important Architecture Decisions
## Known Issues
## Tests
## Open Decisions
## Last Handoff

The project has not yet been implemented. Set the current chunk to the first implementation chunk.

Keep this concise. It is a checkpoint, not a duplicate of the architecture or requirements.
Create DECISIONS.md as an initially empty or short decision log if it does not already exist.
# 6. Step 4 — Start the Coding Conversation
Use a separate coding conversation when practical. Give Claude the repository plus REQUIREMENTS.md, ARCHITECTURE.md, IMPLEMENTATION_PLAN.md, PROJECT_STATE.md, and DECISIONS.md.
## Prompt D — Persistent Coding Rules
# Project Implementation Rules

Source of truth:
- REQUIREMENTS.md = product requirements
- ARCHITECTURE.md = approved architecture
- IMPLEMENTATION_PLAN.md = approved implementation chunks
- PROJECT_STATE.md = current implementation state
- DECISIONS.md = durable decisions

Rules:
1. Implement only the requested chunk.
2. Never implement future chunks unless explicitly instructed.
3. Do not silently change the architecture.
4. Do not invent product requirements.
5. Do not refactor unrelated code.
6. Keep existing tests passing.
7. Add tests for new behavior.
8. Preserve public interfaces unless the current chunk changes them.
9. Prefer the smallest implementation that satisfies requirements.
10. Avoid speculative abstractions.
11. Update PROJECT_STATE.md after each chunk.
12. Record durable architectural decisions in DECISIONS.md.
13. Report architectural conflicts instead of silently resolving them.
14. End every chunk with a concise handoff.
15. Never dump the entire project unless explicitly requested.
16. Do not implement future functionality merely because it is easy.
17. If code conflicts with requirements, report the conflict instead of silently choosing.

Keep responses focused on the current chunk. Prioritize working code and tests over long explanations.
# 7. Step 5 — Implement Exactly One Chunk
## Prompt E — One Chunk
Implement exactly this project chunk:

[CHUNK ID] — [CHUNK NAME]

Use REQUIREMENTS.md, ARCHITECTURE.md, IMPLEMENTATION_PLAN.md, and PROJECT_STATE.md as the source of truth.

Before changing code:
1. Briefly state what this chunk adds.
2. Identify files to create or modify.
3. Mention any blocking dependency or architectural concern.

Then implement ONLY this chunk.

Requirements:
- Preserve the approved architecture.
- Do not implement future chunks.
- Do not invent features.
- Do not refactor unrelated code.
- Keep the project runnable.
- Add/update required tests.
- Make only necessary compatibility changes.

If an architectural problem prevents implementation, STOP and explain the conflict instead of silently redesigning the system.

At the end provide:
1. Files created/modified
2. Functionality implemented
3. Tests added/updated
4. Test results
5. Acceptance criteria status
6. PROJECT_STATE.md changes
7. Concise handoff for the next chunk

Do not repeat the full architecture or requirements.
Use this prompt repeatedly, changing only the chunk ID/name.
# 8. Step 6 — Keep Chunks Bounded
A chunk should represent a coherent capability, not an arbitrary number of lines.
Roughly 1–5 meaningful files is a useful starting point, but engineering judgment wins.
If a chunk becomes too large, stop and split it before continuing.
Do not let Claude implement later chunks 'while it is already in that area.'
Use repository editing tools when available so large source files do not need to be printed into chat.
# 9. Step 7 — Test, Save State, Commit
Run relevant unit/integration tests.
Run the application if runtime behavior changed.
Verify the chunk's acceptance criteria.
Update PROJECT_STATE.md.
Record durable decisions in DECISIONS.md.
Commit the working state to Git when practical.
A useful convention is one Git commit per coherent implementation chunk or tightly related group of chunks. This creates easy recovery points.
# 10. Step 8 — Milestone Review
## Prompt F — Milestone Review
Review the completed milestone against REQUIREMENTS.md, ARCHITECTURE.md, and IMPLEMENTATION_PLAN.md.

Milestone:
[MILESTONE ID] — [MILESTONE NAME]

Do NOT rewrite code yet.

Check:
1. Are all acceptance criteria satisfied?
2. Are all milestone chunks complete?
3. Are requirements missing or partial?
4. Has architecture drift occurred?
5. Are frontend/backend boundaries correct?
6. Is state owned by the correct layer?
7. Are security/privacy requirements satisfied?
8. Are there unnecessary abstractions?
9. Are bugs or technical debt blocking the next milestone?
10. Does the next milestone still have correct dependencies?

Return:
- PASS / NEEDS CORRECTION for each category
- Specific findings
- Required corrections
- Optional improvements that can wait
- Whether the next milestone can begin

Do not introduce new product features.
Fix required corrections before beginning the next milestone.
# 11. Step 9 — Architecture Drift Review
## Prompt G — Drift Review
Perform an architecture drift review of the current project.

Read:
- REQUIREMENTS.md
- ARCHITECTURE.md
- IMPLEMENTATION_PLAN.md
- PROJECT_STATE.md
- DECISIONS.md
- current source tree

Do not rewrite code.

Identify:
1. Missing or partial requirements.
2. Components with responsibilities outside their intended boundary.
3. Duplicated frontend/backend business logic.
4. Provider-specific logic leaking into application services.
5. State stored in the wrong place.
6. Weakened security/privacy boundaries.
7. Unnecessary abstractions or infrastructure.
8. Documentation/code inconsistencies.
9. Missing tests for important behavior.
10. Undocumented architecture changes.

Classify findings Critical, Important, or Minor.

Provide a correction plan ordered by importance.
Do not recommend new product features.
Use this after major milestones rather than after every tiny change.
# 12. Step 10 — Conversation Checkpoint
When a Claude conversation becomes long, do not force it to carry the entire history. Create a compact checkpoint and start a fresh conversation.
## Prompt H — Checkpoint
Create a compact checkpoint for continuing this project in a new conversation.

Return:
PROJECT:
<one sentence>

ARCHITECTURE:
<5–10 bullets containing only important boundaries>

COMPLETED:
<completed milestones/chunks>

CURRENT:
<current chunk>

NEXT:
<next chunk>

IMPORTANT DECISIONS:
<durable decisions>

KNOWN ISSUES:
<unresolved issues>

TEST STATUS:
<current status>

FILES MOST RELEVANT TO NEXT CHUNK:
<list>

Do not reproduce source code, the full requirements, or the full architecture.
PROJECT_STATE.md should remain the canonical repository state; the checkpoint is a convenience for conversation transfer.
# 13. Step 11 — Start a Fresh Claude Conversation
You are continuing an existing software project.

Read these project documents first:
1. REQUIREMENTS.md
2. ARCHITECTURE.md
3. IMPLEMENTATION_PLAN.md
4. PROJECT_STATE.md
5. DECISIONS.md

Then inspect the current source tree.

Do not redesign the architecture.
Do not re-plan completed work.

Confirm:
- current milestone
- current chunk
- next chunk
- important constraints

Then wait for the implementation instruction.
If the repository is available to Claude, the repository files should carry most of the context. Avoid pasting long previous conversations.
# 14. Step 12 — Recovery If Claude Runs Out of Messages
If a conversation ends before implementation is finished, do not restart the project. The repository and control files should contain the project's durable state.
Confirm the latest code is saved.
Confirm PROJECT_STATE.md was updated after the last completed chunk.
Confirm the latest Git commit or working tree state.
Start a new Claude conversation.
Provide the five project-control files and the repository.
Use the fresh-conversation prompt above.
Resume with the current chunk or next chunk.
# 15. Avoid These Requests
Build the entire application.
Generate every file.
Implement all milestones.
Paste the entire repository.
While you're there, implement the next features too.
Rewrite the architecture because one feature is inconvenient.
Wait until the end to test everything.
Each of these encourages large outputs, architectural drift, or difficult recovery.
# 16. Recommended Repository Layout
project/
├── REQUIREMENTS.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── PROJECT_STATE.md
├── DECISIONS.md
├── README.md
├── frontend/
├── backend/
├── tests/
└── application files
# 17. Example Milestone/Chunk Structure
M1 — Foundation
├── M1-C01 Project skeleton
├── M1-C02 Configuration
├── M1-C03 Shared models
├── M1-C04 Provider interface
└── M1-C05 Basic API/health check

M2 — External Provider
├── M2-C01 Provider authentication
├── M2-C02 Provider client
├── M2-C03 Response normalization
├── M2-C04 Search
└── M2-C05 Media resolution

M3 — Streaming / Playback
├── M3-C01 Stream endpoint
├── M3-C02 HTTP Range handling
├── M3-C03 Native player
├── M3-C04 Player controls
└── M3-C05 Retry/error handling

M4 — Discovery UI
├── M4-C01 Search UI
├── M4-C02 Result grid
├── M4-C03 Pagination/infinite scrolling
├── M4-C04 Creator/tag views
└── M4-C05 Navigation

M5 — Session Features
├── M5-C01 Favorites
├── M5-C02 Viewed state
├── M5-C03 Session state
└── M5-C04 Settings

M6 — Security / Hardening
├── M6-C01 Security headers
├── M6-C02 Input/SSRF protection
├── M6-C03 Rate limiting
├── M6-C04 Privacy validation
└── M6-C05 Observability/error handling

M7 — Release
├── M7-C01 Integration tests
├── M7-C02 Performance tests
├── M7-C03 Deployment
└── M7-C04 Final acceptance
This is an example of granularity, not a fixed plan. Claude should derive the actual chunks from the requirements.
# 18. Exact Operating Sequence
PHASE 1 — ARCHITECTURE
1. Prepare REQUIREMENTS.md.
2. Run Prompt A.
3. Save ARCHITECTURE.md.
4. Review only architecture-changing open questions.

PHASE 2 — PLANNING
5. Run Prompt B.
6. Save IMPLEMENTATION_PLAN.md.
7. Run Prompt C.
8. Create/update DECISIONS.md.

PHASE 3 — IMPLEMENTATION
9. Start coding conversation.
10. Give Prompt D.
11. Implement M1-C01 with Prompt E.
12. Test.
13. Update state.
14. Commit.
15. Implement M1-C02.
16. Repeat.

PHASE 4 — MILESTONES
17. Complete all chunks in M1.
18. Run Prompt F.
19. Fix required corrections.
20. Continue to M2.
21. Repeat.

PHASE 5 — REVIEW
22. Run Prompt G after major milestones.
23. Correct important drift.

PHASE 6 — RECOVERY/CONTEXT
24. When conversation becomes large, run Prompt H.
25. Start a fresh conversation with the project-control files.
26. Continue the current/next chunk.

PHASE 7 — RELEASE
27. Run the full test suite.
28. Run security/privacy checks.
29. Run integration/end-to-end tests.
30. Verify every milestone acceptance criterion.
31. Perform final requirements-vs-implementation review.
32. Prepare deployment/release documentation.
# 19. Applying This to the Current Stream-First Media Browser
For the requirements document already prepared for this project, use the same workflow rather than hard-coding the architecture into the implementation prompts.
First obtain ARCHITECTURE.md from the requirements.
Then obtain IMPLEMENTATION_PLAN.md from the architecture.
Validate the provider integration and media-resolution/streaming path early because it is a technically risky core capability.
Do not spend a large amount of LLM output implementing the complete UI before the core media path is proven.
Build the player and streaming behavior incrementally.
Add discovery/search UI after the underlying data and media interfaces are stable.
Add session/privacy/hardening features as bounded milestones.
Finish with integration, privacy, security, performance, and acceptance testing.
# 20. Final Principle
PLAN ONCE
   ↓
DECOMPOSE ONCE
   ↓
IMPLEMENT ONE CHUNK
   ↓
TEST
   ↓
SAVE STATE
   ↓
COMMIT
   ↓
REPEAT
If a response is getting too large, stop at the current coherent boundary, save the state, and continue with the next bounded chunk. The objective is not to minimize the number of Claude messages at any cost; it is to maximize useful implementation per message while keeping the project recoverable.
