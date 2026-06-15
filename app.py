from flask import Flask, render_template, request, jsonify, redirect
import mysql.connector
import random

app = Flask(__name__)

# ---------------- DB CONNECTION ----------------

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="restaurant_db",
        port=3306
    )

# ---------------- TEST ROUTES ----------------

@app.route('/test')
def test():
    return "Backend is working!"

@app.route('/db_test')
def db_test():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        return "MySQL Connected Successfully!"
    except Exception as e:
        return f"Database Connection Failed: {e}"

# ---------------- HOME PAGES ----------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/order')
def order():
    return render_template('order.html')

@app.route('/reservation')
def reservation():
    return render_template('reservation.html')

@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/employee')
def employee():
    return render_template('employee.html')

@app.route('/customer')
def customer():
    return render_template('customerindex.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# ---------------- ANALYTICS ----------------

@app.route('/analytics')
def analytics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT SUM(total_amount) AS revenue FROM orders")
    revenue = cursor.fetchone()['revenue'] or 0

    cursor.execute("""
        SELECT DATE(order_date) AS date,
               SUM(total_amount) AS amount
        FROM orders
        GROUP BY DATE(order_date)
        ORDER BY DATE(order_date)
    """)
    daily_revenue = cursor.fetchall()

    dates = [str(row['date']) for row in daily_revenue]
    amounts = [float(row['amount']) for row in daily_revenue]

    cursor.execute("SELECT COUNT(*) AS orders FROM orders")
    orders = cursor.fetchone()['orders']

    cursor.execute("SELECT SUM(quantity) AS items_sold FROM order_items")
    items = cursor.fetchone()['items_sold'] or 0

    conn.close()

    return render_template(
        "analytics.html",
        revenue=revenue,
        orders=orders,
        items=items,
        dates=dates,
        amounts=amounts
    )

# ---------------- VIEW ORDERS ----------------

@app.route('/view_orders')
def show_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT order_id, bill_no, order_date, total_amount
        FROM orders
        ORDER BY order_id DESC
    """)

    orders = cursor.fetchall()
    conn.close()

    return render_template('view_orders.html', orders=orders)

# ---------------- PLACE ORDER ----------------

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        print("PLACE ORDER HIT")

        data = request.json
        print(data)

        items = data['items']
        total = data['total']

        conn = get_db_connection()
        cursor = conn.cursor()

        bill_no = random.randint(10000, 99999)

        cursor.execute(
            "INSERT INTO orders (bill_no, total_amount) VALUES (%s, %s)",
            (bill_no, total)
        )
        order_id = cursor.lastrowid
        print(f"ORDER INSERTED — order_id={order_id}")

        for item in items:
            item_id    = item['item_id']
            quantity   = item['quantity']
            item_price = item['price']
            subtotal   = round(quantity * item_price, 2)

            cursor.execute(
                """INSERT INTO order_items
                   (order_id, item_id, quantity, item_price, subtotal)
                   VALUES (%s, %s, %s, %s, %s)""",
                (order_id, item_id, quantity, item_price, subtotal)
            )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "order_id": order_id
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({
            "success": False,
            "error": str(e)
        })

# ---------------- ORDER DETAILS ----------------

@app.route('/order/<int:order_id>')
def order_details(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM orders WHERE order_id=%s",
        (order_id,)
    )
    order = cursor.fetchone()

    cursor.execute("""
        SELECT m.item_name,
               oi.quantity,
               oi.item_price,
               oi.subtotal
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.item_id
        WHERE oi.order_id = %s
    """, (order_id,))

    items = cursor.fetchall()
    conn.close()

    return render_template(
        "order_details.html",
        order=order,
        items=items
    )

# ---------------- BILL PAGE ----------------

@app.route('/bill/<int:order_id>')
def bill(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM orders WHERE order_id=%s",
        (order_id,)
    )
    order = cursor.fetchone()

    cursor.execute("""
        SELECT m.item_name,
               oi.quantity,
               oi.item_price,
               oi.subtotal
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.item_id
        WHERE oi.order_id = %s
    """, (order_id,))

    items = cursor.fetchall()
    conn.close()

    return render_template(
        "bill.html",
        order=order,
        items=items
    )

# ---------------- DELETE ORDER ----------------

@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM order_items WHERE order_id=%s",
        (order_id,)
    )
    cursor.execute(
        "DELETE FROM orders WHERE order_id=%s",
        (order_id,)
    )

    conn.commit()
    conn.close()

    return redirect('/view_orders')
# ---------------- RESERVATIONS ----------------

@app.route('/book_reservation', methods=['POST'])
def book_reservation():
    try:
        data = request.get_json()

        customer_name = data['customer_name']
        date          = data['date']
        time          = data['time']
        people        = data['people']
        table_number  = random.randint(1, 20)

        conn = get_db_connection()
        cursor = conn.cursor()

        # First, insert customer if not exists, or get existing customer_id
        cursor.execute(
            "SELECT customer_id FROM customers WHERE customer_name = %s LIMIT 1",
            (customer_name,)
        )
        customer = cursor.fetchone()

        if customer:
            customer_id = customer[0]
        else:
            cursor.execute(
                "INSERT INTO customers (customer_name) VALUES (%s)",
                (customer_name,)
            )
            customer_id = cursor.lastrowid

        # Insert reservation
        cursor.execute("""
            INSERT INTO reservations 
                (customer_id, reservation_date, reservation_time, number_of_people, table_number)
            VALUES (%s, %s, %s, %s, %s)
        """, (customer_id, date, time, people, table_number))

        conn.commit()
        reservation_id = cursor.lastrowid
        conn.close()

        return jsonify({
            "success": True,
            "table_number": table_number,
            "reservation_id": reservation_id
        })

    except Exception as e:
        print("RESERVATION ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500
    
# ---------------- SUBMIT FEEDBACK ----------------
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.get_json()

        customer_name = data['name']
        order_input   = data['order']
        feedback_text = data['feedback']
        mood          = data['mood']
        rating        = data['rating']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if order_id exists — if not, set to NULL
        order_id = None
        if order_input:
            cursor.execute("SELECT order_id FROM orders WHERE order_id = %s OR bill_no = %s",
                           (order_input, order_input))
            row = cursor.fetchone()
            if row:
                order_id = row[0]

        cursor.execute(
            """INSERT INTO feedback
               (customer_name, order_id, feedback_text, mood, rating)
               VALUES (%s, %s, %s, %s, %s)""",
            (customer_name, order_id, feedback_text, mood, rating)
        )

        conn.commit()
        conn.close()

        return jsonify({"message": "Feedback saved successfully"})

    except Exception as e:
        print("FEEDBACK ERROR:", e)
        return jsonify({"error": str(e)}), 500


# ---------------- EMPLOYEES ----------------

@app.route('/get_employees')
def get_employees():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees ORDER BY employee_id")
    employees = cursor.fetchall()
    conn.close()
    return jsonify(employees)

@app.route('/add_employee', methods=['POST'])
def add_employee():
    data = request.json
    manager = data.get('manager')
    if manager == '' or manager is None:
        manager = None
    else:
        manager = int(manager)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO employees (employee_name, role, manager_id, salary, bonus)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        data['name'],
        data['role'],
        manager,
        data['salary'],
        data['bonus']
    ))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/update_employee/<int:emp_id>', methods=['POST'])
def update_employee(emp_id):
    data = request.json
    manager = data.get('manager')
    if manager == '' or manager is None:
        manager = None
    else:
        manager = int(manager)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE employees
        SET employee_name=%s, role=%s, manager_id=%s, salary=%s, bonus=%s
        WHERE employee_id=%s
    """, (
        data['name'],
        data['role'],
        manager,
        data['salary'],
        data['bonus'],
        emp_id
    ))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/delete_employee/<int:emp_id>', methods=['POST'])
def delete_employee(emp_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM employees WHERE employee_id=%s", (emp_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ---------------- API TEST ----------------

@app.route('/api/test')
def api_test():
    return jsonify({"message": "Frontend connected successfully"})

# ---------------- RUN APP ----------------

if __name__ == "__main__":
    app.run(debug=True)
