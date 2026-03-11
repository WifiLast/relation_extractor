import subprocess
import time
import os
import sys

def run_test_flow():
    print("Starting z3_backend.py...")
    # Start the backend server
    server_process = subprocess.Popen(
        [sys.executable, "-u", "z3_backend.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for the server to start
    print("Waiting 5 seconds for server to initialize...")
    time.sleep(5)
    
    # Check if server is still running
    if server_process.poll() is not None:
        print("Server process exited prematurely!")
        out, err = server_process.communicate()
        print(f"Server stdout:\\n{out}")
        print(f"Server stderr:\\n{err}")
        return
        
    print("Running test_pdf_relation_extraction.py...")
    # Run the test script
    test_result = subprocess.run(
        [sys.executable, "test_pdf_relation_extraction.py"],
        capture_output=True,
        text=True
    )
    
    print("Test Output:")
    print(test_result.stdout)
    if test_result.stderr:
        print("Test Errors:")
        print(test_result.stderr)
        
    print("Terminating server...")
    server_process.terminate()
    try:
        server_process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        server_process.kill()

if __name__ == "__main__":
    run_test_flow()
