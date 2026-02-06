"""
Enhanced App with Analytics and Forecasting Capabilities
Simplified version with clearer logic flow
"""

import asyncio
import os
import logging
from typing import Dict

from azure.identity import ManagedIdentityCredential
from microsoft_teams.ai import ChatPrompt, ListMemory
from microsoft_teams.ai.ai_model import AIModel
from microsoft_teams.apps import App, ActivityContext
from microsoft_teams.api import MessageActivity, MessageActivityInput, MessageSubmitActionInvokeActivity

from config import Config
from azure_ai_search_data_source import AzureAISearchDataSource, AzureAISearchDataSourceOptions
from custom_ai_model import create_model_from_config
from analytics_helper import create_analytics_context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = Config()

# Create Azure AI Search with optimized parameters
search_options = AzureAISearchDataSourceOptions(
    name="goodyear-agent-search",
    indexName="rag-1767122801281", 
    azureAISearchApiKey=config.AZURE_SEARCH_KEY,
    azureAISearchEndpoint=config.AZURE_SEARCH_ENDPOINT,
    top_k=15,
    vector_k=35
)

azure_ai_search = AzureAISearchDataSource(search_options)


def load_instructions() -> str:
    """Load instructions from instructions.txt file"""
    try:
        filepath = os.path.join(os.path.dirname(__file__), "instructions.txt")
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.error("instructions.txt not found, using default")
        return "You are a helpful assistant."


INSTRUCTIONS = load_instructions()

# System enhancement for GPT-4o-mini with clear rules
SYSTEM_ENHANCEMENT = """

CRITICAL RESPONSE RULES:
1. ALWAYS cite specific Order Numbers when providing information
2. ALWAYS include Units of Measure (UM) with quantities
3. When multiple line items share an order number, present them as ONE order with multiple items
4. For "how many" questions, count UNIQUE order numbers, not line items
5. Use tables for multi-item responses
6. If search returns no results, say "No records found" - do NOT make up data

ANALYTICAL INTELLIGENCE RULES:
7. When asked about trends, forecasts, or patterns: ANALYZE the data, don't just report it
8. ALWAYS provide confidence levels for forecasts (HIGH/MEDIUM/LOW)
9. Include specific numbers and calculations in analytical responses
10. Provide ACTIONABLE recommendations based on data insights
11. Use the Analytical Summary (if provided) to enhance your responses
12. Think like a manufacturing analyst: consider seasonality, capacity, customer patterns
"""


def create_token_factory():
    """Create token factory for managed identity"""
    def get_token(scopes, tenant_id=None):
        credential = ManagedIdentityCredential(client_id=config.APP_ID)
        scopes_list = [scopes] if isinstance(scopes, str) else scopes
        token = credential.get_token(*scopes_list)
        return token.token
    return get_token


app = App(
    token=create_token_factory() if config.APP_TYPE == "UserAssignedMsi" else None
)

# Create optimized model for analytical responses
model = create_model_from_config(
    temperature=0.3,
    max_tokens=4000,
    top_p=0.9,
    frequency_penalty=0.3,
    presence_penalty=0.2
)

logger.info(f"Model initialized: {model.get_parameters()}")

# Memory management
MAX_CONVERSATION_TURNS = 10
conversation_store: Dict[str, ListMemory] = {}


def get_conversation_memory(conversation_id: str) -> ListMemory:
    """
    Get or create conversation memory
    
    Args:
        conversation_id: Unique conversation identifier
    
    Returns:
        ListMemory instance
    """
    if conversation_id not in conversation_store:
        logger.info(f"Creating new conversation memory: {conversation_id}")
        conversation_store[conversation_id] = ListMemory()
    
    return conversation_store[conversation_id]


def is_analytical_query(query: str) -> bool:
    """
    Simple check if query requires analytical response
    
    Args:
        query: User's query text
    
    Returns:
        True if query is analytical in nature
    """
    analytical_keywords = [
        'forecast', 'predict', 'trend', 'pattern', 'analyze',
        'growth', 'decline', 'compare', 'revenue', 'performance',
        'recommend', 'should i', 'next month', 'last quarter',
        'how much', 'expect', 'projection'
    ]
    
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in analytical_keywords)


async def handle_message_conversation(
    model: AIModel, 
    ctx: ActivityContext[MessageActivity]
) -> None:
    """
    Main conversation handler with analytics support
    
    Flow:
    1. Get conversation memory
    2. Extract user query
    3. Search database (with automatic RecordType filtering)
    4. Generate analytics context (if analytical query)
    5. Send to AI model
    6. Return response
    
    Args:
        model: AI model instance
        ctx: Activity context
    """
    conversation_id = ctx.activity.conversation.id
    logger.info(f"Processing message for conversation: {conversation_id}")
    
    try:
        # Step 1: Get conversation memory
        memory = get_conversation_memory(conversation_id)
        
        # Step 2: Extract user input
        input_text = ctx.activity.strip_mentions_text().text
        logger.info(f"User query: {input_text}")
        
        # Check if this is analytical
        is_analytical = is_analytical_query(input_text)
        if is_analytical:
            logger.info("Detected analytical query - will include analytics context")
        
        # Step 3: Search database (RecordType filtering now happens automatically)
        try:
            data_context = await azure_ai_search.render_data(input_text)
            logger.info(f"Search results: {data_context.metadata}")
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            await ctx.send(
                MessageActivityInput(
                    text="I'm having trouble accessing the database right now. "
                         "Please try again in a moment."
                )
            )
            return
        
        # Step 4: Build context for AI
        enhanced_instructions = INSTRUCTIONS + SYSTEM_ENHANCEMENT
        
        # Add search metadata if available
        metadata_context = ""
        if hasattr(data_context, 'metadata') and data_context.metadata:
            meta = data_context.metadata
            if meta.get('unique_orders', 0) > 0:
                filter_info = ""
                if meta.get('filter_applied'):
                    filter_info = f" (Filtered by: {meta.get('record_type_filter')})"
                
                metadata_context = (
                    f"\n\nSEARCH METADATA: Found {meta['unique_orders']} unique orders "
                    f"in {meta['unique_chunks']} records{filter_info}."
                )
        
        # Step 5: Generate analytics context for analytical queries
        analytics_context = ""
        if is_analytical and data_context.output:
            try:
                analytics_context = create_analytics_context(data_context.output)
                logger.info("Generated analytics context")
            except Exception as e:
                logger.error(f"Analytics generation failed: {e}")
        
        # Combine all context
        full_context = (
            f"{enhanced_instructions}"
            f"{metadata_context}"
            f"{analytics_context}"
            f"\n\nSearch Results:\n{data_context.output}"
        )
        
        # Step 6: Send to AI model
        chat_prompt = ChatPrompt(model)
        
        try:
            chat_result = await chat_prompt.send(
                input=input_text,
                memory=memory,
                instructions=full_context
            )
        except Exception as e:
            logger.error(f"Model completion failed: {e}", exc_info=True)
            await ctx.send(
                MessageActivityInput(
                    text="I encountered an error generating a response. "
                         "Please rephrase your question."
                )
            )
            return
        
        # Step 7: Send response
        response_text = chat_result.response.content
        
        await ctx.send(
            MessageActivityInput(text=response_text)
            .add_ai_generated()
            .add_feedback()
        )
        
        logger.info(f"Response sent successfully for: {conversation_id}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        await ctx.send(
            MessageActivityInput(
                text="An unexpected error occurred. Please try again."
            )
        )


@app.on_message
async def handle_message(ctx: ActivityContext[MessageActivity]):
    """Main message handler"""
    await handle_message_conversation(model, ctx)


@app.on_message_submit_feedback
async def handle_feedback(ctx: ActivityContext[MessageSubmitActionInvokeActivity]):
    """Handle user feedback"""
    activity = ctx.activity
    feedback_value = activity.value.action_value
    
    logger.info(f"User feedback received: {feedback_value}")
    
    # In production: store feedback for analysis and model improvement
    # Example: await store_feedback(conversation_id, message_id, feedback_value)


if __name__ == "__main__":
    logger.info("Starting Goodyear AI Assistant with Analytics...")
    asyncio.run(app.start())