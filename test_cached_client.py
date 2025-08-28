#!/usr/bin/env python3
"""Simple test to verify the cached LLM client implementation."""

import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Test imports
    from elroy.llm.client import LLMClient
    from elroy.llm.cached_client import CachedLLMClient
    from elroy.core.ctx import ElroyContext
    
    print("✓ All imports successful")
    
    # Test ElroyContext creation and llm_client property
    try:
        ctx = ElroyContext.init(
            user_token='test',
            database_url='sqlite:///test.db',
            chat_model='gpt-4o-mini'
        )
        print("✓ ElroyContext created successfully")
        
        # Test accessing llm_client property (this should not raise the cached_property error)
        client = ctx.llm_client
        print(f"✓ llm_client property accessible: {type(client).__name__}")
        
        # Test CachedLLMClient creation
        cached_client = CachedLLMClient(ctx.chat_model, ctx.embedding_model)
        print(f"✓ CachedLLMClient created successfully: {type(cached_client).__name__}")
        
        print("\n🎉 All tests passed! The cached_property error should be fixed.")
        
    except Exception as e:
        print(f"❌ Error creating context or client: {e}")
        sys.exit(1)
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)