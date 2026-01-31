import oracledb
import os
import sys

# --- Connection Details ---
# It's recommended to use environment variables, but we'll use defaults for this script.
db_user = os.environ.get("DB_USER", "YAHYA_ADMIN")
# The password you used when running the script via docker exec
db_password = os.environ.get("DB_PASSWORD", "yahya_admin_password")  
db_host = os.environ.get("DB_HOST", "localhost")
db_port = os.environ.get("DB_PORT", "1521")
# This is the default service name for Oracle 19c, might need changing
db_service = os.environ.get("DB_SERVICE", "ORCLCDB") 

# --- Main Script ---
print("--- Oracle Schema Verification Script ---")
connection = None
try:
    print(f"Attempting to connect to database: {db_host}:{db_port}/{db_service}")
    print(f"User: {db_user}")
    
    # Establish connection to the database
    connection = oracledb.connect(
        user=db_user,
        password=db_password,
        dsn=f"{db_host}:{db_port}/{db_service}"
    )
    print("\n✅ Connection successful!")

    cursor = connection.cursor()

    # --- 1. Verify Tables ---
    print("\n--- 1. Checking Tables ---")
    cursor.execute("SELECT table_name FROM user_tables ORDER BY table_name")
    tables = cursor.fetchall()
    if tables:
        print(f"Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
    else:
        print("❌ No tables found in the schema.")

    # --- 2. Verify Views ---
    print("\n--- 2. Checking Views ---")
    cursor.execute("SELECT view_name FROM user_views ORDER BY view_name")
    views = cursor.fetchall()
    if views:
        print(f"Found {len(views)} views:")
        for view in views:
            print(f"  - {view[0]}")
    else:
        print("❌ No views found in the schema.")

    # --- 3. Verify Procedures and Functions ---
    print("\n--- 3. Checking Procedures & Functions ---")
    cursor.execute("""
        SELECT object_name, object_type, status
        FROM user_objects 
        WHERE object_type IN ('PROCEDURE', 'FUNCTION') 
        ORDER BY object_type, object_name
    """)
    procs_funcs = cursor.fetchall()
    if procs_funcs:
        print(f"Found {len(procs_funcs)} procedures and functions:")
        for obj in procs_funcs:
            # A status of 'INVALID' means the object exists but has errors
            status_icon = "✅" if obj[2] == "VALID" else "❌"
            print(f"  {status_icon} {obj[1]}: {obj[0]} (Status: {obj[2]})")
    else:
        print("❌ No procedures or functions found in the schema.")
        
    # --- 4. Verify Triggers ---
    print("\n--- 4. Checking Triggers ---")
    cursor.execute("SELECT trigger_name, status FROM user_triggers ORDER BY trigger_name")
    triggers = cursor.fetchall()
    if triggers:
        print(f"Found {len(triggers)} triggers:")
        for trigger in triggers:
            status_icon = "✅" if trigger[1] == "ENABLED" else "❌"
            print(f"  {status_icon} TRIGGER: {trigger[0]} (Status: {trigger[1]})")
    else:
        print("❌ No triggers found in the schema.")

    print("\n✅ Schema verification completed successfully.")

except Exception as e:
    print(f"\n❌ ERROR: An error occurred during verification.")
    print(f"Details: {e}")
    print("\n--- Troubleshooting ---")
    print("1. Is the Oracle database container running?")
    print("2. Are the connection details in the script correct (especially password and service name)?")
    print("3. Is the Python 'oracledb' package installed? If not, I will install it now.")
    print("4. Is the database listener running and the Pluggable Database (PDB) open?")
    # Exit with a non-zero code to indicate failure
    sys.exit(1)

finally:
    if connection:
        connection.close()
        print("\nConnection closed.")

print("\n--- Verification Complete ---")
