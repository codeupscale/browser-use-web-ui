import os
from dotenv import load_dotenv

def load_env_from_root():
    """
    Load environment variables from the root .env file.
    This function calculates the path to the root .env file relative to the current file location.
    """
    # Get the current file's directory
    current_dir = os.path.dirname(__file__)
    
    # Navigate to the root directory (browser-use-web-ui)
    # From src/API/utils/ -> src/API/ -> src/ -> root
    root_dir = os.path.join(current_dir, '..', '..', '..')
    
    # Prefer .env mounted at /app/.env inside the container
    env_path = '/app/.env'
    if not os.path.exists(env_path):
        # Fallback to local root .env for non-docker runs
        env_path = os.path.join(root_dir, '.env')
    
    # Debug: Print the calculated path
    print(f"Loading .env from: {env_path}")
    print(f"File exists: {os.path.exists(env_path)}")
    
    # Load the environment variables
    load_dotenv(env_path)
    
    return env_path 