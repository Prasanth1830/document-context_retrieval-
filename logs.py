import sqlite3
import json
from datetime import datetime
import logging
import uuid

logger = logging.getLogger("document-context-retrieval-system")
DB_PATH = "query_logs.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                document_id TEXT,
                user_query TEXT,
                answer_text TEXT,
                source_citations TEXT,
                faithfulness_score REAL,
                answer_relevance_score REAL,
                context_recall_score REAL,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to initialize logs DB: {str(e)}")

def log_rag_query(document_id: str, user_query: str, answer_text: str, source_citations: list, 
                  faithfulness_score: float, answer_relevance_score: float, 
                  context_recall_score: float, status: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        log_id = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO query_logs 
            (id, timestamp, document_id, user_query, answer_text, source_citations, 
             faithfulness_score, answer_relevance_score, context_recall_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log_id,
            datetime.now().isoformat(),
            document_id if document_id else "",
            user_query,
            answer_text,
            json.dumps(source_citations),
            faithfulness_score,
            answer_relevance_score,
            context_recall_score,
            status
        ))
        conn.commit()
        conn.close()
        return log_id
    except Exception as e:
        logger.error(f"Failed to log rag query: {str(e)}")
        return None

def get_query_logs(limit: int = 50):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, document_id, user_query, status, faithfulness_score, answer_relevance_score, context_recall_score FROM query_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in rows:
            logs.append(dict(row))
        return logs
    except Exception as e:
        logger.error(f"Failed to get recent logs: {str(e)}")
        return []

def get_query_log_by_id(log_id: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM query_logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            d = dict(row)
            d["source_citations"] = json.loads(d["source_citations"])
            return d
        return None
    except Exception as e:
        logger.error(f"Failed to get log by ID: {str(e)}")
        return None

def get_dashboard_stats():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # We need a 24h cutoff
        from datetime import datetime, timedelta
        cutoff_24h = (datetime.now() - timedelta(days=1)).isoformat()
        
        stats = {
            "avg_faithfulness_score": {"24h": 0.0, "all_time": 0.0},
            "avg_answer_relevance_score": {"24h": 0.0, "all_time": 0.0},
            "avg_context_recall_score": {"24h": 0.0, "all_time": 0.0},
            "error_rate": {"24h": 0.0, "all_time": 0.0},
            "avg_response_time_seconds": {"24h": 0.0},
            "total_queries_today": 0,
            "total_queries_all_time": 0,
            "corrections_applied_count": 0,
            "top_document_by_query_volume": {"document_id": "N/A", "count": 0},
            "per_document_breakdown": []
        }
        
        # All time queries
        cursor.execute("SELECT * FROM query_logs")
        all_logs = cursor.fetchall()
        
        if not all_logs:
            conn.close()
            return stats
            
        logs_24h = [log for log in all_logs if log["timestamp"] >= cutoff_24h]
        
        stats["total_queries_all_time"] = len(all_logs)
        stats["total_queries_today"] = len(logs_24h)
        
        # Calculate averages for 24h
        if logs_24h:
            stats["avg_faithfulness_score"]["24h"] = sum(log["faithfulness_score"] for log in logs_24h) / len(logs_24h)
            stats["avg_answer_relevance_score"]["24h"] = sum(log["answer_relevance_score"] for log in logs_24h) / len(logs_24h)
            stats["avg_context_recall_score"]["24h"] = sum(log["context_recall_score"] for log in logs_24h) / len(logs_24h)
            errors_24h = sum(1 for log in logs_24h if log["status"] in ["Blocked", "Flagged"])
            stats["error_rate"]["24h"] = (errors_24h / len(logs_24h)) * 100
            
        # Calculate averages for all time
        stats["avg_faithfulness_score"]["all_time"] = sum(log["faithfulness_score"] for log in all_logs) / len(all_logs)
        stats["avg_answer_relevance_score"]["all_time"] = sum(log["answer_relevance_score"] for log in all_logs) / len(all_logs)
        stats["avg_context_recall_score"]["all_time"] = sum(log["context_recall_score"] for log in all_logs) / len(all_logs)
        errors_all_time = sum(1 for log in all_logs if log["status"] in ["Blocked", "Flagged"])
        stats["error_rate"]["all_time"] = (errors_all_time / len(all_logs)) * 100
        
        # Document breakdown
        doc_stats = {}
        for log in all_logs:
            did = log["document_id"]
            if not did:
                did = "Unknown"
            if did not in doc_stats:
                doc_stats[did] = {"queries": 0, "faith_sum": 0.0, "errors": 0}
            doc_stats[did]["queries"] += 1
            doc_stats[did]["faith_sum"] += log["faithfulness_score"]
            if log["status"] in ["Blocked", "Flagged"]:
                doc_stats[did]["errors"] += 1
                
        # Find top document
        top_doc = None
        top_count = 0
        
        for did, data in doc_stats.items():
            if data["queries"] > top_count:
                top_count = data["queries"]
                top_doc = did
                
            stats["per_document_breakdown"].append({
                "document_id": did,
                "query_count": data["queries"],
                "avg_faithfulness_score": data["faith_sum"] / data["queries"],
                "error_rate": (data["errors"] / data["queries"]) * 100
            })
            
        if top_doc:
            stats["top_document_by_query_volume"] = {"document_id": top_doc, "count": top_count}
            
        conn.close()
        
        # Get corrections from KB Explorer
        try:
            kb_conn = sqlite3.connect("kb_explorer.db")
            kb_cursor = kb_conn.cursor()
            kb_cursor.execute("SELECT COUNT(*) FROM kb_answers WHERE frozen = 1")
            stats["corrections_applied_count"] = kb_cursor.fetchone()[0]
            kb_conn.close()
        except:
            pass # Ignore if KB db not ready
            
        return stats
    except Exception as e:
        logger.error(f"Failed to fetch dashboard stats: {str(e)}")
        return None
