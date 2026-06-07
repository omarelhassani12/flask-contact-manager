import sys
import os
import csv
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, Response, jsonify
)
from functools import wraps

from database.db import init_db
from auth.auth_manager import verify_login
from services.contact_service import ContactService, CATEGORIES
from services.admin_service import AdminService
from services.message_service import MessageService
from services.appointment_service import AppointmentService, generate_time_slots
from services.label_service import LabelService
from services.google_calendar_service import GoogleCalendarService

app = Flask(__name__)
app.secret_key = "change-me-in-production-super-secret"

service        = ContactService()
admin_service  = AdminService()
message_service= MessageService()
appt_service   = AppointmentService()
label_service  = LabelService()
gcal_service   = GoogleCalendarService()


# ──────────────────────────────────────────────
# Auth decorator
# ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────
# Auth routes
# ──────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("contacts"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if verify_login(username, password):
            session["logged_in"] = True
            session["username"] = username
            flash(f"Bienvenue, {username} !", "success")
            return redirect(url_for("contacts"))
        else:
            flash("Nom d'utilisateur ou mot de passe incorrect.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Vous avez été déconnecté.", "success")
    return redirect(url_for("login"))


# ──────────────────────────────────────────────
# Contacts routes
# ──────────────────────────────────────────────
@app.route("/contacts")
@login_required
def contacts():
    query      = request.args.get("q", "").strip()
    cat_filter = request.args.get("cat", "").strip()
    lbl_filter = request.args.get("lbl", "").strip()

    if query:
        contact_list = service.search_contacts(query)
    else:
        contact_list = service.get_all_contacts()

    if cat_filter:
        contact_list = [c for c in contact_list if c.get("category") == cat_filter]

    if lbl_filter:
        try:
            lbl_contacts = label_service.get_contacts_by_label(int(lbl_filter))
            lbl_ids = {c["id"] for c in lbl_contacts}
            contact_list = [c for c in contact_list if c["id"] in lbl_ids]
        except Exception:
            pass

    # Attach labels to each contact
    all_labels = label_service.get_all_labels()
    for c in contact_list:
        c["label_list"] = label_service.get_labels_for_contact(c["id"])

    return render_template("contacts.html",
                           contacts=contact_list, query=query,
                           categories=CATEGORIES, cat_filter=cat_filter,
                           all_labels=all_labels, lbl_filter=lbl_filter)


@app.route("/contacts/add", methods=["POST"])
@login_required
def add_contact():
    name     = request.form.get("name", "").strip()
    email    = request.form.get("email", "").strip()
    phone    = request.form.get("phone", "").strip()
    category = request.form.get("category", "").strip()
    address  = request.form.get("address", "").strip()
    fonction = request.form.get("fonction", "").strip()
    company  = request.form.get("company", "").strip()

    ok, msg = service.add_contact(name, email, phone, category, address, fonction, company)
    if ok:
        # Handle labels
        label_ids = request.form.getlist("label_ids")
        if label_ids:
            conn_id = service.get_last_insert_id()
            if conn_id:
                label_service.set_labels_for_contact(conn_id, label_ids)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("contacts"))


@app.route("/contacts/edit/<int:contact_id>", methods=["GET", "POST"])
@login_required
def edit_contact(contact_id):
    if request.method == "GET":
        contact = service.get_contact_by_id(contact_id)
        if not contact:
            return jsonify({"error": "Not found"}), 404
        contact["label_ids"] = [l["id"] for l in label_service.get_labels_for_contact(contact_id)]
        return jsonify(contact)

    name     = request.form.get("name", "").strip()
    email    = request.form.get("email", "").strip()
    phone    = request.form.get("phone", "").strip()
    category = request.form.get("category", "").strip()
    address  = request.form.get("address", "").strip()
    fonction = request.form.get("fonction", "").strip()
    company  = request.form.get("company", "").strip()

    ok, msg = service.update_contact(contact_id, name, email, phone, category, address, fonction, company)
    if ok:
        label_ids = request.form.getlist("label_ids")
        label_service.set_labels_for_contact(contact_id, label_ids)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("contacts"))


@app.route("/contacts/delete/<int:contact_id>", methods=["POST"])
@login_required
def delete_contact(contact_id):
    ok, msg = service.delete_contact(contact_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("contacts"))


@app.route("/contacts/export")
@login_required
def export_csv():
    csv_data = service.export_to_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts_export.csv"}
    )


@app.route("/contacts/import", methods=["POST"])
@login_required
def import_contacts():
    uploaded_file = request.files.get("import_file")
    if not uploaded_file or uploaded_file.filename == "":
        flash("Aucun fichier sélectionné.", "error")
        return redirect(url_for("contacts"))

    filename = uploaded_file.filename.lower()
    added = 0
    skipped_dup = 0
    errors = []

    try:
        if filename.endswith(".csv"):
            stream = io.StringIO(uploaded_file.stream.read().decode("utf-8-sig"))
            reader = csv.DictReader(stream)
            for i, row in enumerate(reader, start=2):
                row_norm = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                name  = row_norm.get("name") or row_norm.get("nom") or ""
                email = row_norm.get("email") or row_norm.get("e-mail") or ""
                phone = row_norm.get("phone") or row_norm.get("téléphone") or row_norm.get("telephone") or ""
                if name and email and phone:
                    ok, msg = service.add_contact(name, email, phone)
                    if ok:
                        added += 1
                    elif "existe déjà" in msg:
                        skipped_dup += 1
                    else:
                        errors.append(f"Ligne {i}: {msg}")
                else:
                    errors.append(f"Ligne {i}: données incomplètes")

        elif filename.endswith((".xlsx", ".xls")):
            import openpyxl
            wb = openpyxl.load_workbook(uploaded_file.stream, read_only=True)
            ws = wb.active
            headers = None
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0:
                    headers = [str(c).strip().lower() if c else "" for c in row]
                    continue
                if not any(row): continue
                row_dict = dict(zip(headers, row))
                name  = str(row_dict.get("name") or row_dict.get("nom") or "").strip()
                email = str(row_dict.get("email") or row_dict.get("e-mail") or "").strip()
                phone = str(row_dict.get("phone") or row_dict.get("téléphone") or row_dict.get("telephone") or "").strip()
                if name and email and phone and name != "None":
                    ok, msg = service.add_contact(name, email, phone)
                    if ok:
                        added += 1
                    elif "existe déjà" in msg:
                        skipped_dup += 1
                    else:
                        errors.append(f"Ligne {i+1}: {msg}")
                else:
                    errors.append(f"Ligne {i+1}: données incomplètes")
        else:
            flash("Format non supporté. Utilisez CSV ou Excel (.xlsx).", "error")
            return redirect(url_for("contacts"))

    except Exception as e:
        flash(f"Erreur lors de l'importation: {str(e)}", "error")
        return redirect(url_for("contacts"))

    if added:
        flash(f"{added} contact(s) importé(s) avec succès.", "success")
    if skipped_dup:
        flash(f"{skipped_dup} contact(s) ignoré(s) : email ou téléphone déjà existant.", "warning")
    if errors:
        flash(f"{len(errors)} ligne(s) en erreur : " + "; ".join(errors[:3]) + ("..." if len(errors) > 3 else ""), "error")

    return redirect(url_for("contacts"))


# ──────────────────────────────────────────────
# Print contact sheet (JSON for client-side print)
# ──────────────────────────────────────────────
@app.route("/contacts/print/<int:contact_id>")
@login_required
def print_contact(contact_id):
    contact = service.get_contact_by_id(contact_id)
    if not contact:
        return jsonify({"error": "Not found"}), 404
    contact["labels"] = label_service.get_labels_for_contact(contact_id)
    appointments = []
    for a in appt_service.get_all_appointments():
        if a["contact_id"] == contact_id:
            appointments.append(a)
    contact["appointments"] = appointments
    return jsonify(contact)


# ──────────────────────────────────────────────
# Labels / Groups routes
# ──────────────────────────────────────────────
@app.route("/labels")
@login_required
def labels():
    all_labels = label_service.get_all_labels_with_counts()
    return jsonify(all_labels)


@app.route("/labels/add", methods=["POST"])
@login_required
def add_label():
    data  = request.get_json() or {}
    name  = data.get("name", "").strip()
    color = data.get("color", "#6366f1").strip()
    ok, msg, label_id = label_service.add_label(name, color)
    if ok:
        return jsonify({"ok": True, "msg": msg, "id": label_id, "name": name, "color": color})
    return jsonify({"ok": False, "msg": msg}), 400


@app.route("/labels/delete/<int:label_id>", methods=["POST"])
@login_required
def delete_label(label_id):
    ok, msg = label_service.delete_label(label_id)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/labels/<int:label_id>/contacts")
@login_required
def get_label_contacts(label_id):
    """Return all contacts with a flag indicating if they're assigned to this label."""
    all_contacts = service.get_all_contacts()
    assigned_ids = {c["id"] for c in label_service.get_contacts_by_label(label_id)}
    result = [
        {
            "id":       c["id"],
            "name":     c["name"],
            "email":    c["email"],
            "assigned": c["id"] in assigned_ids
        }
        for c in all_contacts
    ]
    return jsonify(result)


@app.route("/labels/<int:label_id>/assign", methods=["POST"])
@login_required
def assign_contacts_to_label(label_id):
    """Set exactly which contacts are assigned to this label (replaces all)."""
    data        = request.get_json() or {}
    contact_ids = data.get("contact_ids", [])
    ok, msg     = label_service.set_contacts_for_label(label_id, contact_ids)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/contacts/<int:contact_id>/labels", methods=["POST"])
@login_required
def update_contact_labels(contact_id):
    data = request.get_json() or {}
    label_ids = data.get("label_ids", [])
    ok, msg = label_service.set_labels_for_contact(contact_id, label_ids)
    return jsonify({"ok": ok, "msg": msg})


# ──────────────────────────────────────────────
# ── API Documentation page ─────────────────────────────────
@app.route("/api-docs")
@login_required
def api_docs():
    base = request.host_url.rstrip('/')
    return render_template("api_docs.html", base_url=base)


# ── REST API endpoints (JSON) ──────────────────────────────
@app.route("/api/v1/contacts", methods=["GET"])
@login_required
def api_contacts():
    q   = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    data = service.search_contacts(q) if q else service.get_all_contacts()
    if cat:
        data = [c for c in data if c.get("category","").lower() == cat.lower()]
    return jsonify({"ok": True, "count": len(data), "contacts": data})

@app.route("/api/v1/contacts/<int:contact_id>", methods=["GET"])
@login_required
def api_contact_get(contact_id):
    c = service.get_contact_by_id(contact_id)
    if not c:
        return jsonify({"ok": False, "msg": "Contact introuvable."}), 404
    c["labels"] = label_service.get_labels_for_contact(contact_id)
    return jsonify({"ok": True, "contact": c})

@app.route("/api/v1/contacts", methods=["POST"])
@login_required
def api_contact_create():
    d    = request.get_json() or {}
    ok, msg = service.add_contact(
        d.get("name",""), d.get("email",""), d.get("phone",""),
        d.get("category",""), d.get("address",""), d.get("fonction",""), d.get("company","")
    )
    return jsonify({"ok": ok, "msg": msg}), (201 if ok else 400)

@app.route("/api/v1/contacts/<int:contact_id>", methods=["PUT"])
@login_required
def api_contact_update(contact_id):
    d = request.get_json() or {}
    ok, msg = service.update_contact(
        contact_id,
        d.get("name",""), d.get("email",""), d.get("phone",""),
        d.get("category",""), d.get("address",""), d.get("fonction",""), d.get("company","")
    )
    return jsonify({"ok": ok, "msg": msg}), (200 if ok else 400)

@app.route("/api/v1/contacts/<int:contact_id>", methods=["DELETE"])
@login_required
def api_contact_delete(contact_id):
    ok, msg = service.delete_contact(contact_id)
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/v1/appointments", methods=["GET"])
@login_required
def api_appointments():
    date = request.args.get("date","")
    if date:
        data = appt_service.get_appointments_for_date(date)
    else:
        data = appt_service.get_all_appointments()
    return jsonify({"ok": True, "count": len(data), "appointments": data})

@app.route("/api/v1/labels", methods=["GET"])
@login_required
def api_labels_list():
    return jsonify({"ok": True, "labels": label_service.get_all_labels_with_counts()})


# Admin management routes
# ──────────────────────────────────────────────
@app.route("/admins")
@login_required
def admins():
    admin_list = admin_service.get_all_admins()
    return render_template("admins.html", admins=admin_list, current_user=session.get("username"))


@app.route("/admins/add", methods=["POST"])
@login_required
def add_admin():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    ok, msg = admin_service.add_admin(username, password)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("admins"))


@app.route("/admins/delete/<int:admin_id>", methods=["POST"])
@login_required
def delete_admin(admin_id):
    current = session.get("username")
    ok, msg = admin_service.delete_admin(admin_id, current)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("admins"))


# ──────────────────────────────────────────────
# Messaging routes
# ──────────────────────────────────────────────
@app.route("/contacts/send-email/<int:contact_id>", methods=["POST"])
@login_required
def send_email(contact_id):
    contact = service.get_contact_by_id(contact_id)
    if not contact:
        return jsonify({"ok": False, "msg": "Contact introuvable."}), 404

    subject = request.form.get("subject", "").strip()
    body    = request.form.get("body", "").strip()

    if not subject or not body:
        return jsonify({"ok": False, "msg": "Objet et message requis."}), 400

    ok, msg = message_service.send_email(contact["email"], subject, body)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/contacts/whatsapp-url/<int:contact_id>")
@login_required
def whatsapp_url(contact_id):
    contact = service.get_contact_by_id(contact_id)
    if not contact:
        return jsonify({"ok": False, "msg": "Contact introuvable."}), 404

    message = request.args.get("message", "Bonjour !").strip()
    url = message_service.build_whatsapp_url(contact["phone"], message)
    return jsonify({"ok": True, "url": url})


@app.route("/contacts/send-whatsapp/<int:contact_id>", methods=["POST"])
@login_required
def send_whatsapp(contact_id):
    contact = service.get_contact_by_id(contact_id)
    if not contact:
        return jsonify({"ok": False, "msg": "Contact introuvable."}), 404

    message = request.form.get("message", "").strip()
    if not message:
        return jsonify({"ok": False, "msg": "Le message est vide."}), 400

    ok, msg = message_service.send_whatsapp(contact["phone"], message)
    return jsonify({"ok": ok, "msg": msg})


# ──────────────────────────────────────────────
# Appointments routes
# ──────────────────────────────────────────────
@app.route("/appointments")
@login_required
def appointments():
    all_contacts = service.get_all_contacts()
    all_appts = appt_service.get_all_appointments()
    booked_dates = appt_service.get_booked_dates()
    time_slots = generate_time_slots()
    all_labels = label_service.get_all_labels()
    gcal_connected = bool(session.get("gcal_access_token"))
    gcal_configured = gcal_service.is_configured()
    return render_template("appointments.html",
                           contacts=all_contacts,
                           appointments=all_appts,
                           booked_dates=booked_dates,
                           time_slots=time_slots,
                           all_labels=all_labels,
                           gcal_connected=gcal_connected,
                           gcal_configured=gcal_configured)


@app.route("/appointments/slots")
@login_required
def get_slots():
    date = request.args.get("date", "")
    if not date:
        return jsonify({"error": "date required"}), 400
    booked = appt_service.get_booked_slots(date)
    day_appts = appt_service.get_appointments_for_date(date)
    return jsonify({"booked": booked, "appointments": day_appts})


@app.route("/appointments/book", methods=["POST"])
@login_required
def book_appointment():
    data = request.get_json()
    contact_id     = data.get("contact_id")
    date           = data.get("date")
    time_slot      = data.get("time_slot")
    title          = data.get("title", "")
    notes          = data.get("notes", "")
    reminder_email = data.get("reminder_email", False)
    reminder_sms   = data.get("reminder_sms", False)
    sync_gcal      = data.get("sync_gcal", False)

    if not contact_id or not date or not time_slot:
        return jsonify({"ok": False, "msg": "Données incomplètes."}), 400

    ok, msg, appt_id = appt_service.book_slot(
        contact_id, date, time_slot, title, notes,
        reminder_email=reminder_email, reminder_sms=reminder_sms
    )
    if not ok:
        return jsonify({"ok": False, "msg": msg})

    result = {"ok": True, "msg": msg, "appt_id": appt_id}

    # Send reminder email immediately if requested
    if reminder_email:
        contact = service.get_contact_by_id(contact_id)
        if contact:
            subject = f"Rappel RDV – {title or 'Rendez-vous'}"
            body = (
                f"Bonjour {contact['name']},\n\n"
                f"Votre rendez-vous est confirmé :\n"
                f"Date : {date}\n"
                f"Heure : {time_slot}\n"
                f"Objet : {title or '—'}\n"
                f"Notes : {notes or '—'}\n\n"
                f"Merci et à bientôt."
            )
            e_ok, e_msg = message_service.send_email(contact["email"], subject, body)
            result["reminder_email_sent"] = e_ok
            result["reminder_email_msg"]  = e_msg

    # Send reminder SMS via WhatsApp if requested
    if reminder_sms:
        contact = service.get_contact_by_id(contact_id)
        if contact:
            sms_msg = (
                f"Rappel RDV\n"
                f"Bonjour {contact['name']},\n"
                f"{date} à {time_slot}\n"
                f"{title or 'Rendez-vous'}\n"
                f"Merci de confirmer."
            )
            s_ok, s_msg = message_service.send_whatsapp(contact["phone"], sms_msg)
            result["reminder_sms_sent"] = s_ok
            result["reminder_sms_msg"]  = s_msg

    # Sync to Google Calendar if requested and connected
    if sync_gcal and session.get("gcal_access_token"):
        contact = service.get_contact_by_id(contact_id)
        if contact:
            g_ok, g_data = gcal_service.create_event(
                session["gcal_access_token"],
                contact["name"], date, time_slot, title, notes
            )
            if g_ok:
                appt_service.save_google_event_id(appt_id, g_data)
                result["gcal_synced"] = True
                result["gcal_event_id"] = g_data
            else:
                result["gcal_synced"] = False
                result["gcal_error"] = str(g_data)

    return jsonify(result)


@app.route("/appointments/cancel/<int:appt_id>", methods=["POST"])
@login_required
def cancel_appointment(appt_id):
    ok, msg, google_event_id = appt_service.cancel_appointment(appt_id)
    # Also remove from Google Calendar if synced
    if google_event_id and session.get("gcal_access_token"):
        gcal_service.delete_event(session["gcal_access_token"], google_event_id)
    return jsonify({"ok": ok, "msg": msg})


# ──────────────────────────────────────────────
# Appointment reminder (manual send)
# ──────────────────────────────────────────────
@app.route("/appointments/remind/<int:appt_id>", methods=["POST"])
@login_required
def send_reminder(appt_id):
    data    = request.get_json() or {}
    channel = data.get("channel", "email")  # "email" or "sms"
    appt    = appt_service.get_appointment_by_id(appt_id)
    if not appt:
        return jsonify({"ok": False, "msg": "RDV introuvable."}), 404

    contact = service.get_contact_by_id(appt["contact_id"])
    if not contact:
        return jsonify({"ok": False, "msg": "Contact introuvable."}), 404

    title = appt.get("title") or "Rendez-vous"
    date  = appt["date"]
    time  = appt["time_slot"]

    if channel == "email":
        subject = f"Rappel RDV – {title}"
        body = (
            f"Bonjour {contact['name']},\n\n"
            f"Rappel de votre rendez-vous :\n"
            f"Date : {date}\nHeure : {time}\n"
            f"Objet : {title}\n\nMerci et à bientôt."
        )
        ok, msg = message_service.send_email(contact["email"], subject, body)
    else:
        sms_msg = (
            f"Rappel RDV\nBonjour {contact['name']},\n"
            f"{date} à {time}\n {title}\nMerci de confirmer."
        )
        ok, msg = message_service.send_whatsapp(contact["phone"], sms_msg)

    return jsonify({"ok": ok, "msg": msg})


# ──────────────────────────────────────────────
# Google Calendar OAuth routes
# ──────────────────────────────────────────────
@app.route("/gcal/connect")
@login_required
def gcal_connect():
    if not gcal_service.is_configured():
        flash("Google Calendar non configuré. Ajoutez GOOGLE_CLIENT_ID et GOOGLE_CLIENT_SECRET dans .env", "error")
        return redirect(url_for("appointments"))
    return redirect(gcal_service.get_auth_url())


@app.route("/gcal/callback")
@login_required
def gcal_callback():
    code = request.args.get("code")
    if not code:
        flash("Autorisation Google annulée.", "warning")
        return redirect(url_for("appointments"))
    ok, tokens = gcal_service.exchange_code(code)
    if ok:
        session["gcal_access_token"]  = tokens.get("access_token", "")
        session["gcal_refresh_token"] = tokens.get("refresh_token", "")
        flash("Google Calendar connecté avec succès !", "success")
    else:
        flash(f"Erreur Google Calendar: {tokens}", "error")
    return redirect(url_for("appointments"))


@app.route("/gcal/disconnect")
@login_required
def gcal_disconnect():
    session.pop("gcal_access_token", None)
    session.pop("gcal_refresh_token", None)
    flash("Google Calendar déconnecté.", "success")
    return redirect(url_for("appointments"))


# ──────────────────────────────────────────────
# Bulk delete contacts
# ──────────────────────────────────────────────
@app.route("/contacts/bulk-delete", methods=["POST"])
@login_required
def bulk_delete_contacts():
    data = request.get_json()
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"ok": False, "msg": "Aucun contact sélectionné."}), 400
    deleted = 0
    for cid in ids:
        ok, _ = service.delete_contact(int(cid))
        if ok:
            deleted += 1
    return jsonify({"ok": True, "msg": f"{deleted} contact(s) supprimé(s).", "deleted": deleted})


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
