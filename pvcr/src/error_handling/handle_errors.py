
import os
import logging
import sys


from typing import Any, Type, Dict,Optional
from pydriller import ModifiedFile, Git, Commit
from dotenv import load_dotenv

from cve_utils import cve
from configuration import script_setup as setup

logger = logging.getLogger(__name__)

### To-Do ### 
# incude detailed logs so that I know what hash, file , repo correlates with an error (when possible)



# Custom Exception Classes
class MissingEnvironmentVariableError(Exception):
    """Raised when a required environment variable is missing."""
    pass

class GlobalVariableNotInitializedError(Exception):
    """Raised when a global variable is not initialized."""
    pass

def get_global_variable(var_name: str, expected_type: Type[Any]) -> Any:
    """
    Safely retrieves a global variable and validates its type.

    :param var_name: The name of the global variable to retrieve.
    :param expected_type: The expected type of the variable.
    :return: The variable if found and of the correct type.
    :raises SystemExit: If the variable is missing or of the wrong type.
    """
    value: Any = globals().get(var_name)

    if value is None:
        logging.error(f"Global variable '{var_name}' is missing.")
        sys.exit(1)

    if not isinstance(value, expected_type):
        logging.error(f"Global variable '{var_name}' is not of type {expected_type.__name__}. Found type: {type(value).__name__}.")
        sys.exit(1)

    return value

def safe_dict_set(d: Dict[Any, Any], key: Any, value: Any) -> bool:
    """
    Safely sets a value for a given key in a dictionary, with error handling.
    
    :param d: The dictionary to update.
    :param key: The key to update.
    :param value: The value to assign to the key.
    """
    try:
        d[key] = value
    except TypeError as e:
        logging.error(f"Dictionary is not valid (TypeError): {e} --> dictionary {d}")
        return False
    except KeyError as e:
        logging.error(f"Error setting dictionary[{key}]: {e}")
        return False
    except Exception as e:  # Catch unexpected errors
        logging.error(f"Unexpected error when updating dictionary {d} with key [{key}]: {e}")
        return False
    
    return True

def safe_dict_get(d: Dict[Any, Any], key: Any) -> tuple[Any,bool]: # type: ignore
    """
    Safely retrieves a value for a given key in a dictionary, with error handling.
    
    :param d: The dictionary to query.
    :param key: The key to retrieve.
    
    :return: The value associated with the key if it exists, or None if an error occurs.
    """
    try:
        return (True,d[key])
    except KeyError as e:
        logging.error(f"Key '{key}' not found in dictionary: {e} --> dictionary {d}")
        return (False,None)  # Return None if the key is not found
    except TypeError as e:
        logging.error(f"Invalid dictionary or key type (TypeError): {e} --> dictionary {d}, key {key}")
        return (False,None)
    except Exception as e:  # Catch unexpected errors
        logging.error(f"Unexpected error when accessing dictionary {d} with key [{key}]: {e}")
        return (False,None)



def validate_modified_file(modified_file_obj: ModifiedFile) -> bool:
    """
    Validates the attributes of a PyDriller ModifiedFile object to ensure they have
    the expected types before processing. Logs errors instead of raising exceptions.

    Parameters:
        modified_file_obj (ModifiedFile): The PyDriller ModifiedFile object to validate.

    Returns:
        bool: True if validation passes, False if any error occurs.
    """
    # List of required attributes with their expected types
    required_attributes: dict = {
        'old_path': str,
        'diff_parsed': (str, dict, list)  # Allow string, dict, or list for diff_parsed
    }

    # Identify origin of error
    path: str = modified_file_obj.old_path

    # Validate required attributes and their types
    for attr, expected_type in required_attributes.items():
        
        if not hasattr(modified_file_obj, attr):
            logging.error(f"Missing required attribute '{attr}' in ModifiedFile object. --> {path} ")
            return False
        
        attribute_value: Any = getattr(modified_file_obj, attr)

        # Validate type
        if not isinstance(attribute_value, expected_type):
            logging.error(f"Invalid type for attribute '{attr}'. Expected {expected_type}, got {type(attribute_value)} --> {path}")
            return False

    return True

def git_repo_conversion(selected_repo: str) -> Optional[Git]: ## fix
    """
    Handles errors related to converting a repository path to a Git object.
    Logs the error and continues processing.
    
    Parameters:
        selected_repo (str): The repository path to convert.
        
    Returns:
        selected_git_repo_obj (Git): The Git object representing the selected repository or None if error occurs.
    """
    try:
        # Converting selected repo (path) to a Git object
        selected_git_repo_obj: Git = Git(selected_repo)
        return selected_git_repo_obj
    except FileNotFoundError as e:
        logging.error(f"Repository path '{selected_repo}' not found: {e}")
    except Exception as e:
        logging.critical(f"Unexpected error while converting repo path to Git object: {e}")
    
    # Return None if there was an error but continue execution
    return None

def fetch_commmit_obj(selected_git_repo_obj: Git, patch_commit_hash: str) -> Commit:
    """
    Handles errors related to fetching the commit object from the Git repository.
    Logs the error and continues processing.
    
    Parameters:
        selected_git_repo_obj (Git): The Git object representing the selected repository.
        patch_commit_hash (str): The commit hash to fetch.
        
    Returns:
        patch_commit_obj (Commit): The commit object or None if error occurs.
    """
    try:
        # Getting the commit object (patch) from the commit hash git object
        patch_commit_obj: Commit = selected_git_repo_obj.get_commit(patch_commit_hash)
        return patch_commit_obj
    except ValueError as e:
        logging.error(f"Invalid commit hash '{patch_commit_hash}': {e}")
    except Exception as e:
        logging.critical(f"Unexpected error while accessing commit with hash '{patch_commit_hash}': {e}")
    
    # Return None if there was an error but continue execution
    return None



def safe_get_env_vars(config: setup.SCRIPT_CONFIG, variables_to_check: list[str]) -> None:
    """
    General function to handle loading and checking of environment variables.
    
    Args:
    - cls: The class calling this function (for logging and setting class variables).
    - variables_to_check: A list of environment variable names to check.
    - missing_vars_error_class: Exception class to raise if environment variables are missing.
    
    Returns:
    - None: If successful, environment variables are set as class attributes.
    """

    basic_logger = config.get_basic_logger()

    try:
        load_dotenv()  # Load environment variables from .env file

        # Fetch and assign the environment variables to class variables
        for var in variables_to_check:
            setattr(config, var, os.getenv(var))

        # Check if essential environment variables were set
        missing_vars = [var for var in variables_to_check if not getattr(config, var, None)]
    
        if missing_vars:
            raise MissingEnvironmentVariableError(f"Missing environment variables: {', '.join(missing_vars)}")

    except MissingEnvironmentVariableError as e:
        
        basic_logger.error(f"Error: {e}")
        sys.exit(1)

    except Exception as e:
        
        
        basic_logger.error(f"Error loading environment variables or assigning class variables: {e}")
        sys.exit(1)

    basic_logger.info("Environment variables initialized successfully.")
