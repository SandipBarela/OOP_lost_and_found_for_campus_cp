from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from abc import ABC, abstractmethod
import html

# ==============================================================================
# MEMBER 1: DATA MODELS & OOP PILLARS (Abstraction, Encapsulation, Inheritance)
# ==============================================================================

# 1. ABSTRACTION: Abstract Base Class defining a blueprint for all portal records
class BaseRecord(ABC):
    def __init__(self, record_id, title):
        self.record_id = record_id
        self.title = title

    @abstractmethod
    def get_summary(self):
        """Subclasses MUST implement their own version of this method."""
        pass


# 2. ENCAPSULATION: Protecting sensitive user data (password) using private attributes
class User:
    def __init__(self, email, password, name, role="user"):
        self.email = email
        self.__password = password  # Private attribute (Encapsulation)
        self.name = name
        self.role = role            # "user" or "admin"

    # Public getter/verifier method to safely access private password
    def check_password(self, input_password):
        return self.__password == input_password


# 3. INHERITANCE & POLYMORPHISM: Item inherits from BaseRecord
class Item(BaseRecord):
    def __init__(self, item_id, title, description, location, category, reported_by):
        super().__init__(item_id, title)  # Calling Parent Class Constructor
        self.description = description
        self.location = location
        self.category = category          # "Lost" or "Found"
        self.reported_by = reported_by
        self.status = "Open"              # "Open", "Claimed", or "Resolved"
        self.claimed_by = None

    # POLYMORPHISM: Overriding the abstract method from BaseRecord
    def get_summary(self):
        return f"[{self.category.upper()}] {self.title} at {self.location} ({self.status})"


# ==============================================================================
# MEMBER 2: DATABASE / STATE MANAGER (Classes, Objects & CRUD Operations)
# ==============================================================================

class PortalDatabase:
    def __init__(self):
        # Creating User Objects (Pre-loaded with 1 Admin and 2 Basic Users)
        self.users = {
            "admin@campus.edu": User("admin@campus.edu", "admin123", "Campus Admin", "admin"),
            "student1@campus.edu": User("student1@campus.edu", "pass123", "Aarav (Student 1)", "user"),
            "student2@campus.edu": User("student2@campus.edu", "pass123", "Diya (Student 2)", "user"),
        }
        self.items = []
        self.next_id = 1
        self.logged_in_user = None  # Tracks active session user object

        # Seed initial sample items (Object Construction)
        self.add_item("Blue Water Bottle", "Steel bottle with sticker", "Library 2nd Floor", "Lost", "student1@campus.edu")
        self.add_item("Scientific Calculator", "Casio fx-991EX", "Lab 304", "Found", "student2@campus.edu")

    def authenticate(self, email, password):
        user = self.users.get(email)
        if user and user.check_password(password):
            self.logged_in_user = user
            return True
        return False

    def add_item(self, title, description, location, category, reported_by):
        # Object Construction: Instantiating a new Item object
        new_item = Item(self.next_id, title, description, location, category, reported_by)
        self.items.append(new_item)
        self.next_id += 1

    def claim_item(self, item_id, claimant_email):
        for item in self.items:
            if item.record_id == item_id and item.status == "Open":
                item.status = "Claimed"
                item.claimed_by = claimant_email
                break

    def resolve_item(self, item_id):
        for item in self.items:
            if item.record_id == item_id:
                item.status = "Resolved"
                break

    def delete_item(self, item_id):
        self.items = [item for item in self.items if item.record_id != item_id]

    def search_items(self, query):
        if not query:
            return self.items
        q = query.lower()
        return [
            i for i in self.items
            if q in i.title.lower() or q in i.location.lower() or q in i.description.lower()
        ]


# ==============================================================================
# MEMBER 3: HTML / MINIMAL CSS & JS VIEW GENERATOR (Presentation Layer)
# ==============================================================================

class ViewRenderer:
    @staticmethod
    def layout(title, body_content):
        # Minimalistic CSS + tiny JS confirmation helper
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 850px; margin: 30px auto; padding: 0 15px; background: #f9f9f9; color: #222; }}
        header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
        .card {{ background: #fff; padding: 15px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 15px; }}
        input, select, button {{ padding: 8px; margin: 4px 0; border: 1px solid #ccc; border-radius: 4px; }}
        button {{ background: #222; color: #fff; cursor: pointer; border: none; }}
        button:hover {{ background: #444; }}
        .btn-claim {{ background: #0066cc; }}
        .btn-danger {{ background: #cc0000; }}
        .btn-success {{ background: #28a745; }}
        table {{ width: 100%; border-collapse: collapse; background: #fff; }}
        th, td {{ padding: 10px; border: 1px solid #ddd; text-align: left; }}
        th {{ background: #eee; }}
        .badge-Lost {{ color: #cc0000; font-weight: bold; }}
        .badge-Found {{ color: #28a745; font-weight: bold; }}
    </style>
    <script>
        function confirmAction(msg) {{ return confirm(msg); }}
    </script>
</head>
<body>
    {body_content}
</body>
</html>"""

    @staticmethod
    def login_page(error=""):
        err_html = f"<p style='color:red;'>{error}</p>" if error else ""
        content = f"""
        <div class="card" style="max-width: 400px; margin: 60px auto;">
            <h2>Campus Lost & Found Login</h2>
            {err_html}
            <form method="POST" action="/login">
                <label>Email:</label><br>
                <input type="email" name="email" required style="width:95%;"><br>
                <label>Password:</label><br>
                <input type="password" name="password" required style="width:95%;"><br><br>
                <button type="submit" style="width:100%;">Login</button>
            </form>
            <hr>
            <small>
                <b>Demo Accounts:</b><br>
                Admin: admin@campus.edu / admin123<br>
                User 1: student1@campus.edu / pass123<br>
                User 2: student2@campus.edu / pass123
            </small>
        </div>
        """
        return ViewRenderer.layout("Login - Lost & Found", content)

    @staticmethod
    def user_dashboard(user, items, search_query=""):
        rows = ""
        for item in items:
            # Demonstrating Polymorphism: calling item.get_summary()
            summary_tip = html.escape(item.get_summary())
            action_btn = "-"
            if item.status == "Open" and item.reported_by != user.email:
                action_btn = f"""
                <form method="POST" action="/claim" style="display:inline;" onsubmit="return confirmAction('Claim this item?');">
                    <input type="hidden" name="item_id" value="{item.record_id}">
                    <button type="submit" class="btn-claim">Claim</button>
                </form>"""
            elif item.status == "Claimed":
                action_btn = f"<small>Claimed by {html.escape(item.claimed_by)}</small>"

            rows += f"""
            <tr title="{summary_tip}">
                <td><span class="badge-{item.category}">{item.category}</span></td>
                <td><b>{html.escape(item.title)}</b><br><small>{html.escape(item.description)}</small></td>
                <td>{html.escape(item.location)}</td>
                <td>{item.status}</td>
                <td>{action_btn}</td>
            </tr>"""

        content = f"""
        <header>
            <h2>Lost & Found Portal</h2>
            <div>Welcome, <b>{html.escape(user.name)}</b> | <a href="/logout">Logout</a></div>
        </header>

        <div class="card">
            <h3>Report Lost or Found Item</h3>
            <form method="POST" action="/report">
                <select name="category" required>
                    <option value="Lost">Lost Item</option>
                    <option value="Found">Found Item</option>
                </select>
                <input type="text" name="title" placeholder="Item Name (e.g., Keys)" required>
                <input type="text" name="location" placeholder="Location (e.g., Canteen)" required>
                <input type="text" name="description" placeholder="Short Description" required>
                <button type="submit">Submit Report</button>
            </form>
        </div>

        <div class="card">
            <h3>Search & Browse Items</h3>
            <form method="GET" action="/dashboard">
                <input type="text" name="q" value="{html.escape(search_query)}" placeholder="Search by name, location..." style="width:70%;">
                <button type="submit">Search</button>
                <a href="/dashboard"><button type="button">Reset</button></a>
            </form>
            <br>
            <table>
                <tr><th>Type</th><th>Item Details</th><th>Location</th><th>Status</th><th>Action</th></tr>
                {rows if rows else "<tr><td colspan='5'>No items found.</td></tr>"}
            </table>
        </div>
        """
        return ViewRenderer.layout("User Dashboard", content)

    @staticmethod
    def admin_dashboard(user, items):
        rows = ""
        for item in items:
            rows += f"""
            <tr>
                <td>#{item.record_id}</td>
                <td><span class="badge-{item.category}">{item.category}</span></td>
                <td><b>{html.escape(item.title)}</b> ({html.escape(item.location)})<br><small>By: {html.escape(item.reported_by)}</small></td>
                <td>{item.status} {f'({html.escape(item.claimed_by)})' if item.claimed_by else ''}</td>
                <td>
                    <form method="POST" action="/admin/resolve" style="display:inline;">
                        <input type="hidden" name="item_id" value="{item.record_id}">
                        <button type="submit" class="btn-success">Mark Resolved</button>
                    </form>
                    <form method="POST" action="/admin/delete" style="display:inline;" onsubmit="return confirmAction('Delete this record?');">
                        <input type="hidden" name="item_id" value="{item.record_id}">
                        <button type="submit" class="btn-danger">Delete</button>
                    </form>
                </td>
            </tr>"""

        content = f"""
        <header>
            <h2>Admin Control Panel</h2>
            <div>Logged in as <b>{html.escape(user.name)}</b> | <a href="/logout">Logout</a></div>
        </header>
        <div class="card">
            <h3>All Portal Records ({len(items)})</h3>
            <table>
                <tr><th>ID</th><th>Type</th><th>Item & Reporter</th><th>Status</th><th>Admin Controls</th></tr>
                {rows if rows else "<tr><td colspan='5'>No records available.</td></tr>"}
            </table>
        </div>
        """
        return ViewRenderer.layout("Admin Panel", content)


# ==============================================================================
# MEMBER 4: HTTP REQUEST CONTROLLER (Routing & Inheritance from BaseHTTPRequestHandler)
# ==============================================================================

# Global instance (Object) of PortalDatabase
db = PortalDatabase()

# INHERITANCE: PortalHandler inherits from Python's built-in BaseHTTPRequestHandler
class PortalHandler(BaseHTTPRequestHandler):

    def send_html(self, html_content):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        # Parse URL and query string
        path, _, query_string = self.path.partition("?")
        params = parse_qs(query_string)

        if path == "/" or path == "/login":
            self.send_html(ViewRenderer.login_page())

        elif path == "/logout":
            db.logged_in_user = None
            self.redirect("/login")

        elif path == "/dashboard":
            if not db.logged_in_user or db.logged_in_user.role != "user":
                return self.redirect("/login")
            q = params.get("q", [""])[0]
            filtered_items = db.search_items(q)
            self.send_html(ViewRenderer.user_dashboard(db.logged_in_user, filtered_items, q))

        elif path == "/admin":
            if not db.logged_in_user or db.logged_in_user.role != "admin":
                return self.redirect("/login")
            self.send_html(ViewRenderer.admin_dashboard(db.logged_in_user, db.items))

        else:
            self.redirect("/login")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = parse_qs(self.rfile.read(content_length).decode("utf-8"))

        if self.path == "/login":
            email = post_data.get("email", [""])[0]
            password = post_data.get("password", [""])[0]
            if db.authenticate(email, password):
                if db.logged_in_user.role == "admin":
                    self.redirect("/admin")
                else:
                    self.redirect("/dashboard")
            else:
                self.send_html(ViewRenderer.login_page("Invalid email or password!"))

        elif self.path == "/report" and db.logged_in_user:
            db.add_item(
                title=post_data.get("title", [""])[0],
                description=post_data.get("description", [""])[0],
                location=post_data.get("location", [""])[0],
                category=post_data.get("category", ["Lost"])[0],
                reported_by=db.logged_in_user.email
            )
            self.redirect("/dashboard")

        elif self.path == "/claim" and db.logged_in_user:
            item_id = int(post_data.get("item_id", [0])[0])
            db.claim_item(item_id, db.logged_in_user.email)
            self.redirect("/dashboard")

        elif self.path == "/admin/resolve" and db.logged_in_user and db.logged_in_user.role == "admin":
            item_id = int(post_data.get("item_id", [0])[0])
            db.resolve_item(item_id)
            self.redirect("/admin")

        elif self.path == "/admin/delete" and db.logged_in_user and db.logged_in_user.role == "admin":
            item_id = int(post_data.get("item_id", [0])[0])
            db.delete_item(item_id)
            self.redirect("/admin")

        else:
            self.redirect("/login")


if __name__ == "__main__":
    server = HTTPServer(("localhost", 8000), PortalHandler)
    print("Server started at http://localhost:8000")
    server.serve_forever()