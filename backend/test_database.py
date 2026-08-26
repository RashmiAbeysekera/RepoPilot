"""
Quick manual connectivity check — run this directly to test your DATABASE_URL.

    python test_database.py

This is a convenience script, not a pytest test. Pytest tests live in backend/tests/.
"""
from app.core.database import check_database_health

if check_database_health():
    print("✅ Database connection successful!")
else:
    print("❌ Database connection failed. Check your DATABASE_URL in backend/.env")