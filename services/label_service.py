from database.db import get_connection


class LabelService:

    def get_all_labels(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, color FROM labels ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_label(self, name, color="#6366f1"):
        name = name.strip()
        if not name:
            return False, "Le nom de l'étiquette est requis."
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO labels (name, color) VALUES (?, ?)", (name, color))
            conn.commit()
            label_id = cursor.lastrowid
            conn.close()
            return True, "Étiquette créée.", label_id
        except Exception:
            conn.close()
            return False, "Cette étiquette existe déjà."

    def delete_label(self, label_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM labels WHERE id = ?", (label_id,))
        conn.commit()
        conn.close()
        return True, "Étiquette supprimée."

    def get_labels_for_contact(self, contact_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.id, l.name, l.color FROM labels l
            JOIN contact_labels cl ON cl.label_id = l.id
            WHERE cl.contact_id = ?
            ORDER BY l.name
        """, (contact_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def set_labels_for_contact(self, contact_id, label_ids):
        """Replace all labels for a contact with the given list."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contact_labels WHERE contact_id = ?", (contact_id,))
        for lid in label_ids:
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO contact_labels (contact_id, label_id) VALUES (?, ?)",
                    (contact_id, int(lid))
                )
            except Exception:
                pass
        conn.commit()
        conn.close()
        return True, "Étiquettes mises à jour."

    def get_contacts_by_label(self, label_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.email, c.phone, c.category
            FROM contacts c
            JOIN contact_labels cl ON cl.contact_id = c.id
            WHERE cl.label_id = ?
            ORDER BY c.name
        """, (label_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_all_labels_with_counts(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.id, l.name, l.color, COUNT(cl.contact_id) as contact_count
            FROM labels l
            LEFT JOIN contact_labels cl ON cl.label_id = l.id
            GROUP BY l.id
            ORDER BY l.name
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def set_contacts_for_label(self, label_id, contact_ids):
        """Replace all contacts assigned to this label with the given list."""
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contact_labels WHERE label_id = ?", (label_id,))
        for cid in contact_ids:
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO contact_labels (contact_id, label_id) VALUES (?, ?)",
                    (int(cid), label_id)
                )
            except Exception:
                pass
        conn.commit()
        conn.close()
        return True, "Contacts mis à jour."
