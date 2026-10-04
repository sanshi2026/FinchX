# Repository maintenance

FinchX is a Python library. Keep the root focused on package metadata, README and
release notes, `src/`, `tests/fixtures/`, `docs/`, `examples/`, `tools/` and
`.github/workflows/`. Create local directories only when there is something to put
in them; empty placeholders are unnecessary.

| Path | Purpose and retention |
| --- | --- |
| `data/` | Explicitly saved source data or historical records. Treat as persistent; never clear as cache. |
| `cache/` | Rebuildable cache and newly collected research scratch files. Review for unique research findings before clearing. |
| `logs/` | Explicitly saved diagnostics. Review before archiving; exclude credentials and raw authenticated headers. |
| `.venv/` | Local environment; exclude from source delivery. |
| `build/`, `dist/`, `*.egg-info/` | Standard packaging output. Regenerate from the intended source; do not edit copied implementations. |
| `.pytest_cache/`, `__pycache__/`, `*.py[cod]` | Rebuildable test/runtime caches. |
| `.firecrawl/`, `.codex/`, `.agents/`, `docs/tasks/`, `AGENTS.md` | Local research or agent material. Ignore for delivery; retain unique findings and user-owned files. |
| `.github/` | Reviewed project workflows, included in delivery. |

Ignore rules define delivery boundaries; they do not authorize deletion. Before
cleanup, check tracked modifications/deletions, untracked files, ignored files,
every hidden directory/file including empty directories, and references to each
candidate. Preserve credentials/configuration, real data, research conclusions,
acceptance evidence and previous recovery backups. Archive confirmed generated
files outside the repository with a manifest of paths, sizes and checksums. Restore
only to absent destinations after checking the manifest; never overwrite newer work.

Before a release, review `git ls-files -c -o --exclude-standard`, `git status
--ignored`, and `git check-ignore -v` for hidden paths. Stage an explicit reviewed
file list. Packaging outputs and local recovery manifests do not belong in the
release commit. Check the wheel/sdist file inventory as well as Git status.

Development branches may iterate normally. Before handing a release version to
GitHub, consolidate its changes into one release commit named
`Release FinchX <version>` (for this version, `Release FinchX 2.0.3`). Avoid small
fix commits for the same release. Preserve earlier released commits and tags.
If a pushed commit needs a CI fix, report the conflict with the one-commit rule;
do not force-push without explicit authorization. Commit/push authorization alone
does not authorize tags, GitHub Releases or package publication.

The local `AGENTS.md` records these operating instructions and stays ignored;
this public document records the delivery policy without local research material.
Branch/pull-request CI runs tests and packaging checks without publishing.
The existing Release workflow publishes to PyPI only after an authorized GitHub
Release, and validates the same tag/version/commit through its required jobs.
Verify branch, tag, Release, package/workflow and tested artifacts agree.

## Storage compatibility

Collector cache policy is disabled by default. Article details use a process-local
memory cache. A persistent `SQLiteStorage` is created only when a caller explicitly
constructs it; it is not a repository cache directory created during import.

The current storage JSON format is `finchx.storage.json.v1`. Its allow-listed
Pydantic identifiers contain `module:qualname`. Existing model classes therefore
stay in their historical modules in 2.0.3. An import facade alone would not preserve
stored model identifiers if the actual class moved.

A future model migration should define stable type identifiers and explicit legacy
aliases, keep the allow-list, version the storage format if necessary, and verify
reading old stored objects before writing new ones. Do not dynamically import
arbitrary database-provided classes. This is a future migration plan, not a storage
format change in 2.0.3.
