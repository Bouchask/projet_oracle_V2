import oracledb
from config import SCHEMA_OWNER_USER, SCHEMA_OWNER_PASSWORD, ORACLE_DSN
import sys

def clean_and_create_admin():
    """
    Connects to the database, deletes all data from all tables,
    and then creates a single admin user with login 'admin' and password 'admin'.
    """
    connection = None
    try:
        # Connect as the schema owner to have full permissions
        print(f"Connecting to the database as {SCHEMA_OWNER_USER}...")
        connection = oracledb.connect(user=SCHEMA_OWNER_USER, password=SCHEMA_OWNER_PASSWORD, dsn=ORACLE_DSN)
        cursor = connection.cursor()
        print("✅ Connection successful.")
    except Exception as e:
        print(f"❌ Database connection failed. Please check your config.py and ensure the database is running. Error: {e}", file=sys.stderr)
        sys.exit(1)

    # The order is critical to respect foreign key constraints.
    # Child tables must be cleared before parent tables.
    tables_to_clear = [
        'ATTENDANCE', 'UNBLOCK_REQUEST', 'COURSE_RESULT', 'INSCRIPTION_REQUEST',
        'STUDENT_SECTION', 'SEANCE', 'PROF_COURSE', 'COURSE_PREREQUISITE', 'COURSE', 
        'ADMIN', 'PROF', 'STUDENT', 'USER_ACCOUNT', 'SECTION', 'SEMESTRE', 
        'FILIERE', 'DEPARTEMENT', 'ACADEMIC_YEAR'
    ]

    print("\n--- Step 1: Deleting all data from tables ---")
    
    try:
        # Temporarily disable triggers to allow for clean deletion without side-effects
        print("Disabling triggers for all tables...")
        for table in tables_to_clear:
            try:
                cursor.execute(f"ALTER TABLE {table} DISABLE ALL TRIGGERS")
            except oracledb.DatabaseError as e:
                # Ignore errors if table doesn't exist (in case of partial schema)
                if "ORA-00942" not in str(e):
                    print(f"Warning: Could not disable triggers for {table}. It may not exist. Error: {e}")

        # Delete data from tables
        for table in tables_to_clear:
            try:
                print(f"  - Deleting data from {table}...")
                cursor.execute(f"DELETE FROM {table}")
            except oracledb.DatabaseError as e:
                if "ORA-00942" in str(e): # table or view does not exist
                    print(f"    -> Warning: Table {table} not found, skipping.")
                else:
                    raise # Re-raise other critical database errors

        print("✅ All tables have been cleared.")

        print("\n--- Step 2: Creating admin/admin user ---")
        
        # Insert into user_account first due to foreign key constraint
        cursor.execute(
            "INSERT INTO user_account (login_code, password_hash, role, status) VALUES (:1, :2, :3, :4)",
            ['admin', 'admin', 'ADMIN', 'ACTIVE']
        )
        print("  - Created user in USER_ACCOUNT table.")

        # Insert into admin table
        cursor.execute(
            "INSERT INTO admin (username, full_name) VALUES (:1, :2)",
            ['admin', 'Default Admin']
        )
        print("  - Created user in ADMIN table.")
        
        print("✅ Admin user 'admin'/'admin' created successfully.")
        
        # Commit all changes
        connection.commit()
        print("\nAll changes have been committed to the database.")

    except Exception as e:
        print(f"\n❌ An error occurred. Rolling back changes. Error: {e}", file=sys.stderr)
        if connection:
            connection.rollback()
    finally:
        # Re-enable triggers regardless of success or failure
        print("\nRe-enabling all triggers...")
        for table in tables_to_clear:
             try:
                cursor.execute(f"ALTER TABLE {table} ENABLE ALL TRIGGERS")
             except oracledb.DatabaseError:
                # Ignore errors if table or triggers don't exist
                pass

        # Close the connection
        if connection:
            cursor.close()
            connection.close()
            print("✅ Connection closed.")


if __name__ == "__main__":
    clean_and_create_admin()
