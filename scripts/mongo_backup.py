#!/usr/bin/env python3
"""Script to manage MongoDB test data."""
import json
import os
import argparse
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient

class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for MongoDB data types."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def get_database():
    # Use localhost when running script locally, mongodb when running in container
    client = MongoClient("mongodb://localhost:27017/")
    database = os.getenv("MONGO_DATABASE", "ai-sdlc-codereview-api")
    return client[database]

def dump_database(test_data_dir: str = "test_data"):
    """Dump the current state of MongoDB to the test_data directory."""
    db = get_database()
    
    # Create dumps directory if it doesn't exist
    dumps_dir = os.path.join(test_data_dir, "mongodb_dumps")
    os.makedirs(dumps_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(dumps_dir, f"mongodb_dump_{timestamp}.json")
    
    # Dump data
    dump_data = {}
    for collection_name in db.list_collection_names():
        documents = list(db[collection_name].find())
        # Convert ObjectId to string for JSON serialization
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        dump_data[collection_name] = documents
    
    # Save to file using custom encoder
    with open(output_file, 'w') as f:
        json.dump(dump_data, f, indent=2, cls=MongoJSONEncoder)
    
    print(f"Database dumped to: {output_file}")
    return output_file

def convert_string_ids_to_objectid(data):
    """Convert string IDs to ObjectId in the MongoDB dump data"""
    if isinstance(data, dict):
        for key, value in data.items():
            if key == '_id' or key.endswith('_id'):
                if isinstance(value, str):
                    try:
                        data[key] = ObjectId(value)
                    except:
                        pass
            # Handle arrays of IDs (like classification_ids)
            elif key.endswith('_ids') and isinstance(value, list):
                data[key] = [ObjectId(id_str) for id_str in value if isinstance(id_str, str)]
            elif isinstance(value, (dict, list)):
                convert_string_ids_to_objectid(value)
    elif isinstance(data, list):
        for item in data:
            convert_string_ids_to_objectid(item)
    return data

def convert_string_dates_to_datetime(data):
    """Convert string dates to datetime objects in the MongoDB dump data"""
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ['created_at', 'updated_at'] and isinstance(value, str):
                try:
                    data[key] = datetime.fromisoformat(value)
                except:
                    pass
            elif isinstance(value, (dict, list)):
                convert_string_dates_to_datetime(value)
    elif isinstance(data, list):
        for item in data:
            convert_string_dates_to_datetime(item)
    return data

def restore_database(dump_file: str = None):
    """Restore MongoDB database from a JSON dump file"""
    # If no file specified, use the most recent dump
    if dump_file is None:
        dumps_dir = "test_data/mongodb_dumps"
        if not os.path.exists(dumps_dir):
            print("No dumps directory found")
            return
        
        dumps = sorted([f for f in os.listdir(dumps_dir) if f.endswith('.json')],
                      key=lambda x: os.path.getmtime(os.path.join(dumps_dir, x)),
                      reverse=True)
        
        if not dumps:
            print("No dump files found")
            return
        
        dump_file = os.path.join(dumps_dir, dumps[0])
    
    if not os.path.exists(dump_file):
        print(f"Dump file not found: {dump_file}")
        return
    
    # Load and restore the data
    with open(dump_file) as f:
        data = json.load(f)
    
    # Convert string IDs to ObjectId and dates to datetime
    data = convert_string_ids_to_objectid(data)
    data = convert_string_dates_to_datetime(data)
    
    db = get_database()
    
    # Clear existing collections
    for collection_name in data.keys():
        if collection_name in db.list_collection_names():
            db[collection_name].delete_many({})
    
    # Insert the data
    for collection_name, documents in data.items():
        if documents:  # Only insert if there are documents
            db[collection_name].insert_many(documents)
    
    print(f"Database restored from: {dump_file}")

def main():
    parser = argparse.ArgumentParser(description="Manage MongoDB test data")
    parser.add_argument('action', choices=['dump', 'restore'],
                       help='Action to perform (dump/restore)')
    parser.add_argument('--file', '-f',
                       help='Specific dump file to restore from (for restore action)')
    
    args = parser.parse_args()
    
    if args.action == 'dump':
        dump_database()
    elif args.action == 'restore':
        restore_database(args.file)

if __name__ == "__main__":
    main()
