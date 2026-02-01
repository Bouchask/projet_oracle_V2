# config.py

# =================================================================
# Oracle Connection Details
# =================================================================

# This DSN (Data Source Name) is the address of your Oracle database.
ORACLE_DSN = "localhost:1521/ORCLCDB"

# =================================================================
# Application User Credentials
# =================================================================
# This dictionary maps application roles to the specific, low-privilege
# database users created in security.sql.
#
# The application will dynamically choose which user to connect as
# based on the logged-in user's role.
# =================================================================

APP_USERS = {
    # The AUTH user can ONLY read the user_account table to verify passwords.
    "AUTH": {
        "user": "app_auth", 
        "pass": "auth_password"
    },
    
    # The STUDENT user has read-only access to its own data and can make
    # new inscription requests.
    "STUDENT": {
        "user": "app_student",
        "pass": "student_password"
    },

    # The PROF user can manage courses, attendance, and grades for the
    # courses they are assigned to.
    "PROF": {
        "user": "app_prof",
        "pass": "prof_password"
    },

    # The ADMIN user has full control over the schema to perform
    # administrative tasks.
    "ADMIN": {
        "user": "app_admin",
        "pass": "admin_password"
    }
}

# The YAHYA_ADMIN user is now considered the "schema owner" and should
# only be used for database maintenance (like running db.sql or security.sql),
# not for running the application itself.
SCHEMA_OWNER_USER = "YAHYA_ADMIN"
SCHEMA_OWNER_PASSWORD = "yahya_admin_password"