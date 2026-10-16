# Security Review: Creator Insights

## Scope

Standard current-state first-party repository audit before hardening; one independent baseline, architecture reviewer and focused investigator.

- Scan mode: repository
- Target kind: git_revision
- Target ID: target_sha256_6c84eab5f19d1d413fbebc34d776afee78f3ca9f52a21d722419e880742ffb7d
- Revision: 7e167cc53e1c8ce8c9d44ac9b2c7b0253a1a795f
- Inventory strategy: repository
- Included paths: .
- Excluded paths: none
- Scan context: User requested finding/fixing weaknesses and dedicated Obsidian documentation. Threat model generated from independent source review.

Limitations and exclusions:
- No live deployment/second-account exploit, third-party dependency audit, Git history or model deserialization in this scan.
- Configured worker capacity 4 including parent, rather than preferred 6; sufficient independent review completed.
- Hardening and tests follow this immutable pre-fix report.
- Excluded .venv/\*\*: Vendor code is outside first-party source audit; dependency advisory checks handled separately.
- Excluded artifacts/\*.{joblib,png}: Generated model/image are not implementation and were not deserialized.
- Excluded artifacts/\*.csv: Generated numeric data not audited row by row; all readers/writers/schema/HTML/CSV export controls were reviewed.
- Excluded .git/\*\*: Current-state review only; no revision history.
- Excluded data/\*\*: Local source dataset not audited row by row; fixed consumer and validation paths reviewed.

### Scan Summary

| Field | Value |
| --- | --- |
| Scan outcome | completed |
| Reportable findings | 1 |
| Severity mix | low: 1 |
| Confidence mix | high: 1 |
| Coverage | complete |
| Validation mode | Static source trace with independent parent validation |

Canonical artifacts: `scan-manifest.json`, `findings.json`, and `coverage.json`. This report is a deterministic projection of those files.

## Threat Model

Creator Insights is a single-operator Python research workspace for UCI Facebook Metrics. The normal repository-CWD Streamlit launch binds to 127.0.0.1, displays local data/reports, downloads CSV, saves themes, invokes a CrewAI Flow and optionally syncs Supabase snapshots. There is no application authentication (app.py:49,257; .streamlit/config.toml:1; docs/supabase.md:57). Flow runs analyst tools, verifies handoff, runs scientist tools and recalculates metrics (project_flow.py:93,118,140). Six no-argument tools dispatch deterministic Python; CLI/direct-script paths have distinct orchestration guarantees. Supabase is an optional server REST client, not a browser database client (supabase_store.py:26,46,83).

### Assets

- Source-relative data/dataset_Facebook.csv; artifacts/clean_data.csv, dataset_contract.json, handoff_manifest.json, model.joblib, predictions/split/training JSON and four Markdown reports. Fixed filenames derive from source paths (clean_data.py:8; dashboard_data.py:7-16; modeling_tools.py:14; train_model.py:14,215).
- Anthropic API key and billing authority: repository .env is loaded into environment, then MODEL and ANTHROPIC_API_KEY are passed to LLM. Normal crews max_tokens=4000 and max_iter=4 are not a global budget; test_agent uses 500 (analyst_crew.py:13-41; scientist_crew.py:13-41; test_agent.py:14).
- Supabase server authority: UI Streamlit secrets override by key, then existing environment, then .env; SUPABASE_SECRET_KEY has SERVICE_ROLE fallback. CLI does not load Streamlit secrets (app.py:88; supabase_store.py:26-38; sync_supabase.py:12). Values are never reproduced.
- Cloud snapshot confidentiality/integrity: public.creator_snapshots stores cleaned posts, training JSON and four selected reports. Raw source, binary model, logs and credential files are not uploaded by the builder (supabase_store.py:93-103; dashboard_data.py:10; docs/supabase.md:11).
- Host filesystem/process authority: UI actions overwrite shared artifacts and logs, replace .streamlit/config.toml and launch processes under the server OS account with inherited environment (app.py:70,263-284; dashboard_theme.py:56; training_tools.py:27).
- Provenance/status: fixed-file SHA-256 fingerprints, strict contracts, freshness checks and recalculated saved prediction metrics protect specific integrity properties, not producer authenticity or all research conclusions (handoff_integrity.py:17,37; contract_validation.py:53; project_flow.py:23; evaluation_tools.py:32).

### Trust Boundaries

- Local TCP client -\> server: loopback identifies a host, not an OS account. Another local user without filesystem permissions can reach data/reports, theme saves, paid Flow and optional cloud sync; no login/action owner check exists (.streamlit/config.toml:2; app.py:70,215,248,263,298).
- Browser -\> subprocess: fixed \[sys.executable, '-u', project_flow.py\], repository CWD, inherited environment, DEVNULL stdin, shared artifacts/latest_ui_run.log and 1800s timeout. No shell/user-controlled executable; no subprocess isolation, cross-process lock or explicit descendant cleanup (app.py:264-284).
- LLM -\> tools: six supplied no-argument functions, allow_delegation=False, sequential crews and memory=False restrict model capabilities, not OS principals. Tools dispatch fixed scripts/resources (analyst_crew.py:38,54,69,139; scientist_crew.py:38,52,66,129; analyst_tools.py:9; analysis_tools.py:48; contract_tools.py:52; modeling_tools.py:73; training_tools.py:65; evaluation_tools.py:116).
- Host -\> model provider: MODEL/key consumed by CrewAI; tool results carry aggregates, contract definitions, paths and metrics into agent context. Provider transport/retention/telemetry belongs to dependencies; verbose output goes to console/UI log. No credential isolation between teams (analyst_crew.py:25,105,136,144; scientist_crew.py:25,126; contract_tools.py:43; analysis_tools.py:34; training_tools.py:68).
- Operator-supplied fixed CSV -\> processing: selects seven columns, validates Paid, drops missing Paid; publication validates supported schema/data then seals handoff. Modeling inspection verifies fingerprints before schema/data checks (clean_data.py:9,14,26; contract_tools.py:30,40; modeling_tools.py:18; validate_data.py:8).
- Analyst -\> scientist: Flow and training_tools enforce handoff; both share OS identity/artifacts. Manifest only covers clean_data.csv and dataset_contract.json and is unsigned. Direct train_model.py validates schema/data without fingerprint check; direct crew scripts print raw results outside Flow freshness/report persistence checks (project_flow.py:119,140; training_tools.py:17; handoff_integrity.py:6,50; train_model.py:14-31; analyst_crew.py:148; scientist_crew.py:138).
- Persisted text -\> browser: four fixed local report filenames, cloud reports returned from snapshot, st.markdown without unsafe HTML; logs st.code. Streamlit owns browser sanitization; fixed CSS is the only st.html content. CSV export uses typed integers/allowed post types (dashboard_data.py:10,23,38; app.py:19,215,248,281; supabase_store.py:73).
- Server -\> configured HTTPS origin: operator-selected URL rejects path/query/fragment/userinfo and publishable key prefix. Fixed /rest/v1/creator_snapshots and /rpc/save_creator_snapshot routes; apikey and legacy Bearer headers; 30s timeout and sanitized expected errors (supabase_store.py:29-59). No browser-supplied URL.
- REST -\> SQL: RLS and revoked PUBLIC/anon/authenticated grants; service_role SELECT/INSERT/RPC EXECUTE. SECURITY INVOKER and empty search_path. SQL validates JSON types, positive matched row count and 64-hex ID but does not recompute content hash/full schema. RPC inserts with ON CONFLICT DO NOTHING; captured_at is server-generated, supplied timestamp ignored (supabase/migrations/20261016062319_creator_insights_workspace.sql:3-44; supabase_store.py:83-103).
- UI theme -\> global configuration: validated hex colors and dark boolean update cloned TOML and atomically replace source-relative .streamlit/config.toml. Export currently includes whole TOML. No current secrets in that file. Filters/colors/cloud cache are session-local; local data cache is global (dashboard_theme.py:10,31,56; app.py:30,44,79,115).
- CLI/UI cloud configuration distinction: UI reads st.secrets; sync_supabase.py only env/.env. --check stops after read-only connection test. Normal upload checks latest Flow status, handoff and metrics before separately rereading local data. SQL atomicity does not make filesystem capture transactional (sync_supabase.py:12-22; supabase_store.py:88-103).
- Cloud -\> dashboard: latest row ordered captured_at.desc,id.desc, limit=1; validate_frame and row_count before session-local cache. No user/tenant predicate, consistent with single-operator design but app authentication is missing (supabase_store.py:67-80; app.py:112-118).

### Attacker Capabilities

- Untrusted local OS account/process can reach loopback while owner runs server without direct read permission on owner's files. Capability gained is owner API budget, workspace data/writes and conditional cloud authority; remote reachability requires override/proxy/forwarding not established in source (.streamlit/config.toml:2; app.py:263,298).
- Data supplier can influence CSV only if operator installs it; provider/report source can influence rendered text. Neither is assumed to control Python source, env, credentials or the entire artifacts directory. Fixed tools/contracts/report names constrain transitions (README.md:60; clean_data.py:9; contract_validation.py:53).
- Anon/authenticated Supabase callers are denied by migration; holder of service secret or server OS account already has trusted authority, not a newly gained application privilege (migration:14,43).
- Modification of only a published data/contract file is detected; modification of both manifest and payload is outside unsigned hash authenticity guarantees (handoff_integrity.py:17,37; README.md:154).

### Security Objectives

- Constrain data and management actions to operator identity; loopback/filesystem ownership must not substitute for browser authentication (docs/supabase.md:55-57; app.py:263,298).
- Keep provider/subprocess authority restricted to configured model and fixed tools; no model-selected executable/path (analyst_crew.py:25; analyst_tools.py:10; analysis_tools.py:16; training_tools.py:27).
- Reject incompatible contracts/data and changed handoff before orchestrated modeling regardless of model claims (contract_validation.py:53; validate_data.py:8; modeling_tools.py:18; project_flow.py:128).
- Require fresh outputs, nonempty correctly ended reports and independently recalculated metrics before completed Flow (project_flow.py:23,168; evaluation_tools.py:64).
- Make cloud writes explicit/coherent, validate handoff/evaluation and latest status, preserve idempotence and deny public database roles (supabase_store.py:88,96; migration:14,35).
- Keep credentials out of browser/error payloads and normal cloud snapshots (supabase_store.py:23,54,96; docs/supabase.md:11).

### Assumptions

- User asked to find weaknesses, harden and document in dedicated Obsidian. Source audit precedes remediation; no live exploitation, model requests or cloud operations.
- Documented local single-operator deployment; no dedicated live Supabase project or live grants verified (README.md:17; docs/supabase.md:5,74). A separate hostile local account is a finding prerequisite, not an observed deployed attacker.
- Streamlit effective precedence is defaults/global/CWD config/environment/CLI. app.py reads source-relative theme config, which does not ensure server uses same config under arbitrary CWD/overrides. Loopback claim is conditional on launch (README.md:43,90,98; dashboard_theme.py:10; installed streamlit/config.py).
- Direct training and direct crew startup have weaker orchestration than full Flow, documented above; no model.joblib loading sink exists, only joblib.dump (train_model.py:215).
- Keys 'remaining in .env' is storage shorthand: dotenv loads env and LLM/subprocess consumers receive values. Same account hosts both crews; no OS sandbox (docs/obsidian/02 - ארכיטקטורה וסוכנים.md:40; analyst_crew.py:14,25; training_tools.py:27).
- Pre-hardening concurrency relies on operator prohibition, no lock or per-run staging; hash read checks do not transact the pipeline (README.md:106; docs/supabase.md:49; app.py:268; supabase_store.py:88).
- Snapshot immutability applies to normal hash/RPC insert path; SQL does not recompute hash and owners/external grants unverified. RPC timestamp comes from database (docs/supabase.md:15,22; migration:35).
- Baseline safely reviewed .env presence/ignore/permissions without disclosing or using credential. No tracked secret exposure found; Desktop ancestor 0700 protects local .env (0644). Exact provider destination, validity, telemetry and deployment behavior not verified. .env.example tracing flag is not enforced policy.
- Installed dependency source was consulted for configuration precedence only, not audited as first-party. requirements.txt pins versions but no advisory lookup was part of static scan.

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [Local OS users can invoke the owner's paid workflow without authentication](#finding-1) | low | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] Local OS users can invoke the owner's paid workflow without authentication

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | Independent baseline and parent source trace confirm no authentication gate before protected data/actions. No live second-user exploitation or billable run was attempted. |
| Category | Missing authentication for privileged local service operations |
| CWE | CWE-306 |
| Affected lines | app.py:263-269, app.py:70-79, app.py:111-123, app.py:281-304, analyst_crew.py:12-28, scientist_crew.py:12-28, .streamlit/config.toml:1-3 |

#### Summary

While the owner runs the loopback dashboard, another local OS account can open it and start the full workflow, overwrite workspace outputs/theme, and read reports. Optional Supabase operations also run with server authority. This does not establish remote Internet exposure or arbitrary command execution.

#### Root Cause

The dashboard treats a loopback browser session as the operator. The System button directly starts project_flow.py, whose crew factories load the owner's credential and write the shared artifacts. The same absent gate covers theme saves, reports, logs and optional service-role cloud operations.

**Host-only TCP binding** — `.streamlit/config.toml:1-3`

Loopback restricts network hosts but does not authenticate the OS account opening a browser session.

```
[server]
address = "127.0.0.1"
headless = true
```

**Unauthenticated paid workflow trigger** — `app.py:263`

Any session reaching the System page can submit this action; no identity check precedes it.

```
        if st.button("הפעלת התהליך המלא", icon=":material/play_arrow:", type="primary", width="stretch"):
```

**Server-side execution** — `app.py:269`

The fixed command executes under the server owner's account and environment; fixed argv prevents injection but does not authorize the caller.

```
                        process = subprocess.run([sys.executable, "-u", str(ARTIFACTS.parent / "project_flow.py")], cwd=ARTIFACTS.parent, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=1800)
```

**Owner credential used for LLM calls** — `analyst_crew.py:25-29`

The workflow consumes the owner's API credential, loaded from the project .env at line 14. The scientist factory uses the same pattern.

```
    llm = LLM(
        model=os.environ["MODEL"],
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=4000,
    )
```

#### Validation

No login or authorization check precedes app.py data loading and action handlers. The owner-only filesystem is reachable through an unauthenticated local TCP service. A second local account is the required attacker prerequisite, not an assumed Internet deployment.

Validation method: independent static source review and parent source trace

**Host-only TCP binding** — `.streamlit/config.toml:1-3`

Loopback restricts network hosts but does not authenticate the OS account opening a browser session.

```
[server]
address = "127.0.0.1"
headless = true
```

**Unauthenticated paid workflow trigger** — `app.py:263`

Any session reaching the System page can submit this action; no identity check precedes it.

```
        if st.button("הפעלת התהליך המלא", icon=":material/play_arrow:", type="primary", width="stretch"):
```

**Server-side execution** — `app.py:269`

The fixed command executes under the server owner's account and environment; fixed argv prevents injection but does not authorize the caller.

```
                        process = subprocess.run([sys.executable, "-u", str(ARTIFACTS.parent / "project_flow.py")], cwd=ARTIFACTS.parent, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=1800)
```

**Owner credential used for LLM calls** — `analyst_crew.py:25-29`

The workflow consumes the owner's API credential, loaded from the project .env at line 14. The scientist factory uses the same pattern.

```
    llm = LLM(
        model=os.environ["MODEL"],
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=4000,
    )
```

Limitations:
- No live exploitation or API expenditure; actual presence of another untrusted OS account is unknown.
- Current cloud configuration is absent, so cloud impact is conditional.

#### Dataflow

Local browser session -\> unauthenticated System button -\> fixed subprocess -\> owner API credential and artifacts.

- **Source:** Local browser action

- **Sink:** Owner process and LLM billing

- **Outcome:** Unauthorized API spend and workspace modifications

**Host-only TCP binding** — `.streamlit/config.toml:1-3`

Loopback restricts network hosts but does not authenticate the OS account opening a browser session.

```
[server]
address = "127.0.0.1"
headless = true
```

**Unauthenticated paid workflow trigger** — `app.py:263`

Any session reaching the System page can submit this action; no identity check precedes it.

```
        if st.button("הפעלת התהליך המלא", icon=":material/play_arrow:", type="primary", width="stretch"):
```

**Server-side execution** — `app.py:269`

The fixed command executes under the server owner's account and environment; fixed argv prevents injection but does not authorize the caller.

```
                        process = subprocess.run([sys.executable, "-u", str(ARTIFACTS.parent / "project_flow.py")], cwd=ARTIFACTS.parent, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=1800)
```

**Owner credential used for LLM calls** — `analyst_crew.py:25-29`

The workflow consumes the owner's API credential, loaded from the project .env at line 14. The scientist factory uses the same pattern.

```
    llm = LLM(
        model=os.environ["MODEL"],
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=4000,
    )
```

#### Reachability

Requires a separate untrusted local OS account while the owner runs the server; loopback does not identify the account. No remote access is assumed.

- **Attacker:** Untrusted local OS account

- **Entry point:** http://127.0.0.1:8501

- **Outcome:** Owner-side operations

#### Severity

**Low** — The missing identity check permits owner-side writes and paid API calls, but exploitation requires an untrusted local account on the same host while the server runs. Default loopback binding materially constrains likelihood.

Remote exposure would increase severity; a dedicated trusted single-user host reduces the practical risk.

#### Remediation

Require a high-entropy owner-held access token before rendering any private data or action. Fail closed, compare tokens in constant time, bind session authentication to the current token for rotation, support logout, and retain loopback/origin protections.

Tests:
- An unauthenticated or incorrect-token session cannot load local/cloud data or reach actions.
- Correct token allows ordinary dashboard use; logout and token rotation revoke access.

## Reviewed Surfaces

| Surface | Risk Area | Outcome | Notes |
| --- | --- | --- | --- |
| Local management operations and diagnostic/config exports | not recorded | Reported | Baseline local-account finding validated by parent. Loopback is host isolation, not OS-user authentication; app.py:263-269 reaches owner's subprocess/API authority. Other reviewed gaps are defense-in-depth: raw error/log persistence, full-config export, overlapping runs, descendant timeouts. No separate secret disclosure was established. |
| Supabase API credentials and SQL authorization | not recorded | No issue found | supabase_store.py:20-23,46-59 hides credentials in repr and expected errors. Migration uses RLS, revokes public/anon/authenticated, SECURITY INVOKER and restricted execute. Live service not contacted. |
| Agent tools, subprocesses and data/contract/model pipeline | not recorded | No issue found | All first-party Python files fully reviewed. Fixed no-argument tools and shell-free argv reject command/path injection hypotheses. Strict contract and fixed handoff filenames; direct training schema-only distinction retained. No joblib/pickle load sink. Report HTML escapes tables; dashboard Markdown has unsafe HTML disabled. Shared writes, timeouts and validation/read races are hardening needs, not separate established attacker privilege gains. |
| Configuration, secrets, tests, documentation and generated text | not recorded | No issue found | Baseline fully reviewed all current tracked configuration, SQL, Python, docs and generated text/semantic logs. Parent independently reviewed executable paths, tests and migration. No tracked credential exposure. .env ignored with protected parent directory; local file mode can be tightened. Tests use explicit dummy keys. Numerical CSV rows and binary artifacts are data, not audited implementation. Earlier question about local OS-account boundary is resolved by finding local-dashboard-auth. |

## Open Questions And Follow Up

- Live Supabase authorization and dependency advisories are not verified by this source-only scan.
