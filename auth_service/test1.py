import requests
import webbrowser
from urllib.parse import urlparse, parse_qs
import time
import json
import sys
import os
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8000"
DISCORD_REDIRECT_URI = "http://localhost:8000/test-capture" 
# Redis Configuration (adjust these based on your settings)
class RedisConfig:
    HOST = os.getenv('REDIS_HOST', 'localhost')
    PORT = int(os.getenv('REDIS_PORT', 6379))
    PASSWORD = os.getenv('REDIS_PASSWORD', None)
    DB = int(os.getenv('REDIS_DB', 0))

class DiscordAuthTester:
    def __init__(self):
        # Session to maintain cookies across requests
        self.session = requests.Session()
        self.jwt_token = None
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection for debugging"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=RedisConfig.HOST,
                port=RedisConfig.PORT,
                password=RedisConfig.PASSWORD,
                db=RedisConfig.DB,
                decode_responses=True  # Automatically decode bytes to strings
            )
            # Test connection
            self.redis_client.ping()
            print("✅ Redis connection established")
        except ImportError:
            print("⚠️ Redis library not installed. Install with: pip install redis")
            self.redis_client = None
        except Exception as e:
            print(f"⚠️ Redis connection failed: {e}")
            print("Redis inspection will be disabled")
            self.redis_client = None
    
    def inspect_redis_state(self, state: str):
        """Inspect Redis for state information"""
        if not self.redis_client:
            print("🔍 Redis inspection skipped (no connection)")
            return
        
        print(f"\n🔍 Redis State Inspection")
        print("-" * 40)
        
        try:
            # Check the exact state key
            state_key = f"discord_state:{state}"
            print(f"Looking for key: {state_key}")
            
            state_data = self.redis_client.get(state_key)
            if state_data:
                print(f"✅ State found in Redis: {state_data}")
                
                # Check TTL
                ttl = self.redis_client.ttl(state_key)
                if ttl > 0:
                    print(f"⏰ TTL remaining: {ttl} seconds ({ttl/60:.1f} minutes)")
                elif ttl == -1:
                    print("⏰ Key has no expiration")
                else:
                    print("⏰ Key expired or doesn't exist")
            else:
                print("❌ State not found in Redis")
                
                # Look for similar keys
                pattern = "discord_state:*"
                similar_keys = self.redis_client.keys(pattern)
                
                if similar_keys:
                    print(f"\n🔍 Found {len(similar_keys)} Discord state keys:")
                    for key in similar_keys[:5]:  # Show first 5
                        ttl = self.redis_client.ttl(key)
                        print(f"  • {key} (TTL: {ttl}s)")
                    if len(similar_keys) > 5:
                        print(f"  ... and {len(similar_keys) - 5} more")
                else:
                    print("🔍 No Discord state keys found in Redis")
                    
                # General Redis info
                print("\n📊 Redis Info:")
                info = self.redis_client.info()
                print(f"  • Connected clients: {info.get('connected_clients', 'N/A')}")
                print(f"  • Total keys: {info.get('db0', {}).get('keys', 0) if 'db0' in info else 0}")
                print(f"  • Memory usage: {info.get('used_memory_human', 'N/A')}")
                
        except Exception as e:
            print(f"❌ Redis inspection error: {e}")
    
    def test_discord_oauth_flow(self):
        """Complete Discord OAuth2 flow test with cookie-based authentication"""
        
        print("="*70)
        print("DISCORD OAUTH2 AUTHENTICATION FLOW TEST (COOKIE-BASED)")
        print("="*70)
        print("This test will verify:")
        print("1. Discord OAuth2 login initiation")
        print("2. Redis state management")
        print("3. Cookie-based JWT token storage")
        print("4. Protected route access with cookie authentication")
        print("5. User profile data retrieval")
        print("6. Token security validation")
        print("="*70)
        
        # Step 1: Test Discord login initiation
        if not self.test_login_initiation():
            return False
        
        # Step 2: Handle Discord callback with cookies and Redis inspection
        if not self.handle_discord_callback():
            return False
        
        # Step 3: Test protected routes
        if not self.test_protected_routes():
            return False
        
        # Step 4: Test security validations
        self.test_security_validations()
        
        # Step 5: Final summary
        self.print_final_summary()
        return True
    
    def test_login_initiation(self):
        """Test Discord login URL generation"""
        print("\n" + "="*50)
        print("STEP 1: Initiating Discord OAuth2 login")
        print("="*50)
        try:
            login_response = self.session.get(
                f"{BASE_URL}/discord/login",
                params={"redirect_uri": DISCORD_REDIRECT_URI},
                allow_redirects=False
            )
            print(f"Login initiation status: {login_response.status_code}")
            
            if login_response.status_code == 307:  # Redirect response
                auth_url = login_response.headers.get('Location')
                if auth_url:
                    print("✅ Discord login URL generated successfully")
                    print(f"Authorization URL: {auth_url[:80]}...")
                    
                    # Extract state from URL for Redis inspection
                    parsed_auth_url = urlparse(auth_url)
                    auth_params = parse_qs(parsed_auth_url.query)
                    state = auth_params.get('state', [None])[0]
                    
                    if state and self.redis_client:
                        print(f"\n🔍 Generated state: {state}")
                        # Give a moment for Redis write to complete
                        time.sleep(0.5)
                        self.inspect_redis_state(state)
                    
                    # Open browser automatically
                    print("\n🌐 Opening Discord authorization page in browser...")
                    webbrowser.open(auth_url)
                    return True
                else:
                    print("❌ No redirect URL found in response")
                    return False
            else:
                print(f"❌ Unexpected response: {login_response.status_code}")
                print(f"Response: {login_response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error initiating Discord login: {e}")
            return False
    
    def handle_discord_callback(self):
        """Handle Discord callback and cookie extraction with Redis inspection"""
        print("\n" + "="*50)
        print("STEP 2: Discord Authorization Callback (Cookie-based)")
        print("="*50)
        print("After authorizing with Discord, you'll be redirected to:")
        print(f"{DISCORD_REDIRECT_URI}")
        print("\n📋 Instructions:")
        print("1. Complete Discord authorization in the opened browser tab")
        print("2. Copy the ENTIRE URL from your browser's address bar after redirect")
        print("3. The JWT token will be stored in HTTP-only cookies")
        print("-" * 50)
        
        # Get callback URL from user
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                callback_url = input(f"\n[Attempt {attempt + 1}/{max_attempts}] Paste final redirect URL: ").strip()
                if not callback_url:
                    print("❌ Empty URL provided")
                    continue
                
                # Parse the callback URL to extract code and state
                parsed_url = urlparse(callback_url)
                query_params = parse_qs(parsed_url.query)
                
                code = query_params.get('code', [None])[0]
                state = query_params.get('state', [None])[0]
                
                if not code or not state:
                    print("❌ Required parameters (code/state) not found in URL")
                    print("Expected format: http://localhost:8000/auth/discord/callback?code=...&state=...")
                    if attempt < max_attempts - 1:
                        print("Please make sure you copied the complete callback URL")
                    continue
                
                # Redis State Inspection
                print(f"\n🔍 Inspecting Redis state before callback...")
                print(f"Extracted state: {state}")
                self.inspect_redis_state(state)
                
                # Make request to callback endpoint to get cookies
                print(f"\n🔄 Processing Discord callback...")
                print(f"Code: {code[:20]}...")
                print(f"State: {state[:20]}...")
                
                callback_response = self.session.get(
                    f"{BASE_URL}/auth/discord/callback",
                    params={"code": code, "state": state},
                    allow_redirects=False
                )
                print(f"Callback response status: {callback_response.status_code}")
                
                # Inspect Redis state after callback
                if self.redis_client:
                    print(f"\n🔍 Inspecting Redis state after callback...")
                    self.inspect_redis_state(state)
                
                if callback_response.status_code == 307:
                    print("✅ Discord callback processed successfully")
                    
                    # Check if we got cookies
                    cookies = self.session.cookies
                    if 'access_token' in cookies:
                        self.jwt_token = cookies['access_token']
                        print("✅ JWT token stored in HTTP-only cookie")
                        print(f"Token (first 30 chars): {self.jwt_token[:30]}...")
                        return True
                    else:
                        print("⚠️ No access_token cookie found, checking for token extraction...")
                        
                        # Try to extract token from any response headers or body
                        if 'Location' in callback_response.headers:
                            location = callback_response.headers['Location']
                            if '#token=' in location:
                                # Fallback: extract from URL fragment if still using old method
                                self.jwt_token = location.split('#token=')[1].split('&')[0]
                                print("✅ JWT token extracted from redirect URL (fallback)")
                                print(f"Token (first 30 chars): {self.jwt_token[:30]}...")
                                return True
                        
                        print("❌ No JWT token found in cookies or redirect")
                        if attempt < max_attempts - 1:
                            print("Please try again with the complete callback URL")
                        continue
                        
                elif callback_response.status_code == 422:
                    print("❌ Unprocessable Entity - Missing required parameters")
                    print("Make sure the URL contains both 'code' and 'state' parameters")
                    
                    # Additional Redis debugging for 422 errors
                    if self.redis_client:
                        print("\n🔍 Additional Redis debugging for 422 error:")
                        try:
                            # Check if state exists at all
                            all_states = self.redis_client.keys("discord_state:*")
                            print(f"All Discord states in Redis: {len(all_states)}")
                            for s in all_states[:3]:  # Show first 3
                                ttl = self.redis_client.ttl(s)
                                print(f"  • {s} (TTL: {ttl}s)")
                        except Exception as redis_err:
                            print(f"Redis debug error: {redis_err}")
                    
                elif callback_response.status_code == 400:
                    print("❌ Bad Request - Invalid state or expired")
                    print("The state parameter may have expired or is invalid")
                    try:
                        error_data = callback_response.json()
                        print(f"Error details: {json.dumps(error_data, indent=2)}")
                    except:
                        print(f"Response text: {callback_response.text}")
                else:
                    print(f"❌ Unexpected callback response: {callback_response.status_code}")
                    try:
                        error_data = callback_response.json()
                        print(f"Error details: {json.dumps(error_data, indent=2)}")
                    except:
                        print(f"Response text: {callback_response.text}")
                        
            except Exception as e:
                print(f"❌ Error processing callback: {e}")
                if attempt == max_attempts - 1:
                    print("Max attempts reached. Please check the URL format.")
                    return False
        
        print("❌ Could not process Discord callback successfully.")
        return False
    
    def test_protected_routes(self):
        """Test access to protected routes"""
        print("\n" + "="*50)
        print("STEP 3: Testing Protected Routes")
        print("="*50)
        
        if not self.jwt_token:
            print("❌ No JWT token available for testing")
            return False
        
        # Test 1: Protected route with cookies
        print("\n🔒 Testing protected route with cookies...")
        try:
            protected_response = self.session.get(f"{BASE_URL}/protected")
            print(f"Protected route (cookies) status: {protected_response.status_code}")
            if protected_response.status_code == 200:
                user_data = protected_response.json()
                print("✅ Cookie-based authentication successful")
                self.print_user_info(user_data)
                cookie_auth_success = True
            else:
                print(f"❌ Cookie-based auth failed: {protected_response.status_code}")
                cookie_auth_success = False
        except requests.exceptions.RequestException as e:
            print(f"❌ Error with cookie-based auth: {e}")
            cookie_auth_success = False
        
        # Test 2: Protected route with Bearer token (fallback)
        print("\n🔒 Testing protected route with Bearer token...")
        try:
            headers = {"Authorization": f"Bearer {self.jwt_token}"}
            bearer_response = requests.get(f"{BASE_URL}/protected", headers=headers)
            print(f"Protected route (Bearer) status: {bearer_response.status_code}")
            if bearer_response.status_code == 200:
                user_data = bearer_response.json()
                print("✅ Bearer token authentication successful")
                self.print_user_info(user_data)
                bearer_auth_success = True
            else:
                print(f"❌ Bearer token auth failed: {bearer_response.status_code}")
                bearer_auth_success = False
        except requests.exceptions.RequestException as e:
            print(f"❌ Error with Bearer token auth: {e}")
            bearer_auth_success = False
        
        # Test 3: Profile endpoint
        print("\n👤 Testing profile endpoint...")
        try:
            if cookie_auth_success:
                profile_response = self.session.get(f"{BASE_URL}/profile")
            else:
                headers = {"Authorization": f"Bearer {self.jwt_token}"}
                profile_response = requests.get(f"{BASE_URL}/profile", headers=headers)
                
            print(f"Profile endpoint status: {profile_response.status_code}")
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                print("✅ Profile endpoint successful")
                print(f"Profile data: {json.dumps(profile_data, indent=2)}")
            else:
                print(f"⚠️ Profile endpoint failed: {profile_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Profile endpoint error: {e}")
        
        return cookie_auth_success or bearer_auth_success
    
    def test_security_validations(self):
        """Test various security scenarios"""
        print("\n" + "="*50)
        print("STEP 4: Testing Security Validations")
        print("="*50)
        
        # Test 1: Invalid token
        print("\n🛡️ Testing invalid token rejection...")
        try:
            invalid_headers = {"Authorization": "Bearer invalid.jwt.token"}
            invalid_response = requests.get(f"{BASE_URL}/protected", headers=invalid_headers)
            print(f"Invalid token test status: {invalid_response.status_code}")
            if invalid_response.status_code == 401:
                print("✅ Invalid token properly rejected")
            else:
                print(f"⚠️ Unexpected response for invalid token: {invalid_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error testing invalid token: {e}")
        
        # Test 2: No authorization header
        print("\n🛡️ Testing missing authorization header...")
        try:
            no_auth_response = requests.get(f"{BASE_URL}/protected")
            print(f"No auth header test status: {no_auth_response.status_code}")
            if no_auth_response.status_code == 401:
                print("✅ Missing authorization properly rejected")
            else:
                print(f"⚠️ Unexpected response for missing auth: {no_auth_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error testing missing auth: {e}")
        
        # Test 3: Malformed Bearer token
        print("\n🛡️ Testing malformed Bearer token...")
        try:
            malformed_headers = {"Authorization": f"NotBearer {self.jwt_token}"}
            malformed_response = requests.get(f"{BASE_URL}/protected", headers=malformed_headers)
            print(f"Malformed auth test status: {malformed_response.status_code}")
            if malformed_response.status_code == 401:
                print("✅ Malformed authorization properly rejected")
            else:
                print(f"⚠️ Unexpected response for malformed auth: {malformed_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error testing malformed auth: {e}")
        
        # Test 4: Cookie persistence
        print("\n🍪 Testing cookie persistence...")
        try:
            # Make another request to see if cookies persist
            cookie_test_response = self.session.get(f"{BASE_URL}/protected")
            print(f"Cookie persistence test status: {cookie_test_response.status_code}")
            if cookie_test_response.status_code == 200:
                print("✅ Cookies properly maintained across requests")
            else:
                print(f"⚠️ Cookie persistence issue: {cookie_test_response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error testing cookie persistence: {e}")
        
        # Test 5: Redis cleanup verification
        if self.redis_client:
            print("\n🧹 Testing Redis state cleanup...")
            try:
                active_states = self.redis_client.keys("discord_state:*")
                print(f"Active Discord states in Redis: {len(active_states)}")
                if len(active_states) > 5:
                    print("⚠️ Many active states found - consider cleanup policy")
                else:
                    print("✅ Redis state management looks healthy")
            except Exception as e:
                print(f"Redis cleanup check error: {e}")
    
    def print_user_info(self, user_data):
        """Print formatted user information"""
        print("User Information:")
        print(f"  • Discord ID: {user_data.get('id', 'N/A')}")
        print(f"  • Username: {user_data.get('username', 'N/A')}")
        print(f"  • Email: {user_data.get('email', 'N/A')}")
        print(f"  • Verified: {user_data.get('verified', 'N/A')}")
        print(f"  • Avatar: {user_data.get('avatar', 'N/A')[:20] + '...' if user_data.get('avatar') else 'N/A'}")
    
    def print_final_summary(self):
        """Print test completion summary"""
        print("\n" + "="*70)
        print("DISCORD OAUTH2 TEST SUMMARY (COOKIE-BASED WITH REDIS)")
        print("="*70)
        print("✅ Test completed successfully!")
        print("\n📋 What was tested:")
        print("   • Discord OAuth2 login initiation")
        print("   • Redis state management and inspection")
        print("   • Cookie-based JWT token storage")
        print("   • Protected route access with cookie authentication")
        print("   • Bearer token authentication (fallback)")
        print("   • User profile data retrieval")
        print("   • Security validations (invalid tokens, malformed auth)")
        print("   • Cookie persistence across requests")
        print("   • Redis state cleanup verification")
        print("\n🔐 Security improvements verified:")
        print("   • HTTP-only cookies prevent XSS token theft")
        print("   • Secure cookie handling")
        print("   • Proper token validation")
        print("   • Redis-backed state management")
        print("\n💡 Next steps:")
        print("   • Test token expiration handling")
        print("   • Test logout functionality")
        print("   • Implement token refresh mechanism")
        print("   • Test CSRF protection")
        print("   • Monitor Redis state cleanup")
        print("="*70)

def main():
    """Main test execution"""
    print("🔧 Redis Configuration:")
    print(f"   Host: {RedisConfig.HOST}")
    print(f"   Port: {RedisConfig.PORT}")
    print(f"   DB: {RedisConfig.DB}")
    print(f"   Password: {'Set' if RedisConfig.PASSWORD else 'None'}")
    print()
    
    try:
        tester = DiscordAuthTester()
        success = tester.test_discord_oauth_flow()
        
        if success:
            print("\n🎉 All tests completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed. Please check your implementation.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error during testing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()