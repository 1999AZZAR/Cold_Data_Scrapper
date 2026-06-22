#!/usr/bin/env python3
"""
Orchestrator CLI
Unified controller interface to sequence pipeline tasks and return JSON status logs.
Useful for dashboard integration.
"""

import os
import sys
import argparse
import subprocess
import json
from dotenv import load_dotenv

load_dotenv()

def log(msg, level="INFO"):
    print(f"[{level}] {msg}", file=sys.stderr)

def run_command(args):
    """
    Helper to execute script command and return status.
    """
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return {"status": "success", "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except subprocess.CalledProcessError as e:
        return {"status": "failed", "stdout": e.stdout.strip(), "stderr": e.stderr.strip(), "code": e.returncode}

def main():
    parser = argparse.ArgumentParser(description="Unified controller orchestrator for Cold Data Pipeline.")
    subparsers = parser.add_subparsers(dest="command", help="Orchestration command")
    
    # 1. init
    subparsers.add_parser("init", help="Initialize Database")
    
    # 2. extract-osm
    p_osm = subparsers.add_parser("extract-osm", help="Run OSM extractor")
    p_osm.add_argument("-q", "--query", required=True)
    p_osm.add_argument("-r", "--region", required=True)
    p_osm.add_argument("-o", "--output")
    p_osm.add_argument("-l", "--limit", type=int)
    p_osm.add_argument("--run-id", type=int)
    
    # 3. extract-gmaps
    p_gm = subparsers.add_parser("extract-gmaps", help="Run Google Maps extractor")
    p_gm.add_argument("-q", "--query", required=True)
    p_gm.add_argument("-r", "--region", required=True)
    p_gm.add_argument("-k", "--key")
    p_gm.add_argument("-l", "--limit", type=int)
    p_gm.add_argument("-o", "--output")
    p_gm.add_argument("--run-id", type=int)
    p_gm.add_argument("--search-id")
    
    # 4. enrich
    subparsers.add_parser("enrich", help="Run Social Contacts Enricher")
    
    # 5. validate
    subparsers.add_parser("validate", help="Run Contact Validator")
    
    # 6. dedup
    subparsers.add_parser("dedup", help="Run Deduplicator")
    
    # 7. export
    p_exp = subparsers.add_parser("export", help="Run Export Converter")
    p_exp.add_argument("-o", "--output", required=True)
    p_exp.add_argument("--run-id", type=int)
    p_exp.add_argument("-q", "--query")
    p_exp.add_argument("-r", "--region")
    
    # 8. run-all
    p_all = subparsers.add_parser("run-all", help="Sequence entire pipeline end-to-end")
    p_all.add_argument("-q", "--query", required=True)
    p_all.add_argument("-r", "--region", required=True)
    p_all.add_argument("-o", "--output", required=True)
    p_all.add_argument("-l", "--limit", type=int)
    p_all.add_argument("-k", "--key")
    p_all.add_argument("--run-id", type=int)
    p_all.add_argument("--search-id")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    out_json = {}
    
    if args.command == "init":
        out_json = run_command([sys.executable, "pipeline/db_init.py"])
        
    elif args.command == "extract-osm":
        cmd = [sys.executable, "pipeline/extractor_osm.py", "-q", args.query, "-r", args.region]
        if args.output: cmd += ["-o", args.output]
        if args.limit: cmd += ["-l", str(args.limit)]
        if args.run_id: cmd += ["--run-id", str(args.run_id)]
        out_json = run_command(cmd)
        
    elif args.command == "extract-gmaps":
        cmd = [sys.executable, "pipeline/extractor_gmaps.py", "-q", args.query, "-r", args.region]
        if args.key: cmd += ["-k", args.key]
        if args.limit: cmd += ["-l", str(args.limit)]
        if args.output: cmd += ["-o", args.output]
        if args.run_id: cmd += ["--run-id", str(args.run_id)]
        if args.search_id: cmd += ["--search-id", args.search_id]
        out_json = run_command(cmd)
        
    elif args.command == "enrich":
        out_json = run_command([sys.executable, "pipeline/enricher_socials.py"])
        
    elif args.command == "validate":
        out_json = run_command([sys.executable, "pipeline/validator_contacts.py"])
        
    elif args.command == "dedup":
        out_json = run_command([sys.executable, "pipeline/deduplicator.py"])
        
    elif args.command == "export":
        cmd = [sys.executable, "pipeline/export_converter.py", "-o", args.output]
        if args.run_id: cmd += ["--run-id", str(args.run_id)]
        if args.query: cmd += ["-q", args.query]
        if args.region: cmd += ["-r", args.region]
        out_json = run_command(cmd)
        
    elif args.command == "run-all":
        steps = []
        
        # 1. Run OSM Extractor
        log(f"Step 1/6: Running OSM Extractor...")
        osm_cmd = [sys.executable, "pipeline/extractor_osm.py", "-q", args.query, "-r", args.region]
        if args.limit: osm_cmd += ["-l", str(args.limit)]
        if args.run_id: osm_cmd += ["--run-id", str(args.run_id)]
        res_osm = run_command(osm_cmd)
        steps.append({"step": "extract-osm", "result": res_osm})
        
        # 2. Run Google Maps Extractor
        log(f"Step 2/6: Running Google Maps Extractor...")
        gmaps_cmd = [sys.executable, "pipeline/extractor_gmaps.py", "-q", args.query, "-r", args.region]
        if args.key: gmaps_cmd += ["-k", args.key]
        if args.limit: gmaps_cmd += ["-l", str(args.limit)]
        if args.run_id: gmaps_cmd += ["--run-id", str(args.run_id)]
        if args.search_id: gmaps_cmd += ["--search-id", args.search_id]
        res_gmaps = run_command(gmaps_cmd)
        steps.append({"step": "extract-gmaps", "result": res_gmaps})
        
        if res_osm["status"] == "success" or res_gmaps["status"] == "success":
            # 3. Run Social Media Enricher
            log(f"Step 3/6: Running Social Enricher...")
            res_enrich = run_command([sys.executable, "pipeline/enricher_socials.py"])
            steps.append({"step": "enrich", "result": res_enrich})
            
            # 4. Run Contact Validator
            log(f"Step 4/6: Running Contacts Validator...")
            res_val = run_command([sys.executable, "pipeline/validator_contacts.py"])
            steps.append({"step": "validate", "result": res_val})
            
            # 5. Run Deduplicator
            log(f"Step 5/6: Running Deduplicator...")
            res_dedup = run_command([sys.executable, "pipeline/deduplicator.py"])
            steps.append({"step": "dedup", "result": res_dedup})
            
            # 6. Run Export Converter
            log(f"Step 6/6: Exporting results...")
            exp_cmd = [sys.executable, "pipeline/export_converter.py", "-o", args.output, "-q", args.query, "-r", args.region]
            res_exp = run_command(exp_cmd)
            steps.append({"step": "export", "result": res_exp})
            
            status = "success" if res_exp["status"] == "success" else "failed"
        else:
            status = "failed"
            
        out_json = {"status": status, "steps": steps}
        
    # Return structured JSON output for dashboard interface
    print(json.dumps(out_json, indent=2))

if __name__ == "__main__":
    main()
