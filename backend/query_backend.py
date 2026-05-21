import httpx
import json

def test_local_backend():
    # Test 1: Health endpoint
    try:
        res = httpx.get("http://127.0.0.1:8000/health", timeout=5.0)
        print("Health Status:", res.status_code)
        print("Health Response:", res.json())
    except Exception as e:
        print("Health check failed:", e)

    # Test 2: Generate endpoint
    try:
        print("\nSending POST to generate endpoint...")
        payload = {
            "raw_input": "Need a Java Developer with 5 years experience in Spring Boot and Bangalore location.",
            "input_type": "text"
        }
        res = httpx.post("http://127.0.0.1:8000/api/v1/jds/generate", json=payload, timeout=20.0)
        print("Generate Status:", res.status_code)
        print("Generate Response:", json.dumps(res.json(), indent=2))
    except Exception as e:
        print("Generate failed:", e)

if __name__ == "__main__":
    test_local_backend()
