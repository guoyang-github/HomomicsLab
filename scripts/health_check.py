#!/usr/bin/env python3
"""End-to-end health check for HomicsLab."""

import sys
import httpx


def check_backend() -> bool:
    try:
        response = httpx.get("http://localhost:8080/health", timeout=5.0)
        if response.status_code == 200:
            print("✅ Backend is running")
            return True
        else:
            print(f"❌ Backend returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        return False


def check_chat_api() -> bool:
    try:
        response = httpx.post(
            "http://localhost:8080/api/chat/send",
            json={
                "project_id": "health_check",
                "session_id": "health_session",
                "message": "hello",
            },
            timeout=10.0,
        )
        if response.status_code == 200:
            print("✅ Chat API is responding")
            return True
        else:
            print(f"❌ Chat API returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Chat API error: {e}")
        return False


def main():
    print("Running HomicsLab health check...")

    checks = [
        check_backend(),
        check_chat_api(),
    ]

    if all(checks):
        print("\n✅ All health checks passed")
        return 0
    else:
        print("\n❌ Some health checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
