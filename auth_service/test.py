import requests
import time

# Configuration
BASE_URL = "http://localhost:8000"
EMAIL = "satviksangamkar@gmail.com"
OLD_PASSWORD = "NewSecure@123"
NEW_PASSWORD = "NewSecure@1234"

def main():
    # 1. Test login with existing credentials
    print("\n" + "="*50)
    print("Testing login with existing credentials")
    print("="*50)
    token_response = requests.post(
        f"{BASE_URL}/token",
        data={"username": EMAIL, "password": OLD_PASSWORD, "grant_type": "password"}
    )
    print("Login Response:", token_response.status_code, token_response.json())
    
    if token_response.status_code == 200:
        old_token = token_response.json()["access_token"]
        print("\nTesting protected endpoint with old token...")
        protected_response = requests.get(
            f"{BASE_URL}/protected",
            headers={"Authorization": f"Bearer {old_token}"}
        )
        print("Protected Route Response:", protected_response.status_code, protected_response.json())

    # 2. Initiate password reset
    print("\n" + "="*50)
    print("Initiating password reset")
    print("="*50)
    forgot_response = requests.post(
        f"{BASE_URL}/forgot-password",
        json={"email": EMAIL}
    )
    print("Forgot Password Response:", forgot_response.status_code, forgot_response.json())

    # 3. Get reset token from user
    print("\n" + "="*50)
    print("Check your email for the password reset link")
    print("Copy the token from the URL (after 'token=')")
    print("Example: https://yourapp.com/reset-password?token=abc123-456def")
    print("="*50 + "\n")
    time.sleep(3)  # Give time to check email
    
    reset_token = input("Enter the reset token from your email: ").strip()

    # 4. Reset password
    print("\nResetting password...")
    reset_response = requests.post(
        f"{BASE_URL}/reset-password",
        json={"token": reset_token, "new_password": NEW_PASSWORD}
    )
    print("Reset Password Response:", reset_response.status_code, reset_response.json())

    # 5. Test login with new password
    print("\n" + "="*50)
    print("Testing login with new password")
    print("="*50)
    new_token_response = requests.post(
        f"{BASE_URL}/token",
        data={"username": EMAIL, "password": NEW_PASSWORD, "grant_type": "password"}
    )
    print("Login with New Password Response:", new_token_response.status_code, new_token_response.json())
    
    if new_token_response.status_code == 200:
        new_token = new_token_response.json()["access_token"]
        print("\nTesting protected endpoint with new token...")
        protected_response = requests.get(
            f"{BASE_URL}/protected",
            headers={"Authorization": f"Bearer {new_token}"}
        )
        print("Protected Route Response:", protected_response.status_code, protected_response.json())

    # 6. Verify old token is invalidated
    print("\n" + "="*50)
    print("Testing session invalidation (old token should be invalid)")
    print("="*50)
    if token_response.status_code == 200:
        print("\nTesting protected endpoint with old token...")
        invalid_protected_response = requests.get(
            f"{BASE_URL}/protected",
            headers={"Authorization": f"Bearer {old_token}"}
        )
        print("Old Token Response (should fail):", 
              invalid_protected_response.status_code, 
              invalid_protected_response.json())
    
    # 7. Verify old password doesn't work
    print("\n" + "="*50)
    print("Testing old password no longer works")
    print("="*50)
    old_password_response = requests.post(
        f"{BASE_URL}/token",
        data={"username": EMAIL, "password": OLD_PASSWORD, "grant_type": "password"}
    )
    print("Login with Old Password Response (should fail):", 
          old_password_response.status_code, 
          old_password_response.json())

if __name__ == "__main__":
    main()