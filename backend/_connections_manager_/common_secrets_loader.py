import os
from typing import Optional

def get_env_var(var_name: str, required: bool = True, default: Optional[str] = None) -> str:
    """
    Retrieves an environment variable from os.environ.

    Args:
        var_name (str): The name of the environment variable.
        required (bool): If True, raises ValueError if the variable is not set.
                         Default is True.
        default (str, optional): A default value to return if the variable is not set
                                 and `required` is False.

    Returns:
        str: The value of the environment variable.

    Raises:
        ValueError: If `required` is True and the variable is not set.
    """ 
    try:
        value = os.getenv(var_name)
        if required and (value is None or value == ""): # Check for None or empty string     
            raise ValueError(f"Required environment variable '{var_name}' is not set or is empty.")
    except Exception as e:
        print((f"Error: {e}"))
        raise Exception(e)

    return value 

