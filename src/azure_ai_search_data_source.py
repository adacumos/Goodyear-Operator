from dataclasses import dataclass
from typing import Optional, List
from azure.search.documents.models import QueryType, VectorizedQuery
from openai import AsyncAzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from config import Config

async def get_embedding_vector(text: str):
    client = AsyncAzureOpenAI(
        api_key=Config.AZURE_OPENAI_API_KEY,
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_version="2024-12-01-preview"
    )
    result = await client.embeddings.create(
        model=Config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT, 
        input=text
    )
    
    if not result.data:
        raise Exception(f"Failed to generate embeddings for description: {text}")
    return result.data[0].embedding

@dataclass
class AzureAISearchDataSourceOptions:
    name: str
    indexName: str
    azureAISearchApiKey: str
    azureAISearchEndpoint: str

@dataclass
class Result:
    def __init__(self, output):
        self.output = output

class AzureAISearchDataSource():
    def __init__(self, options: AzureAISearchDataSourceOptions):
        self.name = options.name
        self.options = options
        self.searchClient = SearchClient(
            options.azureAISearchEndpoint,
            options.indexName,
            AzureKeyCredential(options.azureAISearchApiKey)
        )
        
    def name(self):
        return self.name

    async def render_data(self, query):
        # 1. Generate the embedding for the user's question
        embedding = await get_embedding_vector(query)
        
        # 2. Setup the Vector Query             
        vector_query = VectorizedQuery(
            vector=embedding, 
            k_nearest_neighbors=50,
            fields="text_vector"
        )

        if not query:
            return Result('')

        # 3. Select ONLY valid fields from your Index Screenshots
        # Replaced 'SearchID' with 'chunk_id'
        # Added 'NAME_CUSTOMER' for better context
        selectedFields = [
            'chunk',           # Main content
            'chunk_id',        # Unique Key (from screenshot)
            'RecordType',      # Filter category
            'ORDER_NO',        # Specific metadata
            'NAME_CUSTOMER',   # Readable customer name
            'CUSTOMER'         # Customer ID code
        ]

        # 4. Execute Search
        searchResults = self.searchClient.search(
            search_text=query,
            select=selectedFields,
            vector_queries=[vector_query],            
            top=20,
            query_type=QueryType.SEMANTIC,
            semantic_configuration_name="rag-1767122801280-semantic-configuration"
        )

        if not searchResults:
            return Result('')

        # 5. Format the output for the Bot
        docs = []
        for result in searchResults:
            # Construct a header using valid fields from your index
            # Example: "History | GOODYEAR (10055) | Order: 12345"
            record_type = result.get('RecordType', 'Record')
            cust_name = result.get('NAME_CUSTOMER', 'Unknown')
            cust_id = result.get('CUSTOMER', 'N/A')
            order_no = result.get('ORDER_NO', 'N/A')
            
            header = f"{record_type} | {cust_name} ({cust_id}) | Order: {order_no}"
            
            # The 'chunk' field contains the full sentence text
            content = result.get('chunk', 'N/A')
            
            docs.append(f"Source: {header}\nContent: {content}")
        
        # Join chunks with a separator to help the LLM distinguish them
        return Result('\n\n---\n\n'.join(docs))