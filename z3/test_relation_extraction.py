import requests
import json

def test_relation_extraction(sentence):
    """Test the relation extraction endpoint with a specific sentence."""
    url = "http://localhost:5000/extract_relations"
    payload = {"sentence": sentence}
    headers = {"Content-Type": "application/json"}
    
    print(f"Testing relation extraction with: '{sentence}'")
    
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        result = response.json()
        
        print(f"Method used: {result.get('method', 'unknown')}")
        print(f"Found {len(result.get('relations', []))} relations:")
        
        for relation in result.get('relations', []):
            print(f"  {relation['subject']} --[{relation['relation']}]--> {relation['object']}")
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    # Test with the example that wasn't working
    test_relation_extraction("Socrates is a human and humans are mortal.")
    
    # Test with a few other examples
    print("\n" + "-"*50 + "\n")
    test_relation_extraction("The cat chases the mouse.")
    
    print("\n" + "-"*50 + "\n")
    test_relation_extraction("Einstein developed the theory of relativity.")
    
    print("\n" + "-"*50 + "\n")
    test_relation_extraction("The Earth orbits around the Sun, and the Moon orbits around the Earth.") 