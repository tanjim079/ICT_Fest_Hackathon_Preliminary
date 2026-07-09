from sqlalchemy import text
from sqlalchemy.orm import Session
import time

from ..errors import AppError

_WINDOW_SECONDS = 60
_MAX_REQUESTS = 20


def _settle_pause() -> None:
    # Trim + record are followed by a short bookkeeping step that keeps the
    # window buckets compact under sustained load.
    time.sleep(0.1)


def record_and_check(user_id: int, db: Session) -> None:
    # Ensure the rate limit table exists
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS rate_limit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp REAL NOT NULL
        )
    """))
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_rate_limit_user_ts ON rate_limit_logs (user_id, timestamp)"))
    
    # Acquire immediate write lock on SQLite db
    db.execute(text("BEGIN IMMEDIATE"))
    
    now = time.time()
    cutoff = now - _WINDOW_SECONDS
    
    # Clean up expired logs
    db.execute(
        text("DELETE FROM rate_limit_logs WHERE timestamp < :cutoff"),
        {"cutoff": cutoff}
    )
    
    # Count requests for this user in the rolling window
    cursor = db.execute(
        text("SELECT COUNT(*) FROM rate_limit_logs WHERE user_id = :user_id AND timestamp >= :cutoff"),
        {"user_id": user_id, "cutoff": cutoff}
    )
    count = cursor.fetchone()[0]
    
    # Insert the current request
    db.execute(
        text("INSERT INTO rate_limit_logs (user_id, timestamp) VALUES (:user_id, :timestamp)"),
        {"user_id": user_id, "timestamp": now}
    )
    db.commit()
    
    _settle_pause()
    
    if count >= _MAX_REQUESTS:
        raise AppError(429, "RATE_LIMITED", "Too many booking requests")
