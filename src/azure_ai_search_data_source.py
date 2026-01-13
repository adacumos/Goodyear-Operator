"""
Azure AI Search Data Source - Direct OData Filtering
Now uses RecordType field for efficient server-side filtering
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
        timeout=10.0
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
    """Configuration options for Azure AI Search"""
    name: str
    indexName: str
    azureAISearchApiKey: str
    azureAISearchEndpoint: str
    top_k: int = 15  # Number of results to return
    vector_k: int = 35  # Number of vector neighbors to consider


@dataclass
class Result:
    """Enhanced result object with metadata"""
    def __init__(self, output: str, metadata: Optional[Dict[str, Any]] = None):
        self.output = output
        self.metadata = metadata or {}


class AzureAISearchDataSource:
    """
    Improved data source with direct OData filtering on RecordType
    Now that RecordType is filterable, we can use server-side filtering
    """
    
    def __init__(self, options: AzureAISearchDataSourceOptions):
        self.name = options.name
        self.options = options
        self.searchClient = SearchClient(
            options.azureAISearchEndpoint,
            options.indexName,
            AzureKeyCredential(options.azureAISearchApiKey)
        )
        logger.info(f"Initialized search client for index: {options.indexName}")
        
    def _detect_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyze user query to determine search intent and required RecordType
        
        Args:
            query: User's search query
        
        Returns:
            Dictionary with intent information including RecordType filter
        """
        query_lower = query.lower()
        
        intent = {
            "record_type_filter": None,  # OData filter string
            "is_status_check": False,
            "is_count_query": False,
            "query_focus": "general"
        }
        
        # Keywords that indicate OpenOrder (backlog/pending)
        open_order_keywords = [
            "open", "backorder", "pending", "backlog", 
            "on-going", "awaiting", "unfulfilled", "outstanding",
            "back order", "open order", "backlogs", "backorders",
            "back orders", "open orders", "back log", "back logs",
            "openorder", "openorders"
        ]
        
        # Keywords that indicate ShipmentLine (tracking/delivery)
        shipment_keywords = [
            "ship", "track", "deliver", "shipment", "delivery", "shipments" 
            "shipped", "fulfillment", "sent", "dispatched", "shipping"
        ]
        
        # Keywords that indicate History (past/completed)
        history_keywords = [
            "history", "past", "previous", "last", "closed", 
            "historical", "old", "completed", "invoiced"
        ]
        
        # Determine RecordType filter based on keywords
        # Priority: OpenOrder > ShipmentLine > History (most common use cases first)
        if any(keyword in query_lower for keyword in open_order_keywords):
            intent["record_type_filter"] = "RecordType eq 'OpenOrder'"
            intent["is_status_check"] = True
            intent["query_focus"] = "open_orders"
            logger.info("Detected OpenOrder intent - will filter for pending orders")
            
        elif any(keyword in query_lower for keyword in shipment_keywords):
            intent["record_type_filter"] = "RecordType eq 'ShipmentLine'"
            intent["query_focus"] = "shipments"
            logger.info("Detected ShipmentLine intent - will filter for shipments")
            
        elif any(keyword in query_lower for keyword in history_keywords):
            intent["record_type_filter"] = "RecordType eq 'History'"
            intent["query_focus"] = "historical"
            logger.info("Detected History intent - will filter for completed orders")
        
        # Detect count queries
        if any(word in query_lower for word in ["how many", "count", "number of", "total"]):
            intent["is_count_query"] = True
        
        return intent

    def _build_odata_filter(self, intent: Dict[str, Any]) -> Optional[str]:
        """
        Build OData filter string based on detected intent
        
        Args:
            intent: Intent dictionary from _detect_query_intent
        
        Returns:
            OData filter string or None for no filtering
        """
        # If we detected a specific RecordType, use it
        if intent.get("record_type_filter"):
            return intent["record_type_filter"]
        
        # No filter means search all record types
        return None

    async def render_data(self, query: str) -> Result:
        """
        Enhanced data retrieval with direct OData filtering on RecordType
        
        Args:
            query: User's search query
        
        Returns:
            Result object with formatted search results and metadata
        """
        if not query or not query.strip():
            logger.warning("Empty query received")
            return Result('', {'warning': 'Empty query'})
        
        try:
            # Step 1: Analyze query intent
            intent = self._detect_query_intent(query)
            logger.info(f"Query intent: {intent}")
            
            # Step 2: Generate embedding for vector search
            embedding = await get_embedding_vector(query)
            
            # Step 3: Setup vector query
            vector_query = VectorizedQuery(
                vector=embedding, 
                k_nearest_neighbors=self.options.vector_k,
                fields="text_vector"
            )

            # Step 4: Select fields to retrieve
            selected_fields = [
                'chunk',           # Main content
                'chunk_id',        # Unique identifier
                'RecordType',      # Record type (now filterable!)
                'ORDER_NO',        # Order number
                'NAME_CUSTOMER',   # Customer name
                'CUSTOMER',        # Customer code
                'DATE_SHIPPED',    # For history
                'PROM_DT',         # For open orders
                'SL_DATE_SHIP'     # For shipments
            ]

            # Step 5: Build OData filter
            odata_filter = self._build_odata_filter(intent)
            
            # Step 6: Execute search with OData filter
            search_params = {
                'search_text': query,
                'select': selected_fields,
                'vector_queries': [vector_query],
                'top': self.options.top_k,
                'query_type': QueryType.SEMANTIC,
                'semantic_configuration_name': "rag-1767122801281-semantic-configuration"
            }
            
            # Add filter if we have one
            if odata_filter:
                search_params['filter'] = odata_filter
                logger.info(f"Applying OData filter: {odata_filter}")
            else:
                logger.info("No filter applied - searching all RecordTypes")
            
            # Execute search
            searchResults = self.searchClient.search(**search_params)

            # Step 7: Process and group results
            all_results = list(searchResults)
            result_count = len(all_results)
            
            logger.info(f"Retrieved {result_count} results from search")
            
            # Deduplication and grouping
            docs = []
            seen_chunks = set()
            order_groups = {}
            
            for result in all_results:
                # Get chunk content
                content = result.get('chunk', 'N/A')
                
                # Skip duplicates
                if content in seen_chunks:
                    continue
                seen_chunks.add(content)
                
                # Extract metadata
                record_type = result.get('RecordType', 'Unknown')
                cust_name = result.get('NAME_CUSTOMER', 'Unknown')
                cust_id = result.get('CUSTOMER', 'N/A')
                order_no = result.get('ORDER_NO', 'N/A')
                
                # Group by order number
                if order_no not in order_groups:
                    order_groups[order_no] = []
                
                chunk_data = {
                    'record_type': record_type,
                    'customer_name': cust_name,
                    'customer_id': cust_id,
                    'order_no': order_no,
                    'content': content
                }
                order_groups[order_no].append(chunk_data)
            
            # Step 8: Format grouped results
            for order_no, chunks in order_groups.items():
                # Add order header for multi-item orders
                if len(chunks) > 1:
                    first_chunk = chunks[0]
                    docs.append(
                        f"=== ORDER {order_no} ({first_chunk['record_type']}) | "
                        f"{first_chunk['customer_name']} ({first_chunk['customer_id']}) ==="
                    )
                
                # Add individual chunks
                for chunk in chunks:
                    header = (
                        f"{chunk['record_type']} | "
                        f"{chunk['customer_name']} ({chunk['customer_id']}) | "
                        f"Order: {chunk['order_no']}"
                    )
                    docs.append(f"Source: {header}\nContent: {chunk['content']}")
            
            # Step 9: Create metadata
            metadata = {
                'total_results': result_count,
                'unique_chunks': len(seen_chunks),
                'unique_orders': len(order_groups),
                'intent': intent,
                'filter_applied': odata_filter is not None,
                'record_type_filter': odata_filter
            }
            
            # Handle no results
            if not docs:
                logger.warning(f"No results found for query: {query}")
                return Result(
                    "No relevant records found in the database.",
                    metadata
                )
            
            # Step 10: Format output
            formatted_output = '\n\n---\n\n'.join(docs)
            
            # Add summary for count queries
            if intent['is_count_query']:
                summary = (
                    f"SEARCH SUMMARY: Found {len(order_groups)} unique orders "
                    f"across {len(seen_chunks)} records.\n\n"
                )
                formatted_output = summary + formatted_output
            
            logger.info(
                f"Successfully processed query - "
                f"Orders: {len(order_groups)}, Chunks: {len(seen_chunks)}"
            )
            
            return Result(formatted_output, metadata)
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return Result(
                "I encountered an error searching the database. "
                "Please try rephrasing your question.",
                {'error': str(e)}
            )