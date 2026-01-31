# app.py
import streamlit as st
from auth import login_user
from db_utils import init_connection_pool

def display_login_form():
    """Displays the login form and handles login logic."""
    st.header("Login")
    with st.form("login_form"):
        username = st.text_input("Username (Login Code)")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if not username or not password:
                st.warning("Please enter both username and password.")
                return

            user_info = login_user(username, password)
            
            if user_info is not None:
                if isinstance(user_info, str) and user_info == "INACTIVE":
                    st.error("Your account is inactive. Please contact an administrator.")
                else:
                    st.success("Login successful!")
                    # Store user info in session state to persist login
                    st.session_state.logged_in = True
                    st.session_state.user_info = user_info
                    # Rerun the app to redirect to the dashboard
                    st.rerun()
            else:
                st.error("Invalid username or password.")

def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(layout="wide", page_title="Advanced Course Registration System")
    st.title("🎓 Advanced Course Registration System")

    # Initialize the database connection pool once
    init_connection_pool()

    # Check if user is logged in
    if not st.session_state.get("logged_in"):
        display_login_form()
    else:
        user = st.session_state.user_info
        st.sidebar.success(f"Welcome, {user['LOGIN_CODE']}!")
        st.sidebar.write(f"Role: **{user['ROLE']}**")

        # --- Role-based dashboard switching will go here ---
        from admin_dashboard import display_admin_dashboard

        from prof_dashboard import display_prof_dashboard

        from student_dashboard import display_student_dashboard

        if user['ROLE'] == 'ADMIN':
            display_admin_dashboard()
        elif user['ROLE'] == 'PROF':
            display_prof_dashboard()
        elif user['ROLE'] == 'STUDENT':
            display_student_dashboard()
        else:
            st.error("Unknown role. Access denied.")

        if st.sidebar.button("Logout"):
            # Clear session state to log out
            for key in list(st.session_state.keys()):
                if key not in ['db_pool']: # Don't clear the db pool
                    del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()