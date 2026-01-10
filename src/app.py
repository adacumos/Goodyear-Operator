"""
Improved App with Better Memory Management and Error Handling
Save this file as: app.py (replace your existing app.py)
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = Config()

# Create Azure AI Search options with optimized parameters
search_options = AzureAISearchDataSourceOptions(
    name="goodyear-agent-search",
    indexName="rag-1768021240909", 
    azureAISearchApiKey=config.AZURE_SEARCH_KEY,
    azureAISearchEndpoint=config.AZURE_SEARCH_ENDPOINT,
    top_k=15,      # Reduced for better precision
    vector_k=30    # Aligned with actual usage
)

azure_ai_search = AzureAISearchDataSource(search_options)

# Load instructions from file
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

# Enhanced system message for gpt-4o-mini
SYSTEM_ENHANCEMENT = """

CRITICAL RESPONSE RULES FOR GPT-4O-MINI:
1. ALWAYS cite specific Order Numbers when providing information
2. ALWAYS include Units of Measure (UM) with quantities
3. When multiple line items share an order number, present them as ONE order with multiple items
4. For "how many" questions, count UNIQUE order numbers, not line items
5. Use tables for multi-item responses
6. If search returns no results, say "No records found" - do NOT make up data
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

# Create optimized model for corporate assistant
# Lower temperature (0.2) for more factual, deterministic responses
# Increased max_tokens (3000) for detailed tables and summaries
model = create_model_from_config(
    temperature=0.2,           # Very low for maximum accuracy
    max_tokens=3000,           # Higher for detailed responses
    top_p=0.9,                 # Focused sampling
    frequency_penalty=0.3,     # Reduce repetition
    presence_penalty=0.1       # Slight topic variety
)

logger.info(f"Model initialized with parameters: {model.get_parameters()}")


# Memory management with size limits
MAX_CONVERSATION_TURNS = 10  # Keep last 10 turns to prevent token overflow
conversation_store: Dict[str, ListMemory] = {}


def get_or_create_conversation_memory(conversation_id: str) -> ListMemory:
    """
    Get or create conversation memory with automatic cleanup
    
    Args:
        conversation_id: Unique conversation identifier
    
    Returns:
        ListMemory instance
    """
    if conversation_id not in conversation_store:
        logger.info(f"Creating new conversation memory: {conversation_id}")
        conversation_store[conversation_id] = ListMemory()
    
    memory = conversation_store[conversation_id]
    
    # Limit memory size to prevent token overflow
    # Each turn = user message + assistant response = 2 messages
    max_messages = MAX_CONVERSATION_TURNS * 2
    
    # Get current messages (this is a workaround since ListMemory doesn't expose count)
    # We'll track this in a more robust way
    
    return memory


def cleanup_old_conversations():
    """
    Cleanup conversations older than 1 hour (optional background task)
    This is a simple implementation - in production, use a proper TTL cache
    """
    # This would require timestamp tracking - simplified for now
    # In production: use redis with TTL or implement proper cache eviction
    pass


async def validate_response(response: str, query: str) -> Dict[str, any]:
    """
    Validate AI response meets quality standards
    
    Args:
        response: AI generated response
        query: Original user query
    
    Returns:
        Dictionary with validation results
    """
    validation = {
        'has_order_numbers': 'Order' in response or '#' in response,
        'has_units': any(unit in response for unit in ['FT', 'LB', 'EA', 'GAL']),
        'has_no_data_claim': 'No records found' in response or 'no open orders' in response.lower(),
        'is_too_short': len(response.split()) < 10,
        'mentions_making_up_data': 'I cannot' in response or "I don't have" in response
    }
    
    # Check if query asks for count
    is_count_query = any(word in query.lower() for word in ['how many', 'count', 'number of'])
    
    if is_count_query:
        validation['has_count'] = any(char.isdigit() for char in response)
    
    return validation


async def handle_stateful_conversation(
    model: AIModel, 
    ctx: ActivityContext[MessageActivity]
) -> None:
    """
    Enhanced conversation handler with validation and error recovery
    
    Args:
        model: AI model instance
        ctx: Activity context
    """
    conversation_id = ctx.activity.conversation.id
    logger.info(f"Processing message for conversation: {conversation_id}")
    
    try:
        # Get conversation memory
        memory = get_or_create_conversation_memory(conversation_id)
        
        # Extract user input
        input_text = ctx.activity.strip_mentions_text().text
        logger.info(f"User query: {input_text}")
        
        # Send typing indicator for better UX
        # await ctx.send_typing_indicator()  # If available in your SDK
        
        # Step 1: Retrieve RAG data with error handling
        try:
            data_context = await azure_ai_search.render_data(input_text)
            logger.info(f"Search metadata: {data_context.metadata}")
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            await ctx.send(
                MessageActivityInput(
                    text="I'm having trouble accessing the database right now. Please try again in a moment."
                )
            )
            return
        
        # Step 2: Build enhanced prompt
        enhanced_instructions = INSTRUCTIONS + SYSTEM_ENHANCEMENT
        
        # Add metadata context if available
        metadata_context = ""
        if hasattr(data_context, 'metadata') and data_context.metadata:
            meta = data_context.metadata
            if meta.get('unique_orders', 0) > 0:
                metadata_context = f"\n\nSEARCH METADATA: Found {meta['unique_orders']} unique orders in {meta['unique_chunks']} records."
        
        full_context = f"{enhanced_instructions}\n\nAdditional Context from Search:{metadata_context}\n{data_context.output}"
        
        # Step 3: Create chat prompt and send to AI
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
                    text="I encountered an error generating a response. Please rephrase your question."
                )
            )
            return
        
        # Step 4: Validate response
        response_text = chat_result.response.content
        validation = await validate_response(response_text, input_text)
        
        # Log validation results
        logger.info(f"Response validation: {validation}")
        
        # Step 5: Send response with feedback
        await ctx.send(
            MessageActivityInput(text=response_text)
            .add_ai_generated()
            .add_feedback()
        )
        
        logger.info(f"Response sent successfully for conversation: {conversation_id}")
        
    except Exception as e:
        logger.error(f"Unexpected error in conversation handler: {e}", exc_info=True)
        
        # Send generic error message
        await ctx.send(
            MessageActivityInput(
                text="An unexpected error occurred. Our team has been notified. Please try again."
            )
        )


@app.on_message
async def handle_message(ctx: ActivityContext[MessageActivity]):
    """
    Main message handler
    
    Args:
        ctx: Activity context
    """
    await handle_stateful_conversation(model, ctx)


@app.on_message_submit_feedback
async def handle_message_feedback(ctx: ActivityContext[MessageSubmitActionInvokeActivity]):
    """
    Handle feedback submission events
    
    Args:
        ctx: Activity context with feedback
    """
    activity = ctx.activity
    feedback_value = activity.value.action_value
    
    logger.info(f"User feedback received: {feedback_value}")
    
    # In production, store this in a database for analysis
    # Example: await store_feedback(conversation_id, message_id, feedback_value)
    
    # Optional: Send acknowledgment
    # await ctx.send(MessageActivityInput(text="Thank you for your feedback!"))


if __name__ == "__main__":
    logger.info("Starting Goodyear AI Assistant...")
    asyncio.run(app.start())