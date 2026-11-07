"""
SECURITY AUDIT REPORT - DATAMIND PLATFORM

════════════════════════════════════════════════════════
1.1 — Input Flow Map
════════════════════════════════════════════════════════
File Upload Flow:
- filename (uploaded_file.name): Stored in session_state, used in file_loader.py when persisting -> [RISK] (needs sanitization)
- file bytes (uploaded_file.getvalue()): Passed directly to pd.read_csv / UniversalFileLoader -> [RISK]
- File content/structure: DataFrame stored in SQLite -> schema reflection -> potentially passed to LLMs -> [RISK]

Chat Input Flow:
- User text: Passed to st.chat_input() -> handle_chat_query() -> Orchestrator -> LLM via prompt string -> [RISK]

Auth Inputs Flow:
- username, email, password: -> auth.register_user() -> bcrypt & SQLite parameter -> [SAFE] against SQLi, but [RISK] for length/null bypasses.

URL/Query Params:
- st.query_params.get("st"): Used strictly for session token validation -> [SAFE]

════════════════════════════════════════════════════════
1.2 — Database Query Audit
════════════════════════════════════════════════════════
- All SQL commands (SELECT, INSERT, UPDATE, DELETE) inside `database.py` safely use sqlite parameterized format -> [PARAMETERIZED].
- Example: "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
- Safe update patterns with + operations safely evaluated by DB -> e.g., UPDATE users SET failed_attempts = failed_attempts + 1.

FSTRING/CONCAT violations:
- None detected inside actual SQL execution paths.
- Some f-strings are used for dictionary keys and logging, but NO f-strings are interpolated natively into sqlite query executions -> [SAFE].

════════════════════════════════════════════════════════
1.3 — File Operation Audit
════════════════════════════════════════════════════════
- config.py & database.py: os.path.join(DATA_DIR, ...).
- datamind/memory/session.py: os.path.join(UPLOADS_DIR, file_hash). `file_hash` is cryptographically built -> [SAFE].
- No direct user-provided paths supplied natively to open().
- General evaluation: [SAFE], but filename caching (e.g. current_file_name display) [PATH_TRAVERSAL_RISK] if exposed anywhere.

════════════════════════════════════════════════════════
1.4 — LLM Prompt Audit
════════════════════════════════════════════════════════
- datamind/agent/summary_agent.py: user_prompt uses raw `stats_json` via f-string -> [INJECTION_RISK].
- datamind/agent/analyst_agent.py: Includes dynamic raw dataset subsets into user queries -> [INJECTION_RISK].
- datamind/memory/learner.py: Raw data patterns pushed statically -> [INJECTION_RISK].
- datamind/tools/ml_runner.py: Passes cluster characteristics directly into prompt variable natively -> [INJECTION_RISK].

════════════════════════════════════════════════════════
1.5 — Authorization Audit
════════════════════════════════════════════════════════
- database.py exposes fetch primitives referencing `global_file_id` (e.g., `SELECT * FROM global_files`).
- DataManager access uses checks, but underlying agent endpoints via `active_file_id` heavily depend on session bindings rather than strict DB ownership re-checks -> [IDOR_RISK].
"""
