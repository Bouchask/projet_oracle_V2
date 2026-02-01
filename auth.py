# auth.py
import pandas as pd
from db_utils import execute_query
import streamlit as st

def login_user(username, password):
    """
    Validates user credentials against the USER_ACCOUNT table.
    This function uses the 'AUTH' role, which can only read USER_ACCOUNT.
    """
    # Temporarily set the role to AUTH for this specific operation
    # This ensures we use the app_auth user's connection pool
    original_role = st.session_state.get('user_info', {}).get('ROLE')
    if 'user_info' not in st.session_state:
        st.session_state.user_info = {}
    st.session_state.user_info['ROLE'] = 'AUTH'

    try:
        # The public synonym for USER_ACCOUNT will resolve to YAHYA_ADMIN.USER_ACCOUNT
        query = "SELECT USER_ID, LOGIN_CODE, ROLE, STATUS FROM USER_ACCOUNT WHERE LOGIN_CODE = :1 AND PASSWORD_HASH = :2"
        params = [username.upper(), password]
        result_df = execute_query(query, params)
    finally:
        # IMPORTANT: Restore the original role or remove it after the query
        if original_role:
            st.session_state.user_info['ROLE'] = original_role
        else:
            if 'user_info' in st.session_state and 'ROLE' in st.session_state.user_info:
                del st.session_state.user_info['ROLE']

    if not result_df.empty:
        user_data = result_df.iloc[0]
        if user_data['STATUS'] == 'ACTIVE':
            return user_data
        else:
            return "INACTIVE"
    
    return None
