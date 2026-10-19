
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection

app = Flask(__name__)
app.secret_key = "smart-parking-local-dev-key-change-later"

@app.route("/")
def home():
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT COUNT(*) FROM PARKING_SLOT")
        total_slots = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM PARKING_SLOT WHERE status = 'Available'"
        )
        available_slots = cursor.fetchone()[0]

        cursor.close()

        return f"""
        <html>
        <head><title>Smart Parking</title></head>
        <body>
            <h1>Smart Parking Management System</h1>
            <p>Total Parking Slots: {total_slots}</p>
            <p>Available Parking Slots: {available_slots}</p>
            <p><a href="/register">Register as a Customer</a></p>
        </body>
        </html>
        """

    except Exception as error:
        app.logger.exception("Could not load home page")
        return "Unable to load parking information. Check the server terminal.", 500

    finally:
        if connection and connection.is_connected():
            connection.close()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    password = request.form.get("password", "")

    if not name or not email or not phone or len(password) < 8:
        return "Please enter your name, email, phone, and a password of at least 8 characters.", 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        password_hash = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO CUSTOMER
                (name, email, phone, password_hash, address)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, email, phone, password_hash, address or None)
        )

        connection.commit()

        return """
        <h1>Registration Successful!</h1>
        <p>Your customer account has been created.</p>
        <a href="/">Return to Home</a>
        """

    except Exception as error:
        if connection:
            connection.rollback()

        if getattr(error, "errno", None) == 1062:
            return "This email or phone/vehicle identifier may already exist. Please check your details and try again.", 400

        app.logger.exception("Customer registration failed")
        return "Registration failed due to a server error. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT customer_id, name, password_hash "
            "FROM CUSTOMER WHERE email = %s",
            (email,)
        )

        customer = cursor.fetchone()

        if customer and check_password_hash(
            customer["password_hash"], password
        ):
            session["customer_id"] = customer["customer_id"]
            session["customer_name"] = customer["name"]

            return redirect(url_for("dashboard"))

        return "Invalid email or password. Please try again.", 401

    except Exception:
        app.logger.exception("Customer login failed")
        return "Login failed due to a server error. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
@app.route("/dashboard")
def dashboard():
    if "customer_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        customer_name=session["customer_name"]
    )

@app.route("/vehicles", methods=["GET", "POST"])
def vehicles():
    if "customer_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None
    message = ""

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if request.method == "POST":
            vehicle_number = request.form.get(
                "vehicle_number", ""
            ).strip().upper()
            vehicle_type = request.form.get(
                "vehicle_type", ""
            ).strip()
            vehicle_model = request.form.get(
                "vehicle_model", ""
            ).strip()

            if not vehicle_number or vehicle_type not in ("Car", "Bike"):
                message = "Please enter a valid vehicle number and type."
            else:
                cursor.execute(
                    """
                    INSERT INTO VEHICLE
                        (customer_id, vehicle_number,
                         vehicle_type, vehicle_model)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        session["customer_id"],
                        vehicle_number,
                        vehicle_type,
                        vehicle_model or None
                    )
                )
                connection.commit()
                message = "Vehicle added successfully!"

        cursor.execute(
            """
            SELECT vehicle_number, vehicle_type, vehicle_model
            FROM VEHICLE
            WHERE customer_id = %s
            ORDER BY vehicle_id ASC
    
            """,
            (session["customer_id"],)
        )
        customer_vehicles = cursor.fetchall()

        return render_template(
            "vehicles.html",
            vehicles=customer_vehicles,
            message=message
        )

    except Exception as error:
        if connection:
            connection.rollback()

        if getattr(error, "errno", None) == 1062:
            return "This vehicle registration number is already registered.", 400

        app.logger.exception("Could not load customer vehicles")
        return "Unable to process vehicles. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    
@app.route("/slots")
def slots():
    if "customer_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT slot_id, slot_number, slot_type, status
            FROM PARKING_SLOT
            ORDER BY slot_type, slot_number
        """)
        all_slots = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM PARKING_SLOT")
        total_slots = cursor.fetchone()["COUNT(*)"]

        cursor.execute("""
            SELECT COUNT(*) FROM PARKING_SLOT
            WHERE status = 'Available'
        """)
        available_slots = cursor.fetchone()["COUNT(*)"]

        return render_template(
            "slots.html",
            slots=all_slots,
            total_slots=total_slots,
            available_slots=available_slots,
            customer_name=session["customer_name"]
        )

    except Exception:
        app.logger.exception("Could not load parking slots")
        return "Unable to load parking slots. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

   
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/reservations", methods=["GET", "POST"])
def reservations():
    if "customer_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None
    message = ""

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        customer_id = session["customer_id"]

        if request.method == "POST":
            vehicle_id = request.form.get("vehicle_id", "")
            slot_id = request.form.get("slot_id", "")
            reservation_date = request.form.get("reservation_date", "")
            start_time = request.form.get("start_time", "")
            end_time = request.form.get("end_time", "")

            if not all([
                vehicle_id, slot_id, reservation_date,
                start_time, end_time
            ]):
                message = "Please fill in all booking fields."

            elif end_time <= start_time:
                message = "End time must be later than start time."

            else:
                # Check that the vehicle belongs to this customer.
                cursor.execute(
                    """
                    SELECT vehicle_id, vehicle_type
                    FROM VEHICLE
                    WHERE vehicle_id = %s AND customer_id = %s
                    """,
                    (vehicle_id, customer_id)
                )
                vehicle = cursor.fetchone()

                # Check that the selected slot exists and is available.
                cursor.execute(
                    """
                    SELECT slot_id, slot_type
                    FROM PARKING_SLOT
                    WHERE slot_id = %s AND status = 'Available'
                    """,
                    (slot_id,)
                )
                slot = cursor.fetchone()

                if not vehicle:
                    message = "Please select one of your registered vehicles."

                elif not slot:
                    message = "This parking slot is not available."

                elif vehicle["vehicle_type"].lower() != slot["slot_type"].lower():
                    message = "The selected slot does not match your vehicle type."

                else:
                    # Reject past dates.
                    cursor.execute(
                        "SELECT (%s < CURDATE()) AS is_past",
                        (reservation_date,)
                    )
                    date_check = cursor.fetchone()

                    if date_check["is_past"]:
                        message = "Please select today or a future date."

                    else:
                        # Check for an overlapping booking.
                        cursor.execute(
                            """
                            SELECT reservation_id
                            FROM RESERVATION
                            WHERE slot_id = %s
                              AND reservation_date = %s
                              AND status = 'Booked'
                              AND start_time < %s
                              AND end_time > %s
                            """,
                            (
                                slot_id,
                                reservation_date,
                                end_time,
                                start_time
                            )
                        )
                        conflict = cursor.fetchone()

                        if conflict:
                            message = (
                                "This slot is already booked "
                                "during that time. Choose another time or slot."
                            )
                        else:
                            cursor.execute(
                                """
                                INSERT INTO RESERVATION
                                    (customer_id, vehicle_id, slot_id,
                                     reservation_date, start_time,
                                     end_time, status)
                                VALUES (%s, %s, %s, %s, %s, %s, 'Booked')
                                """,
                                (
                                    customer_id,
                                    vehicle_id,
                                    slot_id,
                                    reservation_date,
                                    start_time,
                                    end_time
                                )
                            )
                            connection.commit()
                            message = "Parking reservation created successfully!"

        # Load this customer's vehicles.
        cursor.execute(
            """
            SELECT vehicle_id, vehicle_number, vehicle_type
            FROM VEHICLE
            WHERE customer_id = %s
            ORDER BY vehicle_id ASC
            """,
            (customer_id,)
        )
        customer_vehicles = cursor.fetchall()

        # Show available slots.
        cursor.execute(
            """
            SELECT slot_id, slot_number, slot_type
            FROM PARKING_SLOT
            WHERE status = 'Available'
            ORDER BY slot_type, slot_number
            """
        )
        available_slots = cursor.fetchall()

        # Load this customer's reservation history.
        cursor.execute(
            """
            SELECT r.reservation_date, r.start_time, r.end_time,
                   r.status, p.slot_number, v.vehicle_number
            FROM RESERVATION r
            JOIN PARKING_SLOT p ON r.slot_id = p.slot_id
            JOIN VEHICLE v ON r.vehicle_id = v.vehicle_id
            WHERE r.customer_id = %s
            ORDER BY r.reservation_id ASC
            """,
            (customer_id,)
        )
        customer_reservations = cursor.fetchall()

        return render_template(
            "reservations.html",
            vehicles=customer_vehicles,
            slots=available_slots,
            reservations=customer_reservations,
            message=message
        )

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Reservation processing failed")
        return "Unable to process reservation. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


@app.route("/history")
def history():
    if "customer_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                v.vehicle_number,
                s.slot_number,
                e.entry_time,
                e.exit_time,
                e.status,
                SUM(p.amount) AS amount_paid
            FROM PARKING_ENTRY e
            JOIN VEHICLE v
                ON e.vehicle_id = v.vehicle_id
            JOIN PARKING_SLOT s
                ON e.slot_id = s.slot_id
            JOIN VEHICLE customer_vehicle
                ON customer_vehicle.vehicle_id = e.vehicle_id
            LEFT JOIN PAYMENT p
                ON p.entry_id = e.entry_id
                AND p.payment_status = 'Paid'
            WHERE customer_vehicle.customer_id = %s
            GROUP BY
                e.entry_id,
                v.vehicle_number,
                s.slot_number,
                e.entry_time,
                e.exit_time,
                e.status
            ORDER BY e.entry_time ASC
            """,
            (session["customer_id"],)
        )

        parking_history = cursor.fetchall()

        return render_template(
            "history.html",
            history=parking_history,
            customer_name=session["customer_name"]
        )

    except Exception:
        app.logger.exception("Could not load parking history")
        return "Unable to load parking history. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

    
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html", message="")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT staff_id, name, email, password_hash, role
            FROM STAFF
            WHERE email = %s
            """,
            (email,)
        )
        staff = cursor.fetchone()

        if (
            staff
            and staff["role"].lower() == "admin"
            and check_password_hash(staff["password_hash"], password)
        ):
            session["staff_id"] = staff["staff_id"]
            session["staff_name"] = staff["name"]
            session["staff_role"] = staff["role"]

            return redirect(url_for("admin_dashboard"))

        return render_template(
            "admin_login.html",
            message="Invalid admin credentials."
        ), 401

    except Exception:
        app.logger.exception("Admin login failed")
        return "Unable to process admin login. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


@app.route("/admin-dashboard")
def admin_dashboard():
    if "staff_id" not in session or session.get("staff_role", "").lower() != "admin":
        return redirect(url_for("admin_login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM PARKING_SLOT")
        total_slots = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS total FROM PARKING_SLOT WHERE status = 'Available'"
        )
        available_slots = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM CUSTOMER")
        total_customers = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM VEHICLE")
        total_vehicles = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM RESERVATION")
        total_reservations = cursor.fetchone()["total"]

        
        cursor.execute("""
            SELECT
                COALESCE(SUM(amount), 0) AS total_revenue,
                COUNT(*) AS total_payments
            FROM PAYMENT
            WHERE payment_status = 'Paid'
        """)
        payment_summary = cursor.fetchone()

        total_revenue = float(payment_summary["total_revenue"])
        total_payments = payment_summary["total_payments"]

        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE
                    WHEN LOWER(payment_method) = 'cash'
                    THEN amount ELSE 0
                END), 0) AS cash_revenue,
                COALESCE(SUM(CASE
                    WHEN LOWER(payment_method) = 'upi'
                    THEN amount ELSE 0
                END), 0) AS upi_revenue
            FROM PAYMENT
            WHERE payment_status = 'Paid'
        """)
        method_summary = cursor.fetchone()

        cash_revenue = float(method_summary["cash_revenue"])
        upi_revenue = float(method_summary["upi_revenue"])


        
        return render_template(
            "admin_dashboard.html",
            staff_name=session["staff_name"],
            total_slots=total_slots,
            available_slots=available_slots,
            total_customers=total_customers,
            total_vehicles=total_vehicles,
            total_reservations=total_reservations,
            total_revenue=total_revenue,
            total_payments=total_payments,
            cash_revenue=cash_revenue,
            upi_revenue=upi_revenue
        )


    except Exception:
        app.logger.exception("Could not load admin dashboard")
        return "Unable to load admin dashboard. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

            

@app.route("/admin-payments")
def admin_payments():
    if "staff_id" not in session or session.get("staff_role", "").lower() != "admin":
        return redirect(url_for("admin_login"))
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            p.payment_id,
            p.entry_id,
            p.amount,
            p.payment_method,
            p.payment_status,
            p.payment_date,
            c.name AS customer_name,
            v.vehicle_number,
            pe.entry_time,
            pe.exit_time
        FROM PAYMENT p
        JOIN PARKING_ENTRY pe
            ON p.entry_id = pe.entry_id
        JOIN VEHICLE v
            ON pe.vehicle_id = v.vehicle_id
        JOIN CUSTOMER c
            ON v.customer_id = c.customer_id
        ORDER BY p.payment_id ASC
    """)

    payments = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template(
        "admin_payments.html",
        payments=payments
    )



@app.route("/admin-logout")
def admin_logout():
    session.pop("staff_id", None)
    session.pop("staff_name", None)
    session.pop("staff_role", None)
    return redirect(url_for("admin_login"))


@app.route("/admin-reservations")
def admin_reservations():
    if "staff_id" not in session or session.get("staff_role", "").lower() != "admin":
        return redirect(url_for("admin_login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.reservation_id,
                   r.reservation_date,
                   r.start_time,
                   r.end_time,
                   r.status,
                   c.name AS customer_name,
                   c.phone AS customer_phone,
                   v.vehicle_number,
                   v.vehicle_type,
                   p.slot_number
            FROM RESERVATION r
            JOIN CUSTOMER c ON r.customer_id = c.customer_id
            JOIN VEHICLE v ON r.vehicle_id = v.vehicle_id
            JOIN PARKING_SLOT p ON r.slot_id = p.slot_id
            ORDER BY r.reservation_id ASC
        """)

        reservations = cursor.fetchall()

        return render_template(
            "admin_reservations.html",
            reservations=reservations
        )

    except Exception:
        app.logger.exception("Could not load admin reservations")
        return "Unable to load reservations. Check the VS Code terminal.", 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route("/admin-slots")
def admin_slots():
    if "staff_id" not in session or session.get("staff_role", "").lower() != "admin":
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT slot_id, slot_number, slot_type, status
        FROM PARKING_SLOT
        ORDER BY slot_id ASC
    """)

    slots = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("admin_slots.html", slots=slots)

@app.route("/admin-update-slot/<int:slot_id>", methods=["POST"])
def admin_update_slot(slot_id):
    if "staff_id" not in session or session.get("staff_role", "").lower() != "admin":
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status")

    if new_status not in ["Available", "Unavailable"]:
        return redirect(url_for("admin_slots"))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT status FROM PARKING_SLOT WHERE slot_id = %s FOR UPDATE",
            (slot_id,)
        )
        slot = cursor.fetchone()

        if slot is None:
            connection.rollback()
            return redirect(url_for("admin_slots"))

        if new_status == "Available":
            cursor.execute(
                """
                SELECT COUNT(*) FROM PARKING_ENTRY
                WHERE slot_id = %s AND status = 'Parked'
                """,
                (slot_id,)
            )
            active_entry = cursor.fetchone()[0]

            if active_entry > 0:
                connection.rollback()
                return (
                    "This slot cannot be marked Available because a vehicle is parked in it.",
                    400
                )

        cursor.execute(
            "UPDATE PARKING_SLOT SET status = %s WHERE slot_id = %s",
            (new_status, slot_id)
        )
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("admin_slots"))


@app.route("/admin-customers")
def admin_customers():
    if "staff_id" not in session or session.get("staff_role", "").lower() != "admin":
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                c.customer_id,
                c.name,
                c.email,
                c.phone,
                COUNT(v.vehicle_id) AS vehicle_count
            FROM CUSTOMER c
            LEFT JOIN VEHICLE v
                ON c.customer_id = v.customer_id
            GROUP BY
                c.customer_id,
                c.name,
                c.email,
                c.phone
            ORDER BY c.customer_id ASC
        """)

        customers = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "admin_customers.html",
        customers=customers
    )


@app.route("/admin-vehicles")
def admin_vehicles():
    if "staff_id" not in session or session.get("staff_role", "").lower() != "admin":
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                v.vehicle_id,
                c.name AS customer_name,
                v.vehicle_number,
                v.vehicle_type,
                v.vehicle_model
            FROM VEHICLE v
            INNER JOIN CUSTOMER c
                ON v.customer_id = c.customer_id
            ORDER BY v.vehicle_id ASC
        """)

        vehicles = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "admin_vehicles.html",
        vehicles=vehicles
    )


@app.route("/admin-parking", methods=["GET", "POST"])
def admin_parking():
    if "staff_id" not in session or session.get("staff_role", "").lower() != "admin":
        return redirect(url_for("admin_login"))

    message = ""

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if request.method == "POST":
            action = request.form.get("action")

            if action == "entry":
                vehicle_id = request.form.get("vehicle_id", type=int)
                slot_id = request.form.get("slot_id", type=int)

                if not vehicle_id or not slot_id:
                    message = "Please select a vehicle and parking slot."
                else:
                    # Lock the selected slot while checking and assigning it.
                    connection.start_transaction()

                    cursor.execute(
                        """
                        SELECT slot_id, slot_type, status
                        FROM PARKING_SLOT
                        WHERE slot_id = %s
                        FOR UPDATE
                        """,
                        (slot_id,)
                    )
                    slot = cursor.fetchone()

                    cursor.execute(
                        """
                        SELECT vehicle_id, vehicle_type
                        FROM VEHICLE
                        WHERE vehicle_id = %s
                        """,
                        (vehicle_id,)
                    )
                    vehicle = cursor.fetchone()

                    cursor.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM PARKING_ENTRY
                        WHERE vehicle_id = %s AND status = 'Parked'
                        """,
                        (vehicle_id,)
                    )
                    already_parked = cursor.fetchone()["total"]

                    cursor.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM PARKING_ENTRY
                        WHERE slot_id = %s AND status = 'Parked'
                        """,
                        (slot_id,)
                    )
                    slot_occupied = cursor.fetchone()["total"]

                    if not slot or not vehicle:
                        connection.rollback()
                        message = "Selected vehicle or slot was not found."
                    elif slot["status"] != "Available":
                        connection.rollback()
                        message = "This slot is not available."
                    elif slot_occupied > 0:
                        connection.rollback()
                        message = "A vehicle is already parked in this slot."
                    elif already_parked > 0:
                        connection.rollback()
                        message = "This vehicle is already parked."
                    elif slot["slot_type"].lower() != vehicle["vehicle_type"].lower():
                        connection.rollback()
                        message = "Vehicle type does not match the selected slot."
                    else:
                        cursor.execute(
                            """
                            INSERT INTO PARKING_ENTRY
                                (vehicle_id, slot_id, entry_time, status)
                            VALUES (%s, %s, NOW(), 'Parked')
                            """,
                            (vehicle_id, slot_id)
                        )

                        cursor.execute(
                            """
                            UPDATE PARKING_SLOT
                            SET status = 'Unavailable'
                            WHERE slot_id = %s
                            """,
                            (slot_id,)
                        )

                        connection.commit()
                        message = "Vehicle entry recorded successfully."

            
            elif action == "exit":
                entry_id = request.form.get("entry_id", type=int)

                if not entry_id:
                    message = "Invalid parking entry."
                else:
                    connection.start_transaction()

                    try:
                        cursor.execute(
                            """
                            SELECT pe.entry_id, pe.slot_id, pe.entry_time,
                                   v.vehicle_type
                            FROM PARKING_ENTRY pe
                            JOIN VEHICLE v ON pe.vehicle_id = v.vehicle_id
                            WHERE pe.entry_id = %s
                              AND pe.status = 'Parked'
                            FOR UPDATE
                            """,
                            (entry_id,)
                        )
                        entry = cursor.fetchone()

                        if not entry:
                            connection.rollback()
                            message = "This parking session is not active."
                        else:
                            cursor.execute(
                                """
                                SELECT rate_per_hour
                                FROM PARKING_RATE
                                WHERE LOWER(vehicle_type) = LOWER(%s)
                                ORDER BY effective_from DESC
                                LIMIT 1
                                """,
                                (entry["vehicle_type"],)
                            )
                            rate_row = cursor.fetchone()

                            if not rate_row:
                                connection.rollback()
                                message = "No parking rate found for this vehicle type."
                            else:
                                cursor.execute(
                                    """
                                    SELECT TIMESTAMPDIFF(
                                        MICROSECOND, entry_time, NOW()
                                    ) / 1000000.0 AS duration_seconds
                                    FROM PARKING_ENTRY
                                    WHERE entry_id = %s
                                    """,
                                    (entry_id,)
                                )
                                duration = cursor.fetchone()["duration_seconds"]

                                if duration is None or duration < 0:
                                    connection.rollback()
                                    message = "Unable to calculate parking duration."
                                else:
                                    rate = float(rate_row["rate_per_hour"])
                                    amount = round(
                                        (float(duration) / 3600.0) * rate, 2
                                    )

                                    cursor.execute(
                                        """
                                        UPDATE PARKING_ENTRY
                                        SET exit_time = NOW(), status = 'Completed'
                                        WHERE entry_id = %s
                                          AND status = 'Parked'
                                        """,
                                        (entry_id,)
                                    )

                                    cursor.execute(
                                        """
                                        INSERT INTO PAYMENT
                                            (entry_id, amount, payment_method,
                                             payment_status)
                                        VALUES (%s, %s, 'Cash', 'Paid')
                                        """,
                                        (entry_id, amount)
                                    )

                                    cursor.execute(
                                        """
                                        UPDATE PARKING_SLOT
                                        SET status = 'Available'
                                        WHERE slot_id = %s
                                        """,
                                        (entry["slot_id"],)
                                    )

                                    connection.commit()
                                    message = (
                                        f"Vehicle exit recorded successfully. "
                                        f"Parking fee: ₹{amount:.2f}"
                                    )

                    except Exception:
                        connection.rollback()
                        app.logger.exception("Vehicle exit and fee calculation failed")
                        message = "Vehicle exit failed. Please check the server log."



            else:
                message = "Invalid operation."

        cursor.execute(
            """
            SELECT v.vehicle_id, v.vehicle_number, v.vehicle_type,
                   c.name AS customer_name
            FROM VEHICLE v
            JOIN CUSTOMER c ON v.customer_id = c.customer_id
            ORDER BY v.vehicle_number
            """
        )
        vehicles = cursor.fetchall()

        cursor.execute(
            """
            SELECT slot_id, slot_number, slot_type
            FROM PARKING_SLOT
            WHERE status = 'Available'
            ORDER BY slot_type, slot_number
            """
        )
        available_slots = cursor.fetchall()

        cursor.execute(
            """
            SELECT pe.entry_id, pe.entry_time,
                   v.vehicle_number, v.vehicle_type,
                   ps.slot_number
            FROM PARKING_ENTRY pe
            JOIN VEHICLE v ON pe.vehicle_id = v.vehicle_id
            JOIN PARKING_SLOT ps ON pe.slot_id = ps.slot_id
            WHERE pe.status = 'Parked'
            ORDER BY pe.entry_time
            """
        )
        active_entries = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "admin_parking.html",
        message=message,
        vehicles=vehicles,
        available_slots=available_slots,
        active_entries=active_entries
    )

if __name__ == "__main__":
    app.run(debug=True)