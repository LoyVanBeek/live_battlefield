# Plan: Protect Admin Panel with HTTP Basic Auth or Session Token

## Overview
Add authentication to the admin panel to prevent unauthorized access. Two approaches are documented - HTTP Basic Auth (simpler) or session-based (more flexible).

## References
- Original TODO: docs/TODO.md item 21

## Current State
- Admin panel accessible at `/admin` without any authentication
- Security audit identified this as a critical issue

## Implementation Plan

### Option A: HTTP Basic Auth (Recommended for simplicity)

#### Step 1: Add admin credentials to config
Modify `app/config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # existing settings...
    admin_username: str = "admin"
    admin_password: str = "changeme"  # Change in production
```

#### Step 2: Create auth middleware
Create `app/middleware/auth.py`:
```python
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
import base64

class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for non-admin routes
        if not request.url.path.startswith("/admin"):
            return await call_next(request)
        
        # Check for admin routes that need protection
        admin_routes = ["/admin", "/admin/", "/admin/test-panel"]
        if request.url.path not in admin_routes:
            return await call_next(request)
        
        # Get credentials from header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": "Basic"},
                content={"detail": "Authentication required"}
            )
        
        if not auth_header.startswith("Basic "):
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": "Basic"},
                content={"detail": "Invalid authentication"}
            )
        
        # Decode and verify credentials
        try:
            encoded = auth_header[6:]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)
            
            if (username != settings.admin_username or 
                password != settings.admin_password):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid credentials"}
                )
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication format"}
            )
        
        return await call_next(request)
```

#### Step 3: Register middleware
Modify `app/main.py`:
```python
from app.middleware.auth import AdminAuthMiddleware

app.add_middleware(AdminAuthMiddleware)
```

### Option B: Session-Based Auth (More Flexible)

#### Step 1: Add session middleware
```python
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware, 
    secret_key="your-secret-key-here"
)
```

#### Step 2: Create login page
Create `app/templates/login.html`:
```html
<!-- Simple login form -->
<form method="post" action="/admin/login">
    <input type="text" name="username" placeholder="Username">
    <input type="password" name="password" placeholder="Password">
    <button type="submit">Login</button>
</form>
```

#### Step 3: Add login route
```python
from starlette.datastructures import URL

@app.get("/admin/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/admin/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    
    if (username == settings.admin_username and 
        password == settings.admin_password):
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin")
    
    return templates.TemplateResponse(
        "login.html", 
        {"request": request, "error": "Invalid credentials"}
    )
```

#### Step 4: Add session check middleware
```python
class SessionAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/admin"):
            if not request.session.get("admin_authenticated"):
                return RedirectResponse(url="/admin/login")
        return await call_next(request)
```

## Files to Modify
1. `app/config.py` - Add admin credentials
2. `app/main.py` - Register middleware (choose option A or B)

## Files to Create
- Option A: `app/middleware/auth.py`
- Option B: `app/templates/login.html`, `app/middleware/auth.py`

## Environment Variables
Add to `.env`:
```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password_here
```

## Testing
1. Access `/admin` without credentials - should get 401
2. Access with correct credentials - should see admin panel
3. Access with wrong credentials - should get 403

## Security Notes
- Use strong password in production
- Consider using environment-specific passwords
- Option B supports additional features like "remember me"
