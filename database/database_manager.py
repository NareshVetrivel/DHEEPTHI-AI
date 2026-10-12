"""
Database Manager Module

Handles all SQLite database operations
for ASTRA-AI.

Supports:

- Installed applications
- Application aliases
- Indexed files
- Indexed folders
- File and folder synchronization
- Context-aware conversation memory
- Persistent user context
- Command history
- Thread-safe database access

ASTRA-AI V1
"""

import os
import re
import time
import sqlite3
import threading

from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Union


class CommandRow(dict):
    """
    Dictionary representing a command_history row that also supports
    legacy positional tuple indexing (e.g. row[0], row[1], row[4]).
    """
    def __init__(self, data_dict, data_tuple):
        super().__init__(data_dict)
        self._tuple = tuple(data_tuple)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._tuple[key]
        return super().__getitem__(key)


class DatabaseManager:
    """
    Thread-safe SQLite Database Manager.
    """

    def __init__(self, database_path: Optional[Union[str, Path]] = None):

        # --------------------------------------
        # Database Lock
        # --------------------------------------

        self.lock = threading.RLock()

        # --------------------------------------
        # Project Root
        # --------------------------------------

        project_root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

        # --------------------------------------
        # Database Path
        # --------------------------------------

        if database_path is not None:
            self.database_path = Path(database_path)
        elif os.environ.get("DHEEPTHI_DATABASE_PATH"):
            self.database_path = Path(os.environ["DHEEPTHI_DATABASE_PATH"])
        else:
            self.database_path = (
                project_root /
                "database" /
                "astra.db"
            )

        # --------------------------------------
        # Ensure Database Directory Exists
        # --------------------------------------

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # --------------------------------------
        # Connect Database
        # --------------------------------------

        self.connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
            timeout=30
        )

        # --------------------------------------
        # Improve SQLite Concurrency
        # --------------------------------------

        self.connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        self.connection.execute(
            "PRAGMA synchronous=NORMAL"
        )

        self.cursor = self.connection.cursor()
        self.active_profile_id = "default"

        # --------------------------------------
        # Create Required Tables
        # --------------------------------------

        self.create_tables()

    # ==================================================
    # INTERNAL HELPERS
    # ==================================================

    def _normalize_path(
        self,
        full_path
    ):
        """
        Return a normalized absolute path.
        """

        try:

            return str(
                Path(full_path)
                .resolve()
            )

        except Exception:

            return str(
                Path(full_path)
            )

    # --------------------------------------------------

    def _now(self):
        """
        Return current timestamp.
        """

        return datetime.now().isoformat()

    # --------------------------------------------------
    # Commit
    # --------------------------------------------------

    def commit(self):
        """
        Commit all pending database changes.
        """

        with self.lock:

            if self.connection:

                self.connection.commit()

    # --------------------------------------------------
    # Batch Commit
    # --------------------------------------------------

    def batch_commit(self):
        """
        Commit pending bulk inserts.
        """

        self.commit()

    # ==================================================
    # DATABASE SETUP
    # ==================================================

    def create_tables(self):
        """
        Create all required ASTRA-AI tables.
        """

        with self.lock:

            # --------------------------------------
            # Installed Applications
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    name TEXT UNIQUE NOT NULL,

                    exe_name TEXT NOT NULL,

                    full_path TEXT NOT NULL,

                    source TEXT,

                    last_scanned TEXT

                )
                """
            )

            # --------------------------------------
            # Application Aliases
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS aliases (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    alias TEXT UNIQUE NOT NULL,

                    application_name TEXT NOT NULL

                )
                """
            )

            # --------------------------------------
            # Indexed Files
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS files (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    name TEXT NOT NULL,

                    extension TEXT,

                    full_path TEXT UNIQUE,

                    file_size INTEGER,

                    last_modified TEXT,

                    last_scanned TEXT

                )
                """
            )

            # --------------------------------------
            # Indexed Folders
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS folders (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    name TEXT NOT NULL,

                    full_path TEXT UNIQUE,

                    last_modified TEXT,

                    last_scanned TEXT

                )
                """
            )

            # ======================================
            # CONTEXT-AWARE CONVERSATION MEMORY
            # ======================================

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                conversation_context (

                    id INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                    user_command TEXT
                    NOT NULL,

                    assistant_response TEXT,

                    intent TEXT,

                    target TEXT,

                    context_data TEXT,

                    created_at TEXT
                    NOT NULL

                )
                """
            )

            # --------------------------------------
            # Persistent User Context
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                user_context (

                    id INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                    context_key TEXT
                    UNIQUE NOT NULL,

                    context_value TEXT,

                    updated_at TEXT
                    NOT NULL

                )
                """
            )

            # --------------------------------------
            # Command History
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                command_history (

                    id INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                    command TEXT
                    NOT NULL,

                    intent TEXT,

                    target TEXT,

                    status TEXT,

                    created_at TEXT
                    NOT NULL

                )
                """
            )

            # --------------------------------------
            # Emotional State (Singleton)
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                emotional_state (

                    id INTEGER
                    PRIMARY KEY CHECK (id = 1),

                    current_mood TEXT
                    NOT NULL DEFAULT 'neutral',

                    valence REAL
                    NOT NULL DEFAULT 0.5,

                    arousal REAL
                    NOT NULL DEFAULT 0.5,

                    rapport_level REAL
                    NOT NULL DEFAULT 0.7,

                    last_trigger TEXT,

                    updated_at TEXT
                    NOT NULL

                )
                """
            )

            # --------------------------------------
            # Emotion Logs
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                emotion_logs (

                    id INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                    timestamp TEXT
                    NOT NULL,

                    user_utterance TEXT
                    NOT NULL,

                    detected_stimulus TEXT
                    NOT NULL,

                    prev_mood TEXT
                    NOT NULL,

                    new_mood TEXT
                    NOT NULL,

                    valence_delta REAL
                    NOT NULL,

                    rationale TEXT

                )
                """
            )

            # --------------------------------------
            # Memory Episodes
            # --------------------------------------

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                memory_episodes (

                    id INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                    timestamp TEXT
                    NOT NULL,

                    summary TEXT
                    NOT NULL,

                    emotional_valence REAL
                    DEFAULT 0.5,

                    category TEXT
                    NOT NULL,

                    importance INTEGER
                    NOT NULL DEFAULT 3,

                    access_count INTEGER
                    NOT NULL DEFAULT 0,

                    last_accessed TEXT

                )
                """
            )

            # --------------------------------------
            # People & Identity Table
            # --------------------------------------
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    preferred_name TEXT,
                    relationship_to_dheepthi TEXT DEFAULT 'user',
                    relationship_to_primary_user TEXT,
                    is_primary_user INTEGER DEFAULT 0,
                    is_creator INTEGER DEFAULT 0,
                    identity_source TEXT DEFAULT 'explicit_user',
                    confidence TEXT DEFAULT 'high',
                    voice_profile_id TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_confirmed TEXT
                )
                """
            )

            # Safe schema evolution for user_context columns
            try:
                self.cursor.execute("PRAGMA table_info(user_context)")
                columns = [col[1] for col in self.cursor.fetchall()]
                if "category" not in columns:
                    self.cursor.execute("ALTER TABLE user_context ADD COLUMN category TEXT DEFAULT 'general'")
                if "source" not in columns:
                    self.cursor.execute("ALTER TABLE user_context ADD COLUMN source TEXT DEFAULT 'explicit_user'")
                if "confidence" not in columns:
                    self.cursor.execute("ALTER TABLE user_context ADD COLUMN confidence TEXT DEFAULT 'high'")
                if "importance" not in columns:
                    self.cursor.execute("ALTER TABLE user_context ADD COLUMN importance INTEGER DEFAULT 3")
                if "is_active" not in columns:
                    self.cursor.execute("ALTER TABLE user_context ADD COLUMN is_active INTEGER DEFAULT 1")
            except Exception:
                pass

            # Safe schema evolution for conversation_context columns
            try:
                self.cursor.execute("PRAGMA table_info(conversation_context)")
                c_columns = [col[1] for col in self.cursor.fetchall()]
                if "session_id" not in c_columns:
                    self.cursor.execute("ALTER TABLE conversation_context ADD COLUMN session_id TEXT")
                if "turn_id" not in c_columns:
                    self.cursor.execute("ALTER TABLE conversation_context ADD COLUMN turn_id TEXT")
                if "input_source" not in c_columns:
                    self.cursor.execute("ALTER TABLE conversation_context ADD COLUMN input_source TEXT DEFAULT 'voice'")
                if "turn_status" not in c_columns:
                    self.cursor.execute("ALTER TABLE conversation_context ADD COLUMN turn_status TEXT DEFAULT 'completed'")
                if "persistence_status" not in c_columns:
                    self.cursor.execute("ALTER TABLE conversation_context ADD COLUMN persistence_status TEXT DEFAULT 'committed'")
                if "extracted_memory_ids" not in c_columns:
                    self.cursor.execute("ALTER TABLE conversation_context ADD COLUMN extracted_memory_ids TEXT")
            except Exception:
                pass

            # Safe schema evolution for command_history columns
            try:
                self.cursor.execute("PRAGMA table_info(command_history)")
                ch_columns = [col[1] for col in self.cursor.fetchall()]
                if "session_id" not in ch_columns:
                    self.cursor.execute("ALTER TABLE command_history ADD COLUMN session_id TEXT")
                if "turn_id" not in ch_columns:
                    self.cursor.execute("ALTER TABLE command_history ADD COLUMN turn_id TEXT")
                if "entities" not in ch_columns:
                    self.cursor.execute("ALTER TABLE command_history ADD COLUMN entities TEXT")
                if "result_summary" not in ch_columns:
                    self.cursor.execute("ALTER TABLE command_history ADD COLUMN result_summary TEXT")
                if "error_summary" not in ch_columns:
                    self.cursor.execute("ALTER TABLE command_history ADD COLUMN error_summary TEXT")
                if "execution_time_ms" not in ch_columns:
                    self.cursor.execute("ALTER TABLE command_history ADD COLUMN execution_time_ms INTEGER DEFAULT 0")
            except Exception:
                pass

            # --------------------------------------
            # Permanent Personal Memories Table
            # --------------------------------------
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS personal_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    key TEXT,
                    value TEXT NOT NULL,
                    source_turn_id TEXT,
                    confidence TEXT DEFAULT 'high',
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # --------------------------------------
            # User Profiles Table (Per-User Isolation)
            # --------------------------------------
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    preferred_name TEXT,
                    use_preferred_name INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    is_creator INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Safe schema evolution for profile_id across all relevant tables
            try:
                self.cursor.execute("PRAGMA table_info(user_context)")
                u_cols = [col[1] for col in self.cursor.fetchall()]
                if "profile_id" not in u_cols:
                    self.cursor.execute("ALTER TABLE user_context ADD COLUMN profile_id TEXT DEFAULT 'default'")
            except Exception:
                pass

            try:
                self.cursor.execute("PRAGMA table_info(conversation_context)")
                cc_cols = [col[1] for col in self.cursor.fetchall()]
                if "profile_id" not in cc_cols:
                    self.cursor.execute("ALTER TABLE conversation_context ADD COLUMN profile_id TEXT DEFAULT 'default'")
            except Exception:
                pass

            try:
                self.cursor.execute("PRAGMA table_info(command_history)")
                ch_cols = [col[1] for col in self.cursor.fetchall()]
                if "profile_id" not in ch_cols:
                    self.cursor.execute("ALTER TABLE command_history ADD COLUMN profile_id TEXT DEFAULT 'default'")
            except Exception:
                pass

            try:
                self.cursor.execute("PRAGMA table_info(personal_memories)")
                pm_cols = [col[1] for col in self.cursor.fetchall()]
                if "profile_id" not in pm_cols:
                    self.cursor.execute("ALTER TABLE personal_memories ADD COLUMN profile_id TEXT DEFAULT 'default'")
            except Exception:
                pass

            try:
                self.cursor.execute("PRAGMA table_info(people)")
                p_cols = [col[1] for col in self.cursor.fetchall()]
                if "profile_id" not in p_cols:
                    self.cursor.execute("ALTER TABLE people ADD COLUMN profile_id TEXT DEFAULT 'default'")
            except Exception:
                pass

            try:
                self.cursor.execute("PRAGMA table_info(memory_episodes)")
                me_cols = [col[1] for col in self.cursor.fetchall()]
                if "profile_id" not in me_cols:
                    self.cursor.execute("ALTER TABLE memory_episodes ADD COLUMN profile_id TEXT DEFAULT 'default'")
            except Exception:
                pass

            # Create tasks table for task & commitment memory layer
            try:
                self.cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT UNIQUE NOT NULL,
                        description TEXT NOT NULL,
                        deadline TEXT,
                        status TEXT DEFAULT 'active',
                        source_turn_id TEXT,
                        profile_id TEXT DEFAULT 'default',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
            except Exception:
                pass

            # Ensure default profile exists
            try:
                self.cursor.execute("SELECT id FROM user_profiles WHERE profile_id = 'default' LIMIT 1")
                if not self.cursor.fetchone():
                    now_ts = self._now()
                    self.cursor.execute(
                        """
                        INSERT INTO user_profiles
                        (profile_id, display_name, preferred_name, use_preferred_name, is_active, is_creator, created_at, updated_at)
                        VALUES ('default', 'Default User', NULL, 1, 1, 0, ?, ?)
                        """,
                        (now_ts, now_ts)
                    )
            except Exception:
                pass

            # ======================================
            # INDEXES
            # ======================================

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_people_name
                ON people(name)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_people_person_id
                ON people(person_id)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_user_context_key
                ON user_context(context_key)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_files_name
                ON files(name)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_files_path
                ON files(full_path)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_folders_name
                ON folders(name)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_folders_path
                ON folders(full_path)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_context_created_at
                ON conversation_context(created_at)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_context_intent
                ON conversation_context(intent)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_history_created_at
                ON command_history(created_at)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_emotion_logs_timestamp
                ON emotion_logs(timestamp)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_memory_episodes_importance
                ON memory_episodes(importance)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_memory_episodes_timestamp
                ON memory_episodes(timestamp)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_conv_turn_id
                ON conversation_context(turn_id)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_conv_session_id
                ON conversation_context(session_id)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_cmd_turn_id
                ON command_history(turn_id)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_personal_mem_key
                ON personal_memories(key)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_personal_mem_cat
                ON personal_memories(category)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_personal_mem_turn
                ON personal_memories(source_turn_id)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_conv_profile_id
                ON conversation_context(profile_id)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_personal_mem_profile
                ON personal_memories(profile_id, category, status)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_user_context_profile
                ON user_context(profile_id, context_key)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_people_profile
                ON people(profile_id, name)
                """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_tasks_profile_status
                ON tasks(profile_id, status)
                """
            )

            # --------------------------------------
            # Seed Default Emotional State Singleton
            # --------------------------------------

            self.cursor.execute(
                """
                INSERT OR IGNORE INTO emotional_state
                (id, current_mood, valence, arousal, rapport_level, last_trigger, updated_at)
                VALUES (1, 'neutral', 0.5, 0.5, 0.7, 'init', ?)
                """,
                (
                    self._now(),
                )
            )

            self.connection.commit()

    # ==================================================
    # APPLICATION METHODS
    # ==================================================

    def insert_application(
        self,
        name,
        exe_name,
        full_path,
        source="SCANNER"
    ):

        try:

            with self.lock:

                self.cursor.execute(
                    """
                    INSERT OR REPLACE INTO
                    applications
                    (
                        name,
                        exe_name,
                        full_path,
                        source,
                        last_scanned
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        name.lower(),
                        exe_name,
                        self._normalize_path(
                            full_path
                        ),
                        source,
                        self._now()
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Application Insert Error : {error}"
            )

            return False

    # --------------------------------------------------

    def insert_alias(
        self,
        alias,
        application_name
    ):

        try:

            with self.lock:

                self.cursor.execute(
                    """
                    INSERT OR REPLACE INTO
                    aliases
                    (
                        alias,
                        application_name
                    )
                    VALUES (?, ?)
                    """,
                    (
                        alias.lower(),
                        application_name.lower()
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Alias Insert Error : {error}"
            )

            return False

    # --------------------------------------------------

    def get_application(
        self,
        name
    ):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    exe_name,
                    full_path
                FROM applications
                WHERE name = ?
                """,
                (
                    name.lower(),
                )
            )

            return self.cursor.fetchone()

    # --------------------------------------------------

    def get_alias(
        self,
        alias
    ):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    application_name
                FROM aliases
                WHERE alias = ?
                """,
                (
                    alias.lower(),
                )
            )

            return self.cursor.fetchone()

    # --------------------------------------------------

    def get_all_applications(self):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    exe_name,
                    full_path
                FROM applications
                ORDER BY name
                """
            )

            return self.cursor.fetchall()

    # --------------------------------------------------

    def application_exists(
        self,
        name
    ):

        with self.lock:

            self.cursor.execute(
                """
                SELECT 1
                FROM applications
                WHERE name = ?
                """,
                (
                    name.lower(),
                )
            )

            return (
                self.cursor.fetchone()
                is not None
            )

    # --------------------------------------------------

    def application_count(self):

        with self.lock:

            self.cursor.execute(
                """
                SELECT COUNT(*)
                FROM applications
                """
            )

            return self.cursor.fetchone()[0]

    # ==================================================
    # FILE METHODS
    # ==================================================

    def insert_file(
        self,
        name,
        extension,
        full_path,
        file_size,
        last_modified,
        commit=True
    ):

        try:

            full_path = (
                self._normalize_path(
                    full_path
                )
            )

            with self.lock:

                self.cursor.execute(
                    """
                    INSERT INTO files
                    (
                        name,
                        extension,
                        full_path,
                        file_size,
                        last_modified,
                        last_scanned
                    )
                    VALUES (?, ?, ?, ?, ?, ?)

                    ON CONFLICT(full_path)
                    DO UPDATE SET

                        name = excluded.name,

                        extension = excluded.extension,

                        file_size = excluded.file_size,

                        last_modified = excluded.last_modified,

                        last_scanned = excluded.last_scanned
                    """,
                    (
                        name.lower(),
                        extension.lower(),
                        full_path,
                        file_size,
                        last_modified,
                        self._now()
                    )
                )

                if commit:

                    self.connection.commit()

            return True

        except Exception as error:

            print(
                f"File Insert Error : {error}"
            )

            return False

    # --------------------------------------------------

    def get_file(
        self,
        name
    ):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    extension,
                    full_path
                FROM files
                WHERE name LIKE ?
                LIMIT 1
                """,
                (
                    f"%{name.lower()}%",
                )
            )

            return self.cursor.fetchone()

    # --------------------------------------------------

    def get_file_by_path(
        self,
        full_path
    ):

        full_path = (
            self._normalize_path(
                full_path
            )
        )

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    extension,
                    full_path
                FROM files
                WHERE full_path = ?
                """,
                (
                    full_path,
                )
            )

            return self.cursor.fetchone()

    # --------------------------------------------------

    def search_files(
        self,
        keyword
    ):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    extension,
                    full_path
                FROM files
                WHERE name LIKE ?
                ORDER BY name
                LIMIT 20
                """,
                (
                    f"%{keyword.lower()}%",
                )
            )

            return self.cursor.fetchall()

    # --------------------------------------------------

    def get_all_files(self):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    extension,
                    full_path
                FROM files
                ORDER BY name
                """
            )

            return self.cursor.fetchall()

    # --------------------------------------------------

    def search_by_extension(
        self,
        extension
    ):

        extension = extension.lower()

        if not extension.startswith("."):

            extension = "." + extension

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    extension,
                    full_path
                FROM files
                WHERE extension = ?
                ORDER BY name
                """,
                (
                    extension,
                )
            )

            return self.cursor.fetchall()

    # --------------------------------------------------

    def file_exists(
        self,
        full_path
    ):

        full_path = (
            self._normalize_path(
                full_path
            )
        )

        with self.lock:

            self.cursor.execute(
                """
                SELECT 1
                FROM files
                WHERE full_path = ?
                """,
                (
                    full_path,
                )
            )

            return (
                self.cursor.fetchone()
                is not None
            )

    # --------------------------------------------------

    def search_by_size(
        self,
        minimum_size_mb
    ):

        minimum_size = (
            minimum_size_mb
            * 1024
            * 1024
        )

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    extension,
                    full_path
                FROM files
                WHERE file_size >= ?
                ORDER BY file_size DESC
                """,
                (
                    minimum_size,
                )
            )

            return self.cursor.fetchall()

    # --------------------------------------------------

    def search_by_date(
        self,
        days
    ):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    extension,
                    full_path
                FROM files
                WHERE
                    julianday('now') -
                    julianday(last_modified) <= ?
                ORDER BY last_modified DESC
                """,
                (
                    days,
                )
            )

            return self.cursor.fetchall()

    # --------------------------------------------------

    def file_count(self):

        with self.lock:

            self.cursor.execute(
                """
                SELECT COUNT(*)
                FROM files
                """
            )

            return self.cursor.fetchone()[0]

    # --------------------------------------------------

    def update_file_name(
        self,
        old_path,
        new_name,
        new_path
    ):

        try:

            old_path = self._normalize_path(
                old_path
            )

            new_path = self._normalize_path(
                new_path
            )

            new_file = Path(
                new_path
            )

            if new_file.exists():

                file_size = (
                    new_file.stat()
                    .st_size
                )

                last_modified = (
                    datetime.fromtimestamp(
                        new_file.stat()
                        .st_mtime
                    )
                    .isoformat()
                )

            else:

                file_size = None

                last_modified = self._now()

            with self.lock:

                self.cursor.execute(
                    """
                    UPDATE files
                    SET

                        name = ?,

                        extension = ?,

                        full_path = ?,

                        file_size = ?,

                        last_modified = ?,

                        last_scanned = ?

                    WHERE full_path = ?
                    """,
                    (
                        (
                            new_name
                            or
                            new_file.stem
                        ).lower(),

                        new_file.suffix.lower(),

                        new_path,

                        file_size,

                        last_modified,

                        self._now(),

                        old_path
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Update File Name Error : {error}"
            )

            return False

    # --------------------------------------------------

    def update_file_path(
        self,
        old_path,
        new_path
    ):

        return self.update_file_name(
            old_path=old_path,
            new_name=Path(
                new_path
            ).stem,
            new_path=new_path
        )

    # --------------------------------------------------

    def delete_file(
        self,
        full_path
    ):

        try:

            full_path = (
                self._normalize_path(
                    full_path
                )
            )

            with self.lock:

                self.cursor.execute(
                    """
                    DELETE FROM files
                    WHERE full_path = ?
                    """,
                    (
                        full_path,
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Delete File DB Error : {error}"
            )

            return False

    # --------------------------------------------------

    def refresh_file(
        self,
        file_path,
        commit=True
    ):

        try:

            file = Path(
                file_path
            )

            if (
                not file.exists()
                or
                not file.is_file()
            ):

                return False

            return self.insert_file(

                name=file.stem,

                extension=file.suffix,

                full_path=str(file),

                file_size=(
                    file.stat()
                    .st_size
                ),

                last_modified=(
                    datetime.fromtimestamp(
                        file.stat()
                        .st_mtime
                    )
                    .isoformat()
                ),

                commit=commit
            )

        except Exception as error:

            print(
                f"Refresh File Error : {error}"
            )

            return False

    # --------------------------------------------------

    def delete_missing_file(
        self,
        full_path
    ):

        return self.delete_file(
            full_path
        )

    # --------------------------------------------------

    def clear_files(self):

        with self.lock:

            self.cursor.execute(
                "DELETE FROM files"
            )

            self.connection.commit()

    # ==================================================
    # FOLDER METHODS
    # ==================================================

    def insert_folder(
        self,
        name,
        full_path,
        last_modified=None,
        commit=True
    ):

        try:

            full_path = (
                self._normalize_path(
                    full_path
                )
            )

            folder_path = Path(
                full_path
            )

            if last_modified is None:

                if folder_path.exists():

                    last_modified = (
                        datetime.fromtimestamp(
                            folder_path.stat()
                            .st_mtime
                        )
                        .isoformat()
                    )

                else:

                    last_modified = self._now()

            with self.lock:

                self.cursor.execute(
                    """
                    INSERT INTO folders
                    (
                        name,
                        full_path,
                        last_modified,
                        last_scanned
                    )
                    VALUES (?, ?, ?, ?)

                    ON CONFLICT(full_path)
                    DO UPDATE SET

                        name = excluded.name,

                        last_modified =
                        excluded.last_modified,

                        last_scanned =
                        excluded.last_scanned
                    """,
                    (
                        name.lower(),

                        full_path,

                        last_modified,

                        self._now()
                    )
                )

                if commit:

                    self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Folder Insert Error : {error}"
            )

            return False

    # --------------------------------------------------

    def refresh_folder(
        self,
        folder_path,
        commit=True
    ):

        try:

            folder = Path(
                folder_path
            )

            if (
                not folder.exists()
                or
                not folder.is_dir()
            ):

                return False

            return self.insert_folder(

                name=folder.name,

                full_path=str(folder),

                last_modified=(
                    datetime.fromtimestamp(
                        folder.stat()
                        .st_mtime
                    )
                    .isoformat()
                ),

                commit=commit
            )

        except Exception as error:

            print(
                f"Refresh Folder Error : {error}"
            )

            return False

    # --------------------------------------------------

    def get_folder(
        self,
        name
    ):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    full_path
                FROM folders
                WHERE name LIKE ?
                LIMIT 1
                """,
                (
                    f"%{name.lower()}%",
                )
            )

            return self.cursor.fetchone()

    # --------------------------------------------------

    def get_folder_by_path(
        self,
        full_path
    ):

        full_path = (
            self._normalize_path(
                full_path
            )
        )

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    full_path
                FROM folders
                WHERE full_path = ?
                """,
                (
                    full_path,
                )
            )

            return self.cursor.fetchone()

    # --------------------------------------------------

    def search_folders(
        self,
        keyword
    ):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    full_path
                FROM folders
                WHERE name LIKE ?
                ORDER BY name
                LIMIT 20
                """,
                (
                    f"%{keyword.lower()}%",
                )
            )

            return self.cursor.fetchall()

    # --------------------------------------------------

    def get_all_folders(self):

        with self.lock:

            self.cursor.execute(
                """
                SELECT
                    name,
                    full_path
                FROM folders
                ORDER BY name
                """
            )

            return self.cursor.fetchall()

    # --------------------------------------------------

    def folder_exists(
        self,
        full_path
    ):

        full_path = (
            self._normalize_path(
                full_path
            )
        )

        with self.lock:

            self.cursor.execute(
                """
                SELECT 1
                FROM folders
                WHERE full_path = ?
                """,
                (
                    full_path,
                )
            )

            return (
                self.cursor.fetchone()
                is not None
            )

    # --------------------------------------------------

    def folder_count(self):

        with self.lock:

            self.cursor.execute(
                """
                SELECT COUNT(*)
                FROM folders
                """
            )

            return self.cursor.fetchone()[0]

    # --------------------------------------------------

    def update_folder_name(
        self,
        old_path,
        new_name,
        new_path
    ):

        try:

            old_path = self._normalize_path(
                old_path
            )

            new_path = self._normalize_path(
                new_path
            )

            with self.lock:

                self.cursor.execute(
                    """
                    UPDATE folders
                    SET

                        name = ?,

                        full_path = ?,

                        last_modified = ?,

                        last_scanned = ?

                    WHERE full_path = ?
                    """,
                    (
                        new_name.lower(),

                        new_path,

                        self._now(),

                        self._now(),

                        old_path
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Update Folder Name Error : {error}"
            )

            return False

    # --------------------------------------------------

    def update_folder_path(
        self,
        old_path,
        new_path
    ):

        try:

            new_folder = Path(
                new_path
            )

            return self.update_folder_name(

                old_path=old_path,

                new_name=new_folder.name,

                new_path=new_path
            )

        except Exception as error:

            print(
                f"Update Folder Path Error : {error}"
            )

            return False

    # --------------------------------------------------

    def delete_folder(
        self,
        full_path
    ):

        try:

            full_path = (
                self._normalize_path(
                    full_path
                )
            )

            with self.lock:

                self.cursor.execute(
                    """
                    DELETE FROM folders
                    WHERE full_path = ?
                    """,
                    (
                        full_path,
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Delete Folder DB Error : {error}"
            )

            return False

    # --------------------------------------------------

    def delete_missing_folder(
        self,
        full_path
    ):

        return self.delete_folder(
            full_path
        )

    # --------------------------------------------------

    def clear_folders(self):

        with self.lock:

            self.cursor.execute(
                "DELETE FROM folders"
            )

            self.connection.commit()

    # ==================================================
    # CONTEXT-AWARE MEMORY METHODS
    # ==================================================

    def add_conversation_context(
        self,
        user_command,
        assistant_response=None,
        intent=None,
        target=None,
        context_data=None,
        session_id=None,
        turn_id=None,
        input_source="voice",
        turn_status="completed",
        persistence_status="committed",
        extracted_memory_ids=None
    ):
        """
        Store one conversation interaction.

        context_data can contain additional
        information required for follow-up
        commands.
        """

        try:
            with self.lock:
                now = self._now()
                if turn_id:
                    self.cursor.execute(
                        "SELECT id FROM conversation_context WHERE turn_id = ? LIMIT 1",
                        (str(turn_id),)
                    )
                    existing = self.cursor.fetchone()
                    if existing:
                        self.cursor.execute(
                            """
                            UPDATE conversation_context
                            SET user_command = ?, assistant_response = ?, intent = ?,
                                target = ?, context_data = ?, session_id = ?,
                                input_source = ?, turn_status = ?, persistence_status = ?,
                                extracted_memory_ids = ?
                            WHERE id = ?
                            """,
                            (
                                str(user_command or ""),
                                str(assistant_response or ""),
                                intent,
                                target,
                                context_data,
                                session_id,
                                input_source,
                                turn_status,
                                persistence_status,
                                extracted_memory_ids,
                                existing[0]
                            )
                        )
                        self.connection.commit()
                        return True

                self.cursor.execute(
                    """
                    INSERT INTO
                    conversation_context
                    (
                        user_command,
                        assistant_response,
                        intent,
                        target,
                        context_data,
                        created_at,
                        session_id,
                        turn_id,
                        input_source,
                        turn_status,
                        persistence_status,
                        extracted_memory_ids
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(user_command or ""),
                        str(assistant_response or ""),
                        intent,
                        target,
                        context_data,
                        now,
                        session_id,
                        turn_id,
                        input_source,
                        turn_status,
                        persistence_status,
                        extracted_memory_ids
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:
            print(
                f"Conversation Context Error : "
                f"{error}"
            )
            return False

    def save_user_interaction(
        self,
        turn_id: str,
        user_command: str,
        session_id: Optional[str] = None,
        input_source: str = "voice",
        intent: Optional[str] = None,
        target: Optional[str] = None,
        context_data: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> bool:
        """
        Immediately persists raw finalized user transcript before assistant response
        or memory extraction is ready. Idempotent by turn_id.
        """
        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            with self.lock:
                now = self._now()
                self.cursor.execute(
                    "SELECT id FROM conversation_context WHERE turn_id = ? LIMIT 1",
                    (str(turn_id),)
                )
                existing = self.cursor.fetchone()
                if existing:
                    self.cursor.execute(
                        """
                        UPDATE conversation_context
                        SET user_command = ?, session_id = COALESCE(?, session_id),
                            input_source = COALESCE(?, input_source), intent = COALESCE(?, intent),
                            target = COALESCE(?, target), context_data = COALESCE(?, context_data),
                            profile_id = COALESCE(?, profile_id),
                            persistence_status = 'committed'
                        WHERE id = ?
                        """,
                        (str(user_command or ""), session_id, input_source, intent, target, context_data, target_profile, existing[0])
                    )
                else:
                    self.cursor.execute(
                        """
                        INSERT INTO conversation_context
                        (user_command, assistant_response, intent, target, context_data, created_at,
                         session_id, turn_id, input_source, turn_status, persistence_status, profile_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(user_command or ""),
                            "",
                            intent,
                            target,
                            context_data,
                            now,
                            session_id,
                            str(turn_id),
                            input_source,
                            "user_received",
                            "committed",
                            target_profile
                        )
                    )
                self.connection.commit()
                print(f"[MEMORY] Conversation turn persisted: turn_id={turn_id}")
                return True
        except Exception as error:
            print(f"[MEMORY] Persistence verification failed (save_user_interaction): {error}")
            return False

    def update_assistant_interaction(
        self,
        turn_id: str,
        assistant_response: str,
        turn_status: str = "completed",
        extracted_memory_ids: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> bool:
        """
        Updates the completed assistant response for an existing turn_id.
        If turn_id doesn't exist, inserts the interaction record.
        """
        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            with self.lock:
                now = self._now()
                self.cursor.execute(
                    "SELECT id FROM conversation_context WHERE turn_id = ? LIMIT 1",
                    (str(turn_id),)
                )
                existing = self.cursor.fetchone()
                if existing:
                    self.cursor.execute(
                        """
                        UPDATE conversation_context
                        SET assistant_response = ?, turn_status = ?,
                            extracted_memory_ids = COALESCE(?, extracted_memory_ids),
                            profile_id = COALESCE(?, profile_id),
                            persistence_status = 'committed'
                        WHERE id = ?
                        """,
                        (str(assistant_response or ""), str(turn_status), extracted_memory_ids, target_profile, existing[0])
                    )
                else:
                    self.cursor.execute(
                        """
                        INSERT INTO conversation_context
                        (user_command, assistant_response, intent, target, context_data, created_at,
                         session_id, turn_id, input_source, turn_status, persistence_status, extracted_memory_ids, profile_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "",
                            str(assistant_response or ""),
                            "conversation",
                            "",
                            "",
                            now,
                            None,
                            str(turn_id),
                            "voice",
                            str(turn_status),
                            "committed",
                            extracted_memory_ids,
                            target_profile
                        )
                    )
                self.connection.commit()
                print(f"[MEMORY] Assistant response persisted: turn_id={turn_id}")
                return True
        except Exception as error:
            print(f"[MEMORY] Persistence verification failed (update_assistant_interaction): {error}")
            return False

    def update_turn_status(self, turn_id: str, turn_status: str) -> bool:
        """
        Update the turn_status of an existing turn (e.g. 'completed', 'interrupted', 'error').
        """
        try:
            with self.lock:
                self.cursor.execute(
                    "UPDATE conversation_context SET turn_status = ? WHERE turn_id = ?",
                    (str(turn_status), str(turn_id))
                )
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Update Turn Status Error: {error}")
            return False

    def get_interaction_by_turn_id(self, turn_id: str) -> Optional[dict]:
        """
        Fetch conversation turn by unique turn_id.
        """
        try:
            with self.lock:
                self.cursor.execute(
                    """
                    SELECT id, user_command, assistant_response, intent, target,
                           context_data, created_at, session_id, turn_id, input_source,
                           turn_status, persistence_status, extracted_memory_ids, profile_id
                    FROM conversation_context
                    WHERE turn_id = ?
                    LIMIT 1
                    """,
                    (str(turn_id),)
                )
                row = self.cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "user_command": row[1] or "",
                        "assistant_response": row[2] or "",
                        "intent": row[3] or "",
                        "target": row[4] or "",
                        "context_data": row[5] or "",
                        "created_at": row[6],
                        "session_id": row[7],
                        "turn_id": row[8],
                        "input_source": row[9] or "voice",
                        "turn_status": row[10] or "completed",
                        "persistence_status": row[11] or "committed",
                        "extracted_memory_ids": row[12] or "",
                        "profile_id": row[13] or "default",
                    }
                return None
        except Exception as error:
            print(f"Get Interaction By Turn Id Error: {error}")
            return None

    def get_recent_conversation_window(
        self,
        limit: int = 10,
        session_id: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> List[dict]:
        """
        Fetch recent completed turns in chronological order (oldest to newest)
        for injection into LLM prompt / memory context.
        """
        try:
            limit = max(1, int(limit))
            target_profile = profile_id if profile_id is not None else getattr(self, "active_profile_id", "default")
            with self.lock:
                query = """
                    SELECT id, user_command, assistant_response, intent, target,
                           created_at, session_id, turn_id, input_source, profile_id, turn_status
                    FROM conversation_context
                    WHERE 1=1
                """
                params = []
                if target_profile and target_profile != "all":
                    query += " AND profile_id = ?"
                    params.append(str(target_profile))
                if session_id:
                    query += " AND session_id = ?"
                    params.append(str(session_id))
                query += " ORDER BY id DESC LIMIT ?"
                params.append(limit)

                self.cursor.execute(query, tuple(params))
                rows = self.cursor.fetchall()
                results = []
                for row in reversed(rows):
                    results.append({
                        "id": row[0],
                        "user_command": row[1] or "",
                        "assistant_response": row[2] or "",
                        "intent": row[3] or "",
                        "target": row[4] or "",
                        "timestamp": row[5],
                        "session_id": row[6],
                        "turn_id": row[7],
                        "input_source": row[8] or "voice",
                        "profile_id": row[9] or "default",
                        "turn_status": row[10] if len(row) > 10 else "completed",
                    })
                return results
        except Exception as error:
            print(f"Get Recent Conversation Window Error: {error}")
            return []

    def search_conversation_history(
        self,
        keyword: str,
        limit: int = 10,
        profile_id: Optional[str] = None
    ) -> List[dict]:
        """
        Search conversation history for a keyword in user_command or assistant_response.
        """
        try:
            limit = max(1, int(limit))
            target_profile = profile_id if profile_id is not None else getattr(self, "active_profile_id", "default")
            with self.lock:
                query = """
                    SELECT id, user_command, assistant_response, intent, target,
                           created_at, session_id, turn_id, input_source, profile_id
                    FROM conversation_context
                    WHERE (user_command LIKE ? OR assistant_response LIKE ?)
                """
                params = [f"%{keyword}%", f"%{keyword}%"]
                if target_profile and target_profile != "all":
                    query += " AND profile_id = ?"
                    params.append(str(target_profile))
                query += " ORDER BY id DESC LIMIT ?"
                params.append(limit)

                self.cursor.execute(query, tuple(params))
                rows = self.cursor.fetchall()
                results = []
                for row in reversed(rows):
                    results.append({
                        "id": row[0],
                        "user_command": row[1] or "",
                        "assistant_response": row[2] or "",
                        "intent": row[3] or "",
                        "target": row[4] or "",
                        "timestamp": row[5],
                        "session_id": row[6],
                        "turn_id": row[7],
                        "input_source": row[8] or "voice",
                        "profile_id": row[9] or "default",
                    })
                return results
        except Exception as error:
            print(f"Search Conversation History Error: {error}")
            return []

    def search_conversation_archive(
        self,
        query: str,
        limit: int = 10,
        profile_id: Optional[str] = None
    ) -> List[dict]:
        """
        Full conversation archive search matching multi-token queries across user utterances
        and assistant responses. Ranks results by token match density, phrase overlap, and recency.
        """
        try:
            q_clean = str(query or "").strip().lower()
            if not q_clean:
                return []

            stopwords = {
                "what", "is", "my", "the", "a", "an", "do", "i", "did", "you", "tell", "me",
                "about", "who", "where", "when", "how", "en", "enna", "yaar", "enga", "edhu",
                "solli", "sonnen", "solren", "pathi", "nu", "to", "of", "and", "in", "on", "for",
                "can", "please", "we", "was", "were", "are", "have", "had", "say", "mention", "discuss",
                "said", "told", "talk", "talked", "earlier", "previous", "before", "which", "at"
            }
            raw_tokens = [t.strip() for t in re.findall(r"[\w]+", q_clean) if len(t.strip()) >= 2]
            search_tokens = [t for t in raw_tokens if t not in stopwords]
            if not search_tokens:
                search_tokens = raw_tokens[:4]

            if not search_tokens:
                return []

            # Expand tokens with morphological stems & semantic domain aliases
            expanded_tokens = set(search_tokens)
            for tok in search_tokens:
                stem = re.sub(r"(?:ing|ed|s|ship)$", "", tok)
                if len(stem) >= 3:
                    expanded_tokens.add(stem)

            if any(w in q_clean for w in ("intern", "interning", "internship", "company", "role", "work", "job", "career")):
                expanded_tokens.update(["intern", "internship", "labs", "simposio", "symposium", "developer", "development", "role", "work", "company", "கம்பெனி"])
            if any(w in q_clean for w in ("project", "building", "developing")):
                expanded_tokens.update(["project", "symphowork", "simple work", "zoho", "react", "next.js", "svelte", "platform"])
            if any(w in q_clean for w in ("college", "course", "degree", "study", "studying", "padik")):
                expanded_tokens.update(["college", "course", "degree", "mca", "sona", "university", "institute", "கல்லூரி", "காலேஜ்"])
            if any(w in q_clean for w in ("family", "father", "mother", "brother", "sister", "member")):
                expanded_tokens.update(["father", "mother", "brother", "sister", "family", "senthil", "sangeetha", "deepesh"])

            target_profile = profile_id if profile_id is not None else getattr(self, "active_profile_id", "default")
            limit = max(1, int(limit))

            with self.lock:
                where_clauses = []
                params: List[Any] = []
                if target_profile and target_profile != "all":
                    where_clauses.append("profile_id = ?")
                    params.append(str(target_profile))

                token_clauses = []
                for tok in list(expanded_tokens)[:14]:
                    token_clauses.append("(LOWER(user_command) LIKE ? OR LOWER(assistant_response) LIKE ?)")
                    term = f"%{tok}%"
                    params.extend([term, term])

                where_clauses.append(f"({' OR '.join(token_clauses)})")

                sql = f"""
                    SELECT id, user_command, assistant_response, intent, target,
                           created_at, session_id, turn_id, input_source, profile_id, turn_status
                    FROM conversation_context
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY id DESC LIMIT 50
                """
                self.cursor.execute(sql, tuple(params))
                rows = self.cursor.fetchall()

                scored = []
                for row in rows:
                    u_cmd = str(row[1] or "").lower()
                    a_resp = str(row[2] or "").lower()
                    combined = f"{u_cmd} {a_resp}"

                    score = 0.0
                    for tok in search_tokens:
                        if tok in u_cmd:
                            score += 4.0
                        elif tok in a_resp:
                            score += 2.5

                    for tok in expanded_tokens:
                        if tok not in search_tokens:
                            if tok in u_cmd:
                                score += 2.0
                            elif tok in a_resp:
                                score += 1.5

                    if len(search_tokens) >= 2:
                        phrase_candidate = " ".join(search_tokens[:3])
                        if phrase_candidate in combined:
                            score += 5.0

                    if row[10] == "completed":
                        score += 1.0

                    # Penalize empty assistant responses or noisy repetitive question prompts
                    if not a_resp.strip():
                        score -= 2.0
                    if any(qm in u_cmd for qm in ("டெஸ்டிங்", "testing", "previous conversation")) and not any(k in a_resp for k in ("sangeetha", "senthil", "deepesh", "mca", "sona", "symposium", "sympho")):
                        score -= 2.0

                    # Boost turns with rich factual content
                    if any(k in a_resp for k in ("sangeetha", "senthil", "deepesh", "mca", "sona", "symposium", "fullstack", "internship", "project")):
                        score += 3.0

                    scored.append((score, {
                        "id": row[0],
                        "user_command": row[1] or "",
                        "assistant_response": row[2] or "",
                        "intent": row[3] or "",
                        "target": row[4] or "",
                        "timestamp": row[5],
                        "session_id": row[6],
                        "turn_id": row[7],
                        "input_source": row[8] or "voice",
                        "profile_id": row[9] or "default",
                        "turn_status": row[10] or "completed",
                        "score": score,
                    }))

                scored.sort(key=lambda x: x[0], reverse=True)
                return [item[1] for item in scored[:limit]]
        except Exception as error:
            print(f"Search Conversation Archive Error: {error}")
            return []

    def add_task(
        self,
        description: str,
        task_id: Optional[str] = None,
        deadline: Optional[str] = None,
        status: str = "pending",
        source_turn_id: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> bool:
        """
        Add or update an active or pending task/commitment.
        """
        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            t_id = str(task_id or f"task_{int(time.time() * 1000)}")
            now = self._now()
            with self.lock:
                self.cursor.execute(
                    """
                    INSERT INTO tasks
                    (task_id, description, deadline, status, source_turn_id, profile_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        description = excluded.description,
                        deadline = COALESCE(excluded.deadline, tasks.deadline),
                        status = excluded.status,
                        source_turn_id = COALESCE(excluded.source_turn_id, tasks.source_turn_id),
                        profile_id = excluded.profile_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        t_id,
                        str(description),
                        deadline,
                        str(status),
                        source_turn_id,
                        target_profile,
                        now,
                        now
                    )
                )
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Add Task DB Error: {error}")
            return False

    def update_task_status(
        self,
        task_id_or_keyword: str,
        status: str = "completed",
        new_status: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> bool:
        """
        Updates task status (pending, active, completed, cancelled) by task_id or description keyword.
        """
        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            eff_status = str(new_status or status or "completed")
            now = self._now()
            with self.lock:
                # First try exact task_id
                self.cursor.execute(
                    "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ? AND profile_id = ?",
                    (eff_status, now, str(task_id_or_keyword), target_profile)
                )
                if self.cursor.rowcount > 0:
                    self.connection.commit()
                    return True

                # Clean noise words from keyword
                clean_kw = re.sub(r"(?i)\b(?:the\s+task\s+of|the\s+task|task|of|about|for)\b", "", str(task_id_or_keyword)).strip()
                if clean_kw:
                    kw = f"%{clean_kw}%"
                    self.cursor.execute(
                        "UPDATE tasks SET status = ?, updated_at = ? WHERE profile_id = ? AND description LIKE ? AND (status = 'active' OR status = 'pending')",
                        (eff_status, now, target_profile, kw)
                    )
                    if self.cursor.rowcount > 0:
                        self.connection.commit()
                        return True

                # Try token overlap with pending/active tasks
                tokens = [t.lower() for t in re.findall(r"\w+", str(task_id_or_keyword)) if len(t) >= 3 and t.lower() not in ("task", "the", "completed", "finished", "done", "mudichiten", "submitting", "submit")]
                self.cursor.execute(
                    "SELECT task_id, description FROM tasks WHERE profile_id = ? AND (status = 'active' OR status = 'pending') ORDER BY id DESC",
                    (target_profile,)
                )
                pending_rows = self.cursor.fetchall()
                matched_id = None
                if tokens:
                    for tid, desc in pending_rows:
                        d_lower = str(desc or "").lower()
                        match_count = sum(1 for tok in tokens if tok in d_lower)
                        if match_count >= 1:
                            matched_id = tid
                            break
                elif pending_rows:
                    # Generic completion ("task completed") completes latest pending task
                    matched_id = pending_rows[0][0]

                if matched_id:
                    self.cursor.execute(
                        "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                        (eff_status, now, matched_id)
                    )
                    self.connection.commit()
                    return True

                return False
        except Exception as error:
            print(f"Update Task Status DB Error: {error}")
            return False

    def get_tasks(
        self,
        status: Optional[str] = "pending",
        profile_id: Optional[str] = None,
        limit: int = 10
    ) -> List[dict]:
        """
        Fetch tasks scoped by profile_id and status (pass status=None for all).
        """
        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            limit = max(1, int(limit))
            with self.lock:
                where_clauses = ["profile_id = ?"]
                params: List[Any] = [target_profile]
                if status == "pending" or status == "active":
                    where_clauses.append("(status = 'pending' OR status = 'active')")
                elif status:
                    where_clauses.append("status = ?")
                    params.append(str(status))

                sql = f"""
                    SELECT task_id, description, deadline, status, source_turn_id, profile_id, created_at, updated_at
                    FROM tasks
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY updated_at DESC LIMIT ?
                """
                params.append(limit)
                self.cursor.execute(sql, tuple(params))
                rows = self.cursor.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "task_id": row[0],
                        "description": row[1],
                        "deadline": row[2],
                        "status": row[3],
                        "source_turn_id": row[4],
                        "profile_id": row[5],
                        "created_at": row[6],
                        "updated_at": row[7],
                    })
                return results
        except Exception as error:
            print(f"Get Tasks DB Error: {error}")
            return []

    def add_personal_memory(
        self,
        memory_id: str,
        category: str,
        key: str,
        value: str,
        source_turn_id: Optional[str] = None,
        confidence: str = "high",
        status: str = "active",
        profile_id: Optional[str] = None
    ) -> bool:
        """
        Add or update a permanent personal memory record.
        Ensures corrections supersede prior facts gracefully:
        If status is 'active' and key is provided, prior active memories
        for the same (profile_id, category, key) are superseded.
        """
        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            now = self._now()
            with self.lock:
                # If adding an active memory with a specific key, mark prior active memories as superseded
                if status == "active" and key:
                    self.cursor.execute(
                        """
                        UPDATE personal_memories
                        SET status = 'superseded', updated_at = ?
                        WHERE profile_id = ? AND category = ? AND key = ? AND status = 'active' AND memory_id != ?
                        """,
                        (now, target_profile, str(category), str(key), str(memory_id))
                    )

                self.cursor.execute(
                    """
                    INSERT INTO personal_memories
                    (memory_id, category, key, value, source_turn_id, confidence, status, profile_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(memory_id) DO UPDATE SET
                        category = excluded.category,
                        key = excluded.key,
                        value = excluded.value,
                        source_turn_id = COALESCE(excluded.source_turn_id, personal_memories.source_turn_id),
                        confidence = excluded.confidence,
                        status = excluded.status,
                        profile_id = excluded.profile_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(memory_id),
                        str(category),
                        str(key or ""),
                        str(value),
                        source_turn_id,
                        str(confidence),
                        str(status),
                        target_profile,
                        now,
                        now
                    )
                )
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Add Personal Memory Error: {error}")
            return False

    def get_personal_memories(
        self,
        category: Optional[str] = None,
        key: Optional[str] = None,
        active_only: bool = True,
        profile_id: Optional[str] = None
    ) -> List[dict]:
        """
        Fetch personal memories by category or key and scoped by profile_id.
        If profile_id is None, uses active_profile_id. Pass 'all' to retrieve across profiles.
        """
        try:
            with self.lock:
                query = "SELECT memory_id, category, key, value, source_turn_id, confidence, status, profile_id, created_at, updated_at FROM personal_memories WHERE 1=1"
                params = []
                target_profile = profile_id if profile_id is not None else getattr(self, "active_profile_id", "default")
                if target_profile and target_profile != "all":
                    query += " AND profile_id = ?"
                    params.append(str(target_profile))
                if active_only:
                    query += " AND status = 'active'"
                if category:
                    query += " AND category = ?"
                    params.append(str(category))
                if key:
                    query += " AND key = ?"
                    params.append(str(key))
                query += " ORDER BY id DESC"
                self.cursor.execute(query, tuple(params))
                rows = self.cursor.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "memory_id": row[0],
                        "category": row[1],
                        "key": row[2],
                        "value": row[3],
                        "source_turn_id": row[4],
                        "confidence": row[5],
                        "status": row[6],
                        "profile_id": row[7],
                        "created_at": row[8],
                        "updated_at": row[9],
                    })
                return results
        except Exception as error:
            print(f"Get Personal Memories Error: {error}")
            return []

    def deactivate_personal_memory(
        self,
        key: Optional[str] = None,
        category: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> bool:
        """
        Mark matching personal memories as 'retracted' (deactivated) for the profile.
        """
        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            now = self._now()
            with self.lock:
                query = "UPDATE personal_memories SET status = 'retracted', updated_at = ? WHERE profile_id = ?"
                params = [now, target_profile]
                if key:
                    query += " AND key = ?"
                    params.append(str(key))
                if category:
                    query += " AND category = ?"
                    params.append(str(category))
                self.cursor.execute(query, tuple(params))
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Deactivate Personal Memory Error: {error}")
            return False

    def search_personal_memories(
        self,
        query: str,
        profile_id: Optional[str] = None,
        limit: int = 20
    ) -> List[dict]:
        """
        Search active personal memories across category, key, and value using token matching.
        Returns matching memories scoped to profile_id.
        """
        try:
            tokens = [t.strip().lower() for t in str(query or "").split() if len(t.strip()) >= 2]
            if not tokens:
                return []
            target_profile = profile_id if profile_id is not None else getattr(self, "active_profile_id", "default")
            with self.lock:
                where_clauses = ["status = 'active'"]
                params: List[Any] = []
                if target_profile and target_profile != "all":
                    where_clauses.append("profile_id = ?")
                    params.append(str(target_profile))

                token_clauses = []
                for tok in tokens[:8]:
                    token_clauses.append("(LOWER(category) LIKE ? OR LOWER(key) LIKE ? OR LOWER(value) LIKE ?)")
                    term = f"%{tok}%"
                    params.extend([term, term, term])

                if token_clauses:
                    where_clauses.append(f"({' OR '.join(token_clauses)})")

                sql = f"""
                    SELECT memory_id, category, key, value, source_turn_id, confidence, status, profile_id, created_at, updated_at
                    FROM personal_memories
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY updated_at DESC LIMIT ?
                """
                params.append(max(1, int(limit)))
                self.cursor.execute(sql, tuple(params))
                rows = self.cursor.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "memory_id": row[0],
                        "category": row[1],
                        "key": row[2],
                        "value": row[3],
                        "source_turn_id": row[4],
                        "confidence": row[5],
                        "status": row[6],
                        "profile_id": row[7],
                        "created_at": row[8],
                        "updated_at": row[9],
                    })
                return results
        except Exception as error:
            print(f"Search Personal Memories Error: {error}")
            return []

    def delete_personal_memory(
        self,
        memory_id: Optional[str] = None,
        key: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> bool:
        """
        Permanently delete personal memory record(s) by memory_id or key for profile.
        """
        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            with self.lock:
                if memory_id:
                    self.cursor.execute("DELETE FROM personal_memories WHERE memory_id = ?", (str(memory_id),))
                elif key:
                    self.cursor.execute("DELETE FROM personal_memories WHERE profile_id = ? AND key = ?", (target_profile, str(key)))
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Delete Personal Memory Error: {error}")
            return False

    # ==================================================
    # USER PROFILES (PER-USER IDENTITY ISOLATION)
    # ==================================================

    def set_active_profile_id(self, profile_id: str) -> bool:
        """
        Set the active user profile ID.
        """
        if not profile_id:
            profile_id = "default"
        self.active_profile_id = str(profile_id)
        self.get_or_create_profile(self.active_profile_id)
        return True

    def get_active_profile_id(self) -> str:
        """
        Get the active user profile ID.
        """
        return getattr(self, "active_profile_id", "default") or "default"

    def get_or_create_profile(
        self,
        profile_id: str,
        display_name: Optional[str] = None,
        preferred_name: Optional[str] = None,
        is_creator: bool = False
    ) -> dict:
        """
        Fetch or create a user profile by profile_id.
        """
        with self.lock:
            self.cursor.execute(
                "SELECT profile_id, display_name, preferred_name, use_preferred_name, is_active, is_creator, created_at, updated_at FROM user_profiles WHERE profile_id = ? LIMIT 1",
                (str(profile_id),)
            )
            row = self.cursor.fetchone()
            if row:
                return {
                    "profile_id": row[0],
                    "display_name": row[1] or "",
                    "preferred_name": row[2],
                    "use_preferred_name": bool(row[3]),
                    "is_active": bool(row[4]),
                    "is_creator": bool(row[5]),
                    "created_at": row[6],
                    "updated_at": row[7],
                }
            now = self._now()
            name = display_name or ("Default User" if profile_id == "default" else profile_id)
            self.cursor.execute(
                """
                INSERT INTO user_profiles
                (profile_id, display_name, preferred_name, use_preferred_name, is_active, is_creator, created_at, updated_at)
                VALUES (?, ?, ?, 1, 1, ?, ?, ?)
                """,
                (str(profile_id), name, preferred_name, 1 if is_creator else 0, now, now)
            )
            self.connection.commit()
            return {
                "profile_id": str(profile_id),
                "display_name": name,
                "preferred_name": preferred_name,
                "use_preferred_name": True,
                "is_active": True,
                "is_creator": bool(is_creator),
                "created_at": now,
                "updated_at": now,
            }

    def get_profile(self, profile_id: str) -> Optional[dict]:
        """
        Fetch user profile by profile_id.
        """
        with self.lock:
            self.cursor.execute(
                "SELECT profile_id, display_name, preferred_name, use_preferred_name, is_active, is_creator, created_at, updated_at FROM user_profiles WHERE profile_id = ? LIMIT 1",
                (str(profile_id),)
            )
            row = self.cursor.fetchone()
            if row:
                return {
                    "profile_id": row[0],
                    "display_name": row[1] or "",
                    "preferred_name": row[2],
                    "use_preferred_name": bool(row[3]),
                    "is_active": bool(row[4]),
                    "is_creator": bool(row[5]),
                    "created_at": row[6],
                    "updated_at": row[7],
                }
            return None

    def update_profile(
        self,
        profile_id: str,
        display_name: Optional[str] = None,
        preferred_name: Optional[str] = None,
        use_preferred_name: Optional[bool] = None
    ) -> bool:
        """
        Update user profile fields.
        """
        with self.lock:
            now = self._now()
            fields = []
            params = []
            if display_name is not None:
                fields.append("display_name = ?")
                params.append(display_name)
            if preferred_name is not None:
                fields.append("preferred_name = ?")
                params.append(preferred_name)
            if use_preferred_name is not None:
                fields.append("use_preferred_name = ?")
                params.append(1 if use_preferred_name else 0)
            if not fields:
                return True
            fields.append("updated_at = ?")
            params.append(now)
            params.append(str(profile_id))
            query = f"UPDATE user_profiles SET {', '.join(fields)} WHERE profile_id = ?"
            self.cursor.execute(query, tuple(params))
            self.connection.commit()
            return True

    def list_profiles(self) -> List[dict]:
        """
        List all user profiles.
        """
        with self.lock:
            self.cursor.execute(
                "SELECT profile_id, display_name, preferred_name, use_preferred_name, is_active, is_creator, created_at, updated_at FROM user_profiles ORDER BY id ASC"
            )
            rows = self.cursor.fetchall()
            return [
                {
                    "profile_id": row[0],
                    "display_name": row[1] or "",
                    "preferred_name": row[2],
                    "use_preferred_name": bool(row[3]),
                    "is_active": bool(row[4]),
                    "is_creator": bool(row[5]),
                    "created_at": row[6],
                    "updated_at": row[7],
                }
                for row in rows
            ]

    # --------------------------------------------------

    def get_recent_context(
        self,
        limit=10
    ):
        """
        Return recent conversation context.

        Newest context is returned first.
        """

        try:

            limit = max(
                1,
                int(limit)
            )

            with self.lock:

                self.cursor.execute(
                    """
                    SELECT
                        id,
                        user_command,
                        assistant_response,
                        intent,
                        target,
                        context_data,
                        created_at
                    FROM conversation_context
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (
                        limit,
                    )
                )

                return self.cursor.fetchall()

        except Exception as error:

            print(
                f"Get Recent Context Error : "
                f"{error}"
            )

            return []

    # --------------------------------------------------

    def get_latest_context(
        self
    ):
        """
        Return the latest conversation context.
        """

        contexts = (
            self.get_recent_context(
                limit=1
            )
        )

        if contexts:

            return contexts[0]

        return None

    # --------------------------------------------------

    def get_context_by_intent(
        self,
        intent,
        limit=10
    ):
        """
        Return recent context for
        a specific intent.
        """

        try:

            limit = max(
                1,
                int(limit)
            )

            with self.lock:

                self.cursor.execute(
                    """
                    SELECT
                        id,
                        user_command,
                        assistant_response,
                        intent,
                        target,
                        context_data,
                        created_at
                    FROM conversation_context
                    WHERE intent = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (
                        intent,
                        limit
                    )
                )

                return self.cursor.fetchall()

        except Exception as error:

            print(
                f"Get Context By Intent Error : "
                f"{error}"
            )

            return []

    # --------------------------------------------------

    def clear_conversation_context(
        self
    ):
        """
        Clear temporary conversation memory.
        """

        try:

            with self.lock:

                self.cursor.execute(
                    """
                    DELETE FROM
                    conversation_context
                    """
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Clear Conversation Context Error : "
                f"{error}"
            )

            return False

    # --------------------------------------------------

    def trim_conversation_context(
        self,
        keep_last=100
    ):
        """
        Keep only the latest context records.

        Prevents unlimited database growth.
        """

        try:

            keep_last = max(
                1,
                int(keep_last)
            )

            with self.lock:

                self.cursor.execute(
                    """
                    DELETE FROM conversation_context
                    WHERE id NOT IN
                    (
                        SELECT id
                        FROM conversation_context
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    """,
                    (
                        keep_last,
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Trim Context Error : {error}"
            )

            return False

    # ==================================================
    # USER CONTEXT METHODS
    # ==================================================

    def set_user_context(
        self,
        context_key,
        context_value,
        category="general",
        source="explicit_user",
        confidence="high",
        importance=3,
        is_active=1
    ):
        """
        Store persistent user context with provenance and importance metadata.
        """
        try:
            context_key = (
                str(context_key)
                .strip()
                .lower()
            )
            now = self._now()

            with self.lock:
                try:
                    self.cursor.execute(
                        """
                        INSERT INTO user_context
                        (
                            context_key, context_value, category, source,
                            confidence, importance, is_active, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(context_key)
                        DO UPDATE SET
                            context_value = excluded.context_value,
                            category = excluded.category,
                            source = excluded.source,
                            confidence = excluded.confidence,
                            importance = excluded.importance,
                            is_active = excluded.is_active,
                            updated_at = excluded.updated_at
                        """,
                        (
                            context_key,
                            str(context_value),
                            str(category),
                            str(source),
                            str(confidence),
                            int(importance),
                            int(is_active),
                            now
                        )
                    )
                except Exception:
                    # Fallback for baseline table schema without extra columns
                    self.cursor.execute(
                        """
                        INSERT INTO user_context
                        (context_key, context_value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(context_key)
                        DO UPDATE SET
                            context_value = excluded.context_value,
                            updated_at = excluded.updated_at
                        """,
                        (
                            context_key,
                            str(context_value),
                            now
                        )
                    )

                self.connection.commit()
            return True

        except Exception as error:
            print(f"Set User Context Error : {error}")
            return False

    # --------------------------------------------------

    def get_user_context(
        self,
        context_key,
        default=None,
        active_only=True
    ):
        """
        Get one persistent context value.
        """
        try:
            context_key = (
                str(context_key)
                .strip()
                .lower()
            )

            with self.lock:
                try:
                    if active_only:
                        self.cursor.execute(
                            """
                            SELECT context_value
                            FROM user_context
                            WHERE context_key = ? AND (is_active IS NULL OR is_active = 1)
                            """,
                            (context_key,)
                        )
                    else:
                        self.cursor.execute(
                            "SELECT context_value FROM user_context WHERE context_key = ?",
                            (context_key,)
                        )
                except Exception:
                    self.cursor.execute(
                        "SELECT context_value FROM user_context WHERE context_key = ?",
                        (context_key,)
                    )

                result = self.cursor.fetchone()
                if result:
                    return result[0]

                return default

        except Exception as error:
            print(f"Get User Context Error : {error}")
            return default

    # --------------------------------------------------

    def get_all_user_context(
        self,
        active_only=True
    ):
        """
        Return all persistent context.
        """
        try:
            with self.lock:
                try:
                    if active_only:
                        self.cursor.execute(
                            """
                            SELECT context_key, context_value, updated_at
                            FROM user_context
                            WHERE (is_active IS NULL OR is_active = 1)
                            ORDER BY context_key
                            """
                        )
                    else:
                        self.cursor.execute(
                            "SELECT context_key, context_value, updated_at FROM user_context ORDER BY context_key"
                        )
                except Exception:
                    self.cursor.execute(
                        "SELECT context_key, context_value, updated_at FROM user_context ORDER BY context_key"
                    )

                return self.cursor.fetchall()

        except Exception as error:
            print(f"Get All User Context Error : {error}")
            return []

    # --------------------------------------------------

    def delete_user_context(
        self,
        context_key
    ):
        """
        Delete one persistent context item.
        """
        try:
            context_key = (
                str(context_key)
                .strip()
                .lower()
            )

            with self.lock:
                self.cursor.execute(
                    "DELETE FROM user_context WHERE context_key = ?",
                    (context_key,)
                )
                self.connection.commit()

            return True

        except Exception as error:
            print(f"Delete User Context Error : {error}")
            return False

    # --------------------------------------------------

    def deactivate_user_context(
        self,
        context_key
    ):
        """
        Deactivate and remove one persistent context item (supporting 'forget this').
        """
        try:
            context_key = (
                str(context_key)
                .strip()
                .lower()
            )

            with self.lock:
                try:
                    self.cursor.execute(
                        "UPDATE user_context SET is_active = 0, updated_at = ? WHERE context_key = ?",
                        (self._now(), context_key)
                    )
                except Exception:
                    pass
                self.cursor.execute(
                    "DELETE FROM user_context WHERE context_key = ?",
                    (context_key,)
                )
                self.connection.commit()

            return True

        except Exception as error:
            print(f"Deactivate User Context Error : {error}")
            return False

    # --------------------------------------------------

    def search_user_context(
        self,
        query: str,
        active_only: bool = True
    ):
        """
        Search user context by matching context_key or context_value.
        """
        try:
            q = f"%{str(query).strip().lower()}%"
            with self.lock:
                try:
                    if active_only:
                        self.cursor.execute(
                            """
                            SELECT context_key, context_value, category
                            FROM user_context
                            WHERE (context_key LIKE ? OR context_value LIKE ?)
                              AND (is_active IS NULL OR is_active = 1)
                            """,
                            (q, q)
                        )
                    else:
                        self.cursor.execute(
                            """
                            SELECT context_key, context_value, category
                            FROM user_context
                            WHERE context_key LIKE ? OR context_value LIKE ?
                            """,
                            (q, q)
                        )
                except Exception:
                    self.cursor.execute(
                        """
                        SELECT context_key, context_value, ''
                        FROM user_context
                        WHERE context_key LIKE ? OR context_value LIKE ?
                        """,
                        (q, q)
                    )
                return self.cursor.fetchall()
        except Exception as error:
            print(f"Search User Context Error : {error}")
            return []

    # ==================================================
    # PEOPLE & IDENTITY METHODS
    # ==================================================

    def _row_to_person_dict(self, row) -> dict:
        """Helper to convert a people table row to a dictionary."""
        return {
            "id": row[0],
            "person_id": row[1],
            "name": row[2],
            "preferred_name": row[3],
            "relationship_to_dheepthi": row[4],
            "relationship_to_primary_user": row[5],
            "is_primary_user": bool(row[6]),
            "is_creator": bool(row[7]),
            "identity_source": row[8],
            "confidence": row[9],
            "voice_profile_id": row[10],
            "notes": row[11],
            "created_at": row[12],
            "updated_at": row[13],
            "last_confirmed": row[14],
        }

    def add_or_update_person(
        self,
        name: str,
        preferred_name: str = None,
        relationship_to_dheepthi: str = "user",
        relationship_to_primary_user: str = None,
        is_primary_user: int = 0,
        is_creator: int = 0,
        identity_source: str = "explicit_user",
        confidence: str = "high",
        voice_profile_id: str = None,
        notes: str = "",
        person_id: str = None,
        profile_id: Optional[str] = None,
    ) -> bool:
        """
        Insert or update a person record in the people table.
        """
        try:
            name_clean = str(name).strip()
            if not name_clean:
                return False
            norm_name = name_clean[0].upper() + name_clean[1:]
            p_id = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            pid = str(person_id or (f"person_{norm_name.lower()}" if p_id == "default" else f"person_{p_id}_{norm_name.lower()}")).strip()
            pref = str(preferred_name).strip() if preferred_name else norm_name
            now = self._now()

            with self.lock:
                if is_primary_user:
                    # Clear previous primary user flags if establishing new primary user
                    self.cursor.execute(
                        "UPDATE people SET is_primary_user = 0 WHERE is_primary_user = 1"
                    )

                self.cursor.execute(
                    """
                    INSERT INTO people (
                        person_id, name, preferred_name, relationship_to_dheepthi,
                        relationship_to_primary_user, is_primary_user, is_creator,
                        identity_source, confidence, voice_profile_id, notes,
                        created_at, updated_at, last_confirmed, profile_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(person_id) DO UPDATE SET
                        name = excluded.name,
                        preferred_name = excluded.preferred_name,
                        relationship_to_dheepthi = excluded.relationship_to_dheepthi,
                        relationship_to_primary_user = COALESCE(excluded.relationship_to_primary_user, people.relationship_to_primary_user),
                        is_primary_user = excluded.is_primary_user,
                        is_creator = excluded.is_creator,
                        identity_source = excluded.identity_source,
                        confidence = excluded.confidence,
                        voice_profile_id = COALESCE(excluded.voice_profile_id, people.voice_profile_id),
                        notes = excluded.notes,
                        updated_at = excluded.updated_at,
                        last_confirmed = excluded.last_confirmed,
                        profile_id = excluded.profile_id
                    """,
                    (
                        pid, norm_name, pref, relationship_to_dheepthi,
                        relationship_to_primary_user, int(is_primary_user), int(is_creator),
                        identity_source, confidence, voice_profile_id, notes,
                        now, now, now, p_id
                    )
                )
                self.connection.commit()
            return True
        except Exception as error:
            print(f"Add Or Update Person Error : {error}")
            return False

    def get_person_by_name(self, name: str) -> Optional[dict]:
        """Fetch a person record by name (case-insensitive)."""
        try:
            clean = str(name).strip().lower()
            with self.lock:
                self.cursor.execute(
                    """
                    SELECT id, person_id, name, preferred_name, relationship_to_dheepthi,
                           relationship_to_primary_user, is_primary_user, is_creator,
                           identity_source, confidence, voice_profile_id, notes,
                           created_at, updated_at, last_confirmed
                    FROM people
                    WHERE LOWER(name) = ? OR LOWER(preferred_name) = ?
                    LIMIT 1
                    """,
                    (clean, clean)
                )
                row = self.cursor.fetchone()
                if row:
                    return self._row_to_person_dict(row)
                return None
        except Exception as error:
            print(f"Get Person By Name Error : {error}")
            return None

    def get_person_by_id(self, person_id: str) -> Optional[dict]:
        """Fetch a person record by person_id."""
        try:
            clean = str(person_id).strip().lower()
            with self.lock:
                self.cursor.execute(
                    """
                    SELECT id, person_id, name, preferred_name, relationship_to_dheepthi,
                           relationship_to_primary_user, is_primary_user, is_creator,
                           identity_source, confidence, voice_profile_id, notes,
                           created_at, updated_at, last_confirmed
                    FROM people
                    WHERE LOWER(person_id) = ?
                    LIMIT 1
                    """,
                    (clean,)
                )
                row = self.cursor.fetchone()
                if row:
                    return self._row_to_person_dict(row)
                return None
        except Exception as error:
            print(f"Get Person By Id Error : {error}")
            return None

    def get_primary_user(self) -> Optional[dict]:
        """Fetch the current primary user record if established."""
        try:
            with self.lock:
                self.cursor.execute(
                    """
                    SELECT id, person_id, name, preferred_name, relationship_to_dheepthi,
                           relationship_to_primary_user, is_primary_user, is_creator,
                           identity_source, confidence, voice_profile_id, notes,
                           created_at, updated_at, last_confirmed
                    FROM people
                    WHERE is_primary_user = 1
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                )
                row = self.cursor.fetchone()
                if row:
                    return self._row_to_person_dict(row)
                return None
        except Exception as error:
            print(f"Get Primary User Error : {error}")
            return None

    def get_creators(self) -> list:
        """Fetch all recognized creators."""
        try:
            with self.lock:
                self.cursor.execute(
                    """
                    SELECT id, person_id, name, preferred_name, relationship_to_dheepthi,
                           relationship_to_primary_user, is_primary_user, is_creator,
                           identity_source, confidence, voice_profile_id, notes,
                           created_at, updated_at, last_confirmed
                    FROM people
                    WHERE is_creator = 1
                    ORDER BY id ASC
                    """
                )
                rows = self.cursor.fetchall()
                return [self._row_to_person_dict(r) for r in rows]
        except Exception as error:
            print(f"Get Creators Error : {error}")
            return []

    def get_all_known_people(self, profile_id: Optional[str] = None) -> list:
        """Fetch all known people."""
        try:
            with self.lock:
                target_p = profile_id if profile_id is not None else getattr(self, "active_profile_id", None)
                if target_p:
                    self.cursor.execute(
                        """
                        SELECT id, person_id, name, preferred_name, relationship_to_dheepthi,
                               relationship_to_primary_user, is_primary_user, is_creator,
                               identity_source, confidence, voice_profile_id, notes,
                               created_at, updated_at, last_confirmed
                        FROM people
                        WHERE profile_id = ? OR is_creator = 1
                        ORDER BY updated_at DESC
                        """,
                        (str(target_p),)
                    )
                else:
                    self.cursor.execute(
                        """
                        SELECT id, person_id, name, preferred_name, relationship_to_dheepthi,
                               relationship_to_primary_user, is_primary_user, is_creator,
                               identity_source, confidence, voice_profile_id, notes,
                               created_at, updated_at, last_confirmed
                        FROM people
                        ORDER BY updated_at DESC
                        """
                    )
                rows = self.cursor.fetchall()
                return [self._row_to_person_dict(r) for r in rows]
        except Exception as error:
            print(f"Get All Known People Error : {error}")
            return []

    def delete_person(self, name_or_id: str) -> bool:
        """Delete a person record by name or person_id."""
        try:
            clean = str(name_or_id).strip().lower()
            with self.lock:
                self.cursor.execute(
                    "DELETE FROM people WHERE LOWER(person_id) = ? OR LOWER(name) = ?",
                    (clean, clean)
                )
                self.connection.commit()
            return True
        except Exception as error:
            print(f"Delete Person Error : {error}")
            return False

    # --------------------------------------------------

    def clear_user_context(
        self
    ):
        """
        Remove all persistent user context.
        """

        try:

            with self.lock:

                self.cursor.execute(
                    """
                    DELETE FROM user_context
                    """
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Clear User Context Error : "
                f"{error}"
            )

            return False

    # ==================================================
    # EMOTIONAL STATE METHODS
    # ==================================================

    def get_emotional_state(self) -> dict:
        """
        Return the current singleton emotional state.
        """
        try:
            with self.lock:
                self.cursor.execute(
                    """
                    SELECT current_mood, valence, arousal, rapport_level, last_trigger, updated_at
                    FROM emotional_state
                    WHERE id = 1
                    """
                )
                row = self.cursor.fetchone()
                if row:
                    return {
                        "current_mood": str(row[0]),
                        "valence": float(row[1]),
                        "arousal": float(row[2]),
                        "rapport_level": float(row[3]),
                        "last_trigger": str(row[4] or ""),
                        "updated_at": str(row[5] or "")
                    }

                now = self._now()
                self.cursor.execute(
                    """
                    INSERT INTO emotional_state
                    (id, current_mood, valence, arousal, rapport_level, last_trigger, updated_at)
                    VALUES (1, 'neutral', 0.5, 0.5, 0.7, 'init', ?)
                    """,
                    (now,)
                )
                self.connection.commit()
                return {
                    "current_mood": "neutral",
                    "valence": 0.5,
                    "arousal": 0.5,
                    "rapport_level": 0.7,
                    "last_trigger": "init",
                    "updated_at": now
                }
        except Exception as error:
            print(f"Get Emotional State Error : {error}")
            return {
                "current_mood": "neutral",
                "valence": 0.5,
                "arousal": 0.5,
                "rapport_level": 0.7,
                "last_trigger": "error",
                "updated_at": self._now()
            }

    def set_emotional_state(
        self,
        current_mood: str,
        valence: float,
        arousal: float,
        rapport_level: float,
        last_trigger: str = None
    ) -> bool:
        """
        Update the current singleton emotional state.
        """
        try:
            now = self._now()
            with self.lock:
                self.cursor.execute(
                    """
                    INSERT INTO emotional_state
                    (id, current_mood, valence, arousal, rapport_level, last_trigger, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        current_mood = excluded.current_mood,
                        valence = excluded.valence,
                        arousal = excluded.arousal,
                        rapport_level = excluded.rapport_level,
                        last_trigger = excluded.last_trigger,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(current_mood),
                        float(valence),
                        float(arousal),
                        float(rapport_level),
                        str(last_trigger or ""),
                        now
                    )
                )
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Set Emotional State Error : {error}")
            return False

    def log_emotion_event(
        self,
        user_utterance: str,
        detected_stimulus: str,
        prev_mood: str,
        new_mood: str,
        valence_delta: float,
        rationale: str = ""
    ) -> bool:
        """
        Record an emotional transition event.
        """
        try:
            now = self._now()
            with self.lock:
                self.cursor.execute(
                    """
                    INSERT INTO emotion_logs
                    (timestamp, user_utterance, detected_stimulus, prev_mood, new_mood, valence_delta, rationale)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now,
                        str(user_utterance or ""),
                        str(detected_stimulus or ""),
                        str(prev_mood or ""),
                        str(new_mood or ""),
                        float(valence_delta or 0.0),
                        str(rationale or "")
                    )
                )
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Log Emotion Event Error : {error}")
            return False

    def get_recent_emotion_logs(self, limit: int = 10):
        """
        Return the most recent emotion transition logs.
        """
        try:
            with self.lock:
                self.cursor.execute(
                    """
                    SELECT id, timestamp, user_utterance, detected_stimulus, prev_mood, new_mood, valence_delta, rationale
                    FROM emotion_logs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),)
                )
                return self.cursor.fetchall()
        except Exception as error:
            print(f"Get Recent Emotion Logs Error : {error}")
            return []

    # ==================================================
    # EPISODIC MEMORY METHODS
    # ==================================================

    def add_memory_episode(
        self,
        summary: str,
        emotional_valence: float = 0.5,
        category: str = "conversation",
        importance: int = 3,
        profile_id: Optional[str] = None
    ) -> bool:
        """
        Store a significant interaction or episodic memory scoped by profile_id.
        """
        try:
            now = self._now()
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            with self.lock:
                try:
                    self.cursor.execute(
                        """
                        INSERT INTO memory_episodes
                        (timestamp, summary, emotional_valence, category, importance, access_count, last_accessed, profile_id)
                        VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (
                            now,
                            str(summary or "").strip(),
                            float(emotional_valence or 0.5),
                            str(category or "conversation"),
                            max(1, min(5, int(importance or 3))),
                            now,
                            target_profile
                        )
                    )
                except Exception:
                    self.cursor.execute(
                        """
                        INSERT INTO memory_episodes
                        (timestamp, summary, emotional_valence, category, importance, access_count, last_accessed)
                        VALUES (?, ?, ?, ?, ?, 0, ?)
                        """,
                        (
                            now,
                            str(summary or "").strip(),
                            float(emotional_valence or 0.5),
                            str(category or "conversation"),
                            max(1, min(5, int(importance or 3))),
                            now
                        )
                    )
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Add Memory Episode Error : {error}")
            return False

    def get_recent_episodes(self, limit: int = 10, profile_id: Optional[str] = None):
        """
        Fetch latest memory episodes scoped by profile_id.
        """
        try:
            target_profile = profile_id if profile_id is not None else getattr(self, "active_profile_id", "default")
            with self.lock:
                query = """
                    SELECT id, timestamp, summary, emotional_valence, category, importance, access_count, last_accessed
                    FROM memory_episodes
                """
                params = []
                if target_profile and target_profile != "all":
                    query += " WHERE profile_id = ? OR profile_id IS NULL"
                    params.append(str(target_profile))
                query += " ORDER BY id DESC LIMIT ?"
                params.append(max(1, int(limit)))
                try:
                    self.cursor.execute(query, tuple(params))
                except Exception:
                    self.cursor.execute(
                        """
                        SELECT id, timestamp, summary, emotional_valence, category, importance, access_count, last_accessed
                        FROM memory_episodes
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (max(1, int(limit)),)
                    )
                return self.cursor.fetchall()
        except Exception as error:
            print(f"Get Recent Episodes Error : {error}")
            return []

    def get_important_episodes(self, min_importance: int = 3, limit: int = 10, profile_id: Optional[str] = None):
        """
        Fetch high-importance episodic memories scoped by profile_id.
        """
        try:
            target_profile = profile_id if profile_id is not None else getattr(self, "active_profile_id", "default")
            with self.lock:
                query = """
                    SELECT id, timestamp, summary, emotional_valence, category, importance, access_count, last_accessed
                    FROM memory_episodes
                    WHERE importance >= ?
                """
                params = [int(min_importance)]
                if target_profile and target_profile != "all":
                    query += " AND (profile_id = ? OR profile_id IS NULL)"
                    params.append(str(target_profile))
                query += " ORDER BY importance DESC, id DESC LIMIT ?"
                params.append(max(1, int(limit)))
                try:
                    self.cursor.execute(query, tuple(params))
                except Exception:
                    self.cursor.execute(
                        """
                        SELECT id, timestamp, summary, emotional_valence, category, importance, access_count, last_accessed
                        FROM memory_episodes
                        WHERE importance >= ?
                        ORDER BY importance DESC, id DESC
                        LIMIT ?
                        """,
                        (int(min_importance), max(1, int(limit)))
                    )
                return self.cursor.fetchall()
        except Exception as error:
            print(f"Get Important Episodes Error : {error}")
            return []

    def prune_memory_episodes(self, max_records: int = 200) -> bool:
        """
        Keep episode count within limits by pruning older, low-importance episodes.
        """
        try:
            with self.lock:
                self.cursor.execute("SELECT COUNT(*) FROM memory_episodes")
                count = self.cursor.fetchone()[0]
                if count > max_records:
                    delete_count = count - max_records
                    self.cursor.execute(
                        """
                        DELETE FROM memory_episodes
                        WHERE id IN (
                            SELECT id FROM memory_episodes
                            ORDER BY importance ASC, id ASC
                            LIMIT ?
                        )
                        """,
                        (delete_count,)
                    )
                    self.connection.commit()
                return True
        except Exception as error:
            print(f"Prune Episodes Error : {error}")
            return False

    # ==================================================
    # COMMAND HISTORY METHODS
    # ==================================================

    def add_command_history(
        self,
        command,
        intent=None,
        target=None,
        status="SUCCESS",
        session_id=None,
        turn_id=None,
        entities=None,
        result_summary=None,
        error_summary=None,
        execution_time_ms=0,
        profile_id=None
    ):
        """
        Store executed command history.
        """

        try:
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            with self.lock:
                self.cursor.execute(
                    """
                    INSERT INTO
                    command_history
                    (
                        command,
                        intent,
                        target,
                        status,
                        created_at,
                        session_id,
                        turn_id,
                        entities,
                        result_summary,
                        error_summary,
                        execution_time_ms,
                        profile_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(command or ""),
                        intent,
                        target,
                        str(status or "SUCCESS"),
                        self._now(),
                        session_id,
                        turn_id,
                        entities,
                        result_summary,
                        error_summary,
                        int(execution_time_ms or 0),
                        target_profile
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:
            print(
                f"Command History Error : "
                f"{error}"
            )
            return False

    def log_command_execution(
        self,
        command: str,
        intent: Optional[str] = None,
        target: Optional[str] = None,
        status: str = "started",
        session_id: Optional[str] = None,
        turn_id: Optional[str] = None,
        entities: Optional[str] = None,
        result_summary: Optional[str] = None,
        error_summary: Optional[str] = None,
        execution_time_ms: int = 0,
        profile_id: Optional[str] = None
    ) -> int:
        """
        Record command execution initiation or full execution.
        Returns the inserted row ID.
        """
        try:
            now = self._now()
            target_profile = str(profile_id or getattr(self, "active_profile_id", "default") or "default")
            with self.lock:
                self.cursor.execute(
                    """
                    INSERT INTO command_history
                    (command, intent, target, status, created_at, session_id, turn_id, entities, result_summary, error_summary, execution_time_ms, profile_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(command or ""),
                        intent,
                        target,
                        str(status or "started"),
                        now,
                        session_id,
                        turn_id,
                        entities,
                        result_summary,
                        error_summary,
                        int(execution_time_ms or 0),
                        target_profile
                    )
                )
                self.connection.commit()
                return self.cursor.lastrowid or 0
        except Exception as error:
            print(f"Log Command Execution Error : {error}")
            return 0

    def update_command_execution(
        self,
        command_id: int,
        status: str,
        result_summary: Optional[str] = None,
        error_summary: Optional[str] = None,
        execution_time_ms: int = 0
    ) -> bool:
        """
        Update the outcome of an in-flight or completed command.
        """
        try:
            with self.lock:
                self.cursor.execute(
                    """
                    UPDATE command_history
                    SET status = ?,
                        result_summary = COALESCE(?, result_summary),
                        error_summary = COALESCE(?, error_summary),
                        execution_time_ms = ?
                    WHERE id = ?
                    """,
                    (
                        str(status),
                        result_summary,
                        error_summary,
                        int(execution_time_ms or 0),
                        int(command_id)
                    )
                )
                self.connection.commit()
                return True
        except Exception as error:
            print(f"Update Command Execution Error : {error}")
            return False

    # --------------------------------------------------

    def get_recent_commands(
        self,
        limit=20,
        profile_id: Optional[str] = None
    ):
        """
        Return recently executed commands scoped by profile_id.
        """
        try:
            limit = max(1, int(limit))
            target_profile = profile_id if profile_id is not None else getattr(self, "active_profile_id", "default")
            with self.lock:
                query = """
                    SELECT
                        id, command, intent, target, status, created_at,
                        session_id, turn_id, entities, result_summary, error_summary,
                        execution_time_ms, profile_id
                    FROM command_history
                    WHERE 1=1
                """
                params = []
                if target_profile and target_profile != "all":
                    query += " AND profile_id = ?"
                    params.append(str(target_profile))
                query += " ORDER BY id DESC LIMIT ?"
                params.append(limit)

                self.cursor.execute(query, tuple(params))
                rows = self.cursor.fetchall()
                results = []
                for r in rows:
                    row_dict = {
                        "id": r[0],
                        "command": r[1] or "",
                        "intent": r[2] or "",
                        "target": r[3] or "",
                        "status": r[4] or "",
                        "created_at": r[5] or "",
                        "session_id": r[6] or "",
                        "turn_id": r[7] or "",
                        "entities": r[8] or "",
                        "result_summary": r[9] or "",
                        "error_summary": r[10] or "",
                        "execution_time_ms": r[11] or 0,
                        "profile_id": r[12] or "default",
                    }
                    results.append(CommandRow(row_dict, r))
                return results

        except Exception as error:
            print(f"Get Recent Commands Error : {error}")
            return []

    # --------------------------------------------------

    def get_last_command(
        self
    ):
        """
        Return the most recently
        executed command.
        """

        commands = (
            self.get_recent_commands(
                limit=1
            )
        )

        if commands:

            return commands[0]

        return None

    # --------------------------------------------------

    def clear_command_history(
        self
    ):
        """
        Clear command execution history.
        """

        try:

            with self.lock:

                self.cursor.execute(
                    """
                    DELETE FROM command_history
                    """
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Clear Command History Error : "
                f"{error}"
            )

            return False

    # --------------------------------------------------

    def trim_command_history(
        self,
        keep_last=500
    ):
        """
        Prevent unlimited command
        history growth.
        """

        try:

            keep_last = max(
                1,
                int(keep_last)
            )

            with self.lock:

                self.cursor.execute(
                    """
                    DELETE FROM command_history
                    WHERE id NOT IN
                    (
                        SELECT id
                        FROM command_history
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    """,
                    (
                        keep_last,
                    )
                )

                self.connection.commit()

            return True

        except Exception as error:

            print(
                f"Trim Command History Error : "
                f"{error}"
            )

            return False

    # ==================================================
    # CLEANUP / SYNCHRONIZATION
    # ==================================================

    def remove_missing_files(
        self,
        commit=True
    ):

        try:

            with self.lock:

                self.cursor.execute(
                    """
                    SELECT full_path
                    FROM files
                    """
                )

                paths = (
                    self.cursor.fetchall()
                )

                removed_count = 0

                for (full_path,) in paths:

                    if not Path(
                        full_path
                    ).is_file():

                        self.cursor.execute(
                            """
                            DELETE FROM files
                            WHERE full_path = ?
                            """,
                            (
                                full_path,
                            )
                        )

                        removed_count += 1

                if commit:

                    self.connection.commit()

            return removed_count

        except Exception as error:

            print(
                f"Remove Missing Files Error : "
                f"{error}"
            )

            return 0

    # --------------------------------------------------

    def remove_missing_folders(
        self,
        commit=True
    ):

        try:

            with self.lock:

                self.cursor.execute(
                    """
                    SELECT full_path
                    FROM folders
                    """
                )

                paths = (
                    self.cursor.fetchall()
                )

                removed_count = 0

                for (full_path,) in paths:

                    if not Path(
                        full_path
                    ).is_dir():

                        self.cursor.execute(
                            """
                            DELETE FROM folders
                            WHERE full_path = ?
                            """,
                            (
                                full_path,
                            )
                        )

                        removed_count += 1

                if commit:

                    self.connection.commit()

            return removed_count

        except Exception as error:

            print(
                f"Remove Missing Folders Error : "
                f"{error}"
            )

            return 0

    # ==================================================
    # DATABASE CLEANUP
    # ==================================================

    def clear_database(
        self
    ):
        """
        Remove all stored ASTRA data.
        """

        with self.lock:

            self.cursor.execute(
                "DELETE FROM applications"
            )

            self.cursor.execute(
                "DELETE FROM aliases"
            )

            self.cursor.execute(
                "DELETE FROM files"
            )

            self.cursor.execute(
                "DELETE FROM folders"
            )

            self.cursor.execute(
                "DELETE FROM conversation_context"
            )

            self.cursor.execute(
                "DELETE FROM user_context"
            )

            self.cursor.execute(
                "DELETE FROM command_history"
            )

            self.cursor.execute(
                "DELETE FROM emotion_logs"
            )

            self.cursor.execute(
                "DELETE FROM memory_episodes"
            )

            self.cursor.execute(
                "DELETE FROM emotional_state"
            )

            self.cursor.execute(
                """
                INSERT INTO emotional_state
                (id, current_mood, valence, arousal, rapport_level, last_trigger, updated_at)
                VALUES (1, 'neutral', 0.5, 0.5, 0.7, 'reset', ?)
                """,
                (self._now(),)
            )

            self.connection.commit()

    # ==================================================
    # CLOSE DATABASE
    # ==================================================

    def close(
        self
    ):
        """
        Close SQLite connection safely.
        """

        try:

            with self.lock:

                if self.connection:

                    self.connection.commit()

                    self.connection.close()

                    self.connection = None

        except Exception:

            pass