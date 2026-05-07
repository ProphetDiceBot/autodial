import requests
from typing import List, Optional

class AutodialClient:
    """
    A professional client for interacting with the Autodial server.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        
    def dial(self, target_number: str, 
             context: Optional[str] = None, 
             goals: Optional[str] = None, 
             keywords: Optional[str] = None,
             callback_url: Optional[str] = None,
             system_instructions: Optional[str] = None) -> dict:
        """
        Initiates a single outbound call.
        """
        payload = {
            "to_number": target_number,
            "context": context,
            "goals": goals,
            "keywords": keywords,
            "callback_url": callback_url,
            "system_instructions": system_instructions
        }
        response = requests.post(f"{self.base_url}/dial", json=payload)
        response.raise_for_status()
        return response.json()
        
    def broadcast(self, numbers: List[str], 
                  message: Optional[str] = None,
                  context: Optional[str] = None, 
                  goals: Optional[str] = None, 
                  keywords: Optional[str] = None,
                  callback_url: Optional[str] = None,
                  system_instructions: Optional[str] = None) -> dict:
        """
        Initiates a broadcast to multiple numbers.
        """
        payload = {
            "numbers": numbers,
            "message": message,
            "context": context,
            "goals": goals,
            "keywords": keywords,
            "callback_url": callback_url,
            "system_instructions": system_instructions
        }
        response = requests.post(f"{self.base_url}/broadcast", json=payload)
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    # Example usage:
    # client = AutodialClient("https://your-public-server.com")
    # client.dial("+1234567890", context="Customer Support Inquiry")
    pass
