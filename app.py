from werkzeug.utils import secure_filename
from uuid import uuid4
from flask import Flask, jsonify, request, send_file
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg
import pytesseract
from PIL import Image, ImageOps
import os



def extract_text_from_image(image_path):
    try:
        with Image.open(image_path) as image:
            image.verify()

        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")

            if image.width * image.height > 20000000:
                raise ValueError("Image dimensions are too large")

            extracted_text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6"
            )

            return extracted_text.strip()

    except Exception:
        return ""

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "evidence")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

jwt = JWTManager(app)
def get_db_connection():
    return psycopg.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    full_name = data.get("full_name")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")
    role = "parent"

    if not full_name or not email or not password:
        return jsonify({"error": "Required fields are missing"}), 400

    password_hash = generate_password_hash(password)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users (full_name, email, phone, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id;
            """,
            (full_name, email, phone, password_hash, role)
        )

        user_id = cursor.fetchone()[0]
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "message": "User registered successfully",
            "user_id": user_id
        }), 201

    except psycopg.errors.UniqueViolation:
        conn.rollback()
        conn.close()
        return jsonify({"error": "Email already exists"}), 409

    except Exception as error:
        return jsonify({"error": str(error)}), 500
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id, full_name, email, password_hash, role FROM users WHERE email = %s",
        (email,)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user is None:
        return jsonify({"error": "Invalid email or password"}), 401

    if not check_password_hash(user[3], password):
        return jsonify({"error": "Invalid email or password"}), 401

    access_token = create_access_token(identity=str(user[0]))

    return jsonify({
        "message": "Login successful",
        "user_id": user[0],
        "full_name": user[1],
        "email": user[2],
        "role": user[4],
        "access_token": access_token
    }), 200
@app.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    current_user_id = get_jwt_identity()

    return jsonify({
        "message": "You are authorized!",
        "user_id": current_user_id
    }), 200
@app.route("/create-child", methods=["POST"])
@jwt_required()
def create_child():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request data is required"}), 400

    full_name = data.get("full_name")
    email = data.get("email")
    password = data.get("password")

    if not full_name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    parent_id = get_jwt_identity()
    password_hash = generate_password_hash(password)

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT role FROM users WHERE user_id = %s",
            (parent_id,)
        )

        parent = cursor.fetchone()

        if parent is None or parent[0] != "parent":
            return jsonify({"error": "Only parents can create child accounts"}), 403

        cursor.execute(
            """
            INSERT INTO users (full_name, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id;
            """,
            (full_name, email, password_hash, "child")
        )

        child_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO parent_child (parent_id, child_id)
            VALUES (%s, %s);
            """,
            (parent_id, child_id)
        )

        conn.commit()

        return jsonify({
            "message": "Child account created and linked successfully",
            "child_id": child_id
        }), 201

    except psycopg.errors.UniqueViolation:
        if conn:
            conn.rollback()
        return jsonify({"error": "Email already exists"}), 409

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/my-children", methods=["GET"])
@jwt_required()
def my_children():
    parent_id = get_jwt_identity()

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT role FROM users WHERE user_id = %s",
            (parent_id,)
        )

        parent = cursor.fetchone()

        if parent is None or parent[0] != "parent":
            return jsonify({"error": "Only parents can view their children"}), 403

        cursor.execute(
            """
            SELECT u.user_id, u.full_name, u.email, pc.created_at
            FROM parent_child pc
            JOIN users u ON pc.child_id = u.user_id
            WHERE pc.parent_id = %s
            ORDER BY pc.created_at DESC;
            """,
            (parent_id,)
        )

        children = cursor.fetchall()

        return jsonify({
            "message": "Children retrieved successfully",
            "children": [
                {
                    "child_id": child[0],
                    "full_name": child[1],
                    "email": child[2],
                    "linked_at": child[3].isoformat()
                }
                for child in children
            ]
        }), 200

    except Exception:
        return jsonify({"error": "Unable to retrieve children"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/database-test")
def database_test():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT current_database();")
        database = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({
            "status": "Connected",
            "database": database
        })

    except Exception as error:
        return jsonify({
            "status": "Failed",
            "error": str(error)
        }), 500

@app.route("/submit-report", methods=["POST"])
@jwt_required()
def submit_report():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request data is required"}), 400

    report_category = data.get("report_category")
    description = data.get("description")
    incident_date = data.get("incident_date")

    if not report_category or not description:
        return jsonify({
            "error": "Report category and description are required"
        }), 400

    user_id = get_jwt_identity()

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO reports
            (user_id, report_category, description, incident_date)
            VALUES (%s, %s, %s, %s)
            RETURNING report_id;
            """,
            (user_id, report_category, description, incident_date)
        )

        report_id = cursor.fetchone()[0]
                # Find parents linked to this child
        cursor.execute(
            """
            SELECT parent_id
            FROM parent_child
            WHERE child_id = %s
            """,
            (user_id,)
        )

        parents = cursor.fetchall()

        # Send an alert to each linked parent
        for parent in parents:
            cursor.execute(
                """
                INSERT INTO alerts
                (user_id, report_id, alert_title, alert_message, alert_type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    parent[0],
                    report_id,
                    "New Child Safety Report",
                    "Your child has submitted a new safety report.",
                    "safety"
                )
            ) 
        conn.commit()

        return jsonify({
            "message": "Report submitted successfully",
            "report_id": report_id
        }), 201

    except Exception:
        if conn:
            conn.rollback()
        return jsonify({"error": "Unable to submit report"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/my-reports", methods=["GET"])
@jwt_required()
def my_reports():
    user_id = get_jwt_identity()

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT report_id, report_category, description,
                   incident_date, status, created_at
            FROM reports
            WHERE user_id = %s
            ORDER BY created_at DESC;
            """,
            (user_id,)
        )

        reports = cursor.fetchall()

        return jsonify({
            "message": "Reports retrieved successfully",
            "reports": [
                {
                    "report_id": report[0],
                    "report_category": report[1],
                    "description": report[2],
                    "incident_date": (
                        report[3].isoformat() if report[3] else None
                    ),
                    "status": report[4],
                    "created_at": report[5].isoformat()
                }
                for report in reports
            ]
        }), 200

    except Exception:
        return jsonify({"error": "Unable to retrieve reports"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/upload-evidence", methods=["POST"])
@jwt_required()
def upload_evidence():
    report_id = request.form.get("report_id")
    file = request.files.get("file")

    if not report_id or not report_id.isdigit():
        return jsonify({"error": "Valid report_id is required"}), 400

    if not file or not file.filename:
        return jsonify({"error": "Screenshot file is required"}), 400


    allowed_extensions = {"png", "jpg", "jpeg", "webp"}
    extension = file.filename.rsplit(".", 1)[-1].lower()

    if extension not in allowed_extensions:
        return jsonify({
            "error": "Only PNG, JPG, JPEG and WEBP allowed"
        }), 400

    # Check actual image file signature
    file_header = file.stream.read(12)
    file.stream.seek(0)

    detected_type = None

    if file_header.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_type = "image/png"

    elif file_header.startswith(b"\xff\xd8\xff"):
        detected_type = "image/jpeg"

    elif (
        file_header.startswith(b"RIFF")
        and file_header[8:12] == b"WEBP"
    ):
        detected_type = "image/webp"

    if not detected_type:
        return jsonify({
            "error": "Invalid image file. Upload a genuine PNG, JPG or WEBP image."
        }), 400

    extension_types = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp"
    }

    if extension_types[extension] != detected_type:
        return jsonify({
            "error": "File extension does not match actual image type"
        }), 400

    user_id = get_jwt_identity()
    conn = None
    cursor = None
    file_path = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT report_id FROM reports WHERE report_id = %s AND user_id = %s",
            (report_id, user_id)
        )

        if not cursor.fetchone():
            return jsonify({"error": "Report not found or access denied"}), 403

        safe_name = secure_filename(file.filename)
        unique_name = f"{uuid4().hex}_{safe_name}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)

        file.save(file_path)
        file_size = os.path.getsize(file_path)

        # Extract text from uploaded screenshot using OCR
        extracted_text = extract_text_from_image(file_path)

        cursor.execute(
            """
            INSERT INTO evidence
            (report_id, file_name, file_path, file_type, file_size, extracted_text)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING evidence_id;
            """,
            (report_id, safe_name, file_path, detected_type, file_size, extracted_text)
        )

        evidence_id = cursor.fetchone()[0]
        conn.commit()

        return jsonify({
            "message": "Evidence uploaded successfully",
            "evidence_id": evidence_id,
            "ocr_status": "text_extracted" if extracted_text else "no_text_detected_or_ocr_failed",
            "extracted_text": extracted_text
        }), 201

    except Exception:
        if conn:
            conn.rollback()
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": "Unable to upload evidence"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/my-evidence/<int:report_id>", methods=["GET"])
@jwt_required()
def my_evidence(report_id):
    user_id = get_jwt_identity()
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT e.evidence_id, e.report_id, e.file_name,
                   e.file_type, e.file_size, e.uploaded_at
            FROM evidence e
            JOIN reports r ON e.report_id = r.report_id
            WHERE e.report_id = %s AND r.user_id = %s
            ORDER BY e.uploaded_at DESC;
            """,
            (report_id, user_id)
        )

        rows = cursor.fetchall()

        evidence_list = []
        for row in rows:
            evidence_list.append({
                "evidence_id": row[0],
                "report_id": row[1],
                "file_name": row[2],
                "file_type": row[3],
                "file_size": row[4],
                "uploaded_at": row[5].isoformat() if row[5] else None
            })

        return jsonify({"evidence": evidence_list}), 200

    except Exception:
        return jsonify({"error": "Unable to retrieve evidence"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route("/evidence/<int:evidence_id>/download", methods=["GET"])
@jwt_required()
def download_evidence(evidence_id):
    user_id = int(get_jwt_identity())
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                e.file_path,
                e.file_name,
                e.file_type,
                r.user_id,
                (SELECT role FROM users WHERE user_id = %s),
                EXISTS (
                    SELECT 1
                    FROM parent_child pc
                    WHERE pc.parent_id = %s
                      AND pc.child_id = r.user_id
                )
            FROM evidence e
            JOIN reports r ON r.report_id = e.report_id
            WHERE e.evidence_id = %s
            """,
            (user_id, user_id, evidence_id)
        )

        record = cursor.fetchone()

        if not record:
            return jsonify({"error": "Evidence not found"}), 404

        file_path, file_name, file_type, owner_id, role, is_linked_parent = record

        # Only owner, linked parent or admin can access
        if not (
            role == "admin"
            or owner_id == user_id
            or (role == "parent" and is_linked_parent)
        ):
            return jsonify({"error": "Evidence access denied"}), 403

        if not file_path:
            return jsonify({"error": "Evidence file path missing"}), 404

        # Prevent path traversal and access outside evidence folder
        upload_root = os.path.realpath(app.config["UPLOAD_FOLDER"])
        safe_path = os.path.realpath(file_path)

        if os.path.commonpath([upload_root, safe_path]) != upload_root:
            return jsonify({"error": "Invalid evidence file path"}), 403

        if not os.path.isfile(safe_path):
            return jsonify({"error": "Evidence file not found"}), 404

        allowed_types = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp"
        }

        if file_type not in allowed_types:
            return jsonify({"error": "Unsupported evidence file type"}), 415

        download = request.args.get("download") == "1"

        response = send_file(
            safe_path,
            mimetype=file_type,
            as_attachment=download,
            download_name=os.path.basename(file_name),
            conditional=True
        )

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Content-Security-Policy"] = "sandbox"

        return response

    except Exception:
        app.logger.exception("Evidence retrieval failed")
        return jsonify({"error": "Unable to retrieve evidence"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route("/create-complaint-draft", methods=["POST"])
@jwt_required()
def create_complaint_draft():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request data is required"}), 400

    report_id = data.get("report_id")
    complaint_title = data.get("complaint_title")
    complaint_content = data.get("complaint_content")

    if not report_id or not complaint_title or not complaint_content:
        return jsonify({"error": "All fields are required"}), 400

    user_id = get_jwt_identity()
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT report_id FROM reports WHERE report_id = %s AND user_id = %s",
            (report_id, user_id)
        )

        if not cursor.fetchone():
            return jsonify({"error": "Report not found or access denied"}), 403

        cursor.execute(
            """
            INSERT INTO complaint_drafts
            (report_id, user_id, complaint_title, complaint_content)
            VALUES (%s, %s, %s, %s)
            RETURNING draft_id;
            """,
            (report_id, user_id, complaint_title, complaint_content)
        )

        draft_id = cursor.fetchone()[0]
        conn.commit()

        return jsonify({
            "message": "Complaint draft saved successfully",
            "draft_id": draft_id
        }), 201

    except Exception:
        if conn:
            conn.rollback()
        return jsonify({"error": "Unable to save complaint draft"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/my-complaint-drafts", methods=["GET"])
@jwt_required()
def my_complaint_drafts():
    user_id = get_jwt_identity()
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT draft_id, report_id, complaint_title,
                   complaint_content, status, created_at
            FROM complaint_drafts
            WHERE user_id = %s
            ORDER BY created_at DESC;
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

        drafts = []
        for row in rows:
            drafts.append({
                "draft_id": row[0],
                "report_id": row[1],
                "complaint_title": row[2],
                "complaint_content": row[3],
                "status": row[4],
                "created_at": row[5].isoformat() if row[5] else None
            })

        return jsonify({"complaint_drafts": drafts}), 200

    except Exception:
        return jsonify({"error": "Unable to retrieve complaint drafts"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/create-alert", methods=["POST"])
@jwt_required()
def create_alert():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request data is required"}), 400

    alert_title = data.get("alert_title")
    alert_message = data.get("alert_message")
    alert_type = data.get("alert_type", "safety")

    if not alert_title or not alert_message:
        return jsonify({"error": "Title and message are required"}), 400

    user_id = get_jwt_identity()
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO alerts (user_id, alert_title, alert_message, alert_type)
            VALUES (%s, %s, %s, %s)
            RETURNING alert_id;
            """,
            (user_id, alert_title, alert_message, alert_type)
        )

        alert_id = cursor.fetchone()[0]
        conn.commit()

        return jsonify({
            "message": "Alert created successfully",
            "alert_id": alert_id
        }), 201

    except Exception:
        if conn:
            conn.rollback()
        return jsonify({"error": "Unable to create alert"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/my-alerts", methods=["GET"])
@jwt_required()
def my_alerts():
    user_id = get_jwt_identity()
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT alert_id, alert_title, alert_message,
                   alert_type, is_read, created_at
            FROM alerts
            WHERE user_id = %s
            ORDER BY created_at DESC;
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

        alerts = []
        for row in rows:
            alerts.append({
                "alert_id": row[0],
                "alert_title": row[1],
                "alert_message": row[2],
                "alert_type": row[3],
                "is_read": row[4],
                "created_at": row[5].isoformat()
            })

        return jsonify({"alerts": alerts}), 200

    except Exception:
        return jsonify({"error": "Unable to retrieve alerts"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route("/mark-alert-read/<int:alert_id>", methods=["PUT"])
@jwt_required()
def mark_alert_read(alert_id):
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE alerts SET is_read = TRUE WHERE alert_id = %s AND user_id = %s RETURNING alert_id",
        (alert_id, user_id)
    )

    result = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()

    if not result:
        return jsonify({"error": "Alert not found"}), 404

    return jsonify({
        "message": "Alert marked as read",
        "alert_id": alert_id
    }), 200
@app.route("/add-suspected-offender", methods=["POST"])
@jwt_required()
def add_suspected_offender():
    user_id = int(get_jwt_identity())
    data = request.get_json()

    report_id = data.get("report_id")
    reported_name = data.get("reported_name")
    reported_username = data.get("reported_username")
    platform = data.get("platform")
    match_notes = data.get("match_notes")

    if not report_id:
        return jsonify({"error": "Report ID is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT report_id FROM reports WHERE report_id = %s AND user_id = %s",
        (report_id, user_id)
    )

    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Report not found"}), 404

    cursor.execute(
        """INSERT INTO suspected_offenders
        (report_id, reported_name, reported_username, platform, match_notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING offender_id""",
        (report_id, reported_name, reported_username, platform, match_notes)
    )

    offender_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "Suspected offender added",
        "offender_id": offender_id,
        "verification_status": "unverified"
    }), 201
@app.route("/my-suspected-offenders", methods=["GET"])
@jwt_required()
def my_suspected_offenders():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT so.offender_id, so.report_id, so.reported_name,
               so.reported_username, so.platform, so.match_notes,
               so.verification_status, so.created_at
        FROM suspected_offenders so
        JOIN reports r ON so.report_id = r.report_id
        WHERE r.user_id = %s
        ORDER BY so.created_at DESC
        """,
        (user_id,)
    )

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    offenders = []
    for row in rows:
        offenders.append({
            "offender_id": row[0],
            "report_id": row[1],
            "reported_name": row[2],
            "reported_username": row[3],
            "platform": row[4],
            "match_notes": row[5],
            "verification_status": row[6],
            "created_at": row[7].isoformat() if row[7] else None
        })

    return jsonify({"suspected_offenders": offenders}), 200
@app.route("/admin/reports", methods=["GET"])
@jwt_required()
def admin_reports():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute(
        """
        SELECT report_id, user_id, report_category,
               description, incident_date, status, created_at
        FROM reports
        ORDER BY created_at DESC
        """
    )

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    reports = []
    for row in rows:
        reports.append({
            "report_id": row[0],
            "user_id": row[1],
            "report_category": row[2],
            "description": row[3],
            "incident_date": str(row[4]) if row[4] else None,
            "status": row[5],
            "created_at": row[6].isoformat() if row[6] else None
        })

    return jsonify({"reports": reports}), 200
@app.route("/admin/update-report/<int:report_id>", methods=["PUT"])
@jwt_required()
def admin_update_report(report_id):
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    new_status = data.get("status")

    allowed_statuses = ["pending", "under_review", "resolved", "rejected"]

    if new_status not in allowed_statuses:
        return jsonify({
            "error": "Invalid status",
            "allowed_statuses": allowed_statuses
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute(
        """
        UPDATE reports
        SET status = %s
        WHERE report_id = %s
        RETURNING report_id, user_id, status
        """,
        (new_status, report_id)
    )

    result = cursor.fetchone()

    if not result:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Report not found"}), 404

    report_owner_id = result[1]
    updated_status = result[2]

    # Notify child
    cursor.execute(
        """
        INSERT INTO alerts
        (user_id, report_id, alert_title, alert_message, alert_type)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            report_owner_id,
            report_id,
            "Report Status Updated",
            "Your report status has been updated to: " + updated_status,
            "status"
        )
    )

    # Find linked parents
    cursor.execute(
        """
        SELECT parent_id
        FROM parent_child
        WHERE child_id = %s
        """,
        (report_owner_id,)
    )

    parents = cursor.fetchall()

    # Notify parents
    for parent in parents:
        cursor.execute(
            """
            INSERT INTO alerts
            (user_id, report_id, alert_title, alert_message, alert_type)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                parent[0],
                report_id,
                "Child Report Status Updated",
                "Your child's report status has been updated to: " + updated_status,
                "status"
            )
        )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "Report status updated and notifications sent",
        "report_id": result[0],
        "status": updated_status
    }), 200

@app.route("/admin/report/<int:report_id>", methods=["GET"])
@jwt_required()
def admin_view_report(report_id):
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute(
        """
        SELECT report_id, user_id, report_category,
               description, incident_date, status, created_at
        FROM reports
        WHERE report_id = %s
        """,
        (report_id,)
    )

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return jsonify({"error": "Report not found"}), 404

    return jsonify({
        "report_id": row[0],
        "user_id": row[1],
        "report_category": row[2],
        "description": row[3],
        "incident_date": str(row[4]) if row[4] else None,
        "status": row[5],
        "created_at": row[6].isoformat() if row[6] else None
    }), 200
@app.route("/admin/users", methods=["GET"])
@jwt_required()
def admin_users():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute(
        """
        SELECT user_id, full_name, email, phone, role, created_at
        FROM users
        ORDER BY created_at DESC
        """
    )

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    users = []
    for row in rows:
        users.append({
            "user_id": row[0],
            "full_name": row[1],
            "email": row[2],
            "phone": row[3],
            "role": row[4],
            "created_at": row[5].isoformat() if row[5] else None
        })

    return jsonify({"users": users}), 200
@app.route("/admin/dashboard-stats", methods=["GET"])
@jwt_required()
def admin_dashboard_stats():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute("""
        SELECT
            COUNT(*) AS total_users,
            COUNT(*) FILTER (WHERE role = 'parent') AS total_parents,
            COUNT(*) FILTER (WHERE role = 'child') AS total_children
        FROM users
    """)
    user_stats = cursor.fetchone()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_reports,
            COUNT(*) FILTER (WHERE status = 'pending') AS pending_reports,
            COUNT(*) FILTER (WHERE status = 'under_review') AS under_review_reports,
            COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_reports
        FROM reports
    """)
    report_stats = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({
        "total_users": user_stats[0],
        "total_parents": user_stats[1],
        "total_children": user_stats[2],
        "total_reports": report_stats[0],
        "pending_reports": report_stats[1],
        "under_review_reports": report_stats[2],
        "resolved_reports": report_stats[3]
    }), 200
@app.route("/admin/complaint-drafts", methods=["GET"])
@jwt_required()
def admin_complaint_drafts():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute("""
        SELECT
            draft_id,
            report_id,
            user_id,
            complaint_title,
            complaint_content,
            status,
            created_at
        FROM complaint_drafts
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    drafts = []
    for row in rows:
        drafts.append({
            "draft_id": row[0],
            "report_id": row[1],
            "user_id": row[2],
            "complaint_title": row[3],
            "complaint_content": row[4],
            "status": row[5],
            "created_at": row[6].isoformat() if row[6] else None
        })

    return jsonify({"complaint_drafts": drafts}), 200

@app.route("/admin/update-complaint-draft/<int:draft_id>", methods=["PUT"])
@jwt_required()
def admin_update_complaint_draft(draft_id):
    user_id = int(get_jwt_identity())

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

    allowed_statuses = ["draft", "reviewed", "submitted"]

    if new_status not in allowed_statuses:
        return jsonify({
            "error": "Invalid complaint draft status",
            "allowed_statuses": allowed_statuses
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute(
        """
        UPDATE complaint_drafts
        SET status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE draft_id = %s
        RETURNING draft_id, report_id, status, updated_at
        """,
        (new_status, draft_id)
    )

    updated = cursor.fetchone()

    if not updated:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Complaint draft not found"}), 404

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "Complaint draft status updated successfully",
        "draft_id": updated[0],
        "report_id": updated[1],
        "status": updated[2],
        "updated_at": updated[3].isoformat() if updated[3] else None
    }), 200

@app.route("/admin/evidence", methods=["GET"])
@jwt_required()
def admin_all_evidence():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute("""
        SELECT
            e.evidence_id,
            e.report_id,
            e.file_name,
            e.file_type,
            e.file_size,
            e.uploaded_at,
            r.user_id,
            r.report_category
        FROM evidence e
        JOIN reports r ON e.report_id = r.report_id
        ORDER BY e.uploaded_at DESC
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    evidence_list = []

    for row in rows:
        evidence_list.append({
            "evidence_id": row[0],
            "report_id": row[1],
            "file_name": row[2],
            "file_type": row[3],
            "file_size": row[4],
            "uploaded_at": row[5].isoformat() if row[5] else None,
            "user_id": row[6],
            "report_category": row[7]
        })

    return jsonify({"evidence": evidence_list}), 200
@app.route("/admin/alerts", methods=["GET"])
@jwt_required()
def admin_all_alerts():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute("""
        SELECT
            alert_id, user_id, report_id,
            alert_title, alert_message,
            alert_type, is_read, created_at
        FROM alerts
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    alerts = []
    for row in rows:
        alerts.append({
            "alert_id": row[0],
            "user_id": row[1],
            "report_id": row[2],
            "alert_title": row[3],
            "alert_message": row[4],
            "alert_type": row[5],
            "is_read": row[6],
            "created_at": row[7].isoformat() if row[7] else None
        })

    return jsonify({"alerts": alerts}), 200
@app.route("/parent/children-reports", methods=["GET"])
@jwt_required()
def parent_children_reports():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "parent":
        cursor.close()
        conn.close()
        return jsonify({"error": "Parent access required"}), 403

    cursor.execute("""
        SELECT
            r.report_id,
            r.user_id,
            u.full_name,
            r.report_category,
            r.description,
            r.incident_date,
            r.status,
            r.created_at
        FROM reports r
        JOIN parent_child pc ON pc.child_id = r.user_id
        JOIN users u ON u.user_id = r.user_id
        WHERE pc.parent_id = %s
        ORDER BY r.created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    reports = []

    for row in rows:
        reports.append({
            "report_id": row[0],
            "child_id": row[1],
            "child_name": row[2],
            "report_category": row[3],
            "description": row[4],
            "incident_date": row[5].isoformat() if row[5] else None,
            "status": row[6],
            "created_at": row[7].isoformat() if row[7] else None
        })

    return jsonify({
        "message": "Children reports retrieved successfully",
        "reports": reports
    }), 200
@app.route("/parent/child-evidence/<int:report_id>", methods=["GET"])
@jwt_required()
def parent_child_evidence(report_id):
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.evidence_id, e.report_id, e.file_name,
               e.file_type, e.file_size, e.uploaded_at
        FROM evidence e
        JOIN reports r ON r.report_id = e.report_id
        JOIN parent_child pc ON pc.child_id = r.user_id
        WHERE pc.parent_id = %s AND r.report_id = %s
        ORDER BY e.uploaded_at DESC
    """, (user_id, report_id))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "Child evidence retrieved successfully",
        "evidence": [
            {
                "evidence_id": row[0],
                "report_id": row[1],
                "file_name": row[2],
                "file_type": row[3],
                "file_size": row[4],
                "uploaded_at": row[5].isoformat() if row[5] else None
            }
            for row in rows
        ]
    }), 200

@app.route("/admin/suspected-offenders", methods=["GET"])
@jwt_required()
def admin_suspected_offenders():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute(
        """
        SELECT so.offender_id, so.report_id,
               so.reported_name, so.reported_username,
               so.platform, so.match_notes,
               so.verification_status, so.created_at,
               r.user_id, u.full_name
        FROM suspected_offenders so
        JOIN reports r ON so.report_id = r.report_id
        JOIN users u ON r.user_id = u.user_id
        ORDER BY so.created_at DESC
        """
    )

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    offenders = []

    for row in rows:
        offenders.append({
            "offender_id": row[0],
            "report_id": row[1],
            "reported_name": row[2],
            "reported_username": row[3],
            "platform": row[4],
            "match_notes": row[5],
            "verification_status": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "report_owner_id": row[8],
            "report_owner_name": row[9]
        })

    return jsonify({
        "suspected_offenders": offenders
    }), 200


@app.route("/admin/update-suspected-offender/<int:offender_id>", methods=["PUT"])
@jwt_required()
def admin_update_suspected_offender(offender_id):
    user_id = int(get_jwt_identity())

    data = request.get_json(silent=True) or {}
    new_status = data.get("verification_status")

    allowed_statuses = [
        "unverified",
        "under_review",
        "verified",
        "dismissed"
    ]

    if new_status not in allowed_statuses:
        return jsonify({
            "error": "Invalid verification status",
            "allowed_statuses": allowed_statuses
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT role FROM users WHERE user_id = %s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        cursor.close()
        conn.close()
        return jsonify({"error": "Admin access required"}), 403

    cursor.execute(
        """
        UPDATE suspected_offenders
        SET verification_status = %s
        WHERE offender_id = %s
        RETURNING offender_id, verification_status
        """,
        (new_status, offender_id)
    )

    updated = cursor.fetchone()

    if not updated:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Suspected offender not found"}), 404

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "Verification status updated successfully",
        "offender_id": updated[0],
        "verification_status": updated[1]
    }), 200

if __name__ == "__main__":
    app.run(debug=True)
