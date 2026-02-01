# student_dashboard.py
import streamlit as st
import pandas as pd
from db_utils import execute_query, execute_dml

# --- Helper Functions ---
def get_student_details(login_code):
    """Fetches comprehensive student details and caches them."""
    if 'student_details' not in st.session_state or st.session_state.student_details.get('CODE_APOGE') != login_code:
        query = """
            SELECT 
                s.STUDENT_ID, 
                s.FULL_NAME, 
                s.CODE_APOGE, 
                f.NAME as FILIERE_NAME, 
                sem.CODE as SEMESTRE_CODE,
                s.CURRENT_SEMESTRE_ID
            FROM STUDENT s
            JOIN FILIERE f ON s.FILIERE_ID = f.FILIERE_ID
            JOIN SEMESTRE sem ON s.CURRENT_SEMESTRE_ID = sem.SEMESTRE_ID
            WHERE s.CODE_APOGE = :1
        """
        student_df = execute_query(query, [login_code])
        if not student_df.empty:
            st.session_state.student_details = student_df.iloc[0]
        else:
            return None
    return st.session_state.student_details

# --- UI Components for Tabs ---

def display_dashboard_home(student):
    """Displays the main dashboard with a profile card and summary."""
    st.subheader("🎓 My Dashboard")

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"### {student['FULL_NAME']}")
            st.write(f"**Code Apogée:** {student['CODE_APOGE']}")
            st.write(f"**Filière:** {student['FILIERE_NAME']}")
            st.write(f"**Current Semester:** {student['SEMESTRE_CODE']}")
        
        with col2:
            # Performance Summary
            blocked_df = execute_query("SELECT COUNT(*) as COUNT FROM V_STUDENT_BLOCKED_COURSES WHERE STUDENT_ID = :1", [int(student['STUDENT_ID'])])
            absences_df = execute_query("SELECT SUM(ABSENCES) as TOTAL FROM V_STUDENT_ABSENCE_STATS WHERE STUDENT_ID = :1", [int(student['STUDENT_ID'])])
            
            blocked_count = blocked_df.iloc[0]['COUNT'] if not blocked_df.empty else 0
            total_absences = absences_df.iloc[0]['TOTAL'] if not absences_df.empty and pd.notna(absences_df.iloc[0]['TOTAL']) else 0
            
            st.metric("Courses Blocked", f"{blocked_count}", delta_color="inverse")
            st.metric("Total Absences Recorded", f"{int(total_absences)}")

    if blocked_count > 0:
        st.error("⚠️ **Alert:** You are blocked in one or more courses. Please check the 'Performance' tab for details.")

def display_courses_and_registration(student):
    """Handles course registration and viewing detailed course info."""
    st.subheader("📚 My Courses & Registration")

    # --- 1. My Accepted Courses ---
    st.markdown("#### My Enrolled Courses")
    my_courses_df = execute_query("SELECT COURSE_ID, COURSE_NAME FROM V_STUDENT_CURRENT_COURSES WHERE STUDENT_ID = :1", [int(student['STUDENT_ID'])])

    if not my_courses_df.empty:
        selected_course_name = st.selectbox("Select a course to see details:", my_courses_df['COURSE_NAME'].tolist())
        
        if selected_course_name:
            # --- 2. Detailed Course & Faculty Info ---
            course_id = my_courses_df[my_courses_df['COURSE_NAME'] == selected_course_name].iloc[0]['COURSE_ID']
            course_details_df = execute_query("SELECT * FROM V_DETAIL_COURSE WHERE COURSE_ID = :1", [int(course_id)])
            
            if not course_details_df.empty:
                details = course_details_df.iloc[0]
                with st.container(border=True):
                    st.markdown(f"**Professor:** {details['PROF_NAME'] if pd.notna(details['PROF_NAME']) else 'Not Assigned'}")
                    # Fetch Department from Filiere
                    dept_df = execute_query("SELECT d.NAME FROM DEPARTEMENT d JOIN FILIERE f ON d.DEPARTEMENT_ID = f.DEPARTEMENT_ID WHERE f.NAME = :1", [details['FILIERE']])
                    st.markdown(f"**Department:** {dept_df.iloc[0]['NAME'] if not dept_df.empty else 'N/A'}")
    else:
        st.info("You are not enrolled in any courses yet.")
        
    # --- 3. Academic Registration (Course Enrollment) ---
    with st.expander("Register for New Courses"):
        # Find courses in the student's current semester that they have not yet requested
        available_courses_query = """
            SELECT c.COURSE_ID, c.NAME
            FROM COURSE c
            WHERE c.SEMESTRE_ID = :1 AND c.COURSE_ID NOT IN (
                SELECT ir.COURSE_ID FROM INSCRIPTION_REQUEST ir WHERE ir.STUDENT_ID = :2
            )
        """
        available_courses_df = execute_query(available_courses_query, [int(student['CURRENT_SEMESTRE_ID']), int(student['STUDENT_ID'])])
        
        if not available_courses_df.empty:
            st.write("The following courses are available for your current semester:")
            for _, course in available_courses_df.iterrows():
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{course['NAME']}**")
                if col2.button("Request Enrollment", key=f"register_{course['COURSE_ID']}"):
                    success, msg = execute_dml(
                        "INSERT INTO INSCRIPTION_REQUEST (STUDENT_ID, COURSE_ID, STATUS) VALUES (:1, :2, 'PENDING')",
                        [int(student['STUDENT_ID']), int(course['COURSE_ID'])]
                    )
                    if success:
                        st.success(f"Enrollment request for '{course['NAME']}' sent successfully!")
                        st.rerun()
                    else:
                        st.error(f"Failed to send request: {msg}")
                st.divider()
        else:
            st.info("No new courses are available for registration at this time.")

    st.divider()

    # --- 4. My Enrollment Requests Status ---
    st.markdown("#### My Enrollment Requests Status")
    requests_df = execute_query("""
        SELECT 
            c.NAME AS "Course Name", 
            ir.STATUS, 
            TO_CHAR(ir.REQUEST_DATE, 'YYYY-MM-DD HH24:MI') AS "Request Date"
        FROM INSCRIPTION_REQUEST ir
        JOIN COURSE c ON ir.COURSE_ID = c.COURSE_ID
        WHERE ir.STUDENT_ID = :1
        ORDER BY ir.REQUEST_DATE DESC
    """, [int(student['STUDENT_ID'])])

    if not requests_df.empty:
        # Function to apply color styling
        def style_status(status):
            if status == 'ACCEPTED':
                return 'background-color: #28a745; color: white'
            elif status == 'REJECTED':
                return 'background-color: #dc3545; color: white'
            elif status == 'PENDING':
                return 'background-color: #ffc107; color: black'
            return ''

        st.dataframe(
            requests_df.style.apply(lambda col: col.map(style_status), subset=['STATUS']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("You have no active enrollment requests.")

def display_schedule(student):
    """Displays the student's personal schedule."""
    st.subheader("🗓️ My Schedule")
    
    # Query for all seances related to the student's accepted courses
    schedule_query = """
        SELECT 
            c.NAME as COURSE_NAME,
            se.TYPE,
            se.ROOM,
            se.SEANCE_DATE,
            TO_CHAR(se.START_TIME, 'HH24:MI') as START_TIME,
            TO_CHAR(se.END_TIME, 'HH24:MI') as END_TIME,
            p.FULL_NAME as PROF_NAME
        FROM SEANCE se
        JOIN COURSE c ON se.COURSE_ID = c.COURSE_ID
        JOIN INSCRIPTION_REQUEST ir ON ir.COURSE_ID = c.COURSE_ID
        LEFT JOIN PROF_COURSE pc ON pc.COURSE_ID = c.COURSE_ID
        LEFT JOIN PROF p ON p.PROF_ID = pc.PROF_ID
        WHERE ir.STUDENT_ID = :1 AND ir.STATUS = 'ACCEPTED'
        ORDER BY se.SEANCE_DATE, se.START_TIME
    """
    schedule_df = execute_query(schedule_query, [int(student['STUDENT_ID'])])

    if not schedule_df.empty:
        schedule_df['SEANCE_DATE'] = pd.to_datetime(schedule_df['SEANCE_DATE'])
        today = pd.to_datetime('today').normalize()
        
        upcoming_sessions = schedule_df[schedule_df['SEANCE_DATE'] >= today]
        past_sessions = schedule_df[schedule_df['SEANCE_DATE'] < today]

        st.markdown("#### Upcoming Sessions")
        if not upcoming_sessions.empty:
            st.dataframe(
                upcoming_sessions.rename(columns={
                    'COURSE_NAME': 'Course', 'TYPE': 'Type', 'ROOM': 'Room', 
                    'SEANCE_DATE': 'Date', 'START_TIME': 'Start', 'END_TIME': 'End', 'PROF_NAME': 'Professor'
                }),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No upcoming sessions found.")
        
    else:
        st.info("Your schedule is empty. Enroll in courses to see your schedule.")

def display_performance_and_profile(student):
    """Displays academic performance and profile settings."""
    st.subheader("👤 My Profile & Performance")

    # --- 1. Academic Performance & Warnings ---
    st.markdown("#### Academic Performance")
    
    # Blocked Status
    blocked_df = execute_query("SELECT COURSE_NAME FROM V_STUDENT_BLOCKED_COURSES WHERE STUDENT_ID = :1", [int(student['STUDENT_ID'])])
    if not blocked_df.empty:
        st.error(f"**Alert:** You are currently BLOCKED in the following course(s): **{', '.join(blocked_df['COURSE_NAME'])}**. You cannot continue until this is resolved.")

    # Absence Tracker
    absences_df = execute_query("SELECT COURSE_NAME, ABSENCES FROM V_STUDENT_ABSENCE_STATS WHERE STUDENT_ID = :1", [int(student['STUDENT_ID'])])
    if not absences_df.empty:
        st.write("**Absence Summary:**")
        for _, row in absences_df.iterrows():
            if row['ABSENCES'] >= 2:
                st.warning(f"**{row['COURSE_NAME']}:** {int(row['ABSENCES'])} absences. **Warning: You are close to being blocked.**")
            else:
                st.write(f"**{row['COURSE_NAME']}:** {int(row['ABSENCES'])} absences.")
    else:
        st.info("No absence records found.")
        
    st.divider()

    # --- 2. Security: Change Password ---
    with st.expander("🔑 Change Password"):
        with st.form("change_password_form"):
            new_pass = st.text_input("New Password", type="password")
            confirm_pass = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Update Password"):
                if not new_pass or not confirm_pass:
                    st.warning("Please fill both password fields.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match. Please try again.")
                else:
                    success, msg = execute_dml(
                        "UPDATE USER_ACCOUNT SET PASSWORD_HASH = :1 WHERE LOGIN_CODE = :2",
                        [new_pass, student['CODE_APOGE']]
                    )
                    if success:
                        st.success("Your password has been updated successfully!")
                    else:
                        st.error(f"Could not update password: {msg}")

# --- Main Function ---
def display_student_dashboard():
    """Main function to render the student dashboard."""
    
    login_code = st.session_state.user_info['LOGIN_CODE']
    student = get_student_details(login_code)

    if student is None:
        st.error("Could not retrieve student details. Please contact an administrator.")
        return

    st.title(f"👋 Welcome, {student['FULL_NAME'].split()[0]}!")

    # Define the dashboard tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Dashboard", 
        "My Courses & Registration", 
        "My Schedule", 
        "Performance & Profile"
    ])

    with tab1:
        display_dashboard_home(student)
    
    with tab2:
        display_courses_and_registration(student)
        
    with tab3:
        display_schedule(student)
        
    with tab4:
        display_performance_and_profile(student)