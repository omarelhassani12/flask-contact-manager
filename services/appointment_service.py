from database.db import get_connection
from datetime import datetime, timedelta


def generate_time_slots():
    """Generate 30-min slots from 08:00 to 18:00"""
    slots = []
    start = datetime.strptime("08:00", "%H:%M")
    end = datetime.strptime("18:00", "%H:%M")
    current = start
    while current < end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return slots


class AppointmentService:

    def get_booked_slots(self, date: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT time_slot FROM appointments WHERE date = ?", (date,))
        rows = cursor.fetchall()
        conn.close()
        return [r["time_slot"] for r in rows]

    def get_appointments_for_date(self, date: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.date, a.time_slot, a.title, a.notes,
                   a.reminder_email, a.reminder_sms, a.google_event_id,
                   c.id as contact_id, c.name as contact_name, c.phone, c.email
            FROM appointments a
            JOIN contacts c ON c.id = a.contact_id
            WHERE a.date = ?
            ORDER BY a.time_slot
        """, (date,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_all_appointments(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.date, a.time_slot, a.title, a.notes,
                   a.reminder_email, a.reminder_sms, a.google_event_id,
                   c.id as contact_id, c.name as contact_name, c.phone, c.email
            FROM appointments a
            JOIN contacts c ON c.id = a.contact_id
            ORDER BY a.date, a.time_slot
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def book_slot(self, contact_id, date, time_slot, title="", notes="",
                  reminder_email=False, reminder_sms=False):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM appointments WHERE date=? AND time_slot=?", (date, time_slot))
        if cursor.fetchone():
            conn.close()
            return False, "Ce créneau est déjà réservé.", None
        try:
            cursor.execute(
                """INSERT INTO appointments
                   (contact_id, date, time_slot, title, notes, reminder_email, reminder_sms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (contact_id, date, time_slot, title.strip(), notes.strip(),
                 1 if reminder_email else 0, 1 if reminder_sms else 0)
            )
            conn.commit()
            appt_id = cursor.lastrowid
            conn.close()
            return True, "Rendez-vous ajouté avec succès.", appt_id
        except Exception as e:
            conn.close()
            return False, str(e), None

    def cancel_appointment(self, appointment_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT google_event_id FROM appointments WHERE id=?", (appointment_id,))
        row = cursor.fetchone()
        google_event_id = row["google_event_id"] if row else ""
        cursor.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
        conn.commit()
        conn.close()
        return True, "Rendez-vous annulé.", google_event_id

    def get_booked_dates(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM appointments")
        rows = cursor.fetchall()
        conn.close()
        return [r["date"] for r in rows]

    def save_google_event_id(self, appt_id, event_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE appointments SET google_event_id=? WHERE id=?", (event_id, appt_id))
        conn.commit()
        conn.close()

    def get_appointment_by_id(self, appt_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.date, a.time_slot, a.title, a.notes,
                   a.reminder_email, a.reminder_sms, a.google_event_id,
                   c.id as contact_id, c.name as contact_name, c.phone, c.email
            FROM appointments a
            JOIN contacts c ON c.id = a.contact_id
            WHERE a.id = ?
        """, (appt_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
