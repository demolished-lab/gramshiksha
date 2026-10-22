# GramShiksha Study Studio

A native study workspace that turns GramShiksha's own courses, lessons, textbooks
and revision materials into research notebooks, study packs, flashcards, quizzes
and a Socratic tutor — without sending learners to a third-party tab.

## The short answer about `mcp-anything`

[`gabrielekarra/mcp-anything`](https://github.com/gabrielekarra/mcp-anything) is a
**generator for MCP servers**. It turns an OpenAPI spec, a codebase or a written
brief into a server that exposes tools to an MCP-capable agent. It does **not**
wrap an arbitrary website, and NotebookLM is not an MCP server.

NotebookLM (now Gemini Notebook) has:

| Route | Cost | Status |
|---|---|---|
| Official Gemini Notebook Enterprise API | Paid Google Cloud Enterprise licences | Not compatible with the no-spend rule |
| Unofficial `notebooklm-py` / browser automation | Free, but uses undocumented APIs and Google cookies | Fragile and against Google's terms; only safe as a private, user-controlled authoring worker |
| Native GramShiksha generation | Free tier / our own content | Works today, no third-party redirect |

So the correct architecture is **not** "make NotebookLM native". It is:

> Build a native GramShiksha Studio, and make NotebookLM one optional
> *authoring backend* behind it.

Students never see NotebookLM. They see GramShiksha pages, GramShiksha citations
and GramShiksha downloads.

## Product shape

`/studio` is a signed-in workspace with four tabs:

1. **Sources** — pick a course, lesson, textbook chapter or uploaded PDF. The
   source list is scoped to the learner's class/board or the teacher's school.
2. **Notebook** — a named research project with a short brief, key concepts and
   internal citations.
3. **Create** — study guide, flashcards, quiz, mind map, revision checklist,
   audio script, parent summary, or a lesson plan. Every generated asset can be
   previewed and published back into a course.
4. **Ask** — a Socratic tutor chat grounded in the selected sources. Answers
   cite internal lesson IDs and never link out to a third-party result page.

Every button has a real state: loading, empty, retry, permission-denied,
quota-reached, published and offline-cached.

## Architecture

```
frontend /studio
        │
backend /studio/*  (FastAPI, auth + quotas + moderation)
        │
        ├── native generator (deterministic, no external key)
        ├── optional provider adapter ── OpenRouter / Gemini / other free model
        └── optional NotebookLM worker ── teacher-only, explicit consent
        │
Postgres (notebooks, sources, artifacts, jobs)
Cloudinary (generated PDFs, audio, images)
```

The frontend only calls GramShiksha endpoints. Generated artifacts are stored in
GramShiksha storage and rendered by GramShiksha components. There are no iframes,
no redirects and no third-party result pages in the student flow.

### MCP layer

`mcp-anything` can generate a **GramShiksha MCP server** from our FastAPI OpenAPI
schema. That is useful for trusted agents and teachers:

- `list_courses`, `get_lesson`, `search_content`
- `create_study_pack`, `generate_quiz`, `publish_material`
- `get_class_progress`, `list_unanswered_doubts`

It is an automation surface for our own API, not a NotebookLM bridge.

### NotebookLM adapter (optional, teacher-only)

If the account owner explicitly wants it, a private worker can:

1. Create a notebook from GramShiksha lesson text.
2. Ask NotebookLM for a study guide, quiz, flashcards or audio script.
3. Download the artifact.
4. Moderate it.
5. Upload it to Cloudinary and publish it as a GramShiksha material.

Rules for that worker:

- It is triggered manually by an admin/teacher, never by an anonymous student.
- Google cookies live in an encrypted secret store, never in the repo or browser
  localStorage.
- No student names, emails, phone numbers or doubts are sent to Google.
- The generated asset is labelled "AI-assisted" and carries source citations.
- If Google changes the undocumented API, the worker fails closed and the native
  generator remains available.
- It is disabled by default until the owner re-authenticates and accepts the
  terms-of-service risk.

## Creative feature backlog

### MVP — native, no external key

- **Study Pack**: key concepts, 5 flashcards, 5-question quiz, revision checklist.
- **Explain like a village teacher**: plain-language explanation plus a local
  example, in English/Hindi/Marathi.
- **Doubt → notebook**: turn an unanswered doubt into a source note for a teacher.
- **Offline pack**: cache the pack in the service worker so it opens without data.
- **Teacher planner**: one-week plan from the selected lesson and class timetable.
- **Parent digest**: a short weekly summary of completed lessons and one practice
  suggestion.

### Next — provider adapter

- Socratic tutor that asks one question at a time and never gives the answer first.
- Bilingual audio script and downloadable MP3/PDF.
- Mind map rendered as a native SVG tree, not an image from another site.
- Quiz generator with difficulty levels and explanations.
- "Weak topic rescue" pack assembled from the learner's progress history.
- Teacher moderation queue for AI-generated assets.

### Later — optional NotebookLM worker

- Deep research report from multiple GramShiksha sources.
- Audio Overview script adapted to the local syllabus.
- Mind map and slide outline imported as native assets.
- Multi-source comparison for Classes 11–12.

## Guardrails

- Free tier only. No paid API, domain or hosting is required for the MVP.
- No student PII leaves GramShiksha.
- No scraped copyrighted textbook content is republished.
- AI output is always editable, moderated and labelled; it is never presented as
  an official government textbook.
- Rate limits and per-role quotas protect the free backend.
- If a provider is unavailable, the native generator is the fallback, not an
  error page.

## First implementation slice

1. Add a `studio` router with `GET /studio/sources` and
   `POST /studio/packs` using the native generator.
2. Add `/studio` with Sources, Notebook and Create tabs.
3. Publish a generated pack as a normal GramShiksha material.
4. Add the provider adapter interface and a disabled NotebookLM worker stub.
5. Add tests for permissions, quotas, citations and offline caching.

No Google login is required for this slice.
