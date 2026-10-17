import os
import requests
import json
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class CREATokenHandler:
    def __init__(self):
        self.token_endpoint = "https://identity.crea.ca/connect/token"
        self.client_id = os.getenv("CREA_CLIENT_ID")
        self.client_secret = os.getenv("CREA_CLIENT_SECRET")
        self.access_token = None
        self.token_expires_at = None
    
    def _require_credentials(self) -> None:
        if not self.client_id or not self.client_secret:
            raise ValueError("CREA_CLIENT_ID and CREA_CLIENT_SECRET must be set in environment variables")
    
    def get_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary
        """
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
        
        return self._request_new_token()
    
    def _request_new_token(self) -> str:
        """
        Request a new access token from the CREA API
        """
        self._require_credentials()
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "DDFApi_Read"
        }
        
        try:
            response = requests.post(
                self.token_endpoint,
                headers=headers,
                data=data,
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data["access_token"]
            
            # Calculate expiration time (subtract 60 seconds for safety margin)
            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
            
            print(f"Successfully obtained new access token, expires at: {self.token_expires_at}")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to obtain access token: {str(e)}")
        except KeyError as e:
            raise Exception(f"Invalid token response format: {str(e)}")
    
    def get_authorization_header(self) -> dict:
        """
        Get the authorization header for API requests
        """
        token = self.get_access_token()
        return {"Authorization": f"Bearer {token}"}
    
    def is_token_valid(self) -> bool:
        """
        Check if the current token is valid and not expired
        """
        return (self.access_token is not None and 
                self.token_expires_at is not None and 
                datetime.now() < self.token_expires_at)

# Global instance for easy access
crea_token_handler = CREATokenHandler() 