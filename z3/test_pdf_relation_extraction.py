import requests
import json
import os
import sys

def test_pdf_extraction():
    url = "http://localhost:5999/extract_relations_from_pdf"
    pdf_path = "Sun.pdf"
    
    # Allow overriding the pdf path with a command line argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    
    if not os.path.exists(pdf_path):
        print(f"Error: Could not find {pdf_path}")
        return
        
    print(f"Sending {pdf_path} to {url}...")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (pdf_path, f, 'application/pdf')}
            response = requests.post(url, files=files)
            
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Method used: {data.get('method')}")
            print(f"Processed {data.get('sentences_processed', 0)} sentences.")
            relations = data.get('relations', [])
            print(f"Found {len(relations)} semantic relations:")
            
            for i, rel in enumerate(relations):
                print(f"  [{i+1}] {rel.get('subject', '')} --[{rel.get('relation', '')}]--> {rel.get('object', '')}")
        else:
            print(f"Error Response: {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to the server at {url}.")
        print("Please ensure that z3_backend.py is running.")

if __name__ == "__main__":
    test_pdf_extraction()
