---
title: Jude as a plugin
layout: default
---

# Jude as a plugin: Claude Desktop, ChatGPT, Le Chat

*Written 19 October 2026 from the plugin design and revised 3 November
2026 against the second version of that design (one local server, three
tools, one local window) and against two research reports of 3 November
2026 on ChatGPT and on Mistral. Sections 1–8 describe what ships for
Claude Desktop. Sections 9 and 10 report what the other two assistants
would require, with a confidence label on every fact:
**verified-official** (read on the vendor's own page), **secondary**
(a third party), **inferred** (a conclusion drawn from the official
pages). Nothing in 9–10 has been tried.*

Contents: 1 What a plugin can and cannot filter · 2 The Claude Desktop
flow · 3 Eight invariants in plain words · 4 What never leaves, and what
the browser can still do · 5 Install · 6 The approval record, the audit
log and the local trace · 7 Limits and out of scope · 8 Troubleshooting ·
9 ChatGPT · 10 Mistral Le Chat (now Vibe) · 11 Browser extension
(future) · 12 Résumé en français.

---

## 1. What a plugin can and cannot filter

The model reads whatever the lawyer types in the chat box. Jude's gate
protects **documents** and **answers**; it never protects the prompt.
This is not a defect of Jude's plugin but of the shape of every plugin
to every assistant, and it is the first thing to know before installing.

A plugin to Claude Desktop, ChatGPT or Le Chat is an *MCP server* — a
small program on your machine (or on a server) that the assistant can
call, exposing a short list of named *tools*. The order of events is
fixed by the protocol: the lawyer types a message; the message goes to
the model; the model reads it and decides whether to call a tool; the
tool runs; its result goes back to the model. The plugin is called
*after* the message has been read. There is no hook before.

The plugin is therefore a *commis in the kitchen*, not a *doorman at the
door*. The commis prepares what the chef asks for — reads the file from
disk, redacts it, waits for your approval, hands over the approved text
— and never sees who walked into the restaurant. A doorman who checks
every sentence before it reaches the model would have to stand in the
chat box itself; a plugin cannot stand there (a browser extension could,
§11).

Consequence for daily use: **never type a client name, a matter name or
a file name in the chat box.** Say "analyse the memo I'll pick in Jude",
and choose the matter and the document in Jude's window. The tool
descriptions coach Claude to never ask you for either (§3, I8).

## 2. The Claude Desktop flow

Jude's plugin is one local process (`jude mcp`, started by Claude
Desktop over stdio, with no network) and one local browser tab (Jude's
window, served on `127.0.0.1` on a random port). Three tools:

| Tool | Arguments | Returns | What happens on your machine |
|---|---|---|---|
| `prepare_document` | none | `review_id`, `status`, `next` | Jude opens its window. Claude is told to send you there. |
| `fetch_approved` | `review_id`, `wait_seconds` (5–30) | `status`, and — once — `text`, `sha256`, `chars` | Jude releases the approved pseudonymized text, verified against its record, a single time. |
| `show_answer` | `review_id`, `text` | `{"status": "shown", "chars": n}` | Jude displays Claude's answer with the real names in its window. |

Every result is restricted to the keys `review_id`, `status`, `next`
(and `text`, `sha256`, `chars` on the one release). No matter name, no
file name, no path, no URL, no count of entities ever travels back to
the model. Errors are seven fixed sentences; nothing you typed or uploaded
is echoed into them. When the window already holds a review from
another conversation, `prepare_document` answers
`status: other_review_open` with a fixed hint and **no `review_id`**:
only the conversation that started a review ever holds its id.

The flow, step by step:

1. **You ask.** "Analyse the memorandum I'll pick in Jude." Claude
   calls `prepare_document` — no arguments, so there is nothing to get
   wrong.
2. **Jude opens its window.** A tab appears in your default browser,
   on a one-time link that immediately turns into a session cookie and
   a clean address (no token in the address bar, no name in the tab
   title — it says *Jude*). A tab left open from an earlier review
   wakes up by itself; if no tab opened, `jude mcp open` in a terminal
   opens one.
3. **You choose the matter** (most recently used first) and **the
   document** (`.txt`, `.md`, `.docx`, `.pdf`, `.xlsx`; up to 50 MiB
   and **150 000 characters**, about 50 pages — a longer document must
   be split in Word first). The file is read from your disk by Jude,
   never by Claude; the browser sends the bytes and the file's suffix,
   never its name, so the name does not even reach Jude's own process.
4. **Jude prepares**, offline, and the window says which phase it is in
   (*Reading the document*, *Loading the language models*, *Finding
   names and references*, *Preparing the text*): the readers run (rules,
   your matter's dictionary, spaCy for English, French and Dutch,
   GLiNER small), the text is pseudonymized with the matter's existing
   dictionary (`Org1` stays `Org1` across documents), and the temporary
   copy of the file is deleted before detection starts. Nothing is
   locked while the models load, so *Cancel* answers at once. In
   *smart* mode the public-knowledge tags come from the bundled dataset
   only; Wikipedia is never called (§7).
5. **You review** — the screen *What leaves your computer*:
   - warnings the reader raised: review comments, tracked changes, file
     properties, pages that are images without text — each with one
     sentence saying what was and was not read;
   - the counts (hidden → pseudonyms, kept visible, characters) and the
     languages seen (`fr 83 % · nl 17 %`);
   - a **risk block**: up to three re-identification signals
     (`● HIGH — Org1: …`, from Jude's heuristic risk score), a HIGH line
     when paragraphs are in a language Jude has no model for, and a
     HIGH line when the text contains characters that are invisible on
     screen (zero-width, direction or tag characters — they leave with
     the text; *Show them* renders each as `U+200B`). The block informs;
     it never blocks;
   - per entity, *Keep* (leave visible) and *Hide*, and a *Mark* row to
     hide a term Jude missed. A decision re-applies the stored spans;
     the readers never run twice. Keep on an entity first found in this
     review removes it from the matter at approval (the next document
     asks again); Keep on an entity the matter already knew lasts this
     turn only. Every decision changes the hash of the text, and the
     approval box unticks;
   - **the exact text that leaves, as Claude will read it**, with the
     pseudonyms highlighted, and a toggle *Show the original (stays
     here)* to read the two side by side. The hash and the approval
     always refer to the leaving text.
6. **You approve.** You tick *I have read the list and the text above.
   This exact text may be handed to Claude when Claude asks for it; the
   record is written on this computer first.* and press *Approve*. The
   page sends the SHA-256 of the text as displayed, and whether you
   scrolled the text to its end (recorded as `items_reviewed_text_read`
   rather than `items_reviewed_text_opened`); Jude compares the hash
   with the text it holds, under a lock, and refuses if they differ
   (another tab, a decision taken in between). Then, in **one database
   transaction**: the approval record (who, when, the hash, the counts),
   the confirmation of the entities this review created, the deletions
   the Keep decisions imply, and the audit lines. Only then does the
   review's status become `approved`. Closing the tab never approves;
   there is no timer that approves.
7. **You approve, then you tell Claude.** Approving is the consent, and
   the screen says what it means: *Once you approve, Claude can collect
   this exact text the moment it asks for it, once; you can withdraw
   here until it does.* The window shows the sentence to paste in the chat — *Approved in Jude.*
   — with a *Copy* button, and explains why: Claude cannot see the
   window; your message is what makes it ask. Until Claude collects,
   the button *Withdraw approval — possible until Claude collects*
   cancels the review; the withdrawal and the release are serialised,
   and the page says which side won (*Withdrawn. Nothing was shared.*
   or *Claude collected the text before you withdrew*). Why the manual
   step: a tool call cannot wait for a human. Claude Desktop's limit on
   how long a tool call may run is not published (the first install
   measures it, §8); so `prepare_document` returns at once and
   `fetch_approved` waits 30 seconds at most. Your message wakes
   Claude up.
8. **Claude collects.** `fetch_approved` returns the text and its hash
   — once, as a single text block (the result is not duplicated into a
   structured copy). Jude re-hashes the text against the approval row
   at the moment of release and refuses if anything changed. A second
   call returns `status: released` and no text. The approved text is
   held for **30 minutes** independent of the window, then the approval
   lapses and nothing leaves. The window then reads *Collected by Claude
   at 14:03* and its header changes from *Nothing has left your
   computer* to *One text has been handed to Claude. Record:
   approvals #12.*
9. **Claude answers in pseudonyms**, then calls `show_answer`. Jude's
   window shows the answer with the real names, in a frame labelled as
   the model's text, with a *Copy* button, a legend of the pseudonyms
   that appear in it and a warning on any pseudonym it does not know
   (`Org9` when the matter stops at `Org4`: the model guessed).
   Rehydration uses only the entities released in this review. The chat
   transcript keeps the pseudonyms.

Timers — the clock is yours, not the page's: a review closes after
**20 minutes without you** (a click, a key or a scroll in a visible tab;
the page's automatic refreshes do not count; a countdown appears under
five minutes), with an 8-hour ceiling; an approved text waits
**30 minutes** for Claude; both are settings (`jude mcp --idle-ttl
--approved-hold`). Expired, cancelled and failed reviews delete the
entities and the name variants they created and keep the ones the
matter had before. One review at a time before approval; at most five
approved texts held. A stop request (Claude Desktop quitting, a
SIGTERM) ends the server within 15 seconds whatever its threads are
doing: a running preparation gets 5 seconds, the window 5 seconds, and
a watchdog exits for any step that wedges; the next start sweeps the
entities a cut-off preparation created and closes a pending approval
as `lost_on_restart`.

## 3. Eight invariants in plain words

These are the properties the tests enforce (threat table in the design;
tests under `tests/test_mcp_*.py`). Each is stated as what it means for
you.

- **I1 — Nothing confidential reaches the model.** No matter name, file
  name, real name, path, window address or count in any tool argument,
  result, error message or log line. The tools have no `matter` or
  `path` parameter at all; there is no "list matters" tool. Error
  messages are fixed sentences. The server's error channel (what
  Claude Desktop writes in `mcp-server-jude.log`) is redirected at
  start into a trace file on your disk readable by you alone; the only
  thing that still reaches Desktop's log is a filtered line reduced to
  `<suppressed>` — so neither a library warning, nor a PDF reader's
  C-level message, nor a traceback can carry a fragment of a document
  there.
- **I2 — Two steps, with a record first.** Preparing and releasing are
  separate calls, so no tool blocks on a human. Approval is a click on
  the exact text (hash compared) with the attestation ticked; the record
  is written before the status changes; release is verified against the
  record and happens once; a withdrawal and a release cannot both win;
  every approval row ends with an `outcome` (§6), so the ledger always
  says what happened.
- **I3 — The window is hardened.** Loopback only, random port, one-time
  link that becomes a cookie (a `HEAD` request — a link checker, an
  antivirus — does not use the link up); without the cookie every
  address answers 404 with an empty body; the `Host` header must match
  exactly (no DNS rebinding); every request must come from the same
  origin (`Sec-Fetch-Site`) — a page served by another local program on
  another port, such as `jude ui` or a notebook, is refused — and every
  API call, reads included, needs a header only Jude's own page can
  set; a strict content-security policy with no inline code and no
  external resource; no `Server` header for a port scan to read; the
  tab title is always *Jude*; browser translation, spell-check,
  autofill and password managers are told to stay out by markup;
  uploads are read raw with a size cap and a suffix whitelist checked
  before the body. Closing the tab approves nothing.
- **I4 — Rehydration stays local and per matter.** `show_answer`
  returns a status and a count. The real names appear in the window
  only, restricted to the pseudonyms released in that review, with a
  400 000-character cap and a rate limit. No "dump the mapping" path
  exists.
- **I5 — Pseudonyms are stable for every text that left.** The
  dictionary grows only through approved reviews. A cancelled or
  expired review removes what it created — the new entities *and* the
  name variants it added to known ones — and nothing else; an entity
  created by a review the process did not live to finish is marked
  provisional and swept at the next start; a pseudonym number is
  allocated in one database transaction, so `jude mcp` and `jude ui`
  running at the same time cannot both issue `Org7`; counters never go
  backwards; a `Martin` the person and a `Martin SA` the company stay
  two pseudonyms.
- **I6 — No outbound network, and a tripwire.** Jude makes no network
  call by design; the guard catches regressions. The server runs with
  `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` and no telemetry; the
  Wikipedia provider is never constructed; a `netguard` installed
  *before any detector is imported* turns any `connect`, `sendto`,
  `sendmsg` or name lookup into an error before a packet leaves.
  Loopback (the window) is the only exception.
- **I7 — Clean protocol, bounded machine.** Standard output belongs to
  the protocol; spaCy, torch and progress bars cannot write to it.
  Models load in a worker and never under a lock, so the window and the
  tools stay responsive while a 50-page memo is read; a missing model
  for English, French or Dutch fails closed with a key
  (`models_missing`) that the window explains and `jude mcp doctor`
  fixes; paragraphs in a language Jude has no model for are flagged
  HIGH rather than silently under-read; texts over 150 000 characters
  fail closed; idle pipelines are unloaded; a second `jude mcp` on the
  same data folder exits at once.
- **I8 — The model is coached.** The tool descriptions and the server's
  instructions are static text that tells Claude: take no arguments,
  never ask which matter or which file, wait for the user to say they
  approved, call `fetch_approved` at most three times, use the copy you
  received, never guess, and — when another conversation's review is
  open — tell the user to finish it there rather than call
  `fetch_approved`.

## 4. What never leaves — and what the browser can still do

**Never leaves your computer**: the matter's name, the file's name and
path, the pseudonym mapping, real names, the approval record, the window
address and its cookie, Jude's trace log. The chat box is not filtered
(§1).

**Leaves, once, after your approval**: the pseudonymized text and its
SHA-256, to Claude Desktop, which sends it to Anthropic under the terms
of whoever's Claude account it is. The plugin does not know those terms.
The rule for *smart* mode (public-knowledge tags on the first mention
of a pseudonym) is therefore explicit: **a matter runs in smart mode
through the plugin only if it was created with `jude matter create NAME
--mode smart --endpoint claude-desktop --zr`** — that is, only if *you*
attest that the Claude Desktop account in use is under a zero-retention
regime, which a consumer account is not. Any other matter, including a
smart matter whose attestation names another endpoint, is prepared in
**strict** mode with a one-line notice in the window (*This matter asks
for smart mode, but its zero-retention attestation does not name Claude
Desktop: strict mode is used for this document*). The matter chooser
shows the `ZR` tag only when the attestation names Claude Desktop, and
the approval row records `zero_retention` only when smart mode was
actually used.

**What the browser can still do.** Jude's window is a page in your
default browser. The markup disables translation (`translate="no"`,
the `notranslate` meta), spell-check, autocomplete, autocapitalize and
password-manager capture. But a browser *extension* with host access
reads the page regardless of markup: a grammar checker, a translation
extension, an "AI assistant" extension, a screen recorder. Open Jude's
window in a browser profile without extensions, or in a browser you
keep clean for this purpose. The v1.1 path is a window without a
browser's chrome — a Chrome `--app=` window or a native webview — which
removes the extension surface.

## 5. Install

Jude itself must be installed first (`docs/installation.md`): a virtual
environment with the spaCy models for English, French **and Dutch**
(`en_core_web_lg`, `fr_core_news_md`, `nl_core_news_md` — the plugin
checks all three by default and fails closed when one is missing) and,
if you use it, the GLiNER weights. The plugin reuses that installation;
it bundles no Python.

**A. The installer (primary route, nothing to download)**

```bash
pip install -e ".[mcp]"
jude mcp install-claude-desktop        # --dry-run shows the JSON and writes nothing
```

The installer runs `jude mcp doctor` first and refuses to write if a
check fails. It backs up Claude Desktop's configuration file
(`claude_desktop_config.json.bak-<timestamp>`), adds a `jude` entry
under `mcpServers` with the absolute path of the interpreter it is
running from, leaves every other server untouched, and writes
atomically. Because Claude Desktop does not read your shell's profile,
the installer copies into the entry every one of `JUDE_HOME`,
`HF_HOME`, `HF_HUB_CACHE`, `HUGGINGFACE_HUB_CACHE`, `TRANSFORMERS_CACHE`,
`XDG_CACHE_HOME`, `JUDE_MCP_LANGS`, `JUDE_MCP_GLINER` that is set and
non-empty in the shell you run it from (`--jude-home PATH` wins), and
prints the ones it copied. It ends with "Restart Claude Desktop."
`--uninstall` removes the entry, with a backup.

**B. The bundle (`.mcpb`, one click)**

Download `jude-<version>.mcpb` from the GitHub Release — or build it
with `python scripts/build_mcpb.py` — then double-click it, or open
*Settings › Extensions › Advanced settings › Install Extension…* in
Claude Desktop and choose the file. When asked for *Jude executable*,
pick the `jude` inside your virtual environment (`.venv/bin/jude`;
`.venv\Scripts\jude.exe` on Windows), not a pyenv or asdf shim, which
resolves the interpreter from the wrong directory when Desktop starts
it. Two optional folders follow — *Jude data folder* (your `JUDE_HOME`)
and *Hugging Face cache folder* (your `HF_HOME`): leave both empty
unless you moved them, and the defaults (`~/.jude`, the standard cache)
apply. Restart Claude Desktop. Details for whoever builds the bundle:
`mcpb/README.md`. Use one route, not both: two entries would be two
servers on one database (the second one to start exits by itself, and
the doctor reports the duplicate).

Either way, finish with:

```bash
jude mcp doctor --as-desktop
```

which prints one line per check — interpreter, `jude.mcp` importable,
the Claude Desktop entry or bundle it found, spaCy models for `en`,
`fr`, `nl`, GLiNER weights in the local cache, the PDF and Excel
readers (not required), permissions of `~/.jude` (0700) and `jude.db`
(0600), a loopback bind test, stale temporary files, the trace log (its
path and size, with the reminder that it may contain document text),
Claude Desktop's log path — as `OK`, `MISSING` or `FIX`. `--as-desktop`
runs the same checks again in a subprocess whose environment is the
bare one Claude Desktop gives the server (no shell profile, only the
entry's own `env`), and prints both results side by side when they
differ: that is how a model that *your terminal* finds and *Desktop*
does not shows up before the first review fails. `jude mcp doctor
--fix` asks once, then downloads the missing models **in your terminal,
with the network, where you can see it**, fixes permissions, sweeps
stale files and offers to delete the trace log; it never touches the
Desktop configuration.

**Browser.** The window's same-origin check relies on the
`Sec-Fetch-Site` header, which every current browser sends: Chrome 76,
Firefox 90, Safari 16.4 or later (and Edge, Brave, Arc, which are
Chrome). An older browser is refused with a 403 on every page, which is
the safe failure.

## 6. The approval record, the audit log and the local trace

Every approval is a row in your Jude database, written before the text
is released:

```bash
sqlite3 ~/.jude/jude.db 'select * from approvals'
```

The row carries the SHA-256 of the text as displayed and released, the
time, the approver (the OS user), the review's counts, the attestation
(`items_reviewed_text_read` when you scrolled the text to its end,
`items_reviewed_text_opened` otherwise), the destination (`stdio:` for
the plugin — there is no network host) and an **`outcome`** that is
always filled in at the end: `released` (Claude collected the text),
`refused` (the text no longer matched the record at release; an audit
line `mcp.release.refused` is written and the review fails),
`withdrawn` (you pressed *Withdraw* before Claude collected),
`expired` (Claude did not collect within 30 minutes) or
`lost_on_restart` (the server was stopped with an approval pending; the
next start closes it). `released_at` means *handed to the local pipe
towards Claude Desktop*, not *received by the model* — Jude cannot see
further than its own standard output. This is the record you would
show a bâtonnier or a DPO: what left, when, under which hash, after
whose click, and what became of it.

The audit log (`store.py`, `_log`) receives one line per step of the
review — opened, matter chosen, prepared, approved, released, cancelled
(`mcp.cancel`, with the number of entities and name variants removed),
withdrawn (`mcp.approved.withdrawn`), expired (`mcp.approved.expired`),
refused, and `mcp.recover` at a start that found leftovers — with the
matter id and the review id, never the text. An entity created by a
review is logged by name only once an approval has confirmed it
(`entity.confirm`); a cancelled review leaves no line that carries a
name.

A local trace log (`~/.jude/mcp/trace.log`) holds the full technical
detail — the server's whole error channel, tracebacks included (not
local variables) — in a file readable only by you (mode 0600), rotated
at 2 MiB with three generations kept, whose first line reads *May
contain document text. Never share this file.* `jude mcp doctor --fix`
offers to delete it. Claude Desktop's own log, which you might paste
into a bug report, gets only `<suppressed> exc=<type> at jude/…`. Look
at the trace before sharing anything.

## 7. Limits and out of scope

- **Claude Desktop only.** The plugin is a local process over stdio.
  claude.ai in a browser accepts only *remote connectors* — servers on
  the internet reachable by Anthropic — and cannot start a process on
  your machine. A remote Jude would be a different design (§9–10 say
  what one costs).
- **Python is not bundled.** The `.mcpb` is a pointer to the Jude you
  installed; the models are downloaded once, by you, in a terminal.
- **Wikipedia enrichment is off.** In the Streamlit app a *smart*
  matter may look entities up on Wikipedia, an outbound call you see
  and approve on a dedicated screen. The plugin has no such screen and
  no network: smart mode uses the bundled public-knowledge dataset
  only.
- **There is no "paste text" tool, on purpose.** A tool's arguments are
  written by the model. Any text that reached Jude as an argument would
  already have been read by the model and stored in the transcript —
  a doorman checking papers after letting you in. Documents come from
  the disk, chosen in the window.
- **Documents over 150 000 characters fail closed** (about 50 pages:
  roughly 45 000 tokens of French legal prose, which leaves room for
  the answer in a 200 000-token context). The window says to split the
  document in Word and prepare the parts one by one. Automatic
  splitting into 100 000-character parts, each with its own approval
  row and hash, is noted for v1.1. The figure is a decision, not a
  measurement: Claude Desktop does not publish the size limit of a tool
  result, and the first install measures it (§8).
- **OCR is off.** A PDF that is a scan without a text layer is refused
  with a fixed sentence; `jude redact --ocr` in a terminal reads it,
  and the result can then be prepared.
- **No conversation history.** v1 stores no MCP exchange in Jude's
  `conversations`/`messages` tables; the approval row and the audit
  log are the trace. Whether `show_answer` should also store the
  pseudonymized answer and its rehydration is open.
- **No remote transport.** Nothing in v1 exercises any transport but
  stdio.
- **Later, not now:** a *local second reader* — an offline Ollama model
  on the review screen that reads the redacted text and says what it
  still identifies. It would be the first generative model inside Jude.
  It would never gate and never send.

## 8. Troubleshooting

- `jude mcp doctor --as-desktop` — the first command for any problem:
  it runs the checks both as your terminal and as Claude Desktop, and a
  model present in one and missing in the other is the usual cause of
  *Jude cannot prepare documents yet*. `--fix` for missing models,
  permissions, stale files and the trace log.
- `jude mcp open` — reopens Jude's window when the browser did not
  open. It finds the running server through a file only your user can
  read, challenges it with a signed nonce, prefers the server that has
  a review open, and asks it for a fresh one-time link. When the
  browser cannot be opened at all, it prints a single-use address
  valid for **two minutes** — *Open this single-use address within
  2 minutes* — never the longer-lived link. A dead server's leftovers
  are cleaned and reported as "no Jude window is running; start a
  review from Claude".
- `another jude mcp server is already running for this JUDE_HOME;
  exiting` in Claude Desktop's log — two entries start two servers
  (installer and bundle, or Desktop starting the server twice); the
  second one exits on purpose. `jude mcp doctor` names the duplicate;
  remove one.
- Claude Desktop's logs — macOS `~/Library/Logs/Claude/`
  (`mcp-server-jude.log`, `mcp.log`), Windows `%APPDATA%\Claude\logs\`;
  `jude mcp doctor` prints the exact path it found. They contain no
  text from your documents (I1); the full trace is in Jude's local
  trace log (§6).
- "A review is already open" — the window holds a review from another
  conversation, or an approved text that Claude has not collected yet;
  finish, cancel or withdraw it there. ("Jude is busy" is the same
  ceiling, kept as a second guard.)
- *This tab has no Jude session* — the address was typed by hand or the
  tab was restored by the browser; the session lives only in the tab the
  one-time link opened. Ask Claude again, or run `jude mcp open`.
- "Not approved yet" — Claude polled before you approved; approve in
  the window, then tell Claude.
- A review you approved but Claude never collected — it waits 30
  minutes; say "Approved in Jude" again within that time, or start over
  with a new request (the lapsed approval is recorded as `expired`).
- **The first-install measurement.** Two numbers in this design are
  decisions, not measurements: the 150 000-character cap and the
  30-second maximum wait of `fetch_approved`. After installing, a
  ten-minute test on your own Mac — a result of 150 000 then 300 000
  characters, and a tool that waits 75 seconds — fixes both with the
  facts in hand.

## 9. ChatGPT

*From the research report of 3 November 2026, read against OpenAI's
live pages that day. The naming had changed again: the "Apps SDK"
documentation now lives at developers.openai.com/plugins and the
product is called **plugins**; an "app" is the MCP-server integration
inside a plugin; "connectors" are now "connected apps"; the Codex
desktop app has become the new ChatGPT desktop app (Chat + Work +
Codex, macOS and Windows) and the previous one is "ChatGPT Classic".
Re-check each quotation before relying on it.*

**Where a server must live**

- Public directory submission requires the MCP server "at a stable,
  publicly reachable HTTPS endpoint", speaking MCP streamable HTTP,
  "typically ending in /mcp"; "Do not use Secure MCP Tunnel alone, a
  temporary tunnel, or a local endpoint for public submission"; a
  private server must sit behind "a public HTTPS proxy" with
  OpenAI-managed mTLS and OAuth 2.1 — **verified-official**,
  [developers.openai.com/plugins/build/mcp-server](https://developers.openai.com/plugins/build/mcp-server).
- Private, workspace-only use (*Add custom MCP server* in ChatGPT web)
  accepts "SSE and streaming HTTP" — **verified-official**,
  [developers.openai.com/api/docs/guides/custom-mcp-server](https://developers.openai.com/api/docs/guides/custom-mcp-server).
  The help centre answers the question directly: "Can I connect to a
  local MCP server? Not directly. ChatGPT connects to remote MCP
  servers. If your MCP server runs on a private network, on-premises,
  or on a developer machine, use Secure MCP Tunnel" —
  **verified-official**,
  [help.openai.com/…/12584461](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).
- *Secure MCP Tunnel*: a customer-run, open-source `tunnel-client`
  (Apache-2.0) that long-polls `api.openai.com` outbound-only and
  forwards to an MCP server it reaches "over stdio or HTTP from inside
  your network", a "developer machine" included. It "supports private
  MCP connections, including custom MCP server testing" and "does not
  support public plugin submission or distribution". Limits: 600
  requests a minute, 10 MiB per serialised request or response, a
  120-second deadline, 1 000 queued requests per tunnel, "service
  protections, not throughput or latency guarantees" —
  **verified-official**,
  [developers.openai.com/…/secure-mcp-tunnels](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels),
  [github.com/openai/tunnel-client](https://github.com/openai/tunnel-client).
  OpenAI's own blog: "the same tunnel-client loop works from laptop to
  production" — **verified-official**,
  [developers.openai.com/blog/connect-private-mcp-servers-to-openai-products](https://developers.openai.com/blog/connect-private-mcp-servers-to-openai-products).
  Launch date around 27–28 May 2026 — **secondary** (third-party
  write-ups),
  [agentpedia.codes](https://agentpedia.codes/blog/openai-secure-mcp-tunnels-guide).
- A local stdio server **is** possible, but only on the desktop: (a) the
  new ChatGPT desktop app has *Settings → MCP servers → Add server →
  STDIO or Streamable HTTP*, stored in `~/.codex/config.toml` and shared
  with the Codex CLI and IDE extension; "ChatGPT web doesn't read local
  Codex configuration files" — **verified-official**,
  [learn.chatgpt.com/docs/extend/mcp](https://learn.chatgpt.com/docs/extend/mcp);
  (b) "Desktop-only plugins" declare a stdio server in `mcp.json`
  (`{"type": "stdio", "command": …, "args": […], "cwd": "${PLUGIN_ROOT}"}`),
  "can only be installed from the ChatGPT desktop app", "Users can
  mention them only in threads that run locally", and their directory
  submission "is limited to approved partners" — **verified-official**,
  [developers.openai.com/plugins/deploy/desktop-only](https://developers.openai.com/plugins/deploy/desktop-only).
  The help centre: "Your plugin can include local MCP apps that run on
  your computer, and you can run the plugin on ChatGPT Desktop … does
  not make those tools available on web or mobile" —
  **verified-official**,
  [help.openai.com/…/20001256](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt).
  The new desktop app "includes Chat and Work under ChatGPT, alongside
  Codex, on macOS and Windows" — **verified-official**,
  [help.openai.com/…/20001276](https://help.openai.com/en/articles/20001276-moving-to-the-new-chatgpt-desktop-app).
- Mobile: custom MCP servers "No - web only" — **verified-official**,
  [help.openai.com/…/12584461](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).
- Other OpenAI clients that start a local stdio server: the Codex CLI
  (`[mcp_servers.x]` with `command`/`args`/`env`/`cwd`, `codex mcp add
  x -- <cmd>`), the OpenAI Agents SDK in Python (`MCPServerStdio`) and
  in JavaScript; the Responses API's hosted MCP tool needs a remote
  `server_url` or a `tunnel_id` — **verified-official**,
  [learn.chatgpt.com/docs/extend/mcp](https://learn.chatgpt.com/docs/extend/mcp),
  [openai.github.io/openai-agents-python/mcp](https://openai.github.io/openai-agents-python/mcp/),
  [openai.github.io/openai-agents-js/guides/mcp](https://openai.github.io/openai-agents-js/guides/mcp/).

**Plans and administration**

- Developer Mode is no longer a prerequisite: "add a custom MCP server
  directly from Plugins. You don't need to turn on Developer Mode
  first" — a per-server risk acknowledgement instead —
  **verified-official**,
  [help.openai.com/…/12584461](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).
- "Custom MCP server connections and full MCP support are available for
  ChatGPT Business and Enterprise/Edu customers on ChatGPT web"; Pro
  "can connect custom MCP servers with read/fetch permissions" (no
  write); Plus and Free are not mentioned on the current page —
  **verified-official**, same page.
- Business: "Only admins and owners can create and publish plugins for
  custom MCP servers"; Enterprise/Edu: the role permission "Create
  plugins with MCPs" (off by default) can be granted to members, only
  admins and owners publish, admins can enable or disable each tool
  ("New actions are disabled by default", a "frozen" tool snapshot
  until re-review) and restrict access to groups —
  **verified-official**, same page and
  [help.openai.com/…/20001256](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt).
- Workspace-wide approval policy: *Always ask*, *Allow read actions*,
  *Allow low-risk actions*, *Allow all actions*; Lockdown mode applies;
  "Custom apps are not verified by OpenAI and are intended for
  developer use only" — **verified-official**,
  [help.openai.com/…/11509118](https://help.openai.com/en/articles/11509118-admin-controls-security-and-compliance-for-plugins-and-apps).
- Any tool without the `readOnlyHint` annotation "is treated as a write
  action" and requires confirmation by default; deep research uses
  read/fetch tools only — **verified-official**,
  [developers.openai.com/api/docs/guides/custom-mcp-server](https://developers.openai.com/api/docs/guides/custom-mcp-server).

**Authentication**

- No-auth is allowed ("Many plugin MCP servers can operate in a
  read-only, anonymous mode"), but "anything that exposes
  customer-specific data or write actions should authenticate users".
  Authenticated servers implement OAuth 2.1 per the MCP authorization
  spec: protected-resource metadata, 401 with `WWW-Authenticate`, PKCE
  with `S256` mandatory ("MCP servers are unsupported when their
  authorization server metadata … does not advertise S256"), CIMD
  preferred (client id `https://chatgpt.com/oauth/client.json`), DCR
  still supported, the `resource` parameter echoed into `aud`, the token
  verified on every call — **verified-official**,
  [developers.openai.com/plugins/build/auth](https://developers.openai.com/plugins/build/auth).
- "ChatGPT does not support machine-to-machine OAuth grants such as
  client credentials, service accounts, or JWT bearer assertions, nor
  can it present custom API keys"; it presents an OpenAI-managed client
  certificate (mTLS, SAN `mtls.prod.connectors.openai.com`) and
  publishes its egress IP ranges — **verified-official**, same page.
- The add-server form offers *OAuth*, *No authentication*, *OAuth or no
  authentication*; the plugin manifest also knows `api_key`, but the
  submission portal does not — **verified-official**,
  [developers.openai.com/api/docs/guides/custom-mcp-server](https://developers.openai.com/api/docs/guides/custom-mcp-server),
  [developers.openai.com/plugins/build/plugins](https://developers.openai.com/plugins/build/plugins).
- Public submission additionally requires a publicly accessible domain
  with a verification challenge at `/.well-known/openai-apps-challenge`,
  identity verification, a demo account without MFA, a published
  privacy policy, no Restricted Data (PCI, PHI, government identifiers,
  credentials), that the server "must not pull, reconstruct, or infer
  the full chat log", and "For now, projects with EU data residency
  cannot submit plugins with MCP servers for review"; "For private or
  workspace-only use, use a custom MCP server connection instead" —
  **verified-official**,
  [developers.openai.com/plugins/deploy/app-review](https://developers.openai.com/plugins/deploy/app-review),
  [developers.openai.com/plugins/deploy/submission](https://developers.openai.com/plugins/deploy/submission),
  [developers.openai.com/plugins/plugin-guidelines](https://developers.openai.com/plugins/plugin-guidelines).

**Hidden data in tool results**

- A tool result has `structuredContent` and `content`, "Surfaced to the
  model and the component", and `_meta`, "Delivered only to the
  component. Hidden from the model."; "Only `structuredContent` and
  `content` appear in the conversation transcript. The host forwards
  `_meta` to the component so you can hydrate UI without exposing the
  data to the model" — **verified-official**,
  [developers.openai.com/plugins/reference](https://developers.openai.com/plugins/reference).
  The same documentation warns: "Treat `_meta` as hidden from the model,
  not as a substitute for authorization or secure storage" —
  **verified-official**,
  [developers.openai.com/plugins/build/mcp-server](https://developers.openai.com/plugins/build/mcp-server).
  The component runs in a sandboxed iframe inside ChatGPT;
  `window.openai.toolResponseMetadata` carries "the full MCP result
  envelope, including hidden `_meta`" — **verified-official**,
  [developers.openai.com/plugins/build/chatgpt-ui](https://developers.openai.com/plugins/build/chatgpt-ui).
- Because the *host* forwards `_meta` to the iframe, data placed there
  is hidden from the model but still transits OpenAI's host; for Jude,
  the real names should be displayed by a window the *local* server
  draws (the desktop path) or by a firm-hosted page, never by the
  ChatGPT iframe — **inferred**.

**Data handling**

- Enterprise privacy page (updated 8 January 2026): no training on
  Business/Enterprise/Edu data by default, "any data accessed from apps"
  included; Enterprise/Edu: "Your workspace admins control how long
  your data is retained. Any deleted conversations are removed from our
  systems within 30 days"; Business: deleted or unsaved conversations
  removed within 30 days unless law or harm prevention requires longer,
  and admins "can view, access, export, and delete end user
  conversations"; SOC 2 Type 2, AES-256 at rest, TLS 1.2+, a DPA —
  **verified-official**,
  [openai.com/enterprise-privacy](https://openai.com/enterprise-privacy/).
- Zero data retention is an **API-platform** option, "subject to prior
  approval"; no official page offers it for ChatGPT itself —
  **verified-official**,
  [developers.openai.com/api/docs/guides/your-data](https://developers.openai.com/api/docs/guides/your-data),
  [openai.com/business-data](https://openai.com/business-data/).
- Data residency for ChatGPT: "new ChatGPT Enterprise/Edu customers"
  (Business is not listed), "Europe (EEA + Switzerland)" among the
  regions, at no additional cost; explicitly out of scope: "Data that is
  stored and processed outside OpenAI's infrastructure through external
  integrations (e.g., Apps & MCP…)", and "Information sent to an
  external app, MCP server … is handled under that provider's own …
  terms" — **verified-official**,
  [help.openai.com/…/9903489](https://help.openai.com/en/articles/9903489-data-residency-and-inference-residency-for-chatgpt).
- Enterprise/Edu: "User conversations — including those using any app
  — are available in the Compliance API"; "Information included in
  chats or research outputs follows the applicable conversation,
  feature, and workspace-retention policies" — **verified-official**,
  [help.openai.com/…/11509118](https://help.openai.com/en/articles/11509118-admin-controls-security-and-compliance-for-plugins-and-apps).
  No separate retention rule exists for tool results: the pseudonymized
  text Jude would return is conversation content, retained under the
  workspace policy, and may surface in app-activity records —
  **inferred**.
- Consumer plans: "For ChatGPT Free, Plus, Go, and Pro users: OpenAI may
  use information accessed from apps to train our models if your
  'Improve the model for everyone' setting is on" —
  **verified-official**,
  [help.openai.com/…/11487775](https://help.openai.com/en/articles/11487775-connected-apps-in-chatgpt).

**What follows for Jude** — **inferred**

- Two shapes exist. **(A) True local-first, desktop only**: Jude as a
  stdio server on each lawyer's machine inside the new ChatGPT desktop
  app (*Settings → MCP servers*, or a workspace-uploaded desktop-only
  plugin), the review window drawn locally, nothing to host; but only
  in a Business or Enterprise workspace whose admins allow it, only on
  macOS and Windows, never on the web or mobile, only "in threads that
  run locally" (which threads qualify is untested), and with no public
  listing without partner allow-listing. Whether a workspace can
  distribute such a plugin to its own members without that
  allow-listing is implied by the help centre but not stated —
  **inferred**.
- **(B) Web-capable, firm-hosted**: the requirements below.
- Because the tunnel imposes a 120 s deadline and tool calls are
  synchronous, a human review must stay asynchronous (prepare → review
  → fetch approved), as it is in the Claude Desktop design.

**What a firm-hosted deployment would require** (ChatGPT web, Business
or Enterprise):

1. One Jude MCP server speaking streamable HTTP at a stable `/mcp` URL,
   either on public HTTPS behind a proxy (TLS certificate, mTLS
   verification of ChatGPT's client certificate, optional IP allow-list)
   or kept private behind Secure MCP Tunnel with a tunnel client in the
   firm's network (a Platform organisation with a runtime API key, the
   10 MiB / 120 s / 600-per-minute limits, no SLA), accepting that
   every request and response transits OpenAI's control plane.
2. An OAuth 2.1 authorisation server — the firm's identity provider:
   discovery metadata, PKCE S256, CIMD or DCR, refresh tokens via
   `offline_access`, `resource` → `aud` — because ChatGPT cannot use
   service accounts or API keys.
3. Per-user pseudonym stores partitioned by the OAuth subject, on firm
   infrastructure in the firm's region, under the firm's own retention
   and deletion policy. This is where the real names live.
4. A firm-hosted review page where the lawyer approves what is sent —
   or an MCP-App iframe fed through `_meta`, accepting that the
   rehydrated names then pass through OpenAI's host.
5. Tool annotations (`readOnlyHint`) and confirmation prompts so that
   the "hand to the model" step is an explicit write action.
6. Workspace governance: a Business or Enterprise/Edu plan, admin
   publication, role and action controls, Compliance API awareness,
   Enterprise plus EU data residency if the firm wants EU at-rest
   storage (Business has no residency option), and acceptance that the
   pseudonymized text is conversation content retained under the
   workspace policy. Per-lawyer tunnel clients to individual laptops are
   technically allowed but operationally heavy. Pro accounts get
   read/fetch-only custom MCP; Plus and Free are not documented.

Plus, on Jude's side: the relay or host becomes a sub-processor of
every pseudonymized document and every answer, which needs a written
basis under Art. 458 and a GDPR Art. 28 contract; `approvals` must
record the resolved host, not `stdio:`; the "What leaves" box must name
it; `netguard` must become an allow-list of exactly that host; the HTTP
transport must carry OAuth authentication; and none of the v1 tests
would catch a misconfigured relay that logs bodies.

**Recommendation.** Ship v1 for Claude Desktop (stdio, no network at
all). Keep the server free of transport assumptions — switching the
transport is one line — but open no ChatGPT route before a decision on
whether *any* relay through OpenAI's infrastructure is acceptable under
Art. 458, taken with the facts above in hand and re-verified on the
day. Shape (A) is the only one that keeps the document on the laptop;
shape (B) requires the firm to host, secure and contract for the
server. The pages changed within hours of the research: re-verify
before deciding.

**Open questions from the research**: Plus, Free and Go plans (the
current page is silent; an older "developer mode (beta)" version
reportedly covered Plus and Pro); the tunnel's pricing, GA status and
SLA, and whether every lawyer's laptop needs a billed Platform
organisation; whether a firm can upload a desktop-only plugin to its
own workspace without partner allow-listing; which desktop threads
count as "running locally" (Codex threads certainly, plain Chat threads
unknown); whether ChatGPT Classic supports any local MCP (assume no);
the exact scope of Pro's "read/fetch permissions" (Jude's "hand the
approved text to the model" tool would be a write action and therefore
blocked); whether `_meta` payloads are captured in Compliance API
records and for how long; whether an EU-resident Enterprise workspace
can add private custom MCP servers at all; and the exact launch dates,
which come from third-party or search-summarised release notes.

## 10. Mistral Le Chat (now Vibe)

*From the research report of 3 November 2026, checked against
docs.mistral.ai, help.mistral.ai, legal.mistral.ai, mistral.ai/news,
github.com/mistralai and ollama.com that day.*

**The product has been renamed, and the catalogue has moved**

- On 28 May 2026 Mistral merged Le Chat into **Vibe**: "Le Chat is now
  Vibe — one agent and one licence across work and code"; *Vibe Work*
  is the chat and agent interface, "available on web and mobile" at
  chat.mistral.ai; *Vibe Code* is the CLI, the VS Code extension and
  remote web sandboxes; "Chat (legacy)" is being phased out —
  **verified-official**,
  [mistral.ai/news/vibe-agent](https://mistral.ai/news/vibe-agent/),
  [help.mistral.ai/…/682992](https://help.mistral.ai/en/articles/682992-le-chat-is-now-vibe).
- There is no Mistral desktop application: Vibe Work is documented as
  web and mobile, the Code surfaces are CLI, VS Code extension and
  remote web sessions — **inferred** from
  [docs.mistral.ai/vibe/choose-chat-work-code](https://docs.mistral.ai/vibe/choose-chat-work-code).
  So there is no "local MCP server in a desktop chat client" path
  comparable to Claude Desktop.
- Magistral is retired (`magistral-medium-2509` and
  `magistral-small-2509` retired 31 July 2026); reasoning now comes
  through a `reasoning_effort` parameter on Mistral Large 4, Medium 3.5
  and Small 4 — **verified-official**,
  [docs.mistral.ai/models](https://docs.mistral.ai/models),
  [docs.mistral.ai/studio/conversations/reasoning](https://docs.mistral.ai/studio/conversations/reasoning).
  Mistral Large 4 (1.05 T parameters, 52 B active, 1 M context) launched
  6 October 2026 in **Public Preview**, "trained from scratch … in
  Mistral's own datacenters in Europe"; Mistral Medium 3.5 is
  deprecated (retirement 30 April 2027) — **verified-official**,
  [mistral.ai/news/mistral-large-4](https://mistral.ai/news/mistral-large-4/),
  [docs.mistral.ai/models/mistral-large-4-0](https://docs.mistral.ai/models/mistral-large-4-0),
  [docs.mistral.ai/models/mistral-medium-3-5-26-04](https://docs.mistral.ai/models/mistral-medium-3-5-26-04).
- Regional inference is generally available since 11 August 2026:
  `api.eu.mistral.ai` runs in "Multiple data centers in EU and EFTA
  countries" (+10 % on price, function calling only, no Agents, Batch
  or Files); the global `api.mistral.ai` "does not commit to a specific
  inference location" — **verified-official**,
  [docs.mistral.ai/inference/regional-inference](https://docs.mistral.ai/inference/regional-inference),
  [mistral.ai/news/regional-inference-open-models-new-compute](https://mistral.ai/news/regional-inference-open-models-new-compute/).

**Custom MCP connectors in Vibe Work**

- Two ways to add an MCP connector — the curated directory, or "point
  Work at your own MCP-compatible server"; "Both require an
  administrator"; "On Free, Pro, and Student plans, the account owner
  is the administrator by default" — **verified-official**,
  [docs.mistral.ai/vibe/work/connectors/mcp-connectors](https://docs.mistral.ai/vibe/work/connectors/mcp-connectors).
- The custom-connector form takes a name, a *Server URL* and a
  description; authentication is auto-detected: none, HTTP Bearer or
  Basic, or OAuth 2.1 with dynamic client registration; the server
  "must be accessible over HTTPS with a valid TLS certificate", answer
  the `initialize` call, and "Streamable HTTP is the current standard"
  — **verified-official**, same page. No stdio or local transport is
  offered; a server on the lawyer's machine is excluded unless it is
  published on a public HTTPS name — **inferred**.
- Limitations: no dynamic tool discovery, no MCP resources, no prompt
  templates — tools only, which is all Jude uses; "MCP Connectors
  aren't Mistral products. We don't control third-party servers" —
  **verified-official**, same page.
- The pricing table's row "Custom MCP connectors (beta) — Connect to any
  remote MCP server of choice" is included on all four plans (Free,
  Pro, Team, Enterprise); "Custom deployments — Deploy self-hosted, in
  your private cloud, or on-premises" and SAML SSO are Enterprise-only;
  "Model training" is included on Free and marked "Opt-out" on Pro,
  Team and Enterprise — **verified-official**,
  [mistral.ai/pricing](https://mistral.ai/pricing).
- Data fetched through connectors "is never used to train or fine-tune
  our models, regardless of your plan"; conversations that reference
  connector data follow the plan's data policies —
  **verified-official**,
  [docs.mistral.ai/vibe/work/connectors](https://docs.mistral.ai/vibe/work/connectors).
- Admin controls per workspace and organisation, API keys with connector
  scopes and "Connectors in Vibe Code (GA)" shipped 24 June 2026 —
  **verified-official**,
  [mistral.ai/news/more-control-over-connectors](https://mistral.ai/news/more-control-over-connectors/).

**The developer platform (Mistral Studio) and the local paths**

- Studio *Connectors* (Public Preview, launched 22 May 2026) "are
  registered MCP servers that you can use as tools in conversations and
  Agents … without managing MCP transport locally"; `POST /v1/connectors`
  takes the MCP server **URL** (`format: uri` in the OpenAPI
  specification; transport `streamable-http` or `sse`; no `command`
  field), and a conversation passes `{"type": "connector",
  "connector_id": …}` in `tools`, optionally with
  `requires_confirmation` — remote only — **verified-official**,
  [docs.mistral.ai/studio/connectors](https://docs.mistral.ai/studio/connectors),
  [docs.mistral.ai/studio/connectors/management](https://docs.mistral.ai/studio/connectors/management),
  [docs.mistral.ai/openapi.yaml](https://docs.mistral.ai/openapi.yaml),
  [mistral.ai/news/connectors](https://mistral.ai/news/connectors/).
- The Agents and Conversations APIs (`/v1/agents`, `/v1/conversations`,
  beta) are stateful and are excluded from zero data retention; "If you
  use our Agents API, we keep your Input and Output until you terminate
  your account" — **verified-official**,
  [docs.mistral.ai/studio/agents/agents-api](https://docs.mistral.ai/studio/agents/agents-api),
  [legal.mistral.ai/terms/privacy-policy](https://legal.mistral.ai/terms/privacy-policy).
  For Jude the stateless `/v1/chat/completions` is the right endpoint —
  **inferred**.
- The Python SDK still contains a local stdio MCP client
  (`mistralai.extra.mcp.stdio.MCPClientSTDIO`, registered on a
  `RunContext` and run through `client.beta.conversations.run_async`),
  present in the repository and its examples — **verified-official**,
  [github.com/mistralai/client-python](https://github.com/mistralai/client-python/blob/main/examples/mistral/agents/async_conversation_run_mcp.py)
  — but no longer referenced in the public documentation sitemap; treat
  it as undocumented and legacy — **inferred**,
  [docs.mistral.ai/llms.txt](https://docs.mistral.ai/llms.txt).
- The open-source *Vibe CLI* (`pip install mistral-vibe`, Apache-2.0)
  starts local stdio servers: `vibe mcp add NAME --transport stdio
  --command … --arg …`, or `[[mcp_servers]]` with `transport = "stdio"`
  in `~/.vibe/config.toml`; it also runs fully offline against any
  OpenAI-compatible local server (vLLM, llama.cpp, LM Studio, Ollama)
  with `enable_telemetry = false` — **verified-official**,
  [docs.mistral.ai/vibe/code/cli/mcp-servers](https://docs.mistral.ai/vibe/code/cli/mcp-servers),
  [docs.mistral.ai/vibe/code/cli/offline-models](https://docs.mistral.ai/vibe/code/cli/offline-models),
  [github.com/mistralai/mistral-vibe](https://github.com/mistralai/mistral-vibe).
  It is a coding agent, not a lawyer's chat: useful as a test harness
  for Jude's server, not as a product surface — **inferred**. The VS
  Code extension "runs on the same harness as the CLI", so stdio
  support there is plausible but not documented — **inferred**,
  [mistral.ai/news/vibe-agent](https://mistral.ai/news/vibe-agent/).
- Mistral also hosts its own MCP server (`https://api.mistral.ai/mcp`,
  streamable HTTP, bearer) exposing Studio workspace tools — not
  relevant to Jude's privacy goal — **verified-official**,
  [docs.mistral.ai/resources/mcp](https://docs.mistral.ai/resources/mcp).

**Data**

- "By default, your data is hosted in the European Union. You may,
  however, explicitely use our US API endpoint" (12 August 2026); some
  features may transfer data outside the EU to sub-processors listed in
  the Trust Center, which Enterprise can deactivate —
  **verified-official**,
  [help.mistral.ai/…/347629](https://help.mistral.ai/en/articles/347629-where-do-you-store-my-data-or-my-organization-s-data).
  The privacy policy (effective 3 September 2026) prefers EU providers
  but allows non-EU ones "in exceptional cases" under Art. 46 safeguards
  and SCCs — **verified-official**,
  [legal.mistral.ai/terms/privacy-policy](https://legal.mistral.ai/terms/privacy-policy).
- Retention (same policy): Vibe — "we keep your Input and Output until
  you delete your account or until you delete the conversation"; APIs —
  "thirty (30) rolling days to monitor abuse (unless zero data retention
  is activated)"; Agents API — until account termination —
  **verified-official**, same page. After a manual deletion in Vibe,
  "we may retain different types of data in our backend systems for
  different amounts of time" — **verified-official**,
  [help.mistral.ai/…/347613](https://help.mistral.ai/en/articles/347613-can-i-delete-a-chat-conversation).
- Zero data retention: "available only with pay-as-you-go and only for
  stateless API calls" (`/v1/chat/completions`, FIM, embeddings,
  moderation, OCR, audio); "ZDR is not available for Vibe Work or Chat,
  regardless of your subscription plan", nor for agents, conversations,
  libraries, batch or files; requested through the help centre with
  "sufficient detail of your legitimate reasons", approved "at our
  discretion", visible in *Admin panel › Privacy* once granted; "ZDR
  and training opt-out are separate controls"; "We cannot sign the DPA
  offline" — **verified-official**,
  [help.mistral.ai/…/347612](https://help.mistral.ai/en/articles/347612-can-i-activate-zero-data-retention-zdr),
  [docs.mistral.ai/admin/monitor-comply/zero-data-retention](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention).
- Training (3 September 2026): "Vibe: users are not opted out by default
  and can opt out at any time in their settings"; "Vibe (Teams):
  Administrators can disable data training usage for the entire
  organization"; "Vibe (Enterprise): customers are opted out of training
  by default"; the API/Studio opt-out is a separate toggle (*Admin
  panel › Privacy › Anonymous improvement data*); "Documents attached or
  uploaded within Vibe are considered as input data"; thumbs-up/down
  feedback with a comment authorises use of the rated exchange on any
  plan — **verified-official**,
  [help.mistral.ai/…/455207](https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training),
  [help.mistral.ai/…/323757](https://help.mistral.ai/en/articles/323757-do-you-use-my-user-data-to-train-your-artificial-intelligence-models).
  Whether Pro is opted out by default or merely able to opt out is
  ambiguous between the help centre and the pricing table — an open
  question.
- Commercial Terms (effective 25 September 2026): the customer "retains
  all ownership rights in Customer Data and … owns all Output"; §4.2 no
  training on Customer Data or Outputs except opt-in/opt-out cases,
  Feedback, an Order Form, and "Labs or Preview Models"; §4.3 for those
  models "the opt-out preferences you selected for other Mistral AI
  Products (including through zero data retention)" do not apply — "If
  you do not want your data or outputs used for training, do not use
  Labs or Preview Models" — **verified-official**,
  [legal.mistral.ai/terms/commercial-terms-of-service](https://legal.mistral.ai/terms/commercial-terms-of-service).
  Mistral Large 4's catalogue status is "Public Preview": a potential
  exposure if "Preview Models" covers it — **inferred**.
- The DPA (effective 27 July 2026, online only) excludes abuse
  monitoring "when zero data retention has been activated", lists
  sub-processors in the Trust Center, transfers under adequacy or SCCs,
  and makes personal data inaccessible thirty days after termination;
  SOC 2 Type II and ISO 27001/27701 — **verified-official**,
  [legal.mistral.ai/terms/data-processing-addendum](https://legal.mistral.ai/terms/data-processing-addendum),
  [help.mistral.ai/…/347638](https://help.mistral.ai/en/articles/347638-do-you-have-soc-2-or-iso-27001-certification).
  Connecting an MCP server to Vibe grants Mistral permission to "send
  Customer input to the Third-Party Connector" — **verified-official**,
  [legal.mistral.ai/terms/additional-terms](https://legal.mistral.ai/terms/additional-terms).

**Mistral as an LLM backend — the facts a `MistralClient` would need**

- Chat completions: `POST https://api.mistral.ai/v1/chat/completions`
  (EU: `https://api.eu.mistral.ai/v1/chat/completions`; SDK
  `Mistral(api_key=…, server="eu")`), `Authorization: Bearer`, body
  `{model, messages, temperature, max_tokens, stream, …}`, response
  `{id, object: "chat.completion", model, usage: {prompt_tokens,
  completion_tokens, total_tokens}, choices: [{message: {role,
  content}, finish_reason}]}`; streaming as server-sent events ending
  with `data: [DONE]`; with reasoning on, `content` is a list of
  `thinking` and `text` chunks — **verified-official**,
  [docs.mistral.ai/openapi.yaml](https://docs.mistral.ai/openapi.yaml),
  [docs.mistral.ai/studio/conversations/chat-completion](https://docs.mistral.ai/studio/conversations/chat-completion).
- Model ids to pin: `mistral-small-2603` (Small 4, GA, 256 k, Apache
  2.0, $0.15 / $0.60 per million tokens), `mistral-medium-3-5`
  (deprecated, 256 k, 128 B dense open weights), `mistral-large-4`
  (Public Preview, 1 M, $0.70 / $2.10); `mistral-large-latest` still
  appears in examples but is not among Large 4's names —
  **verified-official**,
  [docs.mistral.ai/models/mistral-small-4-0-26-03](https://docs.mistral.ai/models/mistral-small-4-0-26-03),
  [docs.mistral.ai/models](https://docs.mistral.ai/models).
- Local, through the existing Ollama client: `ministral-3:3b|8b|14b`,
  `magistral:24b`, `mistral-small3.2:24b`, `devstral-small-2:24b`,
  `mistral-medium-3.5:128b`, `mistral-nemo`, `mistral:7b`, `mixtral` —
  **verified-official**,
  [ollama.com/library/mistral-medium-3.5](https://ollama.com/library/mistral-medium-3.5).
  **Warning**: `mistral-large-4:cloud`, `mistral-large-3:675b-cloud` and
  `devstral-small-2:24b-cloud` are *Ollama Cloud* models that run on
  Ollama's servers ("Cloud models do not need to be downloaded") —
  **verified-official**,
  [ollama.com/library/mistral-large-4](https://ollama.com/library/mistral-large-4),
  [docs.ollama.com/cloud](https://docs.ollama.com/cloud). Jude's
  `OllamaClient` treats every model name as inherently zero-retention;
  it should refuse any tag containing `cloud` — **inferred**. Mistral
  Small 4 is not in the Ollama library (404 on 3 November 2026) —
  **verified-official**,
  [ollama.com/search?q=mistral-small](https://ollama.com/search?q=mistral-small).

**What follows for Jude** — **inferred**

- A local-first Jude as a Vibe plugin is not possible: remote
  HTTPS-only connectors, no desktop app, no stdio in Vibe Work. The
  Vibe Code CLI is the one Mistral surface where Jude could run as a
  true local stdio server today, and it is a coding tool.
- A firm-hosted remote connector works technically on every plan, Free
  included (on Free and Pro the user is their own administrator); but
  the chat text typed into Vibe reaches Mistral before Jude's tool
  runs, Vibe has no zero data retention, conversations persist until
  deleted, Free and Pro train unless opted out, and the local review
  window would have to become a page served by the firm's server.

**What a firm-hosted deployment would require** (Vibe Work):

1. A Jude MCP server on a public HTTPS name with a valid certificate,
   speaking streamable HTTP, answering the `initialize` handshake,
   added by the workspace administrator as a custom connector.
2. Authentication — a Bearer token at minimum, OAuth 2.1 with dynamic
   client registration for per-lawyer identity — and per-function
   confirmation left on.
3. Everything through tools: no MCP resources, no prompt templates, no
   dynamic tool discovery.
4. A firm-hosted review page in place of the local window: the document
   is read by the server (upload or document-management integration);
   the approval record and the real-name display live there.
5. The account's privacy settings: the Vibe training opt-out on every
   Pro and Team account (Team admins can disable it organisation-wide;
   Enterprise is opted out by default); acceptance that Vibe Work
   conversations are retained until deleted and that zero data
   retention cannot be obtained for them; an Enterprise self-hosted
   Vibe if the firm wants the conversation inside its own walls (whether
   it accepts a connector on a private network is an open question).
6. On Jude's side, the same items as for ChatGPT: a written basis under
   Art. 458 and an Art. 28 contract (Mistral's DPA is online only), the
   relay host in `approvals` and in the "What leaves" box, `netguard`
   as an allow-list, an authenticated HTTP transport.

**Recommendation.** Do not build a Le Chat / Vibe plugin. Mistral's
real advantage for a Belgian or French bar — a Paris company, EU
hosting by default, EU-only inference on request, a public DPA — is
available through a different door: **Mistral as an LLM backend inside
Jude**. Either (i) a `MistralClient` — an `LLMClient` subclass on the
stateless `POST https://api.eu.mistral.ai/v1/chat/completions`, with
zero data retention requested and approved on a pay-as-you-go account
and the training opt-out set, so that `zero_retention_attested` maps
to the ZDR approval shown in the Admin panel, exactly as for the
Anthropic client — preferring GA models (`mistral-small-2603`) or
Medium 3.5 until Large 4 leaves Public Preview, because of Commercial
Terms §4.3; or (ii) Mistral's open weights fully local through the
existing Ollama client with the tags above, the `cloud` tags refused.
Jude's gate then stays exactly where it is: on your machine, before
the text leaves.

**Open questions from the research**: whether "Preview Models" in
Commercial Terms §4.3 covers `mistral-large-4` (the ZDR page excludes
only "Labs models"); what `mistral-large-latest` resolves to today
(`GET /v1/models`); the Pro training default; whether a solo
practitioner on Free or Pro with pay-as-you-go obtains ZDR, and on what
"legitimate reasons"; whether the global endpoint infers in the EU in
practice (the EU endpoint removes the doubt; check which models it
serves); whether the VS Code extension honours stdio entries; whether
the SDK's local MCP path stays supported; retention and ZDR semantics
of a self-hosted Vibe Enterprise; and whether a community GGUF of
Mistral Small 4 is usable in Ollama before the library publishes it.

## 11. Browser extension (future)

A browser extension is the one place a doorman could stand: inside the
page where the lawyer types, before the message leaves for the model.
It could run Jude's readers on the chat box of claude.ai, chatgpt.com
or chat.mistral.ai and swap names for the matter's pseudonyms before
*Send*, behind the same approval. It is also the hardest surface to
make safe: an extension that reads the chat box reads every other page
too, must either carry the models or talk to the local Jude server,
and is updated through a store the firm does not control. It would not
replace the plugin — the plugin reads files and shows answers; the
extension would guard the prompt — and it is neither designed nor
scheduled; it is listed here so that nobody mistakes the plugin for it.

## 12. Résumé en français

**De quoi on parle.** Un *plugin* (ou *extension*) est un petit
programme que Claude, ChatGPT ou Le Chat peuvent appeler pendant une
conversation. Le protocole qui le permet s'appelle *MCP* : le programme
annonce une courte liste d'*outils* (des fonctions avec un nom), et le
modèle décide, en lisant votre message, s'il en appelle un. Le plugin de
Jude tourne sur votre Mac, lancé par Claude Desktop (l'application de
bureau, pas le site web), et il ne touche jamais au réseau.

**Ce qu'un plugin ne peut pas faire.** Le modèle lit votre message
*avant* d'appeler un outil. Un plugin ne peut donc pas filtrer ce que
vous tapez dans la case de conversation. Analogie : le plugin est un
*commis en cuisine*, pas un *portier à l'entrée*. Il prépare ce que le
chef lui demande ; il ne contrôle pas qui entre dans la salle. Règle
pratique : ne tapez jamais un nom de client, de dossier ou de fichier
dans la conversation. Dites « analyse le mémo que je choisirai dans
Jude », et choisissez le dossier et le fichier dans la fenêtre de Jude.

**Comment ça se passe.** Vous demandez l'analyse ; Claude appelle
l'outil `prepare_document`, qui ne prend aucun argument (il n'y a donc
rien à lui dire). Jude ouvre une fenêtre dans votre navigateur, sur
votre machine seulement (adresse `127.0.0.1`, c'est-à-dire « cet
ordinateur »). Vous y choisissez le dossier et le document — jusqu'à
150 000 caractères, environ 50 pages ; au-delà, il faut découper dans
Word. Jude lit le fichier (le navigateur ne lui transmet même pas le
nom du fichier, seulement son contenu et son extension), remplace les
noms par ses pseudonymes (`Org1`, `Person2`, toujours les mêmes d'un
document à l'autre pour un même dossier), vous montre le résultat avec
ses avertissements (commentaires Word non lus, pages scannées non
lues), ses *signaux de ré-identification* (un passage qui désigne une
partie même sans son nom), les caractères invisibles s'il y en a, et
l'original en regard si vous le demandez. Vous corrigez (*Keep* : garder
un terme visible ; *Hide* : le masquer ; *Mark* : masquer un terme que
Jude a raté). Puis vous cochez l'*attestation* — « J'ai lu la liste et
le texte ci-dessus. Ce texte exact peut être transmis à Claude quand
Claude le demandera ; l'enregistrement est écrit d'abord sur cet
ordinateur » — et vous approuvez. Jude écrit alors sur votre disque,
*avant* de donner quoi que ce soit, un enregistrement avec l'*empreinte*
du texte — un *hash* SHA-256, c'est-à-dire une signature numérique de
64 caractères qui change si une seule lettre change ; analogie : le
sceau de cire qui révèle toute ouverture de l'enveloppe.

**Approuver, puis le dire : deux gestes, et l'écran le dit.** Après
*Approve*, l'écran le dit en une phrase : « Dès l'approbation, Claude
peut prendre ce texte exact au moment où il le demande, une fois ; vous
pouvez le retirer ici jusque-là. » Vous écrivez à Claude « Approved in Jude. » (la fenêtre a
un bouton *Copier*) : Claude ne voit pas la fenêtre, c'est votre message
qui le fait appeler `fetch_approved`, qui reçoit le texte pseudonymisé
une seule fois. Tant que Claude n'est pas venu, un bouton *Retirer
l'approbation* annule tout ; si les deux se croisent, l'écran dit qui a
gagné. Claude répond en pseudonymes, puis appelle `show_answer` : la
fenêtre de Jude vous montre la réponse avec les vrais noms, avec un
bouton *Copier*. Dans Claude, la conversation reste en pseudonymes.
Analogie : vous signez le bon de sortie (l'approbation) ; le coursier
ne passe que quand vous l'appelez (votre message) ; jusqu'à son passage
vous pouvez déchirer le bon.

**Pourquoi il faut le dire vous-même.** Un appel d'outil ne peut pas
attendre un humain. Claude Desktop ne publie pas la durée maximale d'un
appel d'outil — c'est un chiffre à mesurer sur votre Mac dès la première
installation (**hypothèse** jusque-là). Jude rend donc la main tout de
suite et attend votre message pour relancer Claude. Un texte approuvé
reste disponible **30 minutes** ; passé ce délai, l'approbation
s'éteint d'elle-même et rien ne part. Une relecture non approuvée se
ferme après **20 minutes sans vous** (un clic, une touche, un
défilement ; les rafraîchissements automatiques de la page ne comptent
pas). Les deux délais sont des réglages. Une demande d'arrêt (Claude
Desktop qui se ferme, un SIGTERM) termine le serveur en 15 secondes au
plus, quoi que fassent ses fils d'exécution : une préparation en cours
a 5 secondes, la fenêtre 5 secondes, et un chien de garde met fin au
processus si une étape se bloque ; le démarrage suivant supprime les
entités qu'une préparation interrompue avait créées et clôt une
approbation en attente en `lost_on_restart`.

**Ce qui ne quitte jamais votre ordinateur.** Le nom du dossier, le nom
du fichier, la table des pseudonymes, les vrais noms, l'enregistrement
d'approbation. Aucun n'apparaît dans les arguments des outils, dans
leurs réponses, dans les messages d'erreur (ce sont sept phrases fixes)
ni dans les journaux de Claude Desktop : le canal d'erreur du serveur
est détourné dès le démarrage vers un fichier de *trace* sur votre
disque, lisible par vous seul, qui commence par la phrase « Peut
contenir du texte de document. Ne jamais partager ce fichier. » Huit
propriétés sont vérifiées par des tests, de « rien de confidentiel
n'atteint le modèle » à « aucune connexion sortante » — pour cette
dernière, un *garde-fou* logiciel, installé avant même que les lecteurs
ne soient chargés, transforme toute tentative de connexion en erreur
avant qu'un paquet ne parte : Jude ne fait pas d'appel réseau par
conception, le garde-fou attrape les régressions.

**Le registre.** Chaque approbation est une ligne dans votre base de
données, avec l'empreinte, l'heure, votre nom d'utilisateur, et une
colonne *outcome* (« issue ») toujours remplie à la fin : `released`
(Claude a pris le texte), `refused` (le texte ne correspondait plus à
l'enregistrement), `withdrawn` (vous avez retiré l'approbation),
`expired` (Claude n'est pas venu dans les 30 minutes),
`lost_on_restart` (le serveur a été arrêté entre-temps). C'est ce que
vous montreriez à un bâtonnier ou à un DPO.

**Le mode smart dans le plugin.** Le mode *smart* ajoute, à la première
mention d'un pseudonyme, une étiquette de notoriété publique (« Org1 —
contrôleur d'accès désigné au titre du DMA »). Via le plugin, il ne
s'applique que si le dossier a été créé avec `--endpoint claude-desktop
--zr`, c'est-à-dire si *vous* attestez que le compte Claude Desktop
utilisé est sous un régime sans conservation (un compte grand public ne
l'est pas). Tout autre dossier est traité en mode *strict*, avec une
ligne qui le dit dans la fenêtre.

**Jude n'est pas une IA générative.** Ses lecteurs sont des règles
(adresses e-mail, IBAN, références d'affaires), votre dictionnaire par
dossier, et des modèles de *reconnaissance d'entités* (spaCy pour
l'anglais, le français et le néerlandais, GLiNER) qui classent des mots
— « ceci est un nom de personne » — sans rien rédiger. Analogie : un
correcteur orthographique, pas un rédacteur. Un passage dans une langue
pour laquelle Jude n'a pas de modèle (de l'allemand, par exemple) est
signalé en rouge plutôt que lu à moitié en silence. Le seul modèle
génératif prévu est un *second lecteur local* (Ollama, hors ligne) qui,
plus tard, relirait le texte masqué pour dire ce qu'il reconnaît
encore ; il n'enverrait rien et ne déciderait rien.

**Deux façons d'installer.** Soit `pip install -e ".[mcp]"` puis
`jude mcp install-claude-desktop`, qui inscrit Jude dans le fichier de
configuration de Claude Desktop (avec sauvegarde) et y recopie les
variables de votre terminal que Claude Desktop ne verrait pas sinon ;
soit un fichier `.mcpb` à double-cliquer, qui demande où est votre
exécutable `jude` et, facultativement, vos dossiers de données et de
cache. Dans les deux cas, `jude mcp doctor --as-desktop` vérifie
l'installation ligne par ligne, une fois comme votre terminal et une
fois dans l'environnement nu de Claude Desktop — c'est là qu'un modèle
présent pour l'un et absent pour l'autre se voit. Le `.mcpb` ne contient
ni Python ni modèles : c'est un pointeur vers le Jude que vous avez déjà
installé. Point non confirmé (**hypothèse**) : que Claude Desktop
remplace bien la variable `${user_config.jude_path}` dans la commande ;
d'ici là, l'installateur est la voie recommandée. N'utilisez qu'une des
deux voies : deux entrées lanceraient deux serveurs (le second s'arrête
seul, et le doctor signale le doublon).

**Ce que le navigateur peut encore faire.** La fenêtre de Jude est une
page dans votre navigateur. La traduction automatique, le correcteur et
le remplissage automatique sont désactivés par la page ; mais une
*extension* de navigateur qui a accès aux pages (un correcteur de
grammaire, un traducteur, un « assistant IA ») lit tout ce qui s'affiche.
Ouvrez Jude dans un profil de navigateur sans extension. La version
suivante utilisera une fenêtre sans navigateur.

**Et ChatGPT ? Et Mistral ?** Les deux rapports (3 novembre 2026) disent
la même chose : ni ChatGPT sur le web ni Le Chat — rebaptisé *Vibe* en
mai 2026, sans application de bureau — ne lancent un programme sur
votre machine. Ils n'acceptent que des *serveurs distants* : un serveur
sur Internet, en HTTPS, que leur infrastructure appelle. Un Jude
distant devrait donc être hébergé par le cabinet (ou passer par un
*tunnel*, un relais fourni par OpenAI par lequel transite chaque
requête), lire le document côté serveur, s'authentifier par *OAuth* (le
mécanisme « se connecter avec… » qui donne au service un jeton au nom
de l'avocat), et devenir un *sous-traitant* au sens du RGPD, avec un
contrat et une base écrite au titre de l'article 458. Chez OpenAI, la
*rétention zéro* (« nous n'enregistrons pas vos données ») n'existe que
pour l'API, pas pour ChatGPT ; chez Mistral, elle n'existe que pour
l'API sans état, pas pour Vibe. La nouvelle application de bureau
ChatGPT (macOS et Windows) peut, elle, lancer un serveur local, mais
seulement dans un espace de travail Business ou Enterprise, dans des
fils « exécutés localement » dont la liste n'est pas documentée, et la
conversation reste chez OpenAI. Recommandation : rien de tout cela en
v1 ; pour Mistral, la bonne porte est de l'utiliser *comme moteur
derrière Jude* (API européenne `api.eu.mistral.ai`, rétention zéro
demandée et obtenue, refus d'entraînement coché, modèles en
disponibilité générale plutôt qu'en « Public Preview » — pour ces
derniers, les conditions commerciales annulent le refus d'entraînement)
ou en local via Ollama, en refusant les modèles `:cloud` qui tournent
chez Ollama et non sur votre Mac ; la garde de Jude reste alors sur
votre machine. Toutes ces pages changent souvent : à revérifier le jour
où une décision se prend.

**Ce qui est une hypothèse.** La durée maximale d'un appel d'outil et la
taille maximale d'un résultat dans Claude Desktop (d'où les 30 secondes
et les 150 000 caractères, à mesurer en dix minutes après
l'installation) ; la substitution de variable dans le `.mcpb` ; le
dossier `Claude Extensions/` où le doctor cherche le bundle ; le sort
des abonnements ChatGPT Plus et Free ; le réglage d'entraînement par
défaut des comptes Mistral Pro ; l'octroi de la rétention zéro par
Mistral à un petit cabinet ; la portée de « Preview Models » dans les
conditions de Mistral. Tout le reste est écrit dans le code et vérifié
par les tests, ou lu sur les pages officielles citées.
