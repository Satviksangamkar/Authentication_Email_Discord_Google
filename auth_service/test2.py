import os
import pytest
import requests
import json
import time
from urllib.parse import urlparse, parse_qs

# Test configuration
BASE_URL = "http://localhost:8000"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_REDIRECT_URI = "http://127.0.0.1:8000/authorize"

# Test user credentials (replace with actual test account)
TEST_EMAIL = "satviksangamkar3@gmail.com"
TEST_PASSWORD = "Shmth@123"

def debug_google_login():
    """Debug Google login initiation"""
    print("=== Google Login Debug ===")
    
    # 1. Call login endpoint
    response = requests.get(f"{BASE_URL}/login/google", allow_redirects=False)
    print(f"Login response status: {response.status_code}")
    
    if response.status_code != 307:
        print(f"❌ Unexpected status code: {response.status_code}")
        return
        
    # 2. Check redirect location
    if "location" not in response.headers:
        print("❌ No location header in response")
        return
        
    redirect_url = response.headers["location"]
    print(f"Redirect URL: {redirect_url}")
    
    # 3. Parse redirect URL
    parsed = urlparse(redirect_url)
    print(f"Host: {parsed.netloc}")
    print(f"Path: {parsed.path}")
    
    # 4. Parse query parameters
    query_params = parse_qs(parsed.query)
    print("Query parameters:")
    for key, value in query_params.items():
        print(f"  {key}: {value[0]}")
    
    # 5. Verify critical parameters
    issues = []
    
    if parsed.netloc != "accounts.google.com":
        issues.append(f"Invalid host: {parsed.netloc}")
    
    if parsed.path != "/o/oauth2/v2/auth":
        issues.append(f"Invalid path: {parsed.path}")
    
    client_id = query_params.get("client_id", [""])[0]
    if client_id != GOOGLE_CLIENT_ID:
        issues.append(f"Client ID mismatch\n  Expected: {GOOGLE_CLIENT_ID}\n  Actual: {client_id}")
    
    redirect_uri = query_params.get("redirect_uri", [""])[0]
    if redirect_uri != GOOGLE_REDIRECT_URI:
        issues.append(f"Redirect URI mismatch\n  Expected: {GOOGLE_REDIRECT_URI}\n  Actual: {redirect_uri}")
    
    # 6. Print results
    if issues:
        print("\n❌ Found issues:")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("\n✅ All parameters match")
    
    print("\nRecommendations:")
    if client_id != GOOGLE_CLIENT_ID:
        print("- Verify GOOGLE_CLIENT_ID in your .env file matches: 898846556318-aanpddq1r91ma27sgsv4391rgj1c8vq2.apps.googleusercontent.com")
    
    if redirect_uri != GOOGLE_REDIRECT_URI:
        print("- Verify GOOGLE_REDIRECT_URI in your code matches: http://127.0.0.1:8000/authorize")

def test_server_config():
    """Test server configuration endpoint"""
    print("\n=== Server Config Debug ===")
    response = requests.get(f"{BASE_URL}/debug/config")
    
    if response.status_code == 200:
        config = response.json()
        print("Server configuration:")
        print(f"Google Client ID: {config.get('GOOGLE_CLIENT_ID', 'Not set')}")
        print(f"Google Redirect URI: {config.get('GOOGLE_REDIRECT_URI', 'Not set')}")
    else:
        print("❌ Config endpoint not available")

def test_redis_connection():
    """Test Redis connection through the API"""
    print("\n=== Redis Connection Test ===")
    response = requests.get(f"{BASE_URL}/debug/redis/ping")
    
    if response.status_code == 200:
        print("✅ Redis connection working")
    else:
        print(f"❌ Redis connection failed: {response.text}")

if __name__ == "__main__":
    debug_google_login()
    test_server_config()
    test_redis_connection()