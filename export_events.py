#!/usr/bin/env python3
"""
Export events from PostgreSQL to JSONL format for HackerEarth submission.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


def get_database_url() -> str:
    """Get database URL from environment or .env file."""
    # Try environment variable first
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    
    # Try to read from .env file
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    return line.split("=", 1)[1].strip()
    
    # Fallback to default
    return "postgresql://store:CHANGE_ME_STRONG_PASSWORD@localhost:5432/store_intelligence"


def export_events_to_jsonl(output_path: str = "events.jsonl") -> dict[str, Any]:
    """Export events from PostgreSQL to JSONL format."""
    
    # Connect to database
    db_url = get_database_url()
    print(f"Connecting to database...")
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Query events
    query = """
    SELECT 
        event_id,
        timestamp,
        person_id,
        COALESCE(canonical_type, event_type) as event_type,
        zone_id,
        store_id,
        metadata_json->>'camera_id' as camera_id,
        frame_index,
        video_time_sec,
        metadata_json->>'confidence' as confidence,
        metadata_json->'bbox' as bbox,
        metadata_json->'centroid' as centroid,
        metadata_json->>'person_type' as person_type,
        session_id,
        metadata_json->>'dwell_sec' as dwell_sec,
        metadata_json->>'dwell_total_sec' as dwell_total_sec,
        metadata_json->>'visit_number' as visit_number,
        metadata_json->>'is_reentry' as is_reentry,
        metadata_json->>'entry_line' as entry_line,
        metadata_json->>'exit_reason' as exit_reason,
        metadata_json->>'zone_type' as zone_type,
        metadata_json->>'zone_name' as zone_name,
        metadata_json->>'reason' as reason,
        metadata_json->>'video_source' as video_source
    FROM events
    ORDER BY timestamp
    """
    
    print(f"Executing query...")
    cursor.execute(query)
    events = cursor.fetchall()
    
    print(f"Found {len(events)} events")
    
    # Export to JSONL
    output_file = os.path.join(os.path.dirname(__file__), output_path)
    print(f"Writing to {output_file}...")
    
    exported_count = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for event in events:
            # Convert event dict to proper format
            event_dict = dict(event)
            
            # Convert UUID to string
            if event_dict.get("event_id"):
                event_dict["event_id"] = str(event_dict["event_id"])
            if event_dict.get("session_id"):
                event_dict["session_id"] = str(event_dict["session_id"])
            
            # Convert timestamp to ISO format
            if event_dict.get("timestamp"):
                if isinstance(event_dict["timestamp"], datetime):
                    event_dict["timestamp"] = event_dict["timestamp"].isoformat()
                else:
                    event_dict["timestamp"] = str(event_dict["timestamp"])
            
            # Convert numeric types
            if event_dict.get("video_time_sec"):
                event_dict["video_time_sec"] = float(event_dict["video_time_sec"])
            
            # Parse JSON fields from JSONB
            if event_dict.get("bbox"):
                try:
                    event_dict["bbox"] = json.loads(event_dict["bbox"]) if isinstance(event_dict["bbox"], str) else event_dict["bbox"]
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if event_dict.get("centroid"):
                try:
                    event_dict["centroid"] = json.loads(event_dict["centroid"]) if isinstance(event_dict["centroid"], str) else event_dict["centroid"]
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Convert boolean strings to actual booleans
            for bool_field in ["is_reentry"]:
                if event_dict.get(bool_field):
                    if isinstance(event_dict[bool_field], str):
                        event_dict[bool_field] = event_dict[bool_field].lower() == "true"
            
            # Remove None values
            event_dict = {k: v for k, v in event_dict.items() if v is not None}
            
            # Write as JSON line
            f.write(json.dumps(event_dict, separators=(",", ":")) + "\n")
            exported_count += 1
    
    cursor.close()
    conn.close()
    
    return {
        "output_file": output_file,
        "total_events": exported_count,
        "query_count": len(events)
    }


def validate_jsonl(file_path: str) -> dict[str, Any]:
    """Validate JSONL file format."""
    print(f"Validating {file_path}...")
    
    valid_lines = 0
    invalid_lines = 0
    sample_lines = []
    
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            
            try:
                obj = json.loads(line)
                valid_lines += 1
                
                # Collect first 5 sample lines
                if len(sample_lines) < 5:
                    sample_lines.append(obj)
            except json.JSONDecodeError as e:
                invalid_lines += 1
                print(f"Invalid JSON at line {i+1}: {e}")
    
    return {
        "valid_lines": valid_lines,
        "invalid_lines": invalid_lines,
        "sample_lines": sample_lines
    }


def main():
    """Main entry point."""
    print("=" * 60)
    print("HackerEarth Event Log Export")
    print("=" * 60)
    print()
    
    # Export events
    result = export_events_to_jsonl("events.jsonl")
    
    print()
    print("=" * 60)
    print("Export Results")
    print("=" * 60)
    print(f"Output File: {result['output_file']}")
    print(f"Total Events Exported: {result['total_events']}")
    print()
    
    # Validate
    validation = validate_jsonl(result['output_file'])
    
    print("=" * 60)
    print("Validation Results")
    print("=" * 60)
    print(f"Valid Lines: {validation['valid_lines']}")
    print(f"Invalid Lines: {validation['invalid_lines']}")
    print()
    
    # Show sample
    print("=" * 60)
    print("Sample First 5 Lines")
    print("=" * 60)
    for i, line in enumerate(validation['sample_lines'], 1):
        print(f"Line {i}:")
        print(json.dumps(line, indent=2))
        print()
    
    # Final status
    print("=" * 60)
    print("Export Status")
    print("=" * 60)
    if validation['invalid_lines'] == 0 and validation['valid_lines'] > 0:
        print("✅ SUCCESS: events.jsonl generated and validated")
        print(f"📁 File: {result['output_file']}")
        print(f"📊 Total Events: {validation['valid_lines']}")
    else:
        print("❌ FAILED: Validation errors detected")
        sys.exit(1)


if __name__ == "__main__":
    main()
