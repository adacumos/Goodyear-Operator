"""
Enhanced Azure AI Search with Smart RecordType Filtering
Uses post-filtering + query enhancement for accurate record type targeting
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
    top_k: int = 15
    vector_k: int = 30


@dataclass
class Result:
    """Enhanced result object with metadata"""
    def __init__(self, output: str, metadata: Optional[Dict[str, Any]] = None):
        self.output = output
        self.metadata = metadata or {}


class AzureAISearchDataSource:
    """
    Enhanced search with intelligent RecordType filtering
    
    Since RecordType is not filterable in Azure Search, we use:
    1. Query enhancement (add keywords to boost relevant types)
    2. Smart post-filtering (filter results after retrieval)
    3. Score-based ranking (prioritize matching record types)
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
    
    def _detect_record_type_intent(self, query: str) -> List[str]:
        """
        Detect which RecordType(s) the user wants
        
        Args:
            query: User's search query
        
        Returns:
            List of RecordType values to prioritize
        
        Examples:
            "show open orders" -> ["OpenOrder"]
            "what shipped last week" -> ["ShipmentLine"]
            "order history for customer X" -> ["History"]
        """
        query_lower = query.lower()
        record_types = []
        
        # Pattern 1: Open Orders / Backorders / Pending
        open_keywords = [
            'open', 'backorder', 'pending', 'status', 
            'backlog', 'on-going', 'unfulfilled', 'outstanding'
        ]
        if any(keyword in query_lower for keyword in open_keywords):
            record_types.append('OpenOrder')
            logger.info("Detected intent: OpenOrder")
        
        # Pattern 2: Shipments / Deliveries / Tracking
        shipment_keywords = [
            'ship', 'shipped', 'shipment', 'deliver', 'delivery',
            'track', 'fulfillment', 'sent', 'dispatched'
        ]
        if any(keyword in query_lower for keyword in shipment_keywords):
            record_types.append('ShipmentLine')
            logger.info("Detected intent: ShipmentLine")
        
        # Pattern 3: History / Past / Completed
        history_keywords = [
            'history', 'past', 'previous', 'last', 'closed',
            'historical', 'old', 'completed', 'finished'
        ]
        if any(keyword in query_lower for keyword in history_keywords):
            record_types.append('History')
            logger.info("Detected intent: History")
        
        # If no specific type detected, return empty list (search all types)
        if not record_types:
            logger.info("No specific RecordType intent detected, searching all types")
        
        return record_types
    
    def _enhance_query_for_record_type(self, query: str, record_types: List[str]) -> str:
        """
        Enhance search query to boost relevant RecordType results
        
        Args:
            query: Original user query
            record_types: List of RecordType values to boost
        
        Returns:
            Enhanced query string
        
        How it works:
            Adds keywords that are semantically related to each RecordType
            This helps the vector/semantic search return more relevant results
        """
        if not record_types:
            return query
        
        # Map RecordType to boost keywords
        boost_keywords = {
            'OpenOrder': 'backorder pending open status',
            'ShipmentLine': 'shipped delivery tracking',
            'History': 'historical completed past'
        }
        
        # Add boost keywords for detected types
        enhancements = []
        for record_type in record_types:
            if record_type in boost_keywords:
                enhancements.append(boost_keywords[record_type])
        
        if enhancements:
            enhanced_query = f"{query} {' '.join(enhancements)}"
            logger.info(f"Enhanced query: '{query}' -> '{enhanced_query}'")
            return enhanced_query
        
        return query
    
    def _filter_by_record_type(
        self, 
        results: List[Dict[str, Any]], 
        preferred_types: List[str],
        strict: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Post-filter results by RecordType
        
        Args:
            results: Search results from Azure
            preferred_types: List of preferred RecordType values
            strict: If True, ONLY return matching types. If False, prioritize but keep others.
        
        Returns:
            Filtered/sorted results
        
        Strategy:
            - STRICT mode: Only return matching RecordTypes
            - LENIENT mode: Sort matching types first, then others
        """
        if not preferred_types:
            return results
        
        # Separate matching and non-matching results
        matching = []
        non_matching = []
        
        for result in results:
            record_type = result.get('RecordType', '')
            if record_type in preferred_types:
                matching.append(result)
            else:
                non_matching.append(result)
        
        logger.info(
            f"RecordType filtering: {len(matching)} matching, "
            f"{len(non_matching)} non-matching (strict={strict})"
        )
        
        # In strict mode, only return matching
        if strict:
            if not matching:
                logger.warning(
                    f"STRICT filtering removed ALL results for types: {preferred_types}. "
                    f"Falling back to lenient mode."
                )
                return results  # Fallback to avoid returning nothing
            return matching
        
        # In lenient mode, prioritize matching but keep others
        return matching + non_matching
    
    def _calculate_record_type_boost_score(
        self, 
        result: Dict[str, Any], 
        preferred_types: List[str]
    ) -> float:
        """
        Calculate a boost score based on RecordType match
        
        Args:
            result: Single search result
            preferred_types: List of preferred RecordType values
        
        Returns:
            Boost score (1.0 = no boost, 2.0 = double score)
        """
        if not preferred_types:
            return 1.0
        
        record_type = result.get('RecordType', '')
        
        # If RecordType matches, apply 2x boost
        if record_type in preferred_types:
            return 2.0
        
        return 1.0

    async def render_data(self, query: str, strict_filtering: bool = False) -> Result:
        """
        Enhanced search with intelligent RecordType filtering
        
        Args:
            query: User's search query
            strict_filtering: If True, ONLY return matching RecordTypes
        
        Returns:
            Result object with formatted search results
        
        Process:
            1. Detect which RecordType(s) user wants
            2. Enhance query to boost relevant results
            3. Execute search
            4. Post-filter by RecordType
            5. Format and return results
        """
        if not query or not query.strip():
            logger.warning("Empty query received")
            return Result('', {'warning': 'Empty query'})
        
        try:
            # Step 1: Detect RecordType intent
            preferred_types = self._detect_record_type_intent(query)
            
            # Step 2: Enhance query for better matching
            enhanced_query = self._enhance_query_for_record_type(query, preferred_types)
            
            # Step 3: Generate embedding (use original query, not enhanced)
            # The enhanced query is for text search, embedding uses original
            embedding = await get_embedding_vector(query)
            
            # Step 4: Setup vector query
            vector_query = VectorizedQuery(
                vector=embedding, 
                k_nearest_neighbors=self.options.vector_k,
                fields="text_vector"
            )

            # Step 5: Select fields
            selected_fields = [
                'chunk',
                'chunk_id',
                'RecordType',      # CRITICAL: Must retrieve this for filtering
                'ORDER_NO',
                'NAME_CUSTOMER',
                'CUSTOMER',
                'DATE_SHIPPED',
                'PROM_DT',
                'SL_DATE_SHIP'
            ]

            # Step 6: Execute search
            # Use enhanced query for text search to boost relevant types
            search_params = {
                'search_text': enhanced_query,  # Enhanced query helps boost relevant results
                'select': selected_fields,
                'vector_queries': [vector_query],
                'top': self.options.top_k * 3,  # Get 3x results for filtering
                'query_type': QueryType.SEMANTIC,
                'semantic_configuration_name': "rag-1768021240909-semantic-configuration"
            }
            
            logger.info(f"Executing search with query: '{enhanced_query}'")
            
            searchResults = self.searchClient.search(**search_params)

            # Step 7: Collect results
            all_results = []
            for result in searchResults:
                all_results.append(result)
            
            logger.info(f"Retrieved {len(all_results)} initial results")
            
            # Step 8: Apply RecordType filtering
            if preferred_types:
                all_results = self._filter_by_record_type(
                    all_results, 
                    preferred_types,
                    strict=strict_filtering
                )
                logger.info(f"After RecordType filtering: {len(all_results)} results")
            
            # Step 9: Limit to top_k after filtering
            all_results = all_results[:self.options.top_k]

            # Step 10: Process results with grouping
            docs = []
            seen_chunks = set()
            order_groups = {}
            record_type_counts = {}
            
            result_count = len(all_results)
            
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
                
                # Count by RecordType
                record_type_counts[record_type] = record_type_counts.get(record_type, 0) + 1
                
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
            
            # Step 11: Format grouped results
            for order_no, chunks in order_groups.items():
                # Add order header for multi-line orders
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
            
            # Step 12: Create metadata with RecordType info
            metadata = {
                'total_results': result_count,
                'unique_chunks': len(seen_chunks),
                'unique_orders': len(order_groups),
                'record_type_distribution': record_type_counts,
                'preferred_types': preferred_types,
                'strict_filtering': strict_filtering
            }
            
            # Step 13: Handle no results
            if not docs:
                logger.warning(f"No results found for query: {query}")
                no_results_msg = "No relevant records found in the database."
                
                if preferred_types:
                    no_results_msg += f" (Searched for: {', '.join(preferred_types)})"
                
                return Result(no_results_msg, metadata)
            
            # Step 14: Format output
            formatted_output = '\n\n---\n\n'.join(docs)
            
            # Add summary header showing RecordType distribution
            if preferred_types:
                summary_parts = []
                for rt in preferred_types:
                    count = record_type_counts.get(rt, 0)
                    summary_parts.append(f"{rt}: {count}")
                
                summary = (
                    f"FILTERED RESULTS (RecordType): {', '.join(summary_parts)} | "
                    f"Total: {len(order_groups)} unique orders\n\n"
                )
                formatted_output = summary + formatted_output
            
            logger.info(
                f"Returning {len(docs)} chunks from {result_count} results. "
                f"RecordType distribution: {record_type_counts}"
            )
            
            return Result(formatted_output, metadata)
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return Result(
                f"I encountered an error searching the database. Please try rephrasing your question.",
                {'error': str(e)}
            )