"""Test if imports work correctly"""

print("Testing imports...")

try:
    print("1. Testing app.db.session...")
    from app.db.session import get_db
    print("   ✓ get_db imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")

try:
    print("2. Testing app.api.deps...")
    from app.api.deps import CurrentAdmin, get_current_user
    print("   ✓ CurrentAdmin and get_current_user imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")

try:
    print("3. Testing app.db.models...")
    from app.db.models import ScrapingSource
    print("   ✓ ScrapingSource imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")

try:
    print("4. Testing app.api.routes.scraping_sources...")
    from app.api.routes.scraping_sources import router
    print("   ✓ scraping_sources router imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")

try:
    print("5. Testing app.api.router...")
    from app.api.router import api_router
    print("   ✓ api_router imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")

try:
    print("6. Testing app.main...")
    from app.main import app
    print("   ✓ app imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")

print("\n=== All tests completed ===")
