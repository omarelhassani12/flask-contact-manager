import bcrypt
from database.db import get_connection


class AdminService:

    def get_all_admins(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM admins ORDER BY username ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_admin(self, username, password):
        if not username or not password:
            return False, "Nom d'utilisateur et mot de passe requis."
        if len(password) < 6:
            return False, "Le mot de passe doit comporter au moins 6 caractères."

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM admins WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return False, f"L'utilisateur « {username} » existe déjà."

        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        conn.close()
        return True, f"Administrateur « {username} » ajouté avec succès."

    def delete_admin(self, admin_id, current_username):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM admins WHERE id = ?", (admin_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Administrateur introuvable."
        if row["username"] == current_username:
            conn.close()
            return False, "Vous ne pouvez pas supprimer votre propre compte."

        # Prevent deleting last admin
        cursor.execute("SELECT COUNT(*) FROM admins")
        count = cursor.fetchone()[0]
        if count <= 1:
            conn.close()
            return False, "Impossible de supprimer le dernier administrateur."

        cursor.execute("DELETE FROM admins WHERE id = ?", (admin_id,))
        conn.commit()
        conn.close()
        return True, f"Administrateur « {row['username']} » supprimé."
