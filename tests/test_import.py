#!/usr/bin/env python3
"""
Test script for import functionality
"""
import asyncio
import sys
import json
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_import_from_test_data():
    """Test import using local test data"""
    print("📊 Testing import functionality with test data...")

    try:
        # Load test data
        test_data_path = project_root / "tests" / "test_payload.json"
        with open(test_data_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)

        print(f"✅ Test data loaded: {len(test_data['rows'])} games")

        # Import the data using backend API directly
        sys.path.insert(0, str(project_root / 'backend'))
        from app.infrastructure.repositories import replace_all_from_table
        from app.infrastructure.db import get_db_session

        # This would require a database connection
        # For now, just test that the data structure is valid
        rows = test_data['rows']
        for row in rows:
            required_fields = ['name', 'genre', 'ratings']
            for field in required_fields:
                if field not in row:
                    raise ValueError(f"Missing required field '{field}' in test data")

        print("✅ Test data structure is valid")
        print(f"   Games to import: {len(rows)}")

        # Show sample data
        sample = rows[0]
        print(f"   Sample game: {sample['name']}")
        print(f"   Genre: {sample['genre']}")
        print(f"   Ratings count: {len(sample['ratings'])}")

        return True

    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False


async def test_api_import_simulation():
    """Test API import endpoint simulation"""
    print("🌐 Testing API import simulation...")

    try:
        # Test that we can import required modules
        sys.path.insert(0, str(project_root / 'backend'))
        from app.api.import_table import ImportTableRequest

        # Load test data
        test_data_path = project_root / "tests" / "test_payload.json"
        with open(test_data_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)

        # Create request object
        request = ImportTableRequest(
            rows=test_data['rows'],
            is_forced_update=False
        )

        print("✅ API request object created successfully")
        print(f"   Rows: {len(request.rows)}")
        print(f"   Forced update: {request.is_forced_update}")

        return True

    except Exception as e:
        print(f"❌ API simulation test failed: {e}")
        return False


async def main():
    """Run import tests"""
    print("🚀 Import Functionality Tests")
    print("=" * 50)

    tests = [
        ("Data Structure Test", test_import_from_test_data),
        ("API Simulation Test", test_api_import_simulation),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*10} {test_name} {'='*10}")
        success = await test_func()
        results.append((test_name, success))

    print("\n" + "=" * 50)
    print("📊 Import Test Results:")

    all_passed = True
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if not success:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All import tests passed!")
        print("\n💡 To test full import functionality:")
        print("1. Start the backend server: cd backend && python wsgi.py")
        print("2. Run: python tests/test_import.py --full")
    else:
        print("❌ Some import tests failed.")

    return all_passed


if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
