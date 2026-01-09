"""
Custom AI Model Wrapper with Configurable Parameters
This wrapper allows you to control temperature, max_tokens, and other model parameters
"""

from microsoft_teams.openai import OpenAICompletionsAIModel
from typing import Optional, Any, Dict
from config import Config


class CustomAIModel(OpenAICompletionsAIModel):
    """
    Extended AI Model with configurable parameters
    
    Why this approach?
    - Inherits all functionality from OpenAICompletionsAIModel
    - Allows us to inject custom parameters before API calls
    - Easy to maintain and understand
    - Can be extended with more parameters as needed
    """
    
    def __init__(
        self,
        key: str,
        model: str,
        azure_endpoint: str,
        api_version: str = "2024-12-01-preview",
        temperature: float = 0.7,
        max_tokens: int = 1500,
        top_p: float = 0.95,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        **kwargs
    ):
        """
        Initialize the custom AI model with configurable parameters
        
        Args:
            key: Azure OpenAI API key
            model: Model deployment name
            azure_endpoint: Azure OpenAI endpoint
            api_version: API version to use
            temperature: Controls randomness (0.0-2.0). Lower = more focused, Higher = more creative
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter (0.0-1.0)
            frequency_penalty: Reduces repetition (-2.0 to 2.0)
            presence_penalty: Encourages new topics (-2.0 to 2.0)
        """
        # Call parent constructor
        super().__init__(
            key=key,
            model=model,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            **kwargs
        )
        
        # Store custom parameters
        self.model_parameters = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty
        }
    
    async def complete_prompt(self, messages: list, **kwargs) -> Any:
        """
        Override the completion method to inject our custom parameters
        
        This method intercepts the API call and adds our parameters
        before sending to Azure OpenAI
        """
        # Merge our stored parameters with any kwargs passed in
        # kwargs take precedence if provided
        merged_params = {**self.model_parameters, **kwargs}
        
        # Call parent's complete_prompt with merged parameters
        return await super().complete_prompt(messages, **merged_params)
    
    def update_parameters(self, **params):
        """
        Update model parameters on the fly
        
        Usage:
            model.update_parameters(temperature=0.5, max_tokens=2000)
        """
        self.model_parameters.update(params)
    
    def get_parameters(self) -> Dict[str, Any]:
        """
        Get current model parameters
        
        Returns:
            Dictionary of current parameter values
        """
        return self.model_parameters.copy()


def create_model_from_config(
    temperature: float = 0.7,
    max_tokens: int = 1500,
    top_p: float = 0.95,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0
) -> CustomAIModel:
    """
    Factory function to create a configured AI model
    
    This is a simple helper that reads from Config and creates
    a CustomAIModel with the specified parameters.
    
    Args:
        temperature: Controls response randomness (default: 0.7)
        max_tokens: Maximum response length (default: 1500)
        top_p: Nucleus sampling (default: 0.95)
        frequency_penalty: Repetition penalty (default: 0.0)
        presence_penalty: Topic diversity (default: 0.0)
    
    Returns:
        Configured CustomAIModel instance
    """
    return CustomAIModel(
        key=Config.AZURE_OPENAI_API_KEY,
        model=Config.AZURE_OPENAI_MODEL_DEPLOYMENT_NAME,
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_version="2024-12-01-preview",
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )