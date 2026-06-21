#!/usr/bin/env python3
"""
Dashboard Backend Server
Flask API server to trigger scrapers, query database records, and serve dashboard UI.
"""

import os
import sys
import sqlite3
import subprocess
import threading
import json
from flask import Flask, jsonify, request, send_from_directory, Response

app = Flask(__name__, static_folder="static", static_url_path="")
DB_PATH = "data/cold_data.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

# Background runner thread function
def run_pipeline_async(command_args, run_id):
    try:
        # Run orchestrator as subprocess
        result = subprocess.run(
            [sys.executable, "orchestrator.py"] + command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Log outcome
        print(f"[Async Runner] Completed Run ID {run_id}. Exit code: {result.returncode}")
    except Exception as e:
        print(f"[Async Runner] Execution failed for Run ID {run_id}: {e}")

@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")

@app.route("/api/status")
def get_status():
    """
    Returns general stats and metrics.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count totals
        cursor.execute("SELECT COUNT(*) FROM leads WHERE duplicate_of IS NULL")
        clean_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE duplicate_of IS NOT NULL")
        duplicate_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM runs")
        runs_count = cursor.fetchone()[0]
        
        # Get system loads natively on Linux
        cpu_load = 0.0
        try:
            with open("/proc/loadavg", "r") as f:
                cpu_load = float(f.read().split()[0])
        except Exception:
            pass
            
        conn.close()
        
        return jsonify({
            "db_healthy": True,
            "total_clean_leads": clean_count,
            "total_duplicates": duplicate_count,
            "total_runs": runs_count,
            "cpu_load": cpu_load
        })
    except Exception as e:
        return jsonify({"db_healthy": False, "error": str(e)}), 500

@app.route("/api/runs", methods=["GET"])
def get_runs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM runs ORDER BY id DESC")
        runs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(runs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/leads", methods=["GET"])
def get_leads():
    run_id = request.args.get("run_id")
    search = request.args.get("search")
    show_duplicates = request.args.get("duplicates", "false").lower() == "true"
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT l.*, r.query as run_query, r.region as run_region
        FROM leads l
        LEFT JOIN runs r ON l.run_id = r.id
        WHERE 1=1
        """
        params = []
        
        if not show_duplicates:
            query += " AND l.duplicate_of IS NULL"
            
        if run_id:
            query += " AND l.run_id = ?"
            params.append(run_id)
            
        if search:
            query += " AND (l.name LIKE ? OR l.address LIKE ? OR l.category LIKE ?)"
            like_val = f"%{search}%"
            params.extend([like_val, like_val, like_val])
            
        query += " ORDER BY l.id DESC"
        
        cursor.execute(query, params)
        leads = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(leads)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/runs/<int:run_id>", methods=["DELETE"])
def delete_run(run_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM leads WHERE run_id = ?", (run_id,))
        cursor.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Run {run_id} and its leads deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/trigger", methods=["POST"])
def trigger_run():
    """
    Launches a new scraper run in the background.
    """
    data = request.json or {}
    query = data.get("query")
    region = data.get("region")
    limit = data.get("limit")
    
    if not query or not region:
        return jsonify({"error": "Missing query or region"}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create a pending run in the DB to immediately return a run_id to the UI
        cursor.execute(
            "INSERT INTO runs (query, region, status) VALUES (?, ?, 'running')",
            (query, region)
        )
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Construct parameters for the orchestrator
        # Note: orchestrator.py will update the same run_id record if we write custom logic,
        # but to keep it simple, we run run-all and let the database entries flow.
        # To avoid creating a double run, we will run the modules individually in sequence!
        cmd_args = ["run-all", "-q", query, "-r", region, "-o", f"data_{run_id}", "--run-id", str(run_id)]
        if limit:
            cmd_args += ["-l", str(limit)]
            
        # Spawn async thread
        thread = threading.Thread(target=run_pipeline_async, args=(cmd_args, run_id))
        thread.start()
        
        return jsonify({"status": "started", "run_id": run_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/action", methods=["POST"])
def trigger_action():
    """
    Triggers separate pipeline stages (enrich, validate, dedup).
    """
    data = request.json or {}
    action = data.get("action") # enrich, validate, dedup
    
    if action not in ("enrich", "validate", "dedup"):
        return jsonify({"error": "Invalid action"}), 400
        
    try:
        # Spawn async thread for action
        thread = threading.Thread(target=run_pipeline_async, args=([action], 0))
        thread.start()
        return jsonify({"status": "started", "action": action})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/export", methods=["GET"])
def download_export():
    """
    Helper to trigger XML or CSV exports and download the file.
    """
    run_id = request.args.get("run_id")
    format_type = request.args.get("format", "csv").lower()
    
    if format_type not in ("csv", "xml"):
        return "Invalid format", 400
        
    prefix = f"export_run_{run_id}" if run_id else "export_all"
    
    # Run export script
    cmd = [sys.executable, "pipeline/export_converter.py", "-o", prefix]
    if run_id:
        cmd += ["--run-id", run_id]
        
    try:
        subprocess.run(cmd, check=True)
        filename = f"{prefix}.{format_type}"
        return send_from_directory(".", filename, as_attachment=True)
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Cold Data Dashboard on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
