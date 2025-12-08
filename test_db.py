#!/usr/bin/env python3
"""Quick test script to check database state and device registration."""

import sys
from pathlib import Path

# Add server to path
sys.path.insert(0, str(Path(__file__).parent))

from core.database import SessionLocal
from core.models import User, Device
from core.config import settings

def main():
    """Print database state."""
    print(f"Database file: {settings.DATABASE_FILE}")
    print(f"Database exists: {Path(settings.DATABASE_FILE).exists()}")
    print()
    
    db = SessionLocal()
    
    try:
        users = db.query(User).all()
        print(f"Total users: {len(users)}")
        for user in users:
            print(f"  - {user.username} (API Token: {user.api_token[:16]}...)")
        
        print()
        devices = db.query(Device).all()
        print(f"Total devices: {len(devices)}")
        for device in devices:
            print(f"  - {device.device_id} (Token: {device.device_token[:16]}...)")
            print(f"    User ID: {device.user_id}, Last seen: {device.last_seen}, Online: {bool(device.last_seen)}")
        
        print()
        if not users:
            print("⚠️  No users found. Create a user via /register endpoint first.")
        if not devices:
            print("⚠️  No devices found. Register a device via /api/register_device endpoint.")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
