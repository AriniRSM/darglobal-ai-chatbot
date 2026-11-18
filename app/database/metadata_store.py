"""SQLite bookkeeping for crawl/index deduplication and recovery."""
from contextlib import closing
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("METADATA_DB", "data/metadata.sqlite3")

def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS ingestion (
        url TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        status TEXT NOT NULL,
        content_hash TEXT,
        scraped_at TEXT,
        indexed_at TEXT,
        chunk_count INTEGER NOT NULL DEFAULT 0,
        error TEXT
    )""")
    return db

def existing_hash(url):
    with closing(connect()) as db:
        row = db.execute("SELECT content_hash FROM ingestion WHERE url=?", (url,)).fetchone()
    return row[0] if row else None

def record(url, source, status, content_hash=None, scraped_at=None, indexed_at=None, chunk_count=0, error=None):
    with closing(connect()) as db:
        with db:
            db.execute("""INSERT OR REPLACE INTO ingestion
                (url,source,status,content_hash,scraped_at,indexed_at,chunk_count,error)
                VALUES (?,?,?,?,?,?,?,?)""",
                (url,source,status,content_hash,scraped_at,indexed_at,chunk_count,error))
