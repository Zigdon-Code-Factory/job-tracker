# Job Tracker — Current-State Specification

Verified: 2026-10-28. Implementation baseline: commit 2622838.

This describes the application that exists, not a proposed redesign. Source of truth: index.html, server.py, and the tracked JSON dataset. Deployment outside this repository and browser interactions have not been independently verified for this document.

## 1. Purpose and scope

A personal, single-user job-application tracker for organizing opportunities on a Kanban board, recording application metadata and resume variants, and retaining a timeline of status changes. It is personalized to Zack Higdon through the page title and a hardcoded skill list.

The app does not apply to jobs, scrape postings, send email, read inboxes, generate resumes, or integrate directly with Discord or an ATS. Assistant-driven updates are external operational activity, not application features. A URL alone is not evidence of an application; the normal Add Job flow defaults to Saved, although users and API callers may explicitly select another status.

## 2. Architecture and repository

- **Frontend:** one self-contained index.html with inline CSS and vanilla JavaScript. No frontend framework, package manager, external JS/CSS dependencies, or build step.
- **Backend:** server.py, Python standard library only; ThreadingHTTPServer and SimpleHTTPRequestHandler. Server version string: JobTracker/1.0.
- **Authoritative server storage:** data/jobs.json, a JSON array. No relational database or ORM.
- **Browser storage:** localStorage under the key zack-job-tracker, used as a local copy/fallback.
- **Git:** master branch; origin is Zigdon-Code-Factory/job-tracker. The dataset is tracked despite data/ being listed in .gitignore. __pycache__/ and *.pyc are ignored.
- **No checked-in:** deployment manifest, service unit, container definition, CI configuration, dependency lockfile, or automated test suite at the implementation baseline.

Request flow: browser loads HTML → GET /api/jobs → reconcile missing browser IDs → render board. A user mutation updates in-memory state and localStorage, then PUTs the entire collection to the server.

## 3. User interface

### Board

Six fixed columns, in this order:
1. Saved (saved)
2. Applied (applied)
3. Interviewing (interviewing)
4. Offered (offered)
5. Rejected (rejected)
6. Ghosted (ghosted)

Each column has an icon, color, filtered record count, drop zone, and Add button. The global Add Job button defaults to Saved; a column's Add button defaults to that column's status. Status transitions are unrestricted: any column may move to any other column. There is no enforced application state machine or automatic ghosting timer.

Cards show company, title, optional posting link, salary, location, resume label/path, contact, skill tags, match bar, clipped notes, date added, and a priority dot. They show up to five tags plus an additional-count badge. If history has more than one entry, the last three entries appear in a compact preview. Hover actions offer Edit and Delete. Clicking a card opens its detail modal.

### Search, filtering, and sorting

- Case-insensitive substring search across company, title, and individual tags only. Notes, contact, source, location, and resume are not searched.
- Activity filter: all jobs or last 7, 30, 60, or 90 days.
- Last activity is the date of the final history entry, falling back to dateAdded, then 1970-01-01. It is not the maximum date across history and is not updated by ordinary field edits.
- High-priority jobs sort first; remaining order is dateAdded descending. Medium does not explicitly sort ahead of Low.
- Filtering changes column counts. Filters are in-memory and reset on reload.
- There is no pagination, manual within-column ordering, table view, analytics dashboard, or bulk selection.

### Create/edit

Fields: company, job title, URL, location, salary, status, priority, resume used, contact/recruiter, source, comma-separated skills/tags, notes, and date added.

Company and title must be nonempty after trimming. Other inputs are largely free text. New records receive a browser-generated ID combining the current timestamp in base 36 with a short random suffix, and are prepended to the array. New history starts with the selected status, dateAdded, and note Created.

Editing retains the same ID and existing history. Changing status prompts for an optional transition note and appends a history entry with the previous status. Other field edits do not create audit entries. Changing dateAdded does not rewrite prior history. There is no history editor or resume-file upload; resume is just a string.

### Drag and drop / delete

Dragging to a different column changes status and prompts for a note; the history entry records status, current date, note, and from. Dropping into the existing status does nothing. Canceling the note prompt does NOT cancel the move: it records an empty note.

Delete uses a browser confirmation dialog and removes the record from the collection. No soft deletion, archive state, undo, or tombstone exists.

### Detail view

Displays status, priority, location, salary, resume, contact, source, skill match, all tags, notes, and complete status history in stored order. The final entry is visually marked current. Durations use the rounded absolute difference between date values. Total tracking time measures the first to last history dates, not time through today. It is not an interview scheduling interface.

### Presentation and accessibility

Dark theme; horizontally scrolling board. Columns are 300px wide, reduced to 260px at viewport widths of 768px or less; search shrinks from 220px to 160px. Modal content scrolls at up to 90vh. The application uses native drag/drop and browser prompt/confirm/alert dialogs. Focus trapping, Escape dismissal, comprehensive ARIA semantics, and keyboard drag/drop are not implemented. Modals can be closed by clicking the backdrop; detail also has a close button and edit has Cancel.

## 4. Data model

Every normalized job contains:

| Field | Representation / behavior |
|---|---|
| id | String; supplied or generated; identity for updates and browser merging |
| company | Required trimmed string; employer alias accepted |
| title | Required trimmed string; jobTitle alias accepted |
| url | String; link alias accepted |
| location | Free-text string |
| salary | Free-text string, not a numeric compensation range |
| status | saved, applied, interviewing, offered, rejected, or ghosted |
| priority | high, medium, or low; defaults to medium |
| resume | Free-text label/path; resumeUsed alias accepted |
| contact | Free-text contact details; recruiter alias accepted |
| source | Free-text origin, e.g. Lever or Greenhouse |
| tags | Array of strings; skills alias accepted; string input split on commas/newlines |
| notes | Free-text string |
| dateAdded | Date-like string, intended YYYY-MM-DD; date alias accepted |
| history | Array of status-event objects |

History entries generally contain status, date, note, and optionally from. The backend accepts any list as history without validating its elements. Missing/non-list history receives a single Created via API entry. An empty history list remains empty.

API normalization trims common strings, lowercases status/priority, defaults unknown statuses to saved and unknown priorities to medium, and truncates dateAdded to ten characters. It does not validate calendar dates, URL protocols, uniqueness, or consistency between current status and the last history entry. Unknown top-level job fields are discarded by normalization.

If no ID is supplied, the backend takes the first 12 hexadecimal characters of SHA-1 of lowercase company|title|url. This differs from browser IDs. Identity is not a reliable semantic duplicate detector: different URLs or explicit IDs can represent the same role.

Client dates use UTC ISO dates; backend defaults use the host's local date. Around midnight these may differ.

## 5. Skill matching

The frontend has a fixed list of 28 skills: AWS, Azure, Terraform, Kubernetes, Docker, Helm, ArgoCD, Grafana, Kibana, ECS, Spacelift, GitHub Actions, GitLab CI, Bash, PowerShell, MySQL, MSSQL, Linux, DevOps, CI/CD, Infrastructure as Code, Monitoring, Containerization, Cloud Migration, Proxmox, Tailscale, LXC, YAML.

For each configured skill, it checks whether any job tag contains that skill or vice versa, case-insensitively. Score = rounded matched configured skills / number of job tags × 100, capped at 100. Empty tags score zero. Green is 70+; yellow is 40–69; otherwise red.

This is a substring heuristic, not an AI assessment or qualification probability. A single broad tag can match several configured skills and inflate the score. There is no weighting, synonym normalization, experience-level assessment, or editable skills profile.

## 6. HTTP API

JSON requests use Content-Type: application/json. No authentication is required by this server.

### GET /api/jobs
Returns HTTP 200 and the entire stored job array. Missing, unreadable, malformed, or non-array storage is treated as an empty array rather than reported as an error.

### PUT /api/jobs
Accepts an array, normalizes every item, and replaces the entire stored dataset. Returns 200 with {"ok":true,"count":N}. Invalid payload or processing errors return 400 with {"ok":false,"error":"..."}. There is no merge, revision check, or automatically appended transition history.

The UI implements deletion through this replacement operation. There is no DELETE endpoint or per-record GET/PATCH endpoint.

### POST /api/jobs and POST /api/import
Equivalent upsert handlers. Accept a single job, an array, or {"jobs":[...]}. Match existing records by ID only. New records are inserted at the front. Existing records are replaced with normalized incoming fields, retaining old nonempty history; this is not a partial field merge. Omitted fields can reset to defaults and a changed status does not automatically append history.

Success: 200 with ok, added, updated, and count. Errors: 400 with ok:false and error. The existing-ID map is created before processing and is not maintained during the batch: repeated IDs inside one incoming batch can create duplicates or produce update errors. Batch callers should ensure unique IDs.

### OPTIONS and static routes
OPTIONS responds 204. All responses include wildcard CORS origin, methods GET/POST/PUT/OPTIONS, and allowed header Content-Type. Unsupported PUT/POST routes return 404. GET / serves index.html; other GET paths are passed to the static-file handler rooted at the repository.

## 7. Persistence and consistency

Server writes serialize the whole array as indented, key-sorted JSON to data/jobs.json.tmp and replace jobs.json. This reduces partial-file replacement risk but is not a transaction or concurrency-control mechanism. Threaded requests share a fixed temporary filename without locking, so simultaneous writes may race or overwrite changes.

At browser startup, the API is loaded and any localStorage IDs absent from the API are appended and saved. For IDs present in both, server records win. On API failure the browser falls back to its local array. Browser-only merging is not conflict resolution: stale local records can resurrect server-deleted jobs.

On save, localStorage is written first, then a whole-array PUT is attempted. Network failures log a console warning; HTTP error status is not checked. There is no visible saved/offline indicator, automatic retry queue, revision token, polling, WebSocket, or cross-tab synchronization. Concurrent tabs can overwrite one another. Successful API reads without a merge do not refresh localStorage. Malformed localStorage JSON is parsed before the API try/catch and can stop loading.

## 8. Running and operating

Run python3 server.py from a suitable Python environment. Default bind: 0.0.0.0:8787. HOST overrides the bind address. PORT overrides the port; absent PORT, the first positional argument overrides 8787. Paths are based on server.py's directory, not the caller's working directory.

For loopback-only operation: HOST=127.0.0.1 python3 server.py. No TLS termination is implemented. This document does not assert a currently running service, public URL, proxy, or configured authentication layer.

Backups and restoration are external: the tracked dataset can be recovered from Git history, but the application never commits or pushes changes automatically. Browser-local unsynced records are not included in repository backups.

## 9. Security and reliability limitations

This is a trusted personal-network tool, not a hardened public multi-user service:

- No authentication, authorization, accounts, rate limits, request-size limit, or audit actor identity.
- Wildcard CORS and unauthenticated whole-dataset writes expose data and mutation endpoints to any client that can reach the service.
- Static serving is broad: repository contents, including data and potentially .git paths, are not explicitly denied. Path containment uses a string-prefix check rather than a robust relative-path check.
- HTML rendering does not safely escape all attribute/inline-JavaScript contexts; IDs, tags input, some dates/status fields, and URLs need particular care. URL schemes are not constrained. Treat imported content as trusted until hardened.
- Read errors silently become an empty dataset, creating a potential subsequent overwrite risk.
- No transaction isolation, schema migration framework, history immutability, or semantic deduplication.
- UI re-renders the whole app on search input, which may disrupt input focus; browser behavior was not exercised in this review.

These are observed implementation limitations, not features added as part of writing this spec.

## 10. Data snapshot and verification scope

At inspection: 104 records, 104 unique IDs: 61 applied, 40 rejected, 1 interviewing, 2 saved, 0 offered, 0 ghosted. These are current retained records, not an all-time application count; deleted records survive only in prior Git history unless restored elsewhere.

Verification for this documentation task: full source inspection; Python syntax and JSON parsing; unique-ID and status-count checks; isolated temporary-storage API smoke checks; frontend JavaScript syntax check; Git remote synchronization checks. No production dataset mutations or application-feature changes are intended. Browser interaction/end-to-end verification and production deployment validation are outside this inspection.
