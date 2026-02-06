"""
Azure AI Search Data Source - Complete OData Filtering Implementation
Fixed customer extraction to avoid false positives
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from azure.search.documents.models import QueryType, VectorizedQuery
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import logging
import re

from config import Config

# Configure logging
logger = logging.getLogger(__name__)

# Cache for embeddings to reduce API calls for repeated queries
_embedding_cache: Dict[str, List[float]] = {}
MAX_CACHE_SIZE = 100


async def get_embedding_vector(text: str, use_cache: bool = True) -> List[float]:
    """Generate embedding with caching and retry logic"""
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
    """Configuration options for Azure AI Search"""
    name: str
    indexName: str
    azureAISearchApiKey: str
    azureAISearchEndpoint: str
    top_k: int = 15
    vector_k: int = 35


@dataclass
class Result:
    """Enhanced result object with metadata"""
    def __init__(self, output: str, metadata: Optional[Dict[str, Any]] = None):
        self.output = output
        self.metadata = metadata or {}


class QueryIntent:
    """Simple class to hold query analysis results"""
    def __init__(self):
        self.record_type = None  # 'OpenOrder', 'History', or 'ShipmentLine'
        self.customer_code = None  # Customer identifier if mentioned
        self.customer_name = None  # Customer name if mentioned
        self.order_number = None  # Specific order number if mentioned
        self.is_count_query = False  # True if asking "how many"
        self.is_detail_request = False  # True if asking for details of specific order
        self.search_text = ""  # Processed search text
    
    def __str__(self):
        return (
            f"QueryIntent(record_type={self.record_type}, "
            f"customer={self.customer_name or self.customer_code}, "
            f"order={self.order_number}, "
            f"is_count={self.is_count_query}, "
            f"is_detail={self.is_detail_request})"
        )


class AzureAISearchDataSource:
    """Azure AI Search data source with proper OData filtering"""
    
    def __init__(self, options: AzureAISearchDataSourceOptions):
        self.name = options.name
        self.options = options
        self.searchClient = SearchClient(
            options.azureAISearchEndpoint,
            options.indexName,
            AzureKeyCredential(options.azureAISearchApiKey)
        )
        logger.info(f"Initialized search client for index: {options.indexName}")
    
    def _extract_order_number(self, query: str) -> Optional[str]:
        """
        Extract order number from query
        
        Args:
            query: User's search query
        
        Returns:
            Order number if found, None otherwise
        
        Examples:
            "Give me details on order number 90143" → "90143"
            "Show me order 12345" → "12345"
            "Details for order 99999" → "99999"
            "Order #12345" → "12345"
        """
        # Pattern 1: "order number X" or "order # X"
        match = re.search(r'\border\s*(?:number|#|no\.?|num\.?)?\s*([0-9]+)', query, re.IGNORECASE)
        if match:
            order_no = match.group(1)
            logger.info(f"Extracted order number: {order_no}")
            return order_no
        
        # Pattern 2: Just a number after certain keywords
        match = re.search(r'\b(?:details?|info|information|status)\s+(?:on|for|of)?\s*#?\s*([0-9]{5,})', query, re.IGNORECASE)
        if match:
            order_no = match.group(1)
            logger.info(f"Extracted order number from detail request: {order_no}")
            return order_no
        
        # Pattern 3: Direct number reference (5+ digits)
        match = re.search(r'\b([0-9]{5,})\b', query)
        if match:
            order_no = match.group(1)
            logger.info(f"Extracted standalone order number: {order_no}")
            return order_no
        
        return None
    
    def _is_detail_request(self, query: str) -> bool:
        """
        Detect if user is asking for details of a specific order
        
        Args:
            query: User's search query
        
        Returns:
            True if this is a detail request
        
        Examples:
            "Give me details on order 90143" → True
            "Show me details for order 12345" → True
            "Details of order 99999" → True
            "What orders do I have?" → False
        """
        query_lower = query.lower()
        
        detail_keywords = [
            'detail', 'details', 'breakdown', 'break down', 'information',
            'info', 'status', 'show me order', 'give me order', 'get order'
        ]
        
        # Check if query contains detail keywords AND an order number
        has_detail_keyword = any(keyword in query_lower for keyword in detail_keywords)
        has_order_number = self._extract_order_number(query) is not None
        
        return has_detail_keyword and has_order_number
    
    def _extract_customer_info(self, query: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract customer code or name from query
        
        IMPORTANT: This should NOT extract if the query is about:
        - Specific order numbers (e.g., "details on order 90143")
        - Count queries (e.g., "how many orders")
        - Detail requests (e.g., "show me details for...")
        
        Args:
            query: User's search query
        
        Returns:
            Tuple of (customer_code, customer_name)
        
        Examples:
            "orders for ASEPCO" → (None, "ASEPCO")
            "orders for BALDWI" → (None, "BALDWI")
            "ACME orders" → (None, "ACME")
            "Give me details on order 90143" → (None, None)  # NOT a customer!
        """
        query_lower = query.lower()
        
        # SAFETY CHECK 1: Don't extract if asking about order number
        if self._extract_order_number(query) is not None:
            logger.info("Query is about order number, not customer - skipping customer extraction")
            return None, None
        
        # SAFETY CHECK 2: Don't extract if asking for details/breakdown
        if self._is_detail_request(query):
            logger.info("Query is detail request - skipping customer extraction")
            return None, None
        
        # SAFETY CHECK 3: Don't extract if it's a count query
        if self._is_count_query(query):
            logger.info("Query is count query - customer extraction will be more careful")
            # For count queries, we still want customer but be more strict
        
        # Blocklist of words that should NEVER be considered customer names
        blocklist_words = [
            'detail', 'details', 'information', 'info', 'breakdown', 'break', 'down',
            'show', 'give', 'get', 'find', 'search', 'list', 'display',
            'order', 'orders', 'shipment', 'shipments', 'history',
            'open', 'closed', 'pending', 'backlog', 'outstanding',
            'my', 'our', 'the', 'all', 'any', 'some',
            'status', 'number', 'data', 'record', 'records'
        ]
        
        # Pattern 1: "for [customer name]" - most reliable pattern
        match = re.search(
            r'\bfor\s+([A-Z][A-Za-z0-9\s&.-]+?)(?:\?|$|\s+(?:customer|corp|company|inc|ltd)?)', 
            query, 
            re.IGNORECASE
        )
        if match:
            customer_name = match.group(1).strip()
            # Remove trailing keywords
            customer_name = re.sub(r'\s+(customer|corp|company|inc|ltd)$', '', customer_name, flags=re.IGNORECASE).strip()
            
            # Safety check: make sure it's not a blocklisted word
            if customer_name.lower() not in blocklist_words:
                logger.info(f"Extracted customer name: {customer_name}")
                return None, customer_name
            else:
                logger.info(f"Rejected '{customer_name}' - matched blocklist")
                return None, None
        
        # Pattern 2: "[customer name] orders/shipments" - but be careful
        match = re.search(
            r'^([A-Z][A-Za-z0-9\s&.-]+?)\s+(?:orders?|shipments?)', 
            query, 
            re.IGNORECASE
        )
        if match:
            potential_name = match.group(1).strip()
            
            # Check against blocklist
            if potential_name.lower() not in blocklist_words:
                logger.info(f"Extracted customer name from prefix: {potential_name}")
                return None, potential_name
            else:
                logger.info(f"Rejected '{potential_name}' - matched blocklist")
                return None, None
        
        # Pattern 3: "customer [code]" - explicit customer code
        match = re.search(r'customer\s+([A-Z0-9-]+)', query, re.IGNORECASE)
        if match:
            customer_code = match.group(1).strip()
            logger.info(f"Extracted customer code: {customer_code}")
            return customer_code, None
        
        return None, None
    
    def _detect_record_type(self, query: str) -> Optional[str]:
        """Detect RecordType based on keywords"""
        query_lower = query.lower()
        
        open_keywords = [
            'open', 'pending', 'backorder', 'backlog', 'outstanding',
            'awaiting', 'unfulfilled', 'current', 'active'
        ]
        history_keywords = [
            'closed', 'completed', 'finished', 'historical', 'history',
            'past', 'previous', 'old', 'archived', 'invoiced'
        ]
        shipment_keywords = [
            'ship', 'shipped', 'shipment', 'shipments', 'deliver', 'delivery',
            'track', 'tracking', 'sent', 'dispatched'
        ]
        
        if any(keyword in query_lower for keyword in open_keywords):
            logger.info("Detected OpenOrder intent")
            return 'OpenOrder'
        if any(keyword in query_lower for keyword in shipment_keywords):
            logger.info("Detected ShipmentLine intent")
            return 'ShipmentLine'
        if any(keyword in query_lower for keyword in history_keywords):
            logger.info("Detected History intent")
            return 'History'
        
        logger.info("No specific RecordType detected - will search all types")
        return None
    
    def _is_count_query(self, query: str) -> bool:
        """Detect if user is asking for a count"""
        query_lower = query.lower()
        count_keywords = [
            'how many', 'count', 'number of', 'total', 'quantity of',
            'how much', 'sum of'
        ]
        return any(keyword in query_lower for keyword in count_keywords)
    
    def _analyze_query(self, query: str) -> QueryIntent:
        """
        Analyze user query to determine intent
        
        This is the main intelligence function that figures out:
        1. Is this about a specific order number?
        2. Is this a detail request?
        3. What RecordType to filter for?
        4. Which customer (if any)?
        5. Is it a count query?
        """
        intent = QueryIntent()
        
        # IMPORTANT: Check order number FIRST (highest priority)
        intent.order_number = self._extract_order_number(query)
        intent.is_detail_request = self._is_detail_request(query)
        
        # Then check other intents
        intent.is_count_query = self._is_count_query(query)
        intent.record_type = self._detect_record_type(query)
        
        # Extract customer ONLY if not an order number query
        if intent.order_number is None:
            intent.customer_code, intent.customer_name = self._extract_customer_info(query)
        else:
            logger.info("Query is about specific order number - not extracting customer")
        
        # Clean search text
        search_text = query
        for keyword in ['how many', 'count of', 'number of', 'total', 'details', 'detail']:
            search_text = re.sub(keyword, '', search_text, flags=re.IGNORECASE)
        intent.search_text = search_text.strip()
        
        logger.info(f"Query analysis: {intent}")
        return intent
    
    def _build_odata_filter(self, intent: QueryIntent) -> Optional[str]:
        """
        Build OData filter string from intent
        
        Priority order:
        1. Order number (if present)
        2. RecordType + Customer (if present)
        3. RecordType only
        4. Customer only
        5. No filter
        """
        filters = []
        
        # Priority 1: If specific order number, filter by that
        if intent.order_number:
            logger.info(f"Building filter for order number: {intent.order_number}")
            # Search for order number in ORDER_NO field
            # This will match 90143-01, 90143-02, etc.
            filters.append(f"search.ismatch('{intent.order_number}', 'ORDER_NO')")
            return ' and '.join(filters)  # Return early, order number is most specific
        
        # Priority 2: RecordType filter
        if intent.record_type:
            filters.append(f"RecordType eq '{intent.record_type}'")
        
        # Priority 3: Customer filter
        customer_val = intent.customer_name or intent.customer_code
        if customer_val:
            safe_val = customer_val.replace("'", "''")
            logger.info(f"Using dual-field customer filter for: {safe_val}")
            
            # Check BOTH Name and Code fields
            customer_filter = (
                f"("
                f"search.ismatch('{safe_val}', 'NAME_CUSTOMER') or "
                f"search.ismatch('{safe_val}', 'CUSTOMER')"
                f")"
            )
            filters.append(customer_filter)
        
        if filters:
            odata_filter = ' and '.join(filters)
            logger.info(f"Built OData filter: {odata_filter}")
            return odata_filter
        
        return None
    
    async def _execute_count_query(self, query: str, odata_filter: Optional[str]) -> int:
        """Execute a count-only query"""
        try:
            search_params = {
                'search_text': query,
                'filter': odata_filter,
                'include_total_count': True,
                'top': 0
            }
            search_params = {k: v for k, v in search_params.items() if v is not None}
            
            logger.info(f"Executing count query with filter: {odata_filter}")
            results = self.searchClient.search(**search_params)
            count = results.get_count()
            
            logger.info(f"Count query returned: {count} results")
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Count query failed: {e}", exc_info=True)
            return 0
    
    async def render_data(self, query: str) -> Result:
        """Main search function with proper OData filtering"""
        if not query or not query.strip():
            logger.warning("Empty query received")
            return Result('', {'warning': 'Empty query'})
        
        try:
            # Step 1: Analyze query intent
            intent = self._analyze_query(query)
            
            # Step 2: Build OData filter
            odata_filter = self._build_odata_filter(intent)
            
            # Step 3: Handle count queries specially (fast path)
            if intent.is_count_query:
                count = await self._execute_count_query(query, odata_filter)
                
                record_type_text = intent.record_type or "records"
                customer_text = f" for {intent.customer_name or intent.customer_code}" if (intent.customer_name or intent.customer_code) else ""
                
                response_text = f"COUNT RESULT: Found {count} {record_type_text}{customer_text}."
                
                metadata = {
                    'is_count_query': True,
                    'total_count': count,
                    'record_type': intent.record_type,
                    'customer': intent.customer_name or intent.customer_code,
                    'filter_applied': odata_filter
                }
                
                return Result(response_text, metadata)
            
            # Step 4: Generate embedding for regular search
            embedding = await get_embedding_vector(intent.search_text or query)
            
            # Step 5: Setup vector query
            vector_query = VectorizedQuery(
                vector=embedding,
                k_nearest_neighbors=self.options.vector_k,
                fields="text_vector"
            )
            
            # Step 6: Select fields to retrieve
            selected_fields = [
                'chunk', 'chunk_id', 'RecordType', 'ORDER_NO', 
                'NAME_CUSTOMER', 'CUSTOMER', 'DATE_SHIPPED', 'PROM_DT', 'SL_DATE_SHIP'
            ]
            
            # Step 7: Build search parameters
            # ADAPTIVE LIMIT: Increase top_k if we have a specific filter (High Recall Mode)
            current_top_k = self.options.top_k
            if odata_filter and not intent.order_number:
                current_top_k = 380 # Increase limit for broad customer/type queries
                logger.info(f"High Recall Mode: Increased top_k to {current_top_k} due to filter")

            search_params = {
                'search_text': intent.search_text or query,
                'select': selected_fields,
                'vector_queries': [vector_query],
                'top': current_top_k,
                'query_type': QueryType.SEMANTIC,
                'semantic_configuration_name': "rag-1767122801281-semantic-configuration"
            }
            
            # Add OData filter if we have one
            if odata_filter:
                search_params['filter'] = odata_filter
                logger.info(f"Applying OData filter: {odata_filter}")
            else:
                logger.info("No OData filter - searching all RecordTypes")
            
            search_params['include_total_count'] = True
            
            logger.info(f"Executing search with params: top={current_top_k}")
            
            # Step 8: Execute search
            searchResults = self.searchClient.search(**search_params)
            
            # Step 9: Process results
            all_results = list(searchResults)
            result_count = len(all_results)
            total_count = searchResults.get_count() or result_count
            
            logger.info(f"Retrieved {result_count} results (total matching: {total_count})")
            
            # Step 10: Group by base order number
            docs = []
            seen_chunks = set()
            order_groups = {}
            
            for result in all_results:
                content = result.get('chunk', 'N/A')
                
                if content in seen_chunks:
                    continue
                seen_chunks.add(content)
                
                record_type = result.get('RecordType', 'Unknown')
                cust_name = result.get('NAME_CUSTOMER', 'Unknown')
                cust_id = result.get('CUSTOMER', 'N/A')
                order_no = result.get('ORDER_NO', 'N/A')
                
                # Extract base order number (everything before the dash)
                base_order_no = str(order_no).split('-')[0].strip()
                
                if base_order_no not in order_groups:
                    order_groups[base_order_no] = []
                
                chunk_data = {
                    'record_type': record_type,
                    'customer_name': cust_name,
                    'customer_id': cust_id,
                    'order_no': order_no,
                    'base_order_no': base_order_no,
                    'content': content
                }
                order_groups[base_order_no].append(chunk_data)
            
            # Step 11: Format results
            for base_order, chunks in order_groups.items():
                first_chunk = chunks[0]
                
                # Add header showing base order number
                if len(chunks) > 1:
                    docs.append(
                        f"=== ORDER {base_order} ({first_chunk['record_type']}) | "
                        f"{first_chunk['customer_name']} | "
                        f"{len(chunks)} line items ==="
                    )
                
                # Add individual line items
                for chunk in chunks:
                    header = (
                        f"{chunk['record_type']} | "
                        f"{chunk['customer_name']} ({chunk['customer_id']}) | "
                        f"Order: {chunk['order_no']}"
                    )
                    docs.append(f"Source: {header}\nContent: {chunk['content']}")
            
            # Step 12: Create metadata
            metadata = {
                'total_results': result_count,
                'total_matching': total_count,
                'unique_chunks': len(seen_chunks),
                'unique_orders': len(order_groups),  # Count of unique base orders
                'record_type': intent.record_type,
                'customer': intent.customer_name or intent.customer_code,
                'order_number': intent.order_number,
                'is_detail_request': intent.is_detail_request,
                'filter_applied': odata_filter,
                'is_count_query': False
            }
            
            # Handle no results
            if not docs:
                logger.warning(f"No results found for query: {query}")
                no_results_msg = "No relevant records found"
                
                if intent.order_number:
                    no_results_msg += f" for order {intent.order_number}"
                elif intent.record_type:
                    no_results_msg += f" for {intent.record_type}"
                if intent.customer_name or intent.customer_code:
                    no_results_msg += f" for customer {intent.customer_name or intent.customer_code}"
                
                return Result(no_results_msg + ".", metadata)
            
            # Step 13: Format output with summary
            formatted_output = '\n\n---\n\n'.join(docs)
            
            # Build summary
            summary = f"SEARCH SUMMARY: Found {len(order_groups)} unique orders across {len(seen_chunks)} records"
            
            if total_count > result_count:
                summary += f" (showing top {result_count} of {total_count} total matches)"
            
            if intent.order_number:
                summary += f" | Order: {intent.order_number}"
            elif intent.record_type:
                summary += f" | Filtered by: {intent.record_type}"
            
            if intent.customer_name or intent.customer_code:
                summary += f" | Customer: {intent.customer_name or intent.customer_code}"
            
            formatted_output = summary + ".\n\n" + formatted_output
            
            logger.info(
                f"Successfully processed query - "
                f"Orders: {len(order_groups)}, Chunks: {len(seen_chunks)}, "
                f"Total matching: {total_count}"
            )
            
            return Result(formatted_output, metadata)
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return Result(
                "I encountered an error searching the database. "
                "Please try rephrasing your question.",
                {'error': str(e)}
            )