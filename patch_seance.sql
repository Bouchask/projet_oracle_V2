-- patch_seance.sql
-- This script safely adds the ROOM column to the SEANCE table
-- and updates the necessary triggers for overlap validation.

SET SERVEROUTPUT ON;

-- Add ROOM column to SEANCE table if it doesn't exist
DECLARE
  v_column_exists NUMBER;
BEGIN
  SELECT COUNT(*)
  INTO v_column_exists
  FROM user_tab_cols
  WHERE table_name = 'SEANCE' AND column_name = 'ROOM';

  IF v_column_exists = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE SEANCE ADD (ROOM VARCHAR2(50))';
    DBMS_OUTPUT.PUT_LINE('✅ Column ROOM added to SEANCE table.');
  ELSE
    DBMS_OUTPUT.PUT_LINE('ℹ️ Column ROOM already exists in SEANCE table. No action taken.');
  END IF;
END;
/

-- Drop the old trigger if it exists
BEGIN
   EXECUTE IMMEDIATE 'DROP TRIGGER trg_prof_seance_time_conflict';
   DBMS_OUTPUT.PUT_LINE('✅ Trigger trg_prof_seance_time_conflict dropped.');
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE = -4080 THEN
         DBMS_OUTPUT.PUT_LINE('ℹ️ Trigger trg_prof_seance_time_conflict did not exist. No action taken.');
      ELSE
         RAISE;
      END IF;
END;
/

-- Create or replace the new, more comprehensive overlap trigger
CREATE OR REPLACE TRIGGER trg_check_seance_overlap
BEFORE INSERT OR UPDATE ON seance
FOR EACH ROW
DECLARE
    v_prof_conflict   NUMBER;
    v_room_conflict   NUMBER;
    v_prof_id         NUMBER;
BEGIN
    -- Find the professor for the course of the new seance
    BEGIN
        SELECT prof_id INTO v_prof_id
        FROM prof_course
        WHERE course_id = :NEW.course_id
        AND ROWNUM = 1;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            v_prof_id := NULL;
    END;
    
    -- Check for professor overlap if a professor is assigned
    IF v_prof_id IS NOT NULL THEN
        SELECT COUNT(*)
        INTO v_prof_conflict
        FROM seance s
        JOIN prof_course pc ON s.course_id = pc.course_id
        WHERE pc.prof_id = v_prof_id
          AND s.seance_date = :NEW.seance_date
          AND s.seance_id != NVL(:NEW.seance_id, -1) -- Exclude self in case of an update
          AND (:NEW.start_time < s.end_time AND :NEW.end_time > s.start_time);
          
        IF v_prof_conflict > 0 THEN
            RAISE_APPLICATION_ERROR(-20010, 'Professor has a time conflict with another session.');
        END IF;
    END IF;

    -- Check for room overlap
    IF :NEW.room IS NOT NULL THEN
        SELECT COUNT(*)
        INTO v_room_conflict
        FROM seance s
        WHERE s.room = :NEW.room
          AND s.seance_date = :NEW.seance_date
          AND s.seance_id != NVL(:NEW.seance_id, -1) -- Exclude self in case of an update
          AND (:NEW.start_time < s.end_time AND :NEW.end_time > s.start_time);

        IF v_room_conflict > 0 THEN
            RAISE_APPLICATION_ERROR(-20011, 'Room is already booked for an overlapping time slot on this day.');
        END IF;
    END IF;
END;
/

PROMPT ✅ Database patch applied successfully.

COMMIT;
