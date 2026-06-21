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
    
    # 3. extract-gmaps
    p_gm = subparsers.add_parser("extract-gmaps", help="Run Google Maps extractor")
    p_gm.add_argument("-q", "--query", required=True)
    p_gm.add_argument("-r", "--region", required=True)
    p_gm.add_argument("-k", "--key")
    p_gm.add_argument("-l", "--limit", type=int)
    p_gm.add_argument("-o", "--output")
    
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
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    out_json = {}
    
    if args.command == "init":
        out_json = run_command([sys.executable, "db_init.py"])
        
    elif args.command == "extract-osm":
        cmd = [sys.executable, "extractor_osm.py", "-q", args.query, "-r", args.region]
        if args.output: cmd += ["-o", args.output]
        if args.limit: cmd += ["-l", str(args.limit)]
        out_json = run_command(cmd)
        
    elif args.command == "extract-gmaps":
        cmd = [sys.executable, "extractor_gmaps.py", "-q", args.query, "-r", args.region]
        if args.key: cmd += ["-k", args.key]
        if args.limit: cmd += ["-l", str(args.limit)]
        if args.output: cmd += ["-o", args.output]
        out_json = run_command(cmd)
        
    elif args.command == "enrich":
        out_json = run_command([sys.executable, "enricher_socials.py"])
        
    elif args.command == "validate":
        out_json = run_command([sys.executable, "validator_contacts.py"])
        
    elif args.command == "dedup":
        out_json = run_command([sys.executable, "deduplicator.py"])
        
    elif args.command == "export":
        cmd = [sys.executable, "export_converter.py", "-o", args.output]
        if args.run_id: cmd += ["--run-id", str(args.run_id)]
        if args.query: cmd += ["-q", args.query]
        if args.region: cmd += ["-r", args.region]
        out_json = run_command(cmd)
        
    elif args.command == "run-all":
        steps = []
        
        # 1. Run OSM Extractor
        log(f"Step 1/5: Running OSM Extractor...")
        osm_cmd = [sys.executable, "extractor_osm.py", "-q", args.query, "-r", args.region]
        if args.limit: osm_cmd += ["-l", str(args.limit)]
        res_osm = run_command(osm_cmd)
        steps.append({"step": "extract-osm", "result": res_osm})
        
        if res_osm["status"] == "success":
            # 2. Run Social Media Enricher
            log(f"Step 2/5: Running Social Enricher...")
            res_enrich = run_command([sys.executable, "enricher_socials.py"])
            steps.append({"step": "enrich", "result": res_enrich})
            
            # 3. Run Contact Validator
            log(f"Step 3/5: Running Contacts Validator...")
            res_val = run_command([sys.executable, "validator_contacts.py"])
            steps.append({"step": "validate", "result": res_val})
            
            # 4. Run Deduplicator
            log(f"Step 4/5: Running Deduplicator...")
            res_dedup = run_command([sys.executable, "deduplicator.py"])
            steps.append({"step": "dedup", "result": res_dedup})
            
            # 5. Run Export Converter
            log(f"Step 5/5: Exporting results...")
            exp_cmd = [sys.executable, "export_converter.py", "-o", args.output, "-q", args.query, "-r", args.region]
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
