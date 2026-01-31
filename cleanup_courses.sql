-- cleanup_courses.sql
-- This script finds and deletes all courses that are not assigned to any professor.
-- It respects referential integrity by deleting records from dependent tables first.

SET ECHO ON;
SET FEEDBACK ON;

PROMPT -----------------------------------------------------------------
PROMPT Deleting dependent records for unassigned courses...
PROMPT -----------------------------------------------------------------

PROMPT - Deleting from ATTENDANCE...
DELETE FROM ATTENDANCE WHERE SEANCE_ID IN (SELECT SEANCE_ID FROM SEANCE WHERE COURSE_ID NOT IN (SELECT COURSE_ID FROM PROF_COURSE));

PROMPT - Deleting from SEANCE...
DELETE FROM SEANCE WHERE COURSE_ID NOT IN (SELECT COURSE_ID FROM PROF_COURSE);

PROMPT - Deleting from COURSE_RESULT...
DELETE FROM COURSE_RESULT WHERE COURSE_ID NOT IN (SELECT COURSE_ID FROM PROF_COURSE);

PROMPT - Deleting from INSCRIPTION_REQUEST...
DELETE FROM INSCRIPTION_REQUEST WHERE COURSE_ID NOT IN (SELECT COURSE_ID FROM PROF_COURSE);

PROMPT - Deleting from COURSE_PREREQUISITE (as main course)...
DELETE FROM COURSE_PREREQUISITE WHERE COURSE_ID NOT IN (SELECT COURSE_ID FROM PROF_COURSE);

PROMPT - Deleting from COURSE_PREREQUISITE (as prerequisite)...
DELETE FROM COURSE_PREREQUISITE WHERE PREREQUISITE_COURSE_ID NOT IN (SELECT COURSE_ID FROM PROF_COURSE);


PROMPT -----------------------------------------------------------------
PROMPT Deleting unassigned courses from the COURSE table...
PROMPT -----------------------------------------------------------------
DELETE FROM COURSE WHERE COURSE_ID NOT IN (SELECT COURSE_ID FROM PROF_COURSE);


PROMPT -----------------------------------------------------------------
PROMPT Committing changes...
PROMPT -----------------------------------------------------------------
COMMIT;

PROMPT Cleanup complete.
SPOOL OFF;
