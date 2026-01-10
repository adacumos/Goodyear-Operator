import asyncio
import os

from azure.identity import ManagedIdentityCredential
from microsoft_teams.ai import ChatPrompt, ListMemory
from microsoft_teams.ai.ai_model import AIModel
from microsoft_teams.apps import App, ActivityContext
from microsoft_teams.api import MessageActivity, MessageActivityInput, MessageSubmitActionInvokeActivity

from config import Config
from azure_ai_search_data_source import AzureAISearchDataSource, AzureAISearchDataSourceOptions
# Import our custom model
from custom_ai_model import create_model_from_config

config = Config()

# Create Azure AI Search options
search_options = AzureAISearchDataSourceOptions(
    name="goodyear-agent-search",
    indexName="rag-1768021240909", 
    azureAISearchApiKey=config.AZURE_SEARCH_KEY,
    azureAISearchEndpoint=config.AZURE_SEARCH_ENDPOINT
)

azure_ai_search = AzureAISearchDataSource(search_options)

# Load instructions from file
def load_instructions() -> str:
    """Load instructions from instructions.txt file"""
    try:
        with open(os.path.join(os.path.dirname(__file__), "instructions.txt"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "You are a helpful assistant."

INSTRUCTIONS = load_instructions()

def create_token_factory():
    def get_token(scopes, tenant_id=None):
        credential = ManagedIdentityCredential(client_id=config.APP_ID)
        if isinstance(scopes, str):
            scopes_list = [scopes]
        else:
            scopes_list = scopes
        token = credential.get_token(*scopes_list)
        return token.token
    return get_token

app = App(
    token=create_token_factory() if config.APP_TYPE == "UserAssignedMsi" else None
)

# ===================================================================
# UPDATED: Create model with custom parameters
# ===================================================================
# For a corporate assistant that needs to be precise and factual:
# - Lower temperature (0.3) = More focused, deterministic responses
# - Higher max_tokens (2000) = Allows for detailed explanations
# - Lower frequency_penalty = Acceptable repetition for clarity

model = create_model_from_config(
    temperature=0.3,           # Low temperature for factual, precise responses
    max_tokens=2500,           # Allow detailed responses with tables
    top_p=0.9,                 # Slightly focused sampling
    frequency_penalty=0.2,     # Minimal penalty to avoid awkward phrasing
    presence_penalty=0.1       # Slight encouragement for topic variety
)

# You can also update parameters dynamically if needed:
# model.update_parameters(temperature=0.5, max_tokens=1500)

# Or check current parameters:
# print(f"Current model parameters: {model.get_parameters()}")
# ===================================================================


conversation_store: dict[str, ListMemory] = {}

def get_or_create_conversation_memory(conversation_id: str) -> ListMemory:
    """Get or create conversation memory for a specific conversation"""
    if conversation_id not in conversation_store:
        conversation_store[conversation_id] = ListMemory()
    return conversation_store[conversation_id]

async def handle_stateful_conversation(model: AIModel, ctx: ActivityContext[MessageActivity]) -> None:
    """Example of stateful conversation handler that maintains conversation history"""
    # Retrieve existing conversation memory or initialize new one
    memory = get_or_create_conversation_memory(ctx.activity.conversation.id)

    input_text = ctx.activity.strip_mentions_text().text
    
    # 1. Retrieve RAG Data
    data_context = await azure_ai_search.render_data(input_text)

    # Create ChatPrompt with conversation-specific memory
    chat_prompt = ChatPrompt(model)

    # 2. Send to AI
    chat_result = await chat_prompt.send(
        input=input_text,
        memory=memory,
        instructions=f"{INSTRUCTIONS}\n\nAdditional Context from Search:\n{data_context.output}"
    )

    # 3. Send Response Directly
    await ctx.send(
        MessageActivityInput(text=chat_result.response.content)
        .add_ai_generated()
        .add_feedback()
    )

@app.on_message
async def handle_message(ctx: ActivityContext[MessageActivity]):
    """Handle messages using stateful conversation"""
    await handle_stateful_conversation(model, ctx)

@app.on_message_submit_feedback
async def handle_message_feedback(ctx: ActivityContext[MessageSubmitActionInvokeActivity]):
    """Handle feedback submission events"""
    activity = ctx.activity
    print(f"User feedback: {activity.value.action_value}")

if __name__ == "__main__":
    asyncio.run(app.start())