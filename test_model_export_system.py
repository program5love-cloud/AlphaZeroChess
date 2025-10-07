"""
Test script for Model Export & Deployment Integration (Step 8)
Validates all API endpoints and export functionality
"""
import requests
import json
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8001"
API = f"{BASE_URL}/api"

def test_api_endpoint(name, method, url, expected_keys=None, data=None):
    """Test a single API endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data or {}, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS")
            
            if expected_keys:
                for key in expected_keys:
                    if key in result:
                        print(f"  ✓ Found key: {key}")
                    else:
                        print(f"  ✗ Missing key: {key}")
                        return False
            
            # Print sample of response
            if isinstance(result, dict):
                print(f"\nResponse Preview:")
                for key, value in list(result.items())[:5]:
                    if isinstance(value, (list, dict)):
                        print(f"  {key}: {type(value).__name__} with {len(value) if isinstance(value, (list, dict)) else 0} items")
                    else:
                        print(f"  {key}: {value}")
            
            return True
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MODEL EXPORT & DEPLOYMENT SYSTEM - TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: List all models
    results.append(test_api_endpoint(
        "List All Models",
        "GET",
        f"{API}/model/list",
        expected_keys=["success", "models", "count"]
    ))
    
    # Test 2: Get device info
    results.append(test_api_endpoint(
        "Get Device Info",
        "GET",
        f"{API}/device/info",
        expected_keys=["success", "device_type", "device_name"]
    ))
    
    # Test 3: Get model info
    results.append(test_api_endpoint(
        "Get Model Info (model_v1)",
        "GET",
        f"{API}/model/info/model_v1",
        expected_keys=["success", "name", "metadata"]
    ))
    
    # Test 4: List exports
    results.append(test_api_endpoint(
        "List Exported Models",
        "GET",
        f"{API}/model/exports",
        expected_keys=["success", "exports"]
    ))
    
    # Test 5: Get current model
    results.append(test_api_endpoint(
        "Get Current Model",
        "GET",
        f"{API}/model/current",
        expected_keys=["success", "loaded"]
    ))
    
    # Test 6: Load a model
    results.append(test_api_endpoint(
        "Load Model (model_v1)",
        "POST",
        f"{API}/model/load/model_v1",
        expected_keys=["success", "model_name"]
    ))
    
    # Test 7: Export PyTorch model
    results.append(test_api_endpoint(
        "Export PyTorch Model",
        "POST",
        f"{API}/model/export/pytorch/model_v1",
        expected_keys=["success", "format", "filename"],
        data={"metadata": {"test": "automated_test"}}
    ))
    
    # Test 8: Export ONNX model
    results.append(test_api_endpoint(
        "Export ONNX Model",
        "POST",
        f"{API}/model/export/onnx/model_v1",
        expected_keys=["success", "format", "filename"]
    ))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {total - passed} ❌")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Model Export System is fully functional.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
