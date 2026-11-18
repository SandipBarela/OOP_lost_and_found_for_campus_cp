from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from abc import ABC, abstractmethod
import html
import os
import base64
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://kwbnyltlonlakyfyluzl.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Initialize Supabase Client
supabase_client = None
if SUPABASE_KEY and SUPABASE_KEY != "paste_your_anon_key_here":
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Connected to Supabase successfully!")
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")
else:
    print("[NOTE] SUPABASE_KEY not set in .env. Running in local fallback mode.")

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
    def __init__(self, item_id, title, description, location, category, reported_by, image_data=""):
        super().__init__(item_id, title)  # Calling Parent Class Constructor
        self.description = description
        self.location = location
        self.category = category          # "Lost" or "Found"
        self.reported_by = reported_by
        self.image_data = image_data      # Stores optional Base64 image string
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
        self.supabase = supabase_client
        # Creating User Objects (Pre-loaded with 1 Admin and 2 Basic Users)
        self.users = {
            "admin@campus.edu": User("admin@campus.edu", "admin123", "Campus Admin", "admin"),
            "student1@campus.edu": User("student1@campus.edu", "pass123", "Aarav (Student 1)", "user"),
            "student2@campus.edu": User("student2@campus.edu", "pass123", "Diya (Student 2)", "user"),
        }
        self.items = []
        self.next_id = 1
        self.logged_in_user = None  # Tracks active session user object

        # Load initial items from Supabase or fallback
        if self.supabase:
            self.load_from_supabase()
        else:
            # Seed initial sample items (Object Construction)
            self.add_item("Blue Water Bottle", "Steel bottle with sticker", "Library 2nd Floor", "Lost", "student1@campus.edu")
            self.add_item("Scientific Calculator", "Casio fx-991EX", "Lab 304", "Found", "student2@campus.edu")

    def _upload_image_to_supabase(self, image_data):
        """Uploads base64 encoded image to Supabase Storage 'item-images' bucket and returns its public URL."""
        if not self.supabase or not image_data or not image_data.startswith("data:image"):
            return image_data

        try:
            header, base64_str = image_data.split(",", 1)
            mime_type = "image/jpeg"
            if ":" in header and ";" in header:
                mime_type = header.split(":")[1].split(";")[0]

            ext = mime_type.split("/")[-1] if "/" in mime_type else "jpg"
            if ext == "jpeg":
                ext = "jpg"

            image_bytes = base64.b64decode(base64_str)
            file_name = f"item_{uuid.uuid4().hex[:12]}.{ext}"

            # Upload binary to Supabase Storage 'item-images'
            print(f"[Supabase] Uploading image {file_name} to 'item-images' bucket...")
            self.supabase.storage.from_("item-images").upload(
                path=file_name,
                file=image_bytes,
                file_options={"content-type": mime_type}
            )
            # Retrieve the public URL
            public_url = self.supabase.storage.from_("item-images").get_public_url(file_name)
            print(f"[Supabase] Image uploaded successfully! URL: {public_url}")
            return public_url
        except Exception as e:
            print(f"[Supabase Storage Error] {e}")
            return image_data

    def load_from_supabase(self):
        """Loads records from Supabase 'items' and 'users' tables into OOP models."""
        try:
            # Load users
            user_res = self.supabase.table("users").select("*").execute()
            if user_res.data:
                for u in user_res.data:
                    self.users[u["email"]] = User(u["email"], u["password"], u["name"], u.get("role", "user"))

            # Load items
            item_res = self.supabase.table("items").select("*").order("created_at", desc=True).execute()
            if item_res.data:
                self.items = []
                for it in item_res.data:
                    new_item = Item(
                        item_id=it["id"],
                        title=it["title"],
                        description=it.get("description", ""),
                        location=it.get("location", ""),
                        category=it.get("item_type", "Lost"),
                        reported_by=it.get("reported_by", ""),
                        image_data=it.get("image_url", "")
                    )
                    new_item.status = it.get("status", "Open")
                    new_item.claimed_by = it.get("claimed_by")
                    self.items.append(new_item)
                if self.items:
                    self.next_id = max(i.record_id for i in self.items) + 1
        except Exception as e:
            print(f"[Supabase Sync Error] Could not load data: {e}")

    def authenticate(self, email, password):
        # Check in-memory user objects or Supabase
        user = self.users.get(email)
        if user and user.check_password(password):
            self.logged_in_user = user
            return True
        return False

    def add_item(self, title, description, location, category, reported_by, image_data=""):
        # 1. Upload image to Supabase Storage if connected
        image_url = self._upload_image_to_supabase(image_data) if image_data else ""

        # 2. Insert into Supabase table if connected
        item_id = self.next_id
        if self.supabase:
            try:
                res = self.supabase.table("items").insert({
                    "title": title,
                    "description": description,
                    "location": location,
                    "item_type": category,
                    "reported_by": reported_by,
                    "image_url": image_url,
                    "status": "Open"
                }).execute()
                if res.data:
                    item_id = res.data[0]["id"]
            except Exception as e:
                print(f"[Supabase Insert Error] {e}")

        # 3. Object Construction: Instantiating Item object (maintaining OOP principles)
        new_item = Item(item_id, title, description, location, category, reported_by, image_url)
        self.items.insert(0, new_item)
        self.next_id = max(self.next_id + 1, item_id + 1)

    def claim_item(self, item_id, claimant_email):
        for item in self.items:
            if item.record_id == item_id and item.status == "Open":
                item.status = "Claimed"
                item.claimed_by = claimant_email
                if self.supabase:
                    try:
                        self.supabase.table("items").update({"status": "Claimed"}).eq("id", item_id).execute()
                        self.supabase.table("claims").insert({
                            "item_id": item_id,
                            "claimant_email": claimant_email,
                            "status": "Pending"
                        }).execute()
                    except Exception as e:
                        print(f"[Supabase Claim Error] {e}")
                break

    def resolve_item(self, item_id):
        for item in self.items:
            if item.record_id == item_id:
                item.status = "Resolved"
                if self.supabase:
                    try:
                        self.supabase.table("items").update({"status": "Resolved"}).eq("id", item_id).execute()
                    except Exception as e:
                        print(f"[Supabase Resolve Error] {e}")
                break

    def delete_item(self, item_id):
        self.items = [item for item in self.items if item.record_id != item_id]
        if self.supabase:
            try:
                self.supabase.table("items").delete().eq("id", item_id).execute()
            except Exception as e:
                print(f"[Supabase Delete Error] {e}")

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
        # Connection status banner
        if not supabase_client:
            conn_banner = """
            <div style="background: #fff3cd; color: #856404; padding: 10px 15px; border-radius: 4px; margin-bottom: 20px; border: 1px solid #ffeeba; font-size: 13px;">
                ⚠️ <b>Supabase Storage Not Connected:</b> Add your <code>SUPABASE_KEY</code> to the <code>.env</code> file so uploaded photos are automatically saved to your Supabase <code>item-images</code> bucket.
            </div>
            """
        else:
            conn_banner = """
            <div style="background: #d4edda; color: #155724; padding: 8px 15px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #c3e6cb; font-size: 13px;">
                🟢 <b>Supabase Connected:</b> Photos will automatically upload to your <code>item-images</code> storage bucket.
            </div>
            """

        # Minimalistic CSS + tiny JS helpers for confirmation and image encoding
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 30px auto; padding: 0 15px; background: #f9f9f9; color: #222; }}
        header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
        .card {{ background: #fff; padding: 15px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 15px; }}
        input, select, button {{ padding: 8px; margin: 4px 0; border: 1px solid #ccc; border-radius: 4px; }}
        button {{ background: #222; color: #fff; cursor: pointer; border: none; }}
        button:hover {{ background: #444; }}
        .btn-claim {{ background: #0066cc; }}
        .btn-danger {{ background: #cc0000; }}
        .btn-success {{ background: #28a745; }}
        table {{ width: 100%; border-collapse: collapse; background: #fff; }}
        th, td {{ padding: 10px; border: 1px solid #ddd; text-align: left; vertical-align: middle; }}
        th {{ background: #eee; }}
        .badge-Lost {{ color: #cc0000; font-weight: bold; }}
        .badge-Found {{ color: #28a745; font-weight: bold; }}
        .item-img {{ width: 60px; height: 60px; object-fit: cover; border-radius: 4px; border: 1px solid #ccc; }}
    </style>
    <script>
        function confirmAction(msg) {{ return confirm(msg); }}

        // Converts selected image file into a Base64 string for simple form submission
        function encodeImage(input) {{
            if (input.files && input.files[0]) {{
                const reader = new FileReader();
                reader.onload = function(e) {{
                    document.getElementById('image_data').value = e.target.result;
                }};
                reader.readAsDataURL(input.files[0]);
            }}
        }}
    </script>
</head>
<body>
    {conn_banner}
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
            img_tag = f'<img src="{item.image_data}" class="item-img" alt="Item">' if item.image_data else "<small>No image</small>"

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
                <td>{img_tag}</td>
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
                <input type="text" name="description" placeholder="Short Description" required><br>
                <label><small>Optional Image:</small></label>
                <input type="file" accept="image/*" onchange="encodeImage(this)">
                <input type="hidden" name="image_data" id="image_data">
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
                <tr><th>Type</th><th>Photo</th><th>Item Details</th><th>Location</th><th>Status</th><th>Action</th></tr>
                {rows if rows else "<tr><td colspan='6'>No items found.</td></tr>"}
            </table>
        </div>
        """
        return ViewRenderer.layout("User Dashboard", content)

    @staticmethod
    def admin_dashboard(user, items):
        rows = ""
        for item in items:
            img_tag = f'<img src="{item.image_data}" class="item-img" alt="Item">' if item.image_data else "<small>No image</small>"
            rows += f"""
            <tr>
                <td>#{item.record_id}</td>
                <td><span class="badge-{item.category}">{item.category}</span></td>
                <td>{img_tag}</td>
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
                <tr><th>ID</th><th>Type</th><th>Photo</th><th>Item & Reporter</th><th>Status</th><th>Admin Controls</th></tr>
                {rows if rows else "<tr><td colspan='6'>No records available.</td></tr>"}
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
                reported_by=db.logged_in_user.email,
                image_data=post_data.get("image_data", [""])[0]
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