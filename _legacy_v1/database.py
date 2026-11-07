"""
DataMind SaaS - Database Management System
Hardened SQLite implementation with connection pooling (WAL mode) and multi-user isolation.
"""

import sqlite3
import os
import logging
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

# Constants
from config import DB_PATH
os.makedirs("data", exist_ok=True)

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # dict-like row access
        
        # Critical pragmas - run on EVERY new connection
        conn.execute("PRAGMA journal_mode=WAL")       # concurrent reads+writes
        conn.execute("PRAGMA foreign_keys=ON")        # enforce FK constraints
        conn.execute("PRAGMA synchronous=NORMAL")     # safe + faster than FULL
        conn.execute("PRAGMA cache_size=-64000")      # 64MB page cache
        conn.execute("PRAGMA temp_store=MEMORY")      # temp tables in RAM
        
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"DB error: {e}", exc_info=True)
        raise
    finally:
        if conn:
            conn.close()

def initialize_database():
    """Initializes the multi-user SaaS schema with security indexes."""
    with get_db_connection() as conn:
        # System config table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Users table with lockout + session support
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                failed_attempts INTEGER DEFAULT 0,
                lockout_until TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                last_active TIMESTAMP NULL
            )
        """)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")

        # Session tokens
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                ip_hint TEXT NULL,
                is_revoked INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")

        # Password reset tokens (hashed)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Audit log
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                event_type TEXT NOT NULL,
                event_detail TEXT NULL,
                ip_hint TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, created_at)")

        # Global files
        conn.execute("""
            CREATE TABLE IF NOT EXISTS global_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT UNIQUE NOT NULL,
                original_filename TEXT NOT NULL,
                schema_fingerprint TEXT NOT NULL,
                row_count INTEGER,
                col_count INTEGER,
                detected_domain TEXT DEFAULT 'generic',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_global_files_hash ON global_files(file_hash)")

        # User file references
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                global_file_id INTEGER NOT NULL REFERENCES global_files(id),
                display_name TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, global_file_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_files_user ON user_files(user_id)")

        # Analysis memory
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                global_file_id INTEGER NOT NULL REFERENCES global_files(id),
                query TEXT NOT NULL,
                intent TEXT,
                agent_used TEXT,
                response_summary TEXT,
                full_response TEXT,
                artifact_type TEXT,
                artifact_data TEXT,
                was_helpful INTEGER DEFAULT -1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_user_file ON analysis_memory(user_id, global_file_id, created_at)")

        # Learned patterns
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                global_file_id INTEGER NOT NULL REFERENCES global_files(id),
                pattern_type TEXT NOT NULL,
                pattern_description TEXT NOT NULL,
                columns_involved TEXT,
                confidence_score REAL DEFAULT 0.7,
                verification_count INTEGER DEFAULT 1,
                is_verified INTEGER DEFAULT 0,
                decay_weight REAL DEFAULT 1.0,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_user_file 
            ON learned_patterns(user_id, global_file_id, is_verified DESC, decay_weight DESC)
        """)

        # Prediction history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                global_file_id INTEGER NOT NULL REFERENCES global_files(id),
                target_column TEXT,
                task_type TEXT,
                model_used TEXT,
                accuracy_score REAL,
                f1_score REAL,
                rmse REAL,
                feature_importances TEXT,
                prediction_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_user_file ON prediction_history(user_id, global_file_id)")

        # Chat history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                global_file_id INTEGER NOT NULL REFERENCES global_files(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tier INTEGER,
                intent TEXT,
                latency_ms INTEGER,
                is_lab_artifact INTEGER DEFAULT 0,
                lab_target TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_file ON chat_history(user_id, global_file_id, created_at)")

        # Analytical Cache (Carry over from previous schema if needed, but adding user-scoped version or keeping global if preferred)
        # The prompt doesn't explicitly mention analytical_cache, but it's used in and session.py.
        # I'll keep it as a shared resource for now or adapt.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analytical_cache (
                global_file_id INTEGER PRIMARY KEY REFERENCES global_files(id) ON DELETE CASCADE,
                summary_text TEXT,
                viz_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

# --- Core DB Methods ---

# Users
def create_user(username, email, password_hash) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        return cursor.lastrowid

def get_user_by_email(email) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_username(username) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_last_login(user_id):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))

def update_last_active(user_id):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))

def increment_failed_attempts(email) -> int:
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET failed_attempts = failed_attempts + 1 WHERE email = ? COLLATE NOCASE", (email,))
        cursor = conn.execute("SELECT failed_attempts FROM users WHERE email = ? COLLATE NOCASE", (email,))
        row = cursor.fetchone()
        return row['failed_attempts'] if row else 0

def reset_failed_attempts(email):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET failed_attempts = 0, lockout_until = NULL WHERE email = ? COLLATE NOCASE", (email,))

def set_lockout(email, lockout_until_timestamp):
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET lockout_until = ? WHERE email = ? COLLATE NOCASE", (lockout_until_timestamp, email))

def get_lockout_status(email) -> Dict:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT lockout_until, failed_attempts FROM users WHERE email = ? COLLATE NOCASE", (email,))
        row = cursor.fetchone()
        if not row:
            return {"is_locked": False, "lockout_until": None, "failed_attempts": 0}
        
        lockout_until = row['lockout_until']
        if lockout_until:
            # Parse TIMESTAMP if it's a string
            if isinstance(lockout_until, str):
                try:
                    lockout_until = datetime.fromisoformat(lockout_until.replace('Z', '+00:00'))
                except ValueError:
                    lockout_until = None
            
            is_locked = lockout_until > datetime.now(timezone.utc) if lockout_until else False
        else:
            is_locked = False
            
        return {"is_locked": is_locked, "lockout_until": lockout_until, "failed_attempts": row['failed_attempts']}

# Sessions
def create_session(user_id, session_token, expires_at) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO user_sessions (user_id, session_token, expires_at) VALUES (?, ?, ?)",
            (user_id, session_token, expires_at)
        )
        return cursor.lastrowid

def get_session(session_token) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM user_sessions 
            WHERE session_token = ? AND is_revoked = 0 AND expires_at > CURRENT_TIMESTAMP
        """, (session_token,))
        row = cursor.fetchone()
        return dict(row) if row else None

def refresh_session(session_token):
    new_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE user_sessions SET last_active = CURRENT_TIMESTAMP, expires_at = ?
            WHERE session_token = ?
        """, (new_expiry, session_token))

def revoke_session(session_token):
    with get_db_connection() as conn:
        conn.execute("UPDATE user_sessions SET is_revoked = 1 WHERE session_token = ?", (session_token,))

def revoke_all_user_sessions(user_id):
    with get_db_connection() as conn:
        conn.execute("UPDATE user_sessions SET is_revoked = 1 WHERE user_id = ?", (user_id,))

def cleanup_expired_sessions():
    with get_db_connection() as conn:
        conn.execute("DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP OR is_revoked = 1")

# Audit
def log_event(user_id, event_type, event_detail=None, ip_hint=None):
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO audit_log (user_id, event_type, event_detail, ip_hint)
            VALUES (?, ?, ?, ?)
        """, (user_id, event_type, event_detail, ip_hint))

# Password reset
def create_reset_token(user_id, token_hash, expires_at) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token_hash, expires_at))
        return cursor.lastrowid

def get_reset_token(token_hash) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM password_reset_tokens 
            WHERE token_hash = ? AND used = 0 AND expires_at > CURRENT_TIMESTAMP
        """, (token_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None

def consume_reset_token(token_hash):
    with get_db_connection() as conn:
        conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE token_hash = ?", (token_hash,))

# Files
def get_global_file_by_hash(file_hash) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM global_files WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None

def insert_global_file(file_hash, filename, fingerprint_json, row_count, col_count, domain) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO global_files (file_hash, original_filename, schema_fingerprint, row_count, col_count, detected_domain)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_hash) DO UPDATE SET
                original_filename = excluded.original_filename,
                schema_fingerprint = excluded.schema_fingerprint,
                row_count = excluded.row_count,
                col_count = excluded.col_count,
                detected_domain = excluded.detected_domain
            RETURNING id
        """, (file_hash, filename, fingerprint_json, row_count, col_count, domain))
        row = cursor.fetchone()
        return row['id']

def get_user_file_ref(user_id, global_file_id) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM user_files WHERE user_id = ? AND global_file_id = ?", (user_id, global_file_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_user_file_ref(user_id, global_file_id, display_name) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO user_files (user_id, global_file_id, display_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, global_file_id) DO UPDATE SET display_name = excluded.display_name
            RETURNING id
        """, (user_id, global_file_id, display_name))
        row = cursor.fetchone()
        return row['id']

def get_user_files(user_id) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT uf.*, gf.file_hash, gf.original_filename, gf.schema_fingerprint, 
                   gf.row_count, gf.col_count, gf.detected_domain
            FROM user_files uf
            JOIN global_files gf ON uf.global_file_id = gf.id
            WHERE uf.user_id = ?
            ORDER BY uf.uploaded_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

def delete_user_file_ref(user_id, global_file_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM user_files WHERE user_id = ? AND global_file_id = ?", (user_id, global_file_id))

def update_last_accessed(user_id, global_file_id):
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE user_files SET last_accessed = CURRENT_TIMESTAMP 
            WHERE user_id = ? AND global_file_id = ?
        """, (user_id, global_file_id))

# Patterns
def get_patterns_for_user_file(user_id, global_file_id, limit=10) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM learned_patterns 
            WHERE user_id = ? AND global_file_id = ?
            ORDER BY is_verified DESC, confidence_score DESC LIMIT ?
        """, (user_id, global_file_id, limit))
        return [dict(row) for row in cursor.fetchall()]

def upsert_pattern(user_id, global_file_id, pattern_type, description, columns_json, confidence) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO learned_patterns (user_id, global_file_id, pattern_type, pattern_description, columns_involved, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, global_file_id, pattern_description) DO UPDATE SET
                confidence_score = MAX(confidence_score, excluded.confidence_score),
                last_confirmed_at = CURRENT_TIMESTAMP
            RETURNING id
        """, (user_id, global_file_id, pattern_type, description, columns_json, confidence))
        row = cursor.fetchone()
        return row['id']

def update_pattern_decay(user_id=None):
    with get_db_connection() as conn:
        # Check system_config for last run
        cursor = conn.execute("SELECT value FROM system_config WHERE key = 'last_decay_run'")
        row = cursor.fetchone()
        last_run = datetime.fromisoformat(row['value'].replace('Z', '+00:00')) if row else datetime.min.replace(tzinfo=timezone.utc)
        
        if datetime.now(timezone.utc) - last_run > timedelta(hours=24):
            if user_id:
                conn.execute("UPDATE learned_patterns SET decay_weight = decay_weight * 0.95 WHERE user_id = ?", (user_id,))
            else:
                conn.execute("UPDATE learned_patterns SET decay_weight = decay_weight * 0.95")
            
            conn.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('last_decay_run', ?)", 
                         (datetime.now(timezone.utc).isoformat(),))

# Analysis
def save_analysis(user_id, global_file_id, query, intent, agent_used, summary, full_response, artifact_type=None, artifact_data=None) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO analysis_memory 
            (user_id, global_file_id, query, intent, agent_used, response_summary, full_response, artifact_type, artifact_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, (user_id, global_file_id, query, intent, agent_used, summary, full_response, artifact_type, artifact_data))
        row = cursor.fetchone()
        return row['id']

def get_analysis_history(user_id, global_file_id, limit=20) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM analysis_memory 
            WHERE user_id = ? AND global_file_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, global_file_id, limit))
        return [dict(row) for row in cursor.fetchall()]

def update_helpfulness(analysis_id, value):
    with get_db_connection() as conn:
        conn.execute("UPDATE analysis_memory SET was_helpful = ? WHERE id = ?", (value, analysis_id))
        
        if value == 0:
            # Reduce confidence of associated patterns
            cursor = conn.execute("SELECT user_id, global_file_id, created_at FROM analysis_memory WHERE id = ?", (analysis_id,))
            row = cursor.fetchone()
            if row:
                # Find patterns discovered within 1 minute of this analysis
                conn.execute("""
                    UPDATE learned_patterns 
                    SET confidence_score = confidence_score - 0.1
                    WHERE user_id = ? AND global_file_id = ? 
                    AND ABS(strftime('%s', discovered_at) - strftime('%s', ?)) < 60
                """, (row['user_id'], row['global_file_id'], row['created_at']))

# Predictions
def save_prediction(user_id, global_file_id, target_col, task_type, model_used, accuracy, f1, rmse, importances_json, summary) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO prediction_history 
            (user_id, global_file_id, target_column, task_type, model_used, accuracy_score, f1_score, rmse, feature_importances, prediction_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, (user_id, global_file_id, target_col, task_type, model_used, accuracy, f1, rmse, importances_json, summary))
        row = cursor.fetchone()
        return row['id']

def get_best_model(user_id, global_file_id, target_column) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM prediction_history 
            WHERE user_id = ? AND global_file_id = ? AND target_column = ?
            ORDER BY accuracy_score DESC, f1_score DESC LIMIT 1
        """, (user_id, global_file_id, target_column))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_prediction_history(user_id, global_file_id) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM prediction_history 
            WHERE user_id = ? AND global_file_id = ?
            ORDER BY created_at DESC
        """, (user_id, global_file_id))
        return [dict(row) for row in cursor.fetchall()]

# Chat history with cap
def save_chat_message(user_id, global_file_id, role, content, tier, intent, latency_ms, is_lab_artifact=0, lab_target=None):
    with get_db_connection() as conn:
        # Insert message
        conn.execute("""
            INSERT INTO chat_history 
            (user_id, global_file_id, role, content, tier, intent, latency_ms, is_lab_artifact, lab_target)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, global_file_id, role, content, tier, intent, latency_ms, is_lab_artifact, lab_target))
        
        # Cap enforcement: keep newest 500, delete oldest if over cap
        conn.execute("""
            DELETE FROM chat_history 
            WHERE user_id = ? AND global_file_id = ? 
            AND id NOT IN (
                SELECT id FROM chat_history 
                WHERE user_id = ? AND global_file_id = ? 
                ORDER BY created_at DESC LIMIT 500
            )
        """, (user_id, global_file_id, user_id, global_file_id))

def get_chat_history(user_id, global_file_id, limit=50, offset=0) -> List[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM chat_history 
            WHERE user_id = ? AND global_file_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, (user_id, global_file_id, limit, offset))
        rows = cursor.fetchall()
        return [dict(row) for row in reversed(rows)]

# Caching (Analytical)
def get_analytical_cache(global_file_id) -> Optional[Dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM analytical_cache WHERE global_file_id = ?", (global_file_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def upsert_analytical_cache(global_file_id, summary_text: str, viz_json: str) -> None:
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO analytical_cache (global_file_id, summary_text, viz_json)
            VALUES (?, ?, ?)
            ON CONFLICT(global_file_id) DO UPDATE SET
                summary_text = excluded.summary_text,
                viz_json = excluded.viz_json,
                updated_at = CURRENT_TIMESTAMP
        """, (global_file_id, summary_text, viz_json))

# Migration Logic (Phase 6)
def run_migrations():
    with get_db_connection() as conn:
        # Check if migration already ran
        cursor = conn.execute("SELECT value FROM system_config WHERE key = 'migration_v2_done'")
        result = cursor.fetchone()
        if result:
            return

        # Add any missing columns to existing tables
        migration_statements = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS lockout_until TIMESTAMP NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TIMESTAMP NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0",
        ]
        for stmt in migration_statements:
            try:
                conn.execute(stmt)
            except Exception:
                pass  # Column may already exist

        # Mark migration done
        conn.execute("""
            INSERT OR REPLACE INTO system_config (key, value, updated_at)
            VALUES ('migration_v2_done', '1', CURRENT_TIMESTAMP)
        """)
