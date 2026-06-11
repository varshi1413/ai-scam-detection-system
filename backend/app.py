from flask import Flask, request, jsonify, render_template
import sqlite3
import json
import os
import re
from google import genai
from flask_cors import CORS


# ---------------------------
# App setup
# ---------------------------
app = Flask(__name__)
CORS(app)


# ---------------------------
# Gemini AI setup
# ---------------------------
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)
# ---------------------------
# Database setup
# ---------------------------
def init_db():
    print("Initializing database...")
    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    role TEXT DEFAULT 'student',
    verified INTEGER DEFAULT 0,
    institution TEXT
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT,
    linkedin_url TEXT,
    role TEXT,
    contact_method TEXT,
    description TEXT,
    fee_asked INTEGER,
    fee_amount TEXT,
    rating INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        offer_text TEXT,
        company_name TEXT,
        verdict TEXT,
        risk_score INTEGER,
        reasons TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create Admin ABC
    cursor.execute("SELECT * FROM students WHERE email = 'admin_abc@system.com'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO students (name, email, password, role, verified, institution)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Admin ABC", "admin_abc@system.com", "admin123", "admin", 1, "ABC College"))

# Create Admin XYZ
    cursor.execute("SELECT * FROM students WHERE email = 'admin_xyz@system.com'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO students (name, email, password, role, verified, institution)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ("Admin XYZ", "admin_xyz@system.com", "admin123", "admin", 1, "XYZ University"))

    conn.commit()
    conn.close()

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, role, verified, institution FROM students
    WHERE email = ? AND password = ?
    """, (email, password))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Invalid credentials"}), 401

    user_id, role, verified, institution = row

    if role == "student" and verified == 0:
        return jsonify({"error": "Account not approved"}), 403

    return jsonify({
        "message": "Login successful",
        "role": role,
        "user_id": user_id,
        "institution": institution
    })

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    institution = data.get("institution")

    if not institution:
        return jsonify({"error": "Institution is required"}), 400

    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO students (name, email, password, role, verified, institution)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (name, email, password, "student", institution))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Email already registered"}), 400

    conn.close()

    return jsonify({
        "message": "Registered successfully. Await admin approval."
    })

@app.route("/admin/pending/<institution>", methods=["GET"])
def get_pending_students(institution):

    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, name, email
    FROM students
    WHERE verified = 0
    AND role = 'student'
    AND institution = ?
    """, (institution,))

    rows = cursor.fetchall()
    conn.close()

    pending = []
    for r in rows:
        pending.append({
            "id": r[0],
            "name": r[1],
            "email": r[2]
        })

    return jsonify(pending)


@app.route("/admin/approve/<int:student_id>", methods=["POST"])
def approve_student(student_id):

    data = request.get_json()
    role = data.get("role")

    if role != "admin":
        return jsonify({"error": "Unauthorized access"}), 403

    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE students SET verified = 1 WHERE id = ?
    """, (student_id,))

    conn.commit()
    conn.close()

    return jsonify({"message": "Student approved successfully"})



@app.route("/submit_review", methods=["POST"])
def submit_review():
    data = request.get_json()

    # Get values from frontend
    company_name = data.get("company_name", "").strip()
    linkedin_url = data.get("linkedin_url", "").strip()
    role = data.get("role", "").strip()
    description = data.get("description", "").strip()
    fee_asked = data.get("fee_asked", "").strip()  # "Yes" or "No"
    fee_amount = data.get("fee_amount", "").strip()  # only if Yes
    contact_method = data.get("contact_method", "").strip()
    rating = data.get("rating")

    # -----------------------------
    # Mandatory Validation
    # -----------------------------
    if not company_name and not linkedin_url:
        return jsonify({"error": "Either Company Name or LinkedIn URL is required"}), 400

    if linkedin_url and not company_name:
        match = re.search(r'linkedin\.com/company/([^/]+)', linkedin_url)
        if match:
            company_name = match.group(1).replace("-", " ").title()
        else:
            return jsonify({"error": "Invalid LinkedIn Company URL"}), 400

    if not role:
        return jsonify({"error": "Please select a role"}), 400

    if not contact_method:
        return jsonify({"error": "Please select a contact method"}), 400

    if not description:
        return jsonify({"error": "Description is required"}), 400

    if not fee_asked:
        return jsonify({"error": "Please select fee payment option"}), 400

    if fee_asked == "Yes" and not fee_amount:
        return jsonify({"error": "Please enter the fee amount"}), 400

    # Convert Yes/No → 1/0
    fee_value = 1 if fee_asked == "Yes" else 0

    # Convert rating to integer
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except:
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    # -----------------------------
    # Save to Database
    # -----------------------------
    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reviews (
            company_name,
            linkedin_url,
            role,
            contact_method,
            description,
            fee_asked,
            fee_amount,
            rating
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_name,
        linkedin_url,
        role,
        contact_method,
        description,
        fee_value,
        fee_amount if fee_value == 1 else None,
        rating
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Review submitted successfully",
        "company_extracted": company_name
    })


DB_FILE = os.path.join(os.path.dirname(__file__), "offers.db")

@app.route("/community_summary/<company_name>", methods=["GET"])
def community_summary(company_name):
    try:
        # Normalize input
        company_name_normalized = company_name.strip().lower()

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Select only existing columns, trim spaces, and match case-insensitive
            cursor.execute("""
                SELECT fee_asked, contact_method, rating, role, description, fee_amount
                FROM reviews
                WHERE LOWER(TRIM(company_name)) = ?
            """, (company_name_normalized,))

            rows = cursor.fetchall()

        total = len(rows)

        if total == 0:
            return jsonify({
                "company": company_name.title(),
                "reviews_count": 0,
                "final_verdict": "FAKE",
                "summary": f"No community reviews available yet for {company_name.title()}.",
                "details": []
            })

        # Count fees requested
        fee_count = sum(1 for r in rows if r[0] == 1)

        # Average rating
        avg_rating = sum(r[2] for r in rows) / total

        # Verdict logic
        if fee_count / total > 0.5:
            verdict = "FAKE"
        elif avg_rating < 2.5:
            verdict = "SUSPICIOUS"
        else:
            verdict = "REAL"

        # Build summary text
        summary_text = (
            f"Based on {total} student review{'s' if total > 1 else ''}, "
            f"{fee_count} reported fees being asked. "
            f"Average rating is {round(avg_rating, 1)}."
        )

        # Return detailed info per review
        details = [
            {
                "role": r[3],
                "description": r[4],
                "fee_asked": r[0],
                "fee_amount": r[5],
                "contact_method": r[1],
                "rating": r[2]
            } for r in rows
        ]

        return jsonify({
            "company": company_name.title(),
            "reviews_count": total,
            "final_verdict": verdict,
            "summary": summary_text,
            "details": details
        })

    except Exception as e:
        return jsonify({"error": str(e)})


def extract_company_name(text):

    if not text:
        return "Unknown"

    known_companies = ["Google", "Microsoft", "Amazon", "Infosys", "TCS", "Wipro"]
    for company in known_companies:
        if company.lower() in text.lower():
            return company

    pattern = r'\b([A-Z][a-zA-Z0-9]+(?:\s[A-Z][a-zA-Z0-9]+)*\s(?:Solutions|Technologies|Innovations|Systems|Company|Corp|Inc|Ltd|Pvt Ltd))\b'

    match = re.search(pattern, text)

    if match:
        return match.group(1)

    return "Unknown"


def save_offer(offer_text, verdict, risk_score, reasons):
    company_name = extract_company_name(offer_text)

    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO offers (offer_text, company_name, verdict, risk_score, reasons)
        VALUES (?, ?, ?, ?, ?)
    """, (
        offer_text,
        company_name,
        verdict,
        risk_score,
        ", ".join(reasons)
    ))

    conn.commit()
    conn.close()


def get_all_offers():
    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM offers")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_offers_by_company(company_name):
    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM offers WHERE company_name = ?",
        (company_name,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


# ---------------------------
# Routes / APIs
# ---------------------------

def extract_company_from_linkedin(url):
    match = re.search(r'linkedin\.com/company/([^/]+)', url)
    if match:
        return match.group(1).replace("-", " ").title()
    return None


def extract_company_name(text):

    if not text:
        return "Unknown"

    known_companies = ["Google", "Microsoft", "Amazon", "Infosys", "TCS", "Wipro"]

    for company in known_companies:
        if company.lower() in text.lower():
            return company

    pattern = r'\b([A-Za-z0-9]+(?:\s[A-Za-z0-9]+)*\s(?:Solutions|Technologies|Innovations|Systems|Company|Corp|Inc|Ltd|Pvt Ltd))\b'

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group(1).title()

    return "Unknown"



def save_offer(offer_text, company_name, verdict, risk_score, reasons):
    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO offers (offer_text, company_name, verdict, risk_score, reasons)
        VALUES (?, ?, ?, ?, ?)
    """, (
        offer_text,
        company_name,
        verdict,
        risk_score,
        ", ".join(reasons)
    ))

    conn.commit()
    conn.close()


# ---------------------------
# Analyze Offer API
# ---------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/analyze_offer", methods=["POST"])
def analyze_offer():

    data = request.get_json()
    offer_text = data.get("offer_text", "")
    linkedin_url = data.get("linkedin_url")

    # -------------------------
    # Extract company name
    # -------------------------
    company_name = None

    if linkedin_url:
        company_name = extract_company_from_linkedin(linkedin_url)

    if not company_name or company_name == "Unknown":
        company_name = extract_company_name(offer_text)

    # -------------------------
    # Check Community Reviews
    # -------------------------
    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fee_asked, rating
        FROM reviews
        WHERE LOWER(company_name) = LOWER(?)
    """, (company_name,))

    reviews = cursor.fetchall()
    conn.close()

    if reviews:
        total = len(reviews)
        fee_count = sum(1 for r in reviews if r[0] == 1)
        avg_rating = sum(r[1] for r in reviews) / total

        if fee_count / total > 0.5:
            verdict = "FAKE"
        elif avg_rating < 2.5:
            verdict = "SUSPICIOUS"
        else:
            verdict = "REAL"

        return jsonify({
            "source": "community",
            "company": company_name,
            "reviews_count": total,
            "verdict": verdict,
            "risk_score": round((fee_count / total) * 100, 2),
            "reasons": [
                f"{fee_count} out of {total} students reported fee requests.",
                f"Average rating: {round(avg_rating,1)}"
            ]
        })

    # -------------------------
    # Else → Use Gemini AI
    # -------------------------
    prompt = f"""
You are a job fraud detection system.

Respond ONLY with valid JSON.

Format:
{{
  "verdict": "FAKE or REAL or SUSPICIOUS",
  "risk_score": number,
  "reasons": ["reason1", "reason2"]
}}

Offer:
{offer_text}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        raw_text = response.text.strip()

        # Clean markdown safely
        raw_text = raw_text.replace("```json", "")
        raw_text = raw_text.replace("```", "")
        raw_text = raw_text.strip()

        ai_result = json.loads(raw_text)

    except Exception as e:
        print("AI ERROR:", e)

        ai_result = {
            "verdict": "SUSPICIOUS",
            "risk_score": 60,
            "reasons": [
                "Unable to complete AI verification.",
                "Offer structure appears unusual.",
                "Manual verification recommended."
            ]
        }

    # -------------------------
    # Save offer to DB
    # -------------------------
    save_offer(
        offer_text,
        company_name,
        ai_result["verdict"],
        ai_result["risk_score"],
        ai_result["reasons"]
    )

    return jsonify({
        "source": "ai",
        "company": company_name,
        "verdict": ai_result["verdict"],
        "risk_score": ai_result["risk_score"],
        "reasons": ai_result["reasons"]
    })
@app.route("/offers/company/<company_name>", methods=["GET"])
def company_analysis(company_name):

    conn = sqlite3.connect("offers.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT fee_asked, contact_method, selection_process, salary_realism, rating
    FROM reviews WHERE company_name = ?
    """, (company_name,))

    rows = cursor.fetchall()
    conn.close()

    total = len(rows)

    # -----------------------------
    # LEVEL 1: No Reviews → AI
    # -----------------------------
    if total == 0:
        return jsonify({
            "company": company_name,
            "reviews": 0,
            "decision_source": "AI",
            "message": "No community reviews available. Falling back to AI analysis."
        })

    # -----------------------------
    # WEIGHTED RISK CALCULATION
    # -----------------------------

    fee_ratio = sum(1 for r in rows if r[0] == 1) / total
    low_rating_ratio = sum(1 for r in rows if r[4] <= 2) / total

    # Weights (You can tune this later)
    risk_score = 0
    risk_score += fee_ratio * 50       # 50% weight
    risk_score += low_rating_ratio * 30  # 30% weight

    risk_score = round(risk_score, 2)

    # -----------------------------
    # VERDICT LOGIC
    # -----------------------------

    if risk_score >= 60:
        final_verdict = "FAKE"
    elif risk_score >= 30:
        final_verdict = "SUSPICIOUS"
    else:
        final_verdict = "REAL"

    # -----------------------------
    # CONFIDENCE CALCULATION
    # -----------------------------

    if total == 1:
        confidence = 30
    elif total == 2:
        confidence = 50
    elif total <= 5:
        confidence = 70
    else:
        confidence = 90

    # -----------------------------
    # DECISION SOURCE LEVEL
    # -----------------------------

    if total < 3:
        decision_source = "HYBRID"
    else:
        decision_source = "COMMUNITY"

    # -----------------------------
    # FINAL RESPONSE
    # -----------------------------

    return jsonify({
        "company": company_name,
        "reviews": total,
        "decision_source": decision_source,
        "risk_score": risk_score,
        "final_verdict": final_verdict,
        "confidence_percentage": confidence,
        "summary": f"Based on {total} verified student reviews. Risk score: {risk_score}%. Confidence level: {confidence}%."
    })



def summarize_with_rules(company_name, offers):
    total = len(offers)

    fake = 0
    suspicious = 0

    for o in offers:
        verdict = o[3].upper()
        if verdict == "FAKE":
            fake += 1
        elif verdict == "SUSPICIOUS":
            suspicious += 1

    if fake > suspicious:
        final_verdict = "FAKE"
    elif suspicious > 0:
        final_verdict = "SUSPICIOUS"
    else:
        final_verdict = "REAL"

    summary = (
        f"Based on {total} community reports for {company_name}, "
        f"the overall trust level is {final_verdict.lower()}. "
        f"Multiple students reported similar patterns."
    )

    return final_verdict, summary


@app.route("/summary/<company_name>", methods=["GET"])
def company_summary(company_name):
    try:
        offers = get_offers_by_company(company_name)
        if not offers:
            return jsonify({
                "company": company_name,
                "message": "No community data available yet."
            })
        final_verdict, summary = summarize_with_rules(company_name, offers)
        return jsonify({
            "company": company_name,
            "reports_count": len(offers),
            "final_verdict": final_verdict,
            "summary": summary
        })
    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------------------
# Run app
# ---------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
