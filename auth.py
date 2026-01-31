# auth.py
import pandas as pd
from db_utils import execute_query

def login_user(username, password):
    """
    Validates user credentials against the USER_ACCOUNT table.
    
    NOTE: The schema defines a 'PASSWORD_HASH' column but provides no hashing mechanism.
    This function will treat it as a plain-text password for now, which is not secure
    for a production environment.
    
    Args:
        username (str): The user's login code.
        password (str): The user's password.
        
    Returns:
        A pandas Series object with user info (USER_ID, LOGIN_CODE, ROLE, STATUS) if login is successful,
        otherwise returns None.
    """
    # Important: Use query parameters to prevent SQL injection
    query = "SELECT USER_ID, LOGIN_CODE, ROLE, STATUS FROM USER_ACCOUNT WHERE LOGIN_CODE = :1 AND PASSWORD_HASH = :2"
    params = [username.upper(), password] # Assuming login_code is stored in uppercase
    
    result_df = execute_query(query, params)
    
    if not result_df.empty:
        # Check if account is active
        if result_df.iloc[0]['STATUS'] == 'ACTIVE':
            return result_df.iloc[0] # Return the first row (user data)
        else:
            return "INACTIVE" # Special case for inactive accounts
    
    return None
