# Jude for Claude Desktop — the `.mcpb` bundle

This folder is the source of `dist/jude-<version>.mcpb`, the one-click
installer for Claude Desktop. A `.mcpb` file is a zip archive with a
`manifest.json` at its root; Claude Desktop reads the manifest and starts
the server it describes. The user-facing page is
[docs/plugins.md](../docs/plugins.md); this file is for whoever builds
and releases the bundle.

```
mcpb/
├── manifest.json          what Claude Desktop reads
├── icon.png               256×256 PNG, shown in Settings › Extensions
└── server/jude-launcher   entry-point stub (never run by Desktop; see below)
```

The bundle contains **no Python, no language models and no Jude code**.
It is a pointer to a Jude you have already installed. The design
decision behind this is in `docs/plugins.md` §7: a bundle that shipped
Python and the models would weigh gigabytes and would still need the
spaCy and GLiNER weights downloaded once, with the network, in a
terminal where the user can see it happen (`jude mcp doctor --fix`).

## How the bundle finds `jude`

`manifest.json` declares three `user_config` entries: one required file,
two optional folders.

```json
"user_config": {
  "jude_path": {
    "type": "file",
    "title": "Jude executable",
    "description": "Pick the `jude` executable inside your Jude virtual environment (...)",
    "required": true
  },
  "jude_home": {
    "type": "directory",
    "title": "Jude data folder",
    "description": "Leave empty for the default ~/.jude; set it only if you run Jude with JUDE_HOME",
    "required": false
  },
  "hf_home": {
    "type": "directory",
    "title": "Hugging Face cache folder",
    "description": "Leave empty unless you moved the Hugging Face cache (HF_HOME) ...",
    "required": false
  }
}
```

At install time Claude Desktop shows a file picker for the first and a
folder picker for the other two. The chosen values are substituted into
the launch command and its environment:

```json
"mcp_config": {
  "command": "${user_config.jude_path}",
  "args": ["mcp"],
  "env": {
    "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1", "PYTHONUTF8": "1", "TOKENIZERS_PARALLELISM": "false",
    "JUDE_HOME": "${user_config.jude_home}",
    "HF_HOME": "${user_config.hf_home}"
  }
}
```

so Desktop starts `<your venv>/bin/jude mcp` (on Windows,
`<your venv>\Scripts\jude.exe mcp`) with the offline environment the
installer also sets: no Hugging Face downloads, no telemetry, UTF-8
stdio, single-threaded tokenizers.

**The two optional folders.** Claude Desktop starts the server from an
environment that is not your shell's: it does not read your
`.zshrc`, so a `JUDE_HOME` or `HF_HOME` you export there is invisible
to it. The two folder pickers are how the bundle learns about them. An
entry left empty arrives in the server as an *empty string*
(`JUDE_HOME=""`), which `huggingface_hub` and `os.path` would treat as
a path; the server therefore deletes every empty path variable at start
(`jude.mcp.env.normalise_env`, applied to `JUDE_HOME`, `HF_HOME`,
`HF_HUB_CACHE`, `HUGGINGFACE_HUB_CACHE`, `TRANSFORMERS_CACHE`,
`XDG_CACHE_HOME`) and the defaults apply: `~/.jude` and the standard
Hugging Face cache. Leave both empty unless you know you moved them.

Why "not a pyenv/asdf shim": a shim decides which Python to run from the
current directory's `.python-version` or `.tool-versions`. Claude Desktop
starts servers from a directory you do not control, so a shim may pick
an interpreter without Jude in it, or none. The file inside the venv
(`.venv/bin/jude`) has the interpreter path hard-wired in its first line
and works from anywhere. `jude mcp doctor --as-desktop` reproduces
Desktop's bare environment in a subprocess and tells you whether the
Jude that Desktop will start finds its models (§ Install below).

The entry point `server/jude-launcher` is a two-line POSIX shell stub
(`exec "${JUDE_BIN:-jude}" mcp "$@"`, mode 755). Claude Desktop never
runs it — `mcp_config.command` is what runs — but the MCPB format
requires an `entry_point` that exists in the archive, and
`mcpb validate` checks for it. It doubles as a manual launcher:
`JUDE_BIN=.venv/bin/jude mcpb/server/jude-launcher`.

## Build

```bash
python scripts/build_mcpb.py                # → dist/jude-<version>.mcpb
python scripts/build_mcpb.py --check        # validate only, write nothing
python scripts/build_mcpb.py --out build/   # another output directory
python scripts/build_mcpb.py --validate     # also run `npx @anthropic-ai/mcpb validate`
```

The script is standard library only (`zipfile`, `tomllib`, `json`). It
reads the version from `pyproject.toml`, and **refuses to build** —
printing every problem, exit code 1, nothing written — unless:

- `manifest_version`, `name`, `version` (semver, equal to
  `pyproject.toml`), `description`, `author.name` are present;
- `server.type` is `binary`, `node` or `python`; `server.entry_point`
  exists in `mcpb/` and is executable; `server.mcp_config.command` is set;
- every `user_config` entry has a `title`, a `description` and a `type`
  among `string`, `number`, `boolean`, `directory`, `file`; `required`,
  when given, is a boolean;
- every `${…}` inside `mcp_config` is one of the substitutions Claude
  Desktop performs (`${__dirname}`, `${pathSeparator}`, `${/}`,
  `${user_config.<declared key>}`) — a `${HOME}` would be shipped
  verbatim and is rejected; a `${user_config.<key>}` used as the
  `command` must be a *required* entry (an optional one left empty
  would make the command the empty string);
- `icon` is an existing PNG inside `mcpb/`;
- `tools`, when present, is a list of `{name, description}` without
  duplicates.

The archive is written with DEFLATE level 9, Unix modes in each member's
`external_attr`, the entry point forced to `0755`, `manifest.json` first,
then checked with `zipfile.testzip()` before it is moved into `dist/`
(`dist/` is in `.gitignore`). `README.md` and dotfiles under `mcpb/` are
left out of the archive.

`--validate` runs `npx --yes @anthropic-ai/mcpb validate mcpb/manifest.json`
when `npx` is on the PATH. That **downloads an npm package** — a network
call, in your terminal, by you; the Jude server itself never makes one.
This check is for CI before a release: the substitution of
`${user_config.*}` inside `command` (rather than inside `args`) is the
one point of the manifest not yet confirmed against the validator, which
is why the installer below stays the documented primary route until it is.

Release: attach `dist/jude-<version>.mcpb` to the GitHub Release of the
same version. The bundle is self-hosted; it is not submitted to a
directory.

## Install

**From the file** — double-click `jude-<version>.mcpb`, or in Claude
Desktop open *Settings › Extensions › Advanced settings › Install
Extension…* and choose the file. When asked for *Jude executable*, pick
`<your Jude checkout>/.venv/bin/jude`; leave *Jude data folder* and
*Hugging Face cache folder* empty unless you moved them. Restart Claude
Desktop. Then, in a terminal:

```bash
jude mcp doctor --as-desktop   # the same checks, run in the bare environment Desktop uses
```

`--as-desktop` re-runs the checks in a subprocess whose environment is
only `HOME`, `USER`, a minimal `PATH` (on Windows `SystemRoot`,
`USERPROFILE`, `APPDATA`, `PATH`), the `env` of the configured Jude
entry — the bundle's manifest `env`, or the config-file entry — and the
offline variables. When the two runs differ, both are printed under
*as this terminal* and *as Claude Desktop*. The doctor also looks for
the bundle itself (a `manifest.json` named `jude` in Claude Desktop's
extensions directory beside its configuration file — `Claude Extensions/`
on macOS, to be confirmed on the first bundle install) and reports
`OK (bundle)`; when both the bundle and a config-file entry exist it
reports `FIX duplicate: config entry and bundle; remove one`, because
two servers on one `jude.db` would be two writers (the second one to
start exits by itself — the server takes an instance lock — but you
want one, deliberately).

**Without the bundle (no npm, no file picker)** — the installer writes
the same server entry straight into Claude Desktop's configuration file,
with the absolute path of the interpreter it is run from:

```bash
pip install -e ".[mcp]"
jude mcp install-claude-desktop        # --dry-run shows the JSON and writes nothing
                                       # --uninstall removes the entry (with a backup)
                                       # --jude-home PATH sets JUDE_HOME in the entry
```

It writes `{"command": <this venv's python>, "args": ["-m", "jude.mcp"],
"env": {…}}`, where `env` is the offline set above plus every one of
`JUDE_HOME`, `HF_HOME`, `HF_HUB_CACHE`, `HUGGINGFACE_HUB_CACHE`,
`TRANSFORMERS_CACHE`, `XDG_CACHE_HOME`, `JUDE_MCP_LANGS`,
`JUDE_MCP_GLINER` that is set and non-empty in the shell you run it
from (`--jude-home` wins over the shell's `JUDE_HOME`). It prints the
variables it copied, so you see what Desktop will get. It runs
`jude mcp doctor` first and refuses to touch the file if a check fails
(`--skip-doctor` overrides). It backs up the existing file to
`claude_desktop_config.json.bak-<UTC timestamp>`, merges the `jude` key
into `mcpServers` without touching other servers, and writes atomically.
If the file is not valid JSON it stops with exit code 2 and leaves it
alone. It ends with "Restart Claude Desktop."

Configuration file locations: macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`;
Windows `%APPDATA%\Claude\claude_desktop_config.json`; Linux
`$XDG_CONFIG_HOME/Claude/` or `~/.config/Claude/`.

Both routes give the same result: Claude Desktop starts `jude mcp` over
stdio, on your machine, with no network. Use one route, not both.
Uninstall from *Settings › Extensions* (bundle) or
`jude mcp install-claude-desktop --uninstall` (installer).

## Keeping the manifest honest

- `version` must equal `[project].version` in `pyproject.toml`; the build
  fails otherwise. Bump both together.
- `tools` lists exactly the three tools the server registers:
  `prepare_document`, `fetch_approved`, `show_answer`. The descriptions
  here are what Settings › Extensions shows; the descriptions Claude
  reads come from the server's `strings.py` table at run time. Keep the
  two in step when the wording changes.
- `user_config` has exactly `jude_path` (required), `jude_home` and
  `hf_home` (optional directories). Every `${user_config.*}` in
  `mcp_config` must name one of them; the build checks it.
- `compatibility.platforms` is `["darwin", "win32"]`: the two platforms
  Claude Desktop runs on. The launcher stub is POSIX-only but is never run.
- `privacy_policies` is empty on purpose: the bundle sends nothing
  anywhere, so there is no policy to link. If a relay or a remote
  transport is ever added (see `docs/plugins.md` §9–10), that changes.
