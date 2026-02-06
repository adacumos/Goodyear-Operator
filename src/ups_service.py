import logging
import requests
import base64
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class UPSService:
    """
    Native implementation of UPS MCP tools for Teams Bot.
    Handles authentication and package tracking.
    """
    
    def __init__(self, config: Config):
        self.client_id = config.UPS_CLIENT_ID
        self.client_secret = config.UPS_CLIENT_SECRET
        self.environment = config.UPS_ENVIRONMENT.lower()
        
        # Base URLs
        if self.environment == "production":
            self.base_url = "https://onlinetools.ups.com"
            self.track_url = "https://onlinetools.ups.com/api/track/v1/details"
        else:
            # CIE (Test) Environment
            self.base_url = "https://wwwcie.ups.com"
            self.track_url = "https://wwwcie.ups.com/api/track/v1/details"
            
        self.access_token = None
        self.token_expires_at = 0

    def _get_token(self) -> str:
        """
        Get or refresh OAuth 2.0 access token using Client Credentials flow.
        """
        # Return existing valid token if available
        if self.access_token and datetime.now().timestamp() < self.token_expires_at:
            return self.access_token

        if not self.client_id or not self.client_secret:
            logger.error("UPS Request failed: Missing Client ID or Secret")
            raise ValueError("UPS Credentials not configured.")

        url = f"{self.base_url}/security/v1/oauth/token"
        
        # Basic Auth header with Client ID and Secret
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        payload = {
            "grant_type": "client_credentials"
        }
        
        try:
            logger.info(f"Requesting new UPS token from {url}")
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            
            # Set expiration (default usually ~4 hours, subtract buffer)
            expires_in = int(data.get("expires_in", 3600))
            self.token_expires_at = datetime.now().timestamp() + expires_in - 300
            
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to obtain UPS token: {e}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise

    def track_package(self, inquiry_number: str) -> str:
        """
        Track a package using UPS Tracking API.
        
        Args:
            inquiry_number (str): The tracking number (7-34 chars)
            
        Returns:
            str: JSON string of tracking data or error message
        """
        try:
            token = self._get_token()
            
            url = f"{self.track_url}/{inquiry_number}"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "transId": f"track_{inquiry_number}_{int(datetime.now().timestamp())}",
                "transactionSrc": "GoodyearOperatorBot"
            }
            
            # Optional query params can be added here (locale, etc.)
            params = {
                "locale": "en_US",
                "returnSignature": "false",
                "returnMilestones": "true"
            }
            
            logger.info(f"Tracking package {inquiry_number}")
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                # Return the full "trackResponse" object as string for the LLM to parse
                return str(result)
            else:
                error_msg = f"Tracking failed with status {response.status_code}: {response.text}"
                logger.warning(error_msg)
                return f"Error tracking package: {response.text}"
                
        except Exception as e:
            logger.error(f"UPS Tracking error: {e}")
            return f"System error tracking package: {str(e)}"
