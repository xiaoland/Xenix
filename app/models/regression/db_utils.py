#!/usr/bin/env python3
"""
Database utility for storing task results in PostgreSQL.
"""
import os
import json
import psycopg2
from datetime import datetime


def get_db_connection():
    """Get database connection from environment variable"""
    db_url = os.environ.get('DATABASE_URL', 'postgresql://xenix:xenix_password@localhost:5432/xenix_db')
    return psycopg2.connect(db_url)


def update_task_status(task_id, status, error=None):
    """Update task status in database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if error:
            cur.execute(
                """UPDATE tasks SET status = %s, error = %s, updated_at = %s 
                   WHERE task_id = %s""",
                (status, error, datetime.now(), task_id)
            )
        else:
            cur.execute(
                """UPDATE tasks SET status = %s, updated_at = %s 
                   WHERE task_id = %s""",
                (status, datetime.now(), task_id)
            )
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Failed to update task status: {e}")


def store_model_result(task_id, model_name, params, metrics):
    """Store model tuning results in database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            """INSERT INTO model_results 
               (task_id, model, params, mse_train, mae_train, r2_train, 
                mse_test, mae_test, r2_test, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                task_id,
                model_name,
                json.dumps(params),
                str(metrics.get('mse_train', '')),
                str(metrics.get('mae_train', '')),
                str(metrics.get('r2_train', '')),
                str(metrics.get('mse_test', '')),
                str(metrics.get('mae_test', '')),
                str(metrics.get('r2_test', '')),
                datetime.now()
            )
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Failed to store model result: {e}")


def store_comparison_result(task_id, results, best_model):
    """Store model comparison results in database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            """INSERT INTO comparison_results 
               (task_id, results, best_model, created_at)
               VALUES (%s, %s, %s, %s)""",
            (
                task_id,
                json.dumps(results),
                best_model,
                datetime.now()
            )
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Failed to store comparison result: {e}")
