# prof_dashboard.py
import streamlit as st
import pandas as pd
from db_utils import execute_query, call_procedure

def get_prof_id(login_code):
    """Helper function to get prof_id from login_code."""
    if 'prof_id' not in st.session_state:
        prof_df = execute_query("SELECT PROF_ID FROM PROF WHERE CODE_APOGE = :1", params=[login_code])
        if not prof_df.empty:
            st.session_state.prof_id = prof_df.iloc[0]['PROF_ID']
        else:
            st.error("Could not identify professor. Please contact an administrator.")
            return None
    return st.session_state.prof_id

def display_assigned_courses(prof_id):
    """Fetches and displays courses assigned to the professor."""
    st.subheader("📚 My Assigned Courses")
    courses_df = execute_query("SELECT COURSE_NAME, FILIERE, SEMESTRE FROM V_PROF_COURSES WHERE PROF_ID = :1", params=[int(prof_id)])
    
    if not courses_df.empty:
        st.dataframe(courses_df, use_container_width=True)
    else:
        st.info("You are not currently assigned to any courses.")

def display_grade_submission(prof_id):
    """Provides a form for professors to submit grades for students in their courses."""
    st.subheader("📝 Submit Student Grades")

    # Get professor's courses to populate the first dropdown
    courses_df = execute_query("SELECT COURSE_NAME, COURSE_ID FROM V_PROF_COURSES WHERE PROF_ID = :1", params=[int(prof_id)])
    if courses_df.empty:
        st.info("You have no courses to submit grades for.")
        return

    # Create a mapping from name to id
    course_map = pd.Series(courses_df.COURSE_ID.values, index=courses_df.COURSE_NAME).to_dict()
    selected_course_name = st.selectbox("Select a Course", courses_df['COURSE_NAME'])
    
    if selected_course_name:
        course_id = course_map[selected_course_name]
        
        # Get students enrolled in the selected course
        students_df = execute_query("""
            SELECT STUDENT_ID, FULL_NAME 
            FROM V_PROF_STUDENTS_BY_COURSE 
            WHERE PROF_ID = :1 AND COURSE_ID = :2
            ORDER BY FULL_NAME
        """, params=[int(prof_id), int(course_id)])
        
        if students_df.empty:
            st.warning("No students found for this course.")
            return

        with st.form("grade_submission_form"):
            student_map = pd.Series(students_df.STUDENT_ID.values, index=students_df.FULL_NAME).to_dict()
            selected_student_name = st.selectbox("Select a Student", students_df['FULL_NAME'])
            grade = st.number_input("Enter Grade (0-20)", min_value=0.0, max_value=20.0, step=0.5, format="%.2f")
            
            submitted = st.form_submit_button("Submit Grade")

            if submitted:
                student_id = student_map[selected_student_name]
                # Params for: p_student_id, p_course_id, p_grade
                params = [int(student_id), int(course_id), float(grade)]
                
                success, message = call_procedure("sp_prof_submit_grade", params)
                
                if success:
                    st.success(f"Grade {grade} submitted for {selected_student_name}.")
                else:
                    st.error(f"Error submitting grade: {message}")


from db_utils import execute_query, call_procedure, call_function_ref_cursor, execute_dml

def display_attendance_management(prof_id):
    """UI for managing student attendance for a seance."""
    st.subheader("🗓️ Attendance Management")
    
    # Get professor's courses
    courses_df = execute_query("SELECT COURSE_NAME, COURSE_ID FROM V_PROF_COURSES WHERE PROF_ID = :1", params=[int(prof_id)])
    if courses_df.empty:
        return

    course_map = pd.Series(courses_df.COURSE_ID.values, index=courses_df.COURSE_NAME).to_dict()
    selected_course_name = st.selectbox("Select a Course for Attendance", courses_df['COURSE_NAME'], key="attendance_course")
    
    if selected_course_name:
        course_id = course_map[selected_course_name]
        
        # Get seances for the selected course
        seances_df = execute_query("""
            SELECT SEANCE_ID, TO_CHAR(SEANCE_DATE, 'YYYY-MM-DD') || ' (' || TYPE || ')' AS SEANCE_DISPLAY
            FROM V_PROF_SEANCES 
            WHERE PROF_ID = :1 AND COURSE_ID = :2 ORDER BY SEANCE_DATE DESC
        """, params=[int(prof_id), int(course_id)])
        
        if seances_df.empty:
            st.warning("No sessions (seances) found for this course.")
            return

        seance_map = pd.Series(seances_df.SEANCE_ID.values, index=seances_df.SEANCE_DISPLAY).to_dict()
        selected_seance_display = st.selectbox("Select a Session", seances_df['SEANCE_DISPLAY'], key="attendance_seance")

        if selected_seance_display:
            seance_id = seance_map[selected_seance_display]
            
            # Get students for the selected seance
            students_df = call_function_ref_cursor("fn_students_in_seance", params=[int(seance_id)])
            
            if students_df.empty:
                st.info("No students found for this session.")
                return

            st.write(f"**{len(students_df)} students in this session:**")
            
            # Possible statuses
            status_options = ['PLANNED', 'PRESENT', 'ABSENT', 'LATE', 'ABSENT AVEC JUSTIFICATION']

            for _, student in students_df.iterrows():
                cols = st.columns([3, 2, 1])
                cols[0].write(student['FULL_NAME'])
                
                # Find the index of the current status to set the default value of the selectbox
                try:
                    current_status_index = status_options.index(student['STATUS'])
                except ValueError:
                    current_status_index = 0 # Default to 'PLANNED' if status is unknown
                
                new_status = cols[1].selectbox(
                    "Status",
                    options=status_options,
                    index=current_status_index,
                    key=f"status_{seance_id}_{student['STUDENT_ID']}",
                    label_visibility="collapsed"
                )
                
                if cols[2].button("Update", key=f"update_{seance_id}_{student['STUDENT_ID']}"):
                    if new_status != student['STATUS']:
                        dml = "UPDATE ATTENDANCE SET STATUS = :1 WHERE SEANCE_ID = :2 AND STUDENT_ID = :3"
                        params = [new_status, int(seance_id), int(student['STUDENT_ID'])]
                        success, message = execute_dml(dml, params)
                        if success:
                            st.toast(f"Updated {student['FULL_NAME']} to {new_status}", icon="✅")
                            # A full rerun is needed to see the change reflected in the selectbox
                            st.rerun()
                        else:
                            st.error(f"Error updating {student['FULL_NAME']}: {message}")
                    else:
                        st.toast("Status is already set to this value.", icon="ℹ️")


def display_prof_dashboard():
    """Main function to display the professor dashboard."""
    st.header("🧑‍🏫 Professor Dashboard")
    
    prof_user = st.session_state.user_info
    prof_id = get_prof_id(prof_user['LOGIN_CODE'])

    if prof_id:
        display_assigned_courses(prof_id)
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            display_grade_submission(prof_id)
        with col2:
            display_attendance_management(prof_id)
