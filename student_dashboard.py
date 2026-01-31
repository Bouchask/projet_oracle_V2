# student_dashboard.py
import streamlit as st
import pandas as pd
from db_utils import call_function_ref_cursor, execute_query

def get_student_id(login_code):
    """Helper function to get student_id from login_code."""
    if 'student_id' not in st.session_state:
        student_df = execute_query("SELECT STUDENT_ID FROM STUDENT WHERE CODE_APOGE = :1", params=[login_code])
        if not student_df.empty:
            st.session_state.student_id = student_df.iloc[0]['STUDENT_ID']
        else:
            st.error("Could not identify student. Please contact an administrator.")
            return None
    return st.session_state.student_id

def display_my_courses(student_id):
    """Fetches and displays the student's current courses."""
    st.subheader("📖 My Courses")
    courses_df = call_function_ref_cursor("fn_student_courses", params=[int(student_id)])
    if not courses_df.empty:
        # Improve display of status
        def style_status(status):
            if status == 'VALID':
                return 'background-color: #28a745; color: white'
            elif status == 'FAILED':
                return 'background-color: #dc3545; color: white'
            elif status == 'IN_PROGRESS':
                return 'background-color: #ffc107; color: black'
            return ''
        
        st.dataframe(
            courses_df.style.applymap(style_status, subset=['COURSE_STATUS']),
            use_container_width=True
        )
    else:
        st.info("You are not enrolled in any courses for the current semester.")

from db_utils import call_function_ref_cursor, execute_query, execute_dml

def get_student_id(login_code):
    """Helper function to get student_id from login_code."""
    # Use a key in session state that is unique to the student context
    if 'student_id' not in st.session_state or st.session_state.get('login_code') != login_code:
        student_df = execute_query("SELECT STUDENT_ID FROM STUDENT WHERE CODE_APOGE = :1", params=[login_code])
        if not student_df.empty:
            st.session_state.student_id = student_df.iloc[0]['STUDENT_ID']
            st.session_state.login_code = login_code # store current user
        else:
            st.error("Could not identify student. Please contact an administrator.")
            return None
    return st.session_state.student_id

def display_my_courses(student_id):
    """Fetches and displays the student's current courses."""
    st.subheader("📖 My Courses")
    courses_df = call_function_ref_cursor("fn_student_courses", params=[int(student_id)])
    if not courses_df.empty:
        def style_status(status):
            if status == 'VALID': return 'background-color: #28a745; color: white'
            elif status == 'FAILED': return 'background-color: #dc3545; color: white'
            elif status == 'IN_PROGRESS': return 'background-color: #ffc107; color: black'
            return ''
        st.dataframe(courses_df.style.apply(lambda x: x.map(style_status), subset=['COURSE_STATUS']), use_container_width=True)
    else:
        st.info("You are not enrolled in any courses for the current semester.")

def display_my_schedule(student_id):
    """Fetches and displays the student's weekly schedule."""
    st.subheader("🗓️ My Weekly Schedule")
    schedule_df = call_function_ref_cursor("fn_student_seances", params=[int(student_id)])
    if not schedule_df.empty:
        try:
            schedule_df['SEANCE_DATE'] = pd.to_datetime(schedule_df['SEANCE_DATE']).dt.date
            schedule_df['START_TIME'] = pd.to_datetime(schedule_df['START_TIME']).dt.strftime('%H:%M')
            schedule_df['END_TIME'] = pd.to_datetime(schedule_df['END_TIME']).dt.strftime('%H:%M')
            schedule_df['SESSION_INFO'] = schedule_df['COURSE_NAME'] + ' (' + schedule_df['TYPE'] + ')'
            
            st.write("Upcoming sessions:")
            for date, group in schedule_df.groupby('SEANCE_DATE'):
                st.markdown(f"**{date}** ({pd.to_datetime(date).day_name()})")
                for _, row in group.sort_values(by="START_TIME").iterrows():
                    st.markdown(f"- **{row['SESSION_INFO']}**: {row['START_TIME']} - {row['END_TIME']} (Status: *{row['STATUS']}*)")
        except Exception:
            st.dataframe(schedule_df, use_container_width=True)
    else:
        st.info("You have no scheduled sessions.")

def display_missing_prerequisites(student_id):
    """Shows courses the student cannot enroll in due to missing prerequisites."""
    st.subheader("❗ Missing Prerequisites")
    prereq_df = execute_query("SELECT BLOCKED_COURSE, MISSING_PREREQUISITE FROM V_STUDENT_PREREQUISITE_MISSING WHERE STUDENT_ID = :1", params=[int(student_id)])
    if not prereq_df.empty:
        st.warning("You cannot register for the following courses because you are missing prerequisites:")
        st.dataframe(prereq_df, use_container_width=True)
    else:
        st.success("You have all the necessary prerequisites for courses in your semester!")

def display_course_registration(student_id):
    """Lists available courses and allows the student to register."""
    st.subheader("✏️ Register for a New Course")

    # Get all courses for the student's semester that they haven't already requested or are enrolled in
    available_courses_query = """
        SELECT c.COURSE_ID, c.NAME, c.CAPACITY
        FROM COURSE c
        JOIN STUDENT s ON c.SEMESTRE_ID = s.CURRENT_SEMESTRE_ID
        WHERE s.STUDENT_ID = :1
        AND NOT EXISTS (
            SELECT 1 FROM INSCRIPTION_REQUEST ir WHERE ir.STUDENT_ID = s.STUDENT_ID AND ir.COURSE_ID = c.COURSE_ID
        )
        AND NOT EXISTS (
            SELECT 1 FROM COURSE_RESULT cr WHERE cr.STUDENT_ID = s.STUDENT_ID AND cr.COURSE_ID = c.COURSE_ID
        )
    """
    available_courses_df = execute_query(available_courses_query, params=[int(student_id)])

    if available_courses_df.empty:
        st.info("No new courses available for registration at this time.")
        return
        
    st.write("Click 'Register' to request enrollment in a course.")
    for _, course in available_courses_df.iterrows():
        cols = st.columns([4, 1])
        cols[0].markdown(f"**{course['NAME']}** (Capacity: {course['CAPACITY']})")
        if cols[1].button("Register", key=f"register_{course['COURSE_ID']}"):
            dml = "INSERT INTO INSCRIPTION_REQUEST (STUDENT_ID, COURSE_ID) VALUES (:1, :2)"
            success, message = execute_dml(dml, params=[int(student_id), int(course['COURSE_ID'])])
            if success:
                st.success(f"Successfully sent registration request for {course['NAME']}.")
                st.rerun()
            else:
                st.error(f"Registration failed: {message}")
        st.divider()


def display_student_dashboard():
    """Main function to display the student dashboard."""
    st.header("🧑‍🎓 Student Dashboard")
    
    student_user = st.session_state.user_info
    student_id = get_student_id(student_user['LOGIN_CODE'])

    if student_id:
        tab1, tab2, tab3, tab4 = st.tabs(["My Courses", "My Schedule", "Register for Courses", "Prerequisites"])
        
        with tab1:
            display_my_courses(student_id)
        with tab2:
            display_my_schedule(student_id)
        with tab3:
            display_course_registration(student_id)
        with tab4:
            display_missing_prerequisites(student_id)

