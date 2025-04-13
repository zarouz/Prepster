#!/usr/bin/env python3
# generate_secrets.py
"""
Generates cryptographically secure random strings suitable for
Flask secret keys and security salts.

Run this script and copy the output lines into your .env file,
replacing the placeholder values.

DO NOT commit your .env file or share these keys publicly.
"""

import secrets
import sys

# Recommended byte lengths (adjust if you have specific requirements)
# 32 bytes for the main secret key is common (results in 64 hex characters)
SECRET_KEY_BYTES = 32
# 16 bytes for salts is generally sufficient (results in 32 hex characters)
SALT_BYTES = 16

print("-" * 60)
print("Generating secure random keys for your .env file...")
print("-" * 60)

# Generate keys using token_hex for easy copy-pasting
flask_secret_key = secrets.token_hex(SECRET_KEY_BYTES)
password_salt = secrets.token_hex(SALT_BYTES)
email_salt = secrets.token_hex(SALT_BYTES)

# Print the keys in the .env format
print("\n# Copy the following lines into your .env file:")
print("# Replace any existing placeholder lines for these variables.")
print("\n# --- Flask Core ---")
print(f"FLASK_SECRET_KEY={flask_secret_key}")

print("\n# --- Security Salts ---")
print(f"SECURITY_PASSWORD_SALT={password_salt}")
print(f"EMAIL_CONFIRMATION_SALT={email_salt}")

print("-" * 60)
print("\n" + "*" * 15 + " SECURITY WARNING " + "*" * 15)
print("1. Store these keys securely in your .env file.")
print("2. NEVER commit the .env file or these keys to version control (Git).")
print("3. Ensure the .env file has appropriate file permissions (restrict access).")
print("*" * 52 + "\n")