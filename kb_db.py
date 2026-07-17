import sqlite3
import json
import uuid
import logging
from datetime import datetime

logger = logging.getLogger("document-context-retrieval-system")
DB_PATH = "kb_explorer.db"

def init_kb_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kb_answers (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                document_hash TEXT,
                query_pattern TEXT,
                user_query TEXT,
                answer_text TEXT,
                source_citations TEXT,
                faithfulness_score REAL,
                frozen BOOLEAN DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to init kb_answers table: {str(e)}")

def save_kb_answer(document_id: str, document_hash: str, query_pattern: str, user_query: str, 
                   answer_text: str, source_citations: list, faithfulness_score: float):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if an unfrozen one already exists for this pattern/hash.
        # If so, we can overwrite it to keep it clean, or just insert new ones.
        # We will just insert new ones, and maybe later we can clean up.
        # But wait, to keep it simple, we'll insert a new row.
        
        kb_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO kb_answers 
            (id, document_id, document_hash, query_pattern, user_query, answer_text, 
             source_citations, faithfulness_score, frozen, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (
            kb_id, document_id, document_hash, query_pattern, user_query, answer_text,
            json.dumps(source_citations), faithfulness_score, now, now
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save KB answer: {str(e)}")

def get_frozen_answer(document_hash: str, query_pattern: str):
    if query_pattern == "other":
        return None
        
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM kb_answers 
            WHERE document_hash = ? AND query_pattern = ? AND frozen = 1
            ORDER BY updated_at DESC LIMIT 1
        """, (document_hash, query_pattern))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            d = dict(row)
            d["source_citations"] = json.loads(d["source_citations"])
            d["frozen"] = bool(d["frozen"])
            return d
        return None
    except Exception as e:
        logger.error(f"Failed to fetch frozen KB answer: {str(e)}")
        return None

def get_all_kb_answers():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM kb_answers ORDER BY created_at DESC LIMIT 100")
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            d = dict(row)
            d["source_citations"] = json.loads(d["source_citations"])
            d["frozen"] = bool(d["frozen"])
            results.append(d)
        return results
    except Exception as e:
        logger.error(f"Failed to get all KB answers: {str(e)}")
        return []

def toggle_freeze_kb_answer(kb_id: str, freeze: bool):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if freeze:
            # Check score
            cursor.execute("SELECT faithfulness_score FROM kb_answers WHERE id = ?", (kb_id,))
            row = cursor.fetchone()
            if not row or row["faithfulness_score"] < 0.95:
                conn.close()
                raise ValueError("Cannot freeze answer with faithfulness < 0.95")
                
        cursor.execute("UPDATE kb_answers SET frozen = ?, updated_at = ? WHERE id = ?", 
                       (1 if freeze else 0, datetime.now().isoformat(), kb_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to toggle freeze for KB answer: {str(e)}")
        raise e
