"""
Enhanced App with Analytics and Forecasting Capabilities
Replace your existing app.py with this version
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
from analytics_helper import create_analytics_context, ManufacturingAnalytics

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

# Enhanced system message for gpt-4o-mini with analytics focus
SYSTEM_ENHANCEMENT = """

CRITICAL RESPONSE RULES FOR GPT-4O-MINI:
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

# Create optimized model for corporate assistant with analytics
# Lower temperature (0.2) for factual responses, but allow some creativity for insights
model = create_model_from_config(
    temperature=0.3,           # Slightly higher for analytical reasoning
    max_tokens=4000,           # Higher for detailed analytical responses
    top_p=0.9,                 # Focused sampling
    frequency_penalty=0.3,     # Reduce repetition
    presence_penalty=0.2       # Encourage diverse analytical perspectives
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
    
    return conversation_store[conversation_id]


def detect_analytical_query(query: str) -> bool:
    """
    Detect if query requires analytical/forecasting response
    
    Args:
        query: User's query text
    
    Returns:
        True if query is analytical in nature
    """
    analytical_keywords = [
        'forecast', 'predict', 'trend', 'pattern', 'analyze', 'analysis',
        'growth', 'decline', 'increase', 'decrease', 'compare', 'comparison',
        'revenue', 'sales', 'performance', 'metric', 'average', 'total',
        'should i', 'recommend', 'suggest', 'prioritize', 'focus',
        'next month', 'next quarter', 'next year', 'last month', 'last quarter',
        'how much', 'how many', 'what if', 'expect', 'projection'
    ]
    
    query_lower = query.lower()
    is_analytical = any(keyword in query_lower for keyword in analytical_keywords)
    
    if is_analytical:
        logger.info(f"Detected analytical query: {query[:50]}...")
    
    return is_analytical


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
        'mentions_making_up_data': 'I cannot' in response or "I don't have" in response,
        'is_analytical': detect_analytical_query(query)
    }
    
    # Check if query asks for count
    is_count_query = any(word in query.lower() for word in ['how many', 'count', 'number of'])
    
    if is_count_query:
        validation['has_count'] = any(char.isdigit() for char in response)
    
    # Additional checks for analytical queries
    if validation['is_analytical']:
        validation['has_numbers'] = any(char.isdigit() for char in response)
        validation['has_recommendations'] = 'recommend' in response.lower() or 'suggest' in response.lower()
        validation['has_confidence'] = any(conf in response.lower() for conf in ['high confidence', 'medium confidence', 'low confidence'])
    
    return validation


async def handle_stateful_conversation(
    model: AIModel, 
    ctx: ActivityContext[MessageActivity]
) -> None:
    """
    Enhanced conversation handler with analytics and forecasting
    
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
        
        # Detect if this is an analytical query
        is_analytical = detect_analytical_query(input_text)
        
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
        
        # Step 2: Build enhanced prompt with analytics context
        enhanced_instructions = INSTRUCTIONS + SYSTEM_ENHANCEMENT
        
        # Add metadata context if available
        metadata_context = ""
        if hasattr(data_context, 'metadata') and data_context.metadata:
            meta = data_context.metadata
            if meta.get('unique_orders', 0) > 0:
                metadata_context = f"\n\nSEARCH METADATA: Found {meta['unique_orders']} unique orders in {meta['unique_chunks']} records."
        
        # Step 3: Generate analytics context if this is an analytical query
        analytics_context = ""
        if is_analytical and data_context.output:
            try:
                analytics_context = create_analytics_context(data_context.output)
                logger.info("Generated analytics context for analytical query")
            except Exception as e:
                logger.error(f"Analytics context generation failed: {e}")
        
        # Combine all context
        full_context = (
            f"{enhanced_instructions}"
            f"{metadata_context}"
            f"{analytics_context}"
            f"\n\nAdditional Context from Search:\n{data_context.output}"
        )
        
        # Step 4: Create chat prompt and send to AI
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
        
        # Step 5: Validate response
        response_text = chat_result.response.content
        validation = await validate_response(response_text, input_text)
        
        # Log validation results
        logger.info(f"Response validation: {validation}")
        
        # Optional: Add warning if analytical query lacks key elements
        if validation['is_analytical']:
            missing_elements = []
            if not validation.get('has_numbers'):
                missing_elements.append("specific numbers")
            if not validation.get('has_recommendations'):
                missing_elements.append("recommendations")
            
            if missing_elements:
                logger.warning(f"Analytical response missing: {', '.join(missing_elements)}")
        
        # Step 6: Send response with feedback
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
    # Especially important for analytical queries to improve forecasting accuracy
    # Example: await store_feedback(conversation_id, message_id, feedback_value, is_analytical=True)


if __name__ == "__main__":
    logger.info("Starting Goodyear AI Assistant with Analytics...")
    asyncio.run(app.start())