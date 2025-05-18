from pymongo import MongoClient

# MongoDB connection settings - update with your MongoDB connection info
MONGO_URI = "mongodb://192.168.137.7:27017/"
DB_NAME = "relations_db"
COLLECTION_NAME = "relations"

def get_mongo_client():
    """Get a MongoDB client instance"""
    try:
        client = MongoClient(MONGO_URI)
        # Ping the server to test connection
        client.admin.command('ping')
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def save_relation(source_node, target_node, relation_type, properties=None):
    """
    Save a relation to MongoDB.
    
    Args:
        source_node: Dictionary with 'label' and 'props'
        target_node: Dictionary with 'label' and 'props'
        relation_type: String representing the relationship type
        properties: Optional dictionary of relationship properties
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not source_node or not target_node or not relation_type:
        return False
    
    client = get_mongo_client()
    if not client:
        return False
    
    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Create the relation document
        relation_doc = {
            "source": {
                "label": source_node["label"],
                "props": source_node["props"]
            },
            "target": {
                "label": target_node["label"],
                "props": target_node["props"]
            },
            "relation_type": relation_type
        }
        
        # Add properties if provided
        if properties:
            relation_doc["properties"] = properties
        
        # Insert the relation document
        result = collection.insert_one(relation_doc)
        
        return result.acknowledged
    except Exception as e:
        print(f"Error saving relation to MongoDB: {e}")
        return False
    finally:
        client.close()

def find_relations(query):
    """
    Find relations in MongoDB based on a search query.
    
    Args:
        query: String to search for in source name, target name, or relation type
        
    Returns:
        list: List of relation objects with source, relation_type, and target
    """
    if not query:
        return []
    
    client = get_mongo_client()
    if not client:
        return []
    
    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Create search query
        # This searches for the query string in source name, target name, or relation type
        search_query = {
            "$or": [
                {"source.props.name": {"$regex": query, "$options": "i"}},
                {"target.props.name": {"$regex": query, "$options": "i"}},
                {"relation_type": {"$regex": query, "$options": "i"}}
            ]
        }
        
        # Find matching relations
        cursor = collection.find(search_query).limit(50)
        
        # Convert the results to a list of dictionaries
        relations = []
        for doc in cursor:
            relations.append({
                "source": doc["source"]["props"]["name"],
                "relation_type": doc["relation_type"],
                "target": doc["target"]["props"]["name"]
            })
        
        return relations
    except Exception as e:
        print(f"Error finding relations in MongoDB: {e}")
        return []
    finally:
        client.close()

# Helper functions
def ensure_indexes():
    """Create necessary indexes for better query performance"""
    client = get_mongo_client()
    if not client:
        return False
    
    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Create indexes for fields we'll search on
        collection.create_index("source.props.name")
        collection.create_index("target.props.name")
        collection.create_index("relation_type")
        
        return True
    except Exception as e:
        print(f"Error creating indexes: {e}")
        return False
    finally:
        client.close()

# Initialize indexes when the module is imported
ensure_indexes()

# Example usage:
# source = {"label": "Person", "props": {"name": "John", "age": 30}}
# target = {"label": "Company", "props": {"name": "Acme Inc"}}
# save_relation(source, target, "WORKS_FOR", {"since": 2020}) 