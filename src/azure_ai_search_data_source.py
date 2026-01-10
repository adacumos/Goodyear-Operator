"""
Fixed Azure AI Search Data Source - Removed OData Filtering
Works with non-filterable RecordType field
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from azure.search.documents.models import QueryType, VectorizedQuery
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import logging
from datetime import datetime

from config import Config

# Configure logging
logger = logging.getLogger(__name__)

# Cache for embeddings to reduce API calls for repeated queries
_embedding_cache: Dict[str, List[float]] = {}
MAX_CACHE_SIZE = 100

async def get_embedding_vector(text: str, use_cache: bool = True) -> List[float]:
    """
    Generate embedding with caching and retry logic
    
    Args:
        text: Input text to embed
        use_cache: Whether to use cached embeddings
    
    Returns:
        Embedding vector
    """
    # Check cache first
    cache_key = text.lower().strip()
    if use_cache and cache_key in _embedding_cache:
        logger.info(f"Using cached embedding for query: {text[:50]}...")
        return _embedding_cache[cache_key]
    
    client = AsyncAzureOpenAI(
        api_key=Config.AZURE_OPENAI_API_KEY,
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_version="2024-12-01-preview",
        timeout=10.0  # Add timeout
    )
    
    try:
        result = await client.embeddings.create(
            model=Config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT, 
            input=text
        )
        
        if not result.data:
            raise Exception(f"Failed to generate embeddings for: {text}")
        
        embedding = result.data[0].embedding
        
        # Cache the result (with size limit)
        if len(_embedding_cache) >= MAX_CACHE_SIZE:
            # Remove oldest entry
            _embedding_cache.pop(next(iter(_embedding_cache)))
        _embedding_cache[cache_key] = embedding
        
        return embedding
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise


@dataclass
class AzureAISearchDataSourceOptions:
    name: str
    indexName: str
    azureAISearchApiKey: str
    azureAISearchEndpoint: str
    # New: Allow configuration
    top_k: int = 15  # Reduced from 20 for better precision
    vector_k: int = 30  # Reduced from 50 to match usage


@dataclass
class Result:
    """Enhanced result object with metadata"""
    def __init__(self, output: str, metadata: Optional[Dict[str, Any]] = None):
        self.output = output
        self.metadata = metadata or {}


class AzureAISearchDataSource:
    """Improved data source with better error handling and performance"""
    
    def __init__(self, options: AzureAISearchDataSourceOptions):
        self.name = options.name
        self.options = options
        self.searchClient = SearchClient(
            options.azureAISearchEndpoint,
            options.indexName,
            AzureKeyCredential(options.azureAISearchApiKey)
        )
        logger.info(f"Initialized search client for index: {options.indexName}")
        
    def _extract_search_intent(self, query: str) -> Dict[str, Any]:
        """
        Extract search intent to help with post-filtering
        
        Returns:
            Dictionary with intent information
        """
        query_lower = query.lower()
        
        intent = {
            "record_types": [],
            "is_status_check": False,
            "is_count_query": False,
            "customer_mentioned": False
        }
        
        # Detect record type preferences (for post-filtering and logging)
        if any(word in query_lower for word in ["open", "backorder", "pending", "status", "backlog"]):
            intent["record_types"].append("OpenOrder")
            intent["is_status_check"] = True
        
        if any(word in query_lower for word in ["ship", "track", "deliver", "shipment", "delivery"]):
            intent["record_types"].append("ShipmentLine")
        
        if any(word in query_lower for word in ["history", "past", "previous", "last", "closed"]):
            intent["record_types"].append("History")
        
        # Detect count queries
        if any(word in query_lower for word in ["how many", "count", "number of", "total"]):
            intent["is_count_query"] = True
        
        # Detect customer mention
        if any(word in query_lower for word in ["customer", "for"]):
            intent["customer_mentioned"] = True
        
        return intent

    def _post_filter_by_record_type(
        self, 
        results: List[Dict[str, Any]], 
        preferred_types: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Post-filter results by RecordType after retrieval
        
        Args:
            results: Search results
            preferred_types: List of preferred RecordType values
        
        Returns:
            Filtered results
        """
        if not preferred_types:
            return results
        
        filtered = [r for r in results if r.get('RecordType') in preferred_types]
        
        # If filtering removed all results, return original
        if not filtered:
            logger.warning(f"Post-filtering by {preferred_types} removed all results, using unfiltered")
            return results
        
        logger.info(f"Post-filtered: {len(results)} -> {len(filtered)} results (types: {preferred_types})")
        return filtered

    async def render_data(self, query: str) -> Result:
        """
        Enhanced data retrieval with intent detection and post-filtering
        
        Args:
            query: User's search query
        
        Returns:
            Result object with formatted search results
        """
        if not query or not query.strip():
            logger.warning("Empty query received")
            return Result('', {'warning': 'Empty query'})
        
        try:
            # Extract intent for smarter retrieval
            intent = self._extract_search_intent(query)
            logger.info(f"Detected intent: {intent}")
            
            # Generate embedding
            embedding = await get_embedding_vector(query)
            
            # Setup vector query with optimized k
            vector_query = VectorizedQuery(
                vector=embedding, 
                k_nearest_neighbors=self.options.vector_k,
                fields="text_vector"
            )

            # Select fields (optimized - only what's needed)
            selected_fields = [
                'chunk',           # Main content
                'chunk_id',        # Unique identifier
                'RecordType',      # Filter category (for post-filtering)
                'ORDER_NO',        # Order number
                'NAME_CUSTOMER',   # Customer name
                'CUSTOMER',        # Customer code
                'DATE_SHIPPED',    # For history
                'PROM_DT',         # For open orders
                'SL_DATE_SHIP'     # For shipments
            ]

            # Execute search WITHOUT filter (since RecordType is not filterable)
            search_params = {
                'search_text': query,
                'select': selected_fields,
                'vector_queries': [vector_query],
                'top': self.options.top_k * 2,  # Get more results for post-filtering
                'query_type': QueryType.SEMANTIC,
                'semantic_configuration_name': "rag-1768021240909-semantic-configuration"
            }
            
            logger.info(f"Executing search without OData filter (RecordType not filterable)")
            
            searchResults = self.searchClient.search(**search_params)

            # Collect all results for post-filtering
            all_results = []
            for result in searchResults:
                all_results.append(result)
            
            # Post-filter by RecordType if intent is clear
            if intent['record_types']:
                all_results = self._post_filter_by_record_type(
                    all_results, 
                    intent['record_types']
                )
            
            # Limit to top_k after filtering
            all_results = all_results[:self.options.top_k]

            # Process results with grouping and deduplication
            docs = []
            seen_chunks = set()  # Deduplicate identical chunks
            order_groups = {}    # Group by order number
            
            result_count = len(all_results)
            for result in all_results:
                # Get chunk content
                content = result.get('chunk', 'N/A')
                
                # Skip duplicates
                if content in seen_chunks:
                    continue
                seen_chunks.add(content)
                
                # Extract metadata
                record_type = result.get('RecordType', 'Record')
                cust_name = result.get('NAME_CUSTOMER', 'Unknown')
                cust_id = result.get('CUSTOMER', 'N/A')
                order_no = result.get('ORDER_NO', 'N/A')
                
                # Group by order number for better context
                if order_no not in order_groups:
                    order_groups[order_no] = []
                
                # Create structured chunk with metadata
                chunk_data = {
                    'record_type': record_type,
                    'customer_name': cust_name,
                    'customer_id': cust_id,
                    'order_no': order_no,
                    'content': content
                }
                order_groups[order_no].append(chunk_data)
            
            # Format grouped results
            for order_no, chunks in order_groups.items():
                # Add order header
                if len(chunks) > 1:
                    first_chunk = chunks[0]
                    docs.append(
                        f"=== ORDER {order_no} ({first_chunk['record_type']}) | "
                        f"{first_chunk['customer_name']} ({first_chunk['customer_id']}) ==="
                    )
                
                # Add individual chunks
                for chunk in chunks:
                    header = f"{chunk['record_type']} | {chunk['customer_name']} ({chunk['customer_id']}) | Order: {chunk['order_no']}"
                    docs.append(f"Source: {header}\nContent: {chunk['content']}")
            
            # Create metadata
            metadata = {
                'total_results': result_count,
                'unique_chunks': len(seen_chunks),
                'unique_orders': len(order_groups),
                'intent': intent,
                'post_filtered': len(intent['record_types']) > 0
            }
            
            if not docs:
                logger.warning(f"No results found for query: {query}")
                return Result(
                    "No relevant records found in the database.",
                    metadata
                )
            
            # Join with clear separators
            formatted_output = '\n\n---\n\n'.join(docs)
            
            # Add summary header for count queries
            if intent['is_count_query']:
                summary = f"SEARCH SUMMARY: Found {len(order_groups)} unique orders across {len(seen_chunks)} records.\n\n"
                formatted_output = summary + formatted_output
            
            logger.info(f"Retrieved {len(docs)} chunks from {result_count} results")
            
            return Result(formatted_output, metadata)
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            # Return graceful error instead of failing
            return Result(
                f"I encountered an error searching the database. Please try rephrasing your question.",
                {'error': str(e)}
            )