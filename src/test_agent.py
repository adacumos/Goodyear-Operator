"""
Test Script for Goodyear RAG Agent
Run this to validate your setup before deployment
"""

import asyncio
import logging
from typing import List, Dict
from azure_ai_search_data_source import AzureAISearchDataSource, AzureAISearchDataSourceOptions, get_embedding_vector
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test queries covering common use cases
TEST_QUERIES: List[Dict[str, str]] = [
    {
        "query": "How many open orders do I have?",
        "expected_type": "count",
        "description": "Tests aggregation and counting logic"
    },
    {
        "query": "Do I have open orders for Baldwin?",
        "expected_type": "customer_filter",
        "description": "Tests customer name filtering"
    },
    {
        "query": "What is the status of order 55012?",
        "expected_type": "specific_order",
        "description": "Tests exact order number matching"
    },
    {
        "query": "Do I have any shipments for ACME Corp?",
        "expected_type": "shipment_search",
        "description": "Tests shipment record retrieval"
    },
    {
        "query": "Show me recent history for customer 12345",
        "expected_type": "history_search",
        "description": "Tests historical data retrieval"
    },
    {
        "query": "What shipped yesterday?",
        "expected_type": "date_filter",
        "description": "Tests temporal filtering"
    }
]


async def test_embedding_generation():
    """Test 1: Verify embedding generation works"""
    logger.info("=" * 60)
    logger.info("TEST 1: Embedding Generation")
    logger.info("=" * 60)
    
    try:
        test_text = "How many open orders do I have?"
        embedding = await get_embedding_vector(test_text)
        
        assert embedding is not None, "Embedding is None"
        assert isinstance(embedding, list), "Embedding is not a list"
        assert len(embedding) > 0, "Embedding is empty"
        
        logger.info(f"✅ Embedding generated successfully")
        logger.info(f"   Embedding dimension: {len(embedding)}")
        logger.info(f"   Sample values: {embedding[:5]}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Embedding generation failed: {e}")
        return False


async def test_search_connectivity():
    """Test 2: Verify Azure AI Search connectivity"""
    logger.info("=" * 60)
    logger.info("TEST 2: Azure AI Search Connectivity")
    logger.info("=" * 60)
    
    try:
        config = Config()
        
        search_options = AzureAISearchDataSourceOptions(
            name="test-search",
            indexName="rag-1768021240909",
            azureAISearchApiKey=config.AZURE_SEARCH_KEY,
            azureAISearchEndpoint=config.AZURE_SEARCH_ENDPOINT,
            top_k=5,
            vector_k=10
        )
        
        search_client = AzureAISearchDataSource(search_options)
        
        # Simple test query
        result = await search_client.render_data("test query")
        
        assert result is not None, "Search result is None"
        
        logger.info(f"✅ Search connectivity successful")
        logger.info(f"   Metadata: {result.metadata if hasattr(result, 'metadata') else 'N/A'}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Search connectivity failed: {e}")
        return False


async def test_intent_extraction():
    """Test 3: Verify intent extraction works correctly"""
    logger.info("=" * 60)
    logger.info("TEST 3: Intent Extraction")
    logger.info("=" * 60)
    
    try:
        config = Config()
        search_options = AzureAISearchDataSourceOptions(
            name="test-search",
            indexName="rag-1768021240909",
            azureAISearchApiKey=config.AZURE_SEARCH_KEY,
            azureAISearchEndpoint=config.AZURE_SEARCH_ENDPOINT
        )
        
        search_client = AzureAISearchDataSource(search_options)
        
        test_cases = [
            ("How many open orders?", ["OpenOrder"]),
            ("Show me shipments", ["ShipmentLine"]),
            ("What is the history?", ["History"]),
            ("Open orders and shipments", ["OpenOrder", "ShipmentLine"])
        ]
        
        all_passed = True
        for query, expected_types in test_cases:
            intent = search_client._extract_search_intent(query)
            
            # Check if expected record types are detected
            for expected_type in expected_types:
                if expected_type not in intent['record_types']:
                    logger.error(f"❌ Failed to detect {expected_type} in '{query}'")
                    all_passed = False
                else:
                    logger.info(f"✅ Correctly detected {expected_type} in '{query}'")
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Intent extraction test failed: {e}")
        return False


async def test_search_queries():
    """Test 4: Run actual search queries and verify results"""
    logger.info("=" * 60)
    logger.info("TEST 4: Search Query Execution")
    logger.info("=" * 60)
    
    config = Config()
    search_options = AzureAISearchDataSourceOptions(
        name="test-search",
        indexName="rag-1768021240909",
        azureAISearchApiKey=config.AZURE_SEARCH_KEY,
        azureAISearchEndpoint=config.AZURE_SEARCH_ENDPOINT,
        top_k=10,
        vector_k=20
    )
    
    search_client = AzureAISearchDataSource(search_options)
    
    results = []
    
    for test_case in TEST_QUERIES:
        logger.info(f"\n--- Testing: {test_case['description']} ---")
        logger.info(f"Query: '{test_case['query']}'")
        
        try:
            result = await search_client.render_data(test_case['query'])
            
            # Validate result
            has_content = len(result.output) > 0
            has_metadata = hasattr(result, 'metadata') and result.metadata is not None
            
            test_result = {
                'query': test_case['query'],
                'type': test_case['expected_type'],
                'has_content': has_content,
                'has_metadata': has_metadata,
                'metadata': result.metadata if has_metadata else {},
                'output_length': len(result.output)
            }
            
            results.append(test_result)
            
            if has_content:
                logger.info(f"✅ Query returned results")
                logger.info(f"   Output length: {len(result.output)} chars")
                if has_metadata:
                    logger.info(f"   Metadata: {result.metadata}")
                
                # Show sample output
                sample = result.output[:200] + "..." if len(result.output) > 200 else result.output
                logger.info(f"   Sample output: {sample}")
            else:
                logger.warning(f"⚠️  Query returned no results (might be expected if no data)")
                
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            results.append({
                'query': test_case['query'],
                'type': test_case['expected_type'],
                'error': str(e)
            })
    
    return results


async def test_deduplication():
    """Test 5: Verify deduplication works"""
    logger.info("=" * 60)
    logger.info("TEST 5: Result Deduplication")
    logger.info("=" * 60)
    
    # This test checks if the same chunk appears multiple times
    config = Config()
    search_options = AzureAISearchDataSourceOptions(
        name="test-search",
        indexName="rag-1768021240909",
        azureAISearchApiKey=config.AZURE_SEARCH_KEY,
        azureAISearchEndpoint=config.AZURE_SEARCH_ENDPOINT,
        top_k=20,  # Increase to potentially get duplicates
        vector_k=30
    )
    
    search_client = AzureAISearchDataSource(search_options)
    
    try:
        # Run a broad query that might return duplicates
        result = await search_client.render_data("open orders")
        
        # Check for duplicate chunks
        chunks = result.output.split('---')
        unique_chunks = set(chunk.strip() for chunk in chunks)
        
        if len(chunks) == len(unique_chunks):
            logger.info(f"✅ No duplicate chunks found ({len(chunks)} total)")
            return True
        else:
            duplicates = len(chunks) - len(unique_chunks)
            logger.warning(f"⚠️  Found {duplicates} duplicate chunks")
            return False
            
    except Exception as e:
        logger.error(f"❌ Deduplication test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests and generate report"""
    logger.info("\n" + "=" * 60)
    logger.info("GOODYEAR RAG AGENT TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    test_results = {
        'embedding': await test_embedding_generation(),
        'connectivity': await test_search_connectivity(),
        'intent': await test_intent_extraction(),
        'deduplication': await test_deduplication(),
    }
    
    # Run search queries test
    query_results = await test_search_queries()
    test_results['queries'] = query_results
    
    # Generate report
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for k, v in test_results.items() if k != 'queries' and v)
    total = len(test_results) - 1  # Exclude queries from count
    
    logger.info(f"\nCore Tests: {passed}/{total} passed")
    
    for test_name, result in test_results.items():
        if test_name != 'queries':
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"  {status} - {test_name}")
    
    logger.info(f"\nQuery Tests: {len(query_results)} queries executed")
    successful_queries = sum(1 for r in query_results if 'error' not in r and r.get('has_content'))
    logger.info(f"  {successful_queries}/{len(query_results)} returned results")
    
    # Recommendations
    logger.info("\n" + "=" * 60)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 60)
    
    if not test_results['embedding']:
        logger.warning("⚠️  Fix Azure OpenAI embedding endpoint configuration")
    
    if not test_results['connectivity']:
        logger.warning("⚠️  Fix Azure AI Search connectivity issues")
    
    if successful_queries < len(query_results) * 0.5:
        logger.warning("⚠️  Less than 50% of queries returned results - check your index data")
    
    if all(test_results[k] for k in ['embedding', 'connectivity', 'intent']):
        logger.info("✅ All core tests passed - system is ready for deployment!")
    else:
        logger.warning("⚠️  Some tests failed - review configuration before deploying")
    
    return test_results


if __name__ == "__main__":
    print("\nStarting Goodyear RAG Agent Test Suite...\n")
    results = asyncio.run(run_all_tests())
    print("\nTest suite completed. Review the output above for details.\n")