from neo4j import GraphDatabase

# URI examples: "neo4j://localhost", "neo4j+s://xxx.databases.neo4j.io"
URI = "neo4j://192.168.137.7"
AUTH = ("neo4j", "3lor-qna")

def save_relation(source_node, target_node, relation_type, properties=None):
    if not source_node or not target_node or not relation_type:
        return False
    
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        if not driver:
            return False
            
        try:
            driver.verify_connectivity()
            with driver.session() as session:
                # Create the Cypher query to create/merge nodes and relationship
                query = (
                    f"MERGE (source:{source_node['label']} {dict_to_props(source_node['props'])}) "
                    f"MERGE (target:{target_node['label']} {dict_to_props(target_node['props'])}) "
                    f"MERGE (source)-[r:{relation_type}]->(target)"
                )
                
                # Add properties to relationship if provided
                if properties:
                    query += f" SET r = {dict_to_props(properties)}"
                
                result = session.run(query)
                return True
        except Exception as e:
            print(f"Error saving relation: {e}")
            return False

def find_relations(query):
    """
    Find relations in Neo4j based on a search query.
    The query can be an entity name or a relation type.
    Returns a list of relation objects with source, relation_type, and target.
    """
    if not query:
        return []
    
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        if not driver:
            return []
            
        try:
            driver.verify_connectivity()
            with driver.session() as session:
                # Create Cypher query to find relations by node name or relation type
                # This looks for nodes whose name property contains the query term
                # or relations whose type contains the query term
                cypher_query = """
                MATCH (source)-[r]->(target)
                WHERE 
                    source.name CONTAINS $query OR
                    target.name CONTAINS $query OR
                    type(r) CONTAINS toUpper($query)
                RETURN source.name as source, type(r) as relation_type, target.name as target
                LIMIT 50
                """
                
                result = session.run(cypher_query, query=query)
                
                # Convert the results to a list of dictionaries
                relations = []
                for record in result:
                    relations.append({
                        "source": record["source"],
                        "relation_type": record["relation_type"],
                        "target": record["target"]
                    })
                
                return relations
        except Exception as e:
            print(f"Error finding relations: {e}")
            return []
    
def dict_to_props(props):
    """Convert a Python dictionary to Neo4j properties string format."""
    if not props:
        return "{}"
    props_str = "{"
    for key, value in props.items():
        if isinstance(value, str):
            props_str += f"{key}: \"{value}\", "
        else:
            props_str += f"{key}: {value}, "
    props_str = props_str.rstrip(", ") + "}"
    return props_str

# Example usage:
# source = {"label": "Person", "props": {"name": "John", "age": 30}}
# target = {"label": "Company", "props": {"name": "Acme Inc"}}
# save_relation(source, target, "WORKS_FOR", {"since": 2020})