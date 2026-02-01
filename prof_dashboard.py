# prof_dashboard.py
import streamlit as st
import pandas as pd
from db_utils import execute_query, execute_dml, call_procedure, call_function_ref_cursor

# --- Helper Functions ---
def get_prof_id(login_code):
    """Fetches professor ID from login code and caches it."""
    if 'prof_id' not in st.session_state or st.session_state.get('login_code') != login_code:
        prof_df = execute_query("SELECT PROF_ID FROM PROF WHERE CODE_APOGE = :1", [login_code])
        if not prof_df.empty:
            st.session_state.prof_id = int(prof_df.iloc[0]['PROF_ID'])
            st.session_state.login_code = login_code
        else:
            st.error("Could not identify professor profile. Please contact an administrator.")
            return None
    return st.session_state.prof_id

# --- UI Components for Tabs ---

def display_course_overview(prof_id):
    """Tab for viewing course and student list details."""
    st.subheader("My Courses & Students")

    # Fetch professor's courses for the current academic year
    courses_query = """
        SELECT c.COURSE_ID, c.NAME FROM COURSE c
        JOIN PROF_COURSE pc ON c.COURSE_ID = pc.COURSE_ID
        JOIN SEMESTRE s ON c.SEMESTRE_ID = s.SEMESTRE_ID
        WHERE pc.PROF_ID = :1 AND s.YEAR_ID = (SELECT MAX(YEAR_ID) FROM ACADEMIC_YEAR)
    """
    courses_df = execute_query(courses_query, [prof_id])

    if not courses_df.empty:
        selected_course = st.selectbox("Select a course to view student enrollments:", courses_df['NAME'].tolist())
        
        if selected_course:
            course_id = int(courses_df[courses_df['NAME'] == selected_course].iloc[0]['COURSE_ID'])

            # Fetch enrolled students with their inscription status and request ID
            students_query = """
                SELECT s.STUDENT_ID, s.FULL_NAME, ir.STATUS as INSCRIPTION_STATUS, ir.REQUEST_ID
                FROM STUDENT s
                JOIN INSCRIPTION_REQUEST ir ON s.STUDENT_ID = ir.STUDENT_ID
                WHERE ir.COURSE_ID = :1 AND ir.STATUS IN ('PENDING', 'ACCEPTED')
            """
            students_df = execute_query(students_query, [course_id])
            
            # Fetch blocked students for this professor's courses
            blocked_students_df = execute_query("SELECT STUDENT_ID, COURSE_NAME FROM V_PROF_BLOCKED_STUDENTS WHERE PROF_ID = :1", [prof_id])

            if not students_df.empty:
                def get_academic_status(row):
                    is_blocked = blocked_students_df[
                        (blocked_students_df['STUDENT_ID'] == row['STUDENT_ID']) & 
                        (blocked_students_df['COURSE_NAME'] == selected_course)
                    ]
                    return "BLOCKED" if not is_blocked.empty else "OK"
                
                students_df['ACADEMIC_STATUS'] = students_df.apply(get_academic_status, axis=1)
                st.dataframe(students_df[['FULL_NAME', 'INSCRIPTION_STATUS', 'ACADEMIC_STATUS']], use_container_width=True)
            else:
                st.info("No students have requested enrollment for this course yet.")

            # --- Manage Pending Requests ---
            st.divider()
            st.markdown("#### Manage Pending Requests")
            pending_requests_df = students_df[students_df['INSCRIPTION_STATUS'] == 'PENDING']

            if not pending_requests_df.empty:
                for _, row in pending_requests_df.iterrows():
                    request_id = int(row['REQUEST_ID'])
                    student_name = row['FULL_NAME']
                    
                    col1, col2, col3 = st.columns([2, 1, 1])
                    col1.write(student_name)
                    
                    if col2.button("✅ Accept", key=f"accept_{request_id}"):
                        success, msg = execute_dml("UPDATE INSCRIPTION_REQUEST SET status = 'ACCEPTED' WHERE request_id = :1", [request_id])
                        if success:
                            st.success(f"Accepted {student_name}. They will now be added to session rosters.")
                            st.rerun()
                        else:
                            st.error(f"Could not accept {student_name}: {msg}")
                    
                    if col3.button("❌ Refuse", key=f"refuse_{request_id}"):
                        success, msg = execute_dml("UPDATE INSCRIPTION_REQUEST SET status = 'REJECTED' WHERE request_id = :1", [request_id])
                        if success:
                            st.warning(f"Refused enrollment for {student_name}.")
                            st.rerun()
                        else:
                            st.error(f"An error occurred: {msg}")
            else:
                st.info("There are no pending enrollment requests for this course.")
    else:
        st.info("You are not assigned to any courses for the current academic year.")

def display_attendance_management(prof_id):
    """Tab for managing student attendance."""
    st.subheader("Attendance Management")
    st.info("ℹ️ Note: The system will automatically block a student from a course after 3 recorded absences.", icon="ℹ️")

    # Select a course, then a seance
    seances_df = execute_query("SELECT SEANCE_ID, COURSE_NAME, TO_CHAR(SEANCE_DATE, 'YYYY-MM-DD') || ' (' || TYPE || ')' AS SEANCE_DISPLAY FROM V_PROF_SEANCES WHERE PROF_ID = :1 ORDER BY SEANCE_DATE DESC", [prof_id])

    if not seances_df.empty:
        seances_df['display'] = seances_df['COURSE_NAME'] + ' - ' + seances_df['SEANCE_DISPLAY']
        selected_seance_display = st.selectbox("Select a session to mark attendance:", seances_df['display'])
        
        seance_id = int(seances_df[seances_df['display'] == selected_seance_display].iloc[0]['SEANCE_ID'])

        # --- Fetch detailed session info for the card ---
        session_details_query = """
            SELECT
                f.NAME AS FILIERE_NAME,
                sec.NAME AS SECTION_NAME,
                se.ROOM,
                se.TYPE,
                TO_CHAR(se.START_TIME, 'HH24:MI') AS START_TIME,
                TO_CHAR(se.END_TIME, 'HH24:MI') AS END_TIME,
                se.SEANCE_DATE
            FROM SEANCE se
            JOIN COURSE c ON se.COURSE_ID = c.COURSE_ID
            JOIN SEMESTRE sm ON c.SEMESTRE_ID = sm.SEMESTRE_ID
            JOIN FILIERE f ON sm.FILIERE_ID = f.FILIERE_ID
            JOIN SECTION sec ON se.SECTION_ID = sec.SECTION_ID
            WHERE se.SEANCE_ID = :1
        """
        session_details_df = execute_query(session_details_query, [seance_id])

        if not session_details_df.empty:
            details = session_details_df.iloc[0]
            with st.container(border=True):
                st.markdown("#### Session Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Course:** {selected_seance_display.split(' - ')[0].split(' (')[0]}") # Extract course name from display
                    st.write(f"**Filière:** {details['FILIERE_NAME']}")
                    st.write(f"**Section:** {details['SECTION_NAME']}")
                with col2:
                    st.write(f"**Type:** {details['TYPE']}")
                    st.write(f"**Room:** {details['ROOM']}")
                    st.write(f"**Date:** {details['SEANCE_DATE'].strftime('%Y-%m-%d')}") # Format date
                    st.write(f"**Time:** {details['START_TIME']} - {details['END_TIME']}")
            st.markdown("---")
        
        # Get students for the selected seance
        students_in_seance_df = call_function_ref_cursor("fn_students_in_seance", [seance_id])

        if not students_in_seance_df.empty:
            st.write(f"**{len(students_in_seance_df)} students in this session:**")
            status_options = ['PLANNED', 'PRESENT', 'ABSENT', 'LATE', 'ABSENT AVEC JUSTIFICATION']

            for _, student in students_in_seance_df.iterrows():
                cols = st.columns([3, 2, 1])
                cols[0].write(student['FULL_NAME'])
                
                current_status_index = status_options.index(student['STATUS']) if student['STATUS'] in status_options else 0
                
                new_status = cols[1].selectbox(
                    "Status", options=status_options, index=current_status_index, 
                    key=f"status_{seance_id}_{student['STUDENT_ID']}", label_visibility="collapsed"
                )
                
                if cols[2].button("Update", key=f"update_{seance_id}_{student['STUDENT_ID']}"):
                    if new_status != student['STATUS']:
                        success, msg = execute_dml(
                            "UPDATE ATTENDANCE SET STATUS = :1 WHERE SEANCE_ID = :2 AND STUDENT_ID = :3",
                            [new_status, seance_id, int(student['STUDENT_ID'])]
                        )
                        if success:
                            st.toast(f"Updated {student['FULL_NAME']} to {new_status}", icon="✅")
                            st.rerun()
                        else:
                            st.error(f"Failed to update: {msg}")
        else:
            st.info("No students found for this session.")
    else:
        st.warning("You have no scheduled sessions.")

def display_grade_submission(prof_id):
    """Tab for submitting student grades."""
    st.subheader("Grade Submission")

    # Corrected: Select COURSE_NAME instead of NAME
    courses_df = execute_query("SELECT COURSE_ID, COURSE_NAME FROM V_PROF_COURSES WHERE PROF_ID = :1", [prof_id])
    if courses_df.empty:
        st.info("You have no courses to submit grades for.")
        return

    with st.form("grade_submission_form"):
        # Corrected: Use COURSE_NAME column
        selected_course_name = st.selectbox("Select a Course", courses_df['COURSE_NAME'].unique())
        # Corrected: Use COURSE_NAME column for filtering
        course_id = int(courses_df[courses_df['COURSE_NAME'] == selected_course_name].iloc[0]['COURSE_ID'])
        
        students_df = execute_query("SELECT STUDENT_ID, FULL_NAME FROM V_PROF_STUDENTS_BY_COURSE WHERE PROF_ID = :1 AND COURSE_ID = :2 ORDER BY FULL_NAME", [prof_id, course_id])
        
        if students_df.empty:
            st.warning("No students are enrolled in this course.")
            st.form_submit_button("Submit Grade", disabled=True)
            return

        selected_student_name = st.selectbox("Select a Student", students_df['FULL_NAME'])
        student_id = int(students_df[students_df['FULL_NAME'] == selected_student_name].iloc[0]['STUDENT_ID'])
        
        grade = st.number_input("Enter Grade (0-20)", min_value=0.0, max_value=20.0, step=0.5, format="%.2f")
        
        if st.form_submit_button("Submit Grade"):
            params = [student_id, course_id, float(grade)]
            success, message = call_procedure("sp_prof_submit_grade", params)
            
            if success:
                st.success(f"Grade {grade} submitted successfully for {selected_student_name}.")
            else:
                st.error(f"Error submitting grade: {message}")

def display_student_performance(prof_id):
    """Tab for viewing student performance stats."""
    st.subheader("Student Performance Analytics")
    
    st.markdown("#### Absence Summary")
    st.write("This table shows the total number of recorded absences for each student in your courses.")

    absence_query = """
        SELECT 
            s.FULL_NAME as "Student Name", 
            c.NAME as "Course", 
            COUNT(CASE WHEN a.STATUS = 'ABSENT' THEN 1 END) as "Absence Count"
        FROM ATTENDANCE a
        JOIN STUDENT s ON a.student_id = s.student_id
        JOIN SEANCE se ON a.seance_id = se.seance_id
        JOIN COURSE c ON se.course_id = c.course_id
        JOIN PROF_COURSE pc ON c.course_id = pc.course_id
        WHERE pc.prof_id = :1
        GROUP BY s.FULL_NAME, c.NAME
        HAVING COUNT(CASE WHEN a.STATUS = 'ABSENT' THEN 1 END) > 0
        ORDER BY "Absence Count" DESC, s.FULL_NAME
    """
    absence_stats_df = execute_query(absence_query, [prof_id])

    if not absence_stats_df.empty:
        st.dataframe(absence_stats_df, use_container_width=True, hide_index=True)
    else:
        st.info("No absences have been recorded for students in your courses.")

# --- Main Dashboard Function ---
def display_prof_dashboard():
    """Main function to display the professor dashboard."""
    
    login_code = st.session_state.user_info['LOGIN_CODE']
    prof_id = get_prof_id(login_code)

    if prof_id:
        st.title(f"🧑‍🏫 Professor Dashboard")

        tab1, tab2, tab3, tab4 = st.tabs([
            "My Courses", 
            "Attendance", 
            "Grading", 
            "Student Performance"
        ])

        with tab1:
            display_course_overview(prof_id)
        
        with tab2:
            display_attendance_management(prof_id)

        with tab3:
            display_grade_submission(prof_id)
            
        with tab4:
            display_student_performance(prof_id)