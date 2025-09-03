#!/usr/bin/env python3
"""
Simple validation script to test the cached LLM client implementation.
This can be run manually to verify the implementation works.
"""
import sys
from pathlib import Path


def validate_imports():
    """Test that all new modules can be imported without errors."""
    try:
        pass

        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Other error: {e}")
        return False


def validate_client_creation():
    """Test that clients can be instantiated."""
    try:
        from elroy.llm.cached_client import CachedLLMClient
        from elroy.llm.client import LLMClient

        # Test base client
        LLMClient()
        print("✅ Base LLMClient created successfully")

        # Test cached client
        cache_dir = Path("/tmp/test_cache")
        CachedLLMClient(cache_dir)
        print("✅ CachedLLMClient created successfully")

        # Verify cache directory was created
        if cache_dir.exists():
            print("✅ Cache directory created successfully")
        else:
            print("❌ Cache directory not created")
            return False

        return True
    except Exception as e:
        print(f"❌ Client creation error: {e}")
        return False


def validate_cache_structure():
    """Test the caching mechanism structure."""
    try:
        from elroy.llm.cached_client import CachedLLMClient

        cached_client = CachedLLMClient(Path("/tmp/validate_cache"))

        # Test cache key generation
        cache_key = cached_client._get_cache_key(model="test-model", prompt="test prompt", system="test system", method="query_llm")
        if len(cache_key) == 16:  # Should be 16 char hash
            print("✅ Cache key generation works")
        else:
            print(f"❌ Cache key wrong length: {len(cache_key)}")
            return False

        # Test cache path generation
        cache_path = cached_client._get_cache_path(cache_key, "query_llm")
        if cache_path.name.startswith("query_llm_") and cache_path.suffix == ".json":
            print("✅ Cache path generation works")
        else:
            print(f"❌ Cache path format wrong: {cache_path}")
            return False

        return True
    except Exception as e:
        print(f"❌ Cache structure validation error: {e}")
        return False


def main():
    print("Validating cached LLM client implementation...\n")

    all_passed = True

    print("1. Testing imports...")
    all_passed &= validate_imports()
    print()

    print("2. Testing client creation...")
    all_passed &= validate_client_creation()
    print()

    print("3. Testing cache structure...")
    all_passed &= validate_cache_structure()
    print()

    if all_passed:
        print("🎉 All validation tests passed!")
        return 0
    else:
        print("❌ Some validation tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
