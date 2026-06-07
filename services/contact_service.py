import csv
import io
from database.db import get_connection

CATEGORIES = ["Patient", "Fournisseur", "Laboratoire", "Client", "Autre"]

class ContactService:

    def get_all_contacts(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, phone, category, address, fonction, company FROM contacts ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_contact_by_id(self, contact_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, phone, category, address, fonction, company FROM contacts WHERE id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def _check_duplicate(self, email, phone, exclude_id=None):
        """
        Returns (field, existing_name) if email or phone already exists,
        None if no duplicate found.
        exclude_id: skip this contact's own row (for updates).
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Check email
        if exclude_id:
            cursor.execute(
                "SELECT id, name FROM contacts WHERE LOWER(email) = LOWER(?) AND id != ?",
                (email.strip(), exclude_id)
            )
        else:
            cursor.execute(
                "SELECT id, name FROM contacts WHERE LOWER(email) = LOWER(?)",
                (email.strip(),)
            )
        row = cursor.fetchone()
        if row:
            conn.close()
            return "email", row["name"]

        # Check phone — normalize by stripping spaces/dashes for comparison
        norm_phone = phone.strip().replace(" ", "").replace("-", "")
        cursor.execute("SELECT id, name, phone FROM contacts" + (" WHERE id != ?" if exclude_id else ""),
                       (exclude_id,) if exclude_id else ())
        for r in cursor.fetchall():
            existing_norm = (r["phone"] or "").replace(" ", "").replace("-", "")
            if existing_norm == norm_phone:
                conn.close()
                return "téléphone", r["name"]

        conn.close()
        return None

    def add_contact(self, name, email, phone, category="", address="", fonction="", company=""):
        if not name or not email or not phone:
            return False, "Tous les champs obligatoires doivent être remplis."

        # Duplicate check
        dup = self._check_duplicate(email.strip(), phone.strip())
        if dup:
            field, existing_name = dup
            return False, f"Ce {field} existe déjà pour le contact « {existing_name} »."

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contacts (name, email, phone, category, address, fonction, company) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name.strip(), email.strip(), phone.strip(), category.strip(), address.strip(), fonction.strip(), company.strip())
        )
        conn.commit()
        self._last_id = cursor.lastrowid
        conn.close()
        return True, "Contact ajouté avec succès."

    def get_last_insert_id(self):
        return getattr(self, "_last_id", None)

    def update_contact(self, contact_id, name, email, phone, category="", address="", fonction="", company=""):
        if not name or not email or not phone:
            return False, "Tous les champs obligatoires doivent être remplis."

        # Duplicate check (exclude the contact being updated)
        dup = self._check_duplicate(email.strip(), phone.strip(), exclude_id=contact_id)
        if dup:
            field, existing_name = dup
            return False, f"Ce {field} existe déjà pour le contact « {existing_name} »."

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE contacts SET name = ?, email = ?, phone = ?, category = ?, address = ?, fonction = ?, company = ? WHERE id = ?",
            (name.strip(), email.strip(), phone.strip(), category.strip(), address.strip(), fonction.strip(), company.strip(), contact_id)
        )
        conn.commit()
        conn.close()
        return True, "Contact mis à jour avec succès."

    def delete_contact(self, contact_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
        conn.close()
        return True, "Contact supprimé avec succès."

    def search_contacts(self, query):
        query = query.strip().lower()
        all_contacts = self.get_all_contacts()
        return [
            c for c in all_contacts
            if query in c["name"].lower()
            or query in c["email"].lower()
            or query in c["phone"].lower()
            or query in (c["category"] or "").lower()
            or query in (c["company"] or "").lower()
            or query in (c["fonction"] or "").lower()
        ]

    def export_to_csv(self):
        contacts = self.get_all_contacts()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "Email", "Phone", "Category", "Company", "Function", "Address"])
        for c in contacts:
            writer.writerow([c["id"], c["name"], c["email"], c["phone"],
                             c.get("category",""), c.get("company",""), c.get("fonction",""), c.get("address","")])
        return output.getvalue()
