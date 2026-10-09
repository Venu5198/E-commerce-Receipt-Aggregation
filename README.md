# E-commerce Receipt Aggregation API

High-performance asynchronous FastAPI microservice connected to MongoDB. Aggregates data across four collections (`profiles`, `orders`, `products`, `invoices`) to generate unified receipts in a single roundtrip without N+1 query overhead, equipped with production-grade backend architecture.

---

## Architecture & Backend Concepts

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Incoming HTTP Request                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    [1. Observability Middleware]   ▼  Assigns X-Request-ID & Starts Stopwatch
    [2. Rate Limiting Middleware]   ▼  Enforces 120 req/min sliding window
    [3. Auth & RBAC Dependency]     ▼  Decodes JWT & Checks Role Permissions
                                    │
                      ┌─────────────┴─────────────┐
                      ▼                           ▼
        [Cache Hit (Fast Path)]         [Cache Miss (DB Aggregation)]
         Returns Cached Receipt          Batch queries Profiles, Orders,
         in < 1ms                        Products ($in), and Invoices
                      │                           │
                      │                           ▼
                      │                   Populates Cache (60s TTL)
                      │                           │
                      └─────────────┬─────────────┘
                                    │
    [4. Background Tasks Worker]    ▼  Dispatches async email & audit log
    [5. Response Headers Attached]  ▼  Adds X-Request-ID & X-Process-Time
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                        200 OK / 202 Accepted                           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Backend Concepts by Category (How Each is Used in This Application)

| Category | Backend Concepts Applied | How We Used It in This Application | Key Files & Endpoints |
|---|---|---|---|
| **1. Security & Identity** | • Bcrypt Password Hashing<br>• Stateless JWT Tokens<br>• Role-Based Access Control (RBAC) | • User passwords hashed with salt before storage in `users` collection.<br>• 24-hour signed JWTs issued on login/register.<br>• Route guards (`require_role(["admin"])`) enforce role permissions. | • [app/security.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/security.py)<br>• [app/dependencies.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/dependencies.py)<br>• `POST /api/v1/auth/register`<br>• `POST /api/v1/auth/login`<br>• `GET /api/v1/auth/admin-only` |
| **2. Data Modeling & Query Optimization** | • Async ODM / Driver (Motor)<br>• Pydantic v2 Schema Validation<br>• Batch Querying (No N+1 queries) | • 4 distinct collections (`profiles`, `orders`, `products`, `invoices`) typed via Pydantic.<br>• Product IDs in an order fetched in a single `$in` query instead of looping queries. | • [app/models/](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/models/)<br>• [app/services/receipt_service.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/services/receipt_service.py)<br>• `GET /api/v1/orders/{order_id}/receipt` |
| **3. Performance & Caching** | • In-Memory Key-Value Caching<br>• Time-To-Live (TTL) Lazy Eviction<br>• Event-Driven Invalidation | • Aggregated receipts cached for 60 seconds (`receipt:{order_id}`). Repeated requests respond in `< 1ms`.<br>• Updating or deleting an order or invoice automatically purges stale receipt cache. | • [app/services/cache_service.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/services/cache_service.py)<br>• [app/routers/orders.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/routers/orders.py)<br>• [app/routers/invoices.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/routers/invoices.py) |
| **4. Resilience & Traffic Shaping** | • Sliding-Window Rate Limiting<br>• HTTP 429 Status & `Retry-After`<br>• Quota Signaling Headers | • Tracks client IP requests over a 60-second window, capping at 120 req/min.<br>• Returns `X-RateLimit-Limit` and `X-RateLimit-Remaining`.<br>• Exempts `/health` and `/docs`. | • [app/middleware/rate_limiter.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/middleware/rate_limiter.py)<br>• [app/main.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/main.py) |
| **5. Observability & Tracing** | • Distributed Correlation IDs (`X-Request-ID`)<br>• Monotonic Process Latency (`X-Process-Time`)<br>• Centralized Exception Handling<br>• Machine-readable JSON Logging | • Middleware attaches unique trace ID to requests and response headers.<br>• Measures wall-clock execution time.<br>• Central handlers normalize 500, 422, and 404 responses with trace ID. | • [app/middleware/observability.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/middleware/observability.py)<br>• [app/middleware/error_handler.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/middleware/error_handler.py) |
| **6. Asynchronous Jobs & Auditing** | • Out-of-band Coroutines (`BackgroundTasks`)<br>• Non-blocking I/O<br>• Audit Trail Persistence | • Email dispatch triggers out-of-band and immediately returns `202 Accepted`.<br>• Background task records compliance event in MongoDB `audit_logs` collection. | • [app/services/notification_service.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/services/notification_service.py)<br>• `POST /api/v1/orders/{order_id}/receipt/dispatch` |

---

## In-Depth Backend Concepts Explained

### 1. Authentication & Role-Based Access Control (RBAC)
* **Problem**: Unprotected endpoints expose customer data and allow unauthorized writes or deletes.
* **Solution**: Bcrypt password hashing + stateless signed JSON Web Tokens (JWT) + FastAPI dependency injection for role verification (`customer`, `admin`, `manager`).

#### Code Implementation ([app/security.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/security.py) & [app/dependencies.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/dependencies.py))
```python
def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=1440))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def require_role(allowed_roles: List[str]) -> Callable:
    async def role_checker(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access denied.")
        return current_user
    return role_checker
```

#### Line-by-Line Breakdown:
- `to_encode = data.copy()`: Clones user payload (`sub`, `role`) so original dictionary remains untouched.
- `expire = datetime.now(timezone.utc) + ...`: Enforces UTC token expiration to prevent clock-skew errors across servers.
- `to_encode.update({"exp": expire})`: Adds standard JWT RFC 7519 `exp` claim.
- `jwt.encode(...)`: Cryptographically signs payload with HMAC-SHA256 (`HS256`) and a secret key.
- `current_user: UserModel = Depends(get_current_user)`: Injects authenticated user parsed from the HTTP Bearer header.
- `if current_user.role not in allowed_roles:`: Rejects requests with HTTP 403 Forbidden if user lacks necessary permissions.

---

### 2. Observability & Distributed Tracing
* **Problem**: When requests fail in production, debugging across logs without a unified identifier is chaotic.
* **Solution**: `RequestTracingMiddleware` attaches an immutable `X-Request-ID` correlation ID and stopwatch timer `X-Process-Time` to every request and response, while emitting structured JSON logs.

#### Code Implementation ([app/middleware/observability.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/middleware/observability.py))
```python
class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        process_time = time.perf_counter() - start_time

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        logger.info(f'{{"request_id": "{request_id}", "status": {response.status_code}, "latency": {process_time:.4f}}}')
        return response
```

#### Line-by-Line Breakdown:
- `request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"`: Reuses incoming gateway/client trace ID or provisions a new one.
- `request.state.request_id = request_id`: Attaches trace ID to FastAPI request state for access across exception handlers.
- `start_time = time.perf_counter()`: Starts high-resolution monotonic timer unaffected by system clock adjustments.
- `response = await call_next(request)`: Yields control to router endpoint and awaits response.
- `response.headers["X-Process-Time"] = ...`: Exposes exact execution duration in response headers for client diagnostics.
- `logger.info(...)`: Emits machine-parseable JSON log line suitable for Datadog, CloudWatch, or ELK Stack.

---

### 3. In-Memory Caching & Cache Invalidation
* **Problem**: Aggregating receipts joins 4 MongoDB collections. Repeated calls for the same order create redundant database load.
* **Solution**: Async Cache layer with Time-to-Live (TTL) and event-driven cache invalidation on order or invoice updates.

#### Code Implementation ([app/services/cache_service.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/services/cache_service.py))
```python
class CacheService:
    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        self._store[key] = CacheEntry(value=value, expires_at=time.time() + ttl_seconds)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
```

#### Line-by-Line Breakdown:
- `entry = self._store.get(key)`: Retrieves cached object in O(1) time.
- `if time.time() > entry.expires_at:`: Lazy expiration checks whether TTL has passed without requiring background sweeping threads.
- `del self._store[key]`: Purges expired memory entry on demand.
- `self._store.pop(key, None)`: Evicts stale keys immediately whenever `PUT`, `PATCH`, or `DELETE` executes on orders/invoices.

---

### 4. Rate Limiting & Throttling
* **Problem**: Unrestricted clients can flood endpoints, exhausting server CPU and MongoDB connection pools.
* **Solution**: Sliding-window rate limiter per client IP returning `429 Too Many Requests` with RFC `Retry-After` headers.

#### Code Implementation ([app/middleware/rate_limiter.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/middleware/rate_limiter.py))
```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        timestamps = [t for t in self._clients[client_ip] if t > window_start]
        self._clients[client_ip] = timestamps

        if len(timestamps) >= self.max_requests:
            return JSONResponse(status_code=429, content={"error": "RateLimitExceeded"})

        self._clients[client_ip].append(now)
        response: Response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(self.max_requests - len(timestamps))
        return response
```

#### Line-by-Line Breakdown:
- `if request.url.path in self.exempt_paths`: Bypasses health checks (`/health`) and OpenAPI docs (`/docs`).
- `client_ip = request.client.host ...`: Extracts remote client host IP as throttle identity.
- `window_start = now - self.window_seconds`: Defines sliding timestamp boundary (e.g. past 60 seconds).
- `timestamps = [t for t in ... if t > window_start]`: Prunes expired call records to keep memory bounded.
- `if len(timestamps) >= self.max_requests`: Rejects request immediately with HTTP 429 when budget is exhausted.
- `response.headers["X-RateLimit-Remaining"]`: Communicates remaining request quota to client.

---

### 5. Asynchronous Background Tasks
* **Problem**: Dispatching customer emails or audit logs synchronously adds 200ms–2000ms latency to HTTP requests.
* **Solution**: Non-blocking background worker (`BackgroundTasks`) executes side effects out-of-band and returns `202 Accepted` immediately.

#### Code Implementation ([app/routers/receipts.py](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/app/routers/receipts.py))
```python
@router.post("/{order_id}/receipt/dispatch", status_code=status.HTTP_202_ACCEPTED)
async def dispatch_receipt_async(
    order_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    service = ReceiptService(db)
    receipt = await service.get_receipt(order_id)

    background_tasks.add_task(
        notification_service.dispatch_receipt_email,
        db,
        receipt.order_id,
        receipt.customer.email or "customer@example.com",
        receipt.summary.total_amount,
        receipt.summary.currency,
    )
    return {"status": "queued", "receipt_id": receipt.receipt_id}
```

#### Line-by-Line Breakdown:
- `status_code=status.HTTP_202_ACCEPTED`: Signals HTTP standard that job was accepted for asynchronous processing.
- `service.get_receipt(order_id)`: Resolves receipt details synchronously (from cache or DB).
- `background_tasks.add_task(...)`: Registers coroutine to run *after* response is sent to the client.
- `notification_service.dispatch_receipt_email`: Dispatches email notification and writes audit log to MongoDB `audit_logs` collection asynchronously.

---

## REST API Endpoints Overview

| Resource | Method | Path | Description | Auth Required |
|---|---|---|---|---|
| **Auth** | `POST` | `/api/v1/auth/register` | Register new user + return JWT | No |
| | `POST` | `/api/v1/auth/login` | Authenticate + return JWT | No |
| | `GET` | `/api/v1/auth/me` | Fetch authenticated user profile | Bearer Token |
| | `GET` | `/api/v1/auth/admin-only` | Example RBAC endpoint | Admin Role |
| **Profiles** | `POST` | `/api/v1/profiles` | Create customer profile (201 Created) | Optional |
| | `GET` | `/api/v1/profiles` | List profiles (with pagination) | Optional |
| | `GET` | `/api/v1/profiles/{user_id}` | Retrieve profile by user ID or _id | Optional |
| | `PUT` | `/api/v1/profiles/{user_id}` | Full replace update | Optional |
| | `PATCH` | `/api/v1/profiles/{user_id}` | Partial update | Optional |
| | `DELETE` | `/api/v1/profiles/{user_id}` | Delete profile (204 No Content) | Optional |
| **Products** | `POST` | `/api/v1/products` | Create product (201 Created) | Optional |
| | `GET` | `/api/v1/products` | List products (filter category, in_stock) | Optional |
| | `GET` | `/api/v1/products/{product_id}` | Retrieve product by product ID or _id | Optional |
| | `PUT` | `/api/v1/products/{product_id}` | Full replace update | Optional |
| | `PATCH` | `/api/v1/products/{product_id}` | Partial update | Optional |
| | `DELETE` | `/api/v1/products/{product_id}` | Delete product (204 No Content) | Optional |
| **Orders** | `POST` | `/api/v1/orders` | Create order with auto calculations | Optional |
| | `GET` | `/api/v1/orders` | List orders (filter user_id, status) | Optional |
| | `GET` | `/api/v1/orders/{order_id}` | Retrieve order by ID | Optional |
| | `PUT` | `/api/v1/orders/{order_id}` | Full replace update (clears cache) | Optional |
| | `PATCH` | `/api/v1/orders/{order_id}` | Partial update (clears cache) | Optional |
| | `DELETE` | `/api/v1/orders/{order_id}` | Delete order (clears cache) | Optional |
| **Invoices** | `POST` | `/api/v1/invoices` | Create invoice record | Optional |
| | `GET` | `/api/v1/invoices` | List invoices (filter order_id, status) | Optional |
| | `GET` | `/api/v1/invoices/{invoice_id}` | Retrieve invoice by ID | Optional |
| | `PUT` | `/api/v1/invoices/{invoice_id}` | Full replace update (clears cache) | Optional |
| | `PATCH` | `/api/v1/invoices/{invoice_id}` | Partial update (clears cache) | Optional |
| | `DELETE` | `/api/v1/invoices/{invoice_id}` | Delete invoice (clears cache) | Optional |
| **Receipts** | `GET` | `/api/v1/orders/{order_id}/receipt` | Aggregated receipt (joins 4 collections, cached) | No |
| | `POST` | `/api/v1/orders/{order_id}/receipt/dispatch` | Background email dispatch & audit log (202) | No |

---

## Local Development & Testing

### 1. Install Dependencies
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run Test Suite (15 Tests)
```bash
pytest -v
```

### 3. Seed Realistic Test Data
```bash
python scripts/seed_data.py
```

### 4. Run API Locally
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Distributed Scaling & Event-Driven Architecture

### System Scaling Topology

```
                         ┌───────────────────────────┐
                         │   Load Balancer (Nginx)   │
                         └─────────────┬─────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
   ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
   │ API Replica 1   │        │ API Replica 2   │        │ API Replica 3   │
   │ (FastAPI Async) │        │ (FastAPI Async) │        │ (FastAPI Async) │
   └────────┬────────┘        └────────┬────────┘        └────────┬────────┘
            │                          │                          │
            ├──────────────────────────┼──────────────────────────┤
            ▼                          ▼                          ▼
 ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
 │  Redis 7.2 Cluster   │   │  RabbitMQ 3.13 AMQP  │   │   MongoDB Replica    │
 │ (Distributed Cache)  │   │   (Event Streaming)  │   │  (Persistent Store)  │
 └──────────────────────┘   └──────────┬───────────┘   └──────────────────────┘
                                       │
                            ┌──────────┴──────────┐
                            ▼                     ▼
                 ┌───────────────────┐ ┌───────────────────┐
                 │ Email Worker Pods │ │ Audit Log Workers │
                 └───────────────────┘ └───────────────────┘
```

---

### Core Principles Enabling Horizontal Scaling

1. **Stateless API Replicas**:
   - Authenticated with stateless HMAC-SHA256 JWT tokens. No server-side session stickiness is needed; any API replica can handle any user request seamlessly.
2. **Distributed Shared Cache (Redis)**:
   - Config: `REDIS_URL=redis://redis:6379/0`, `USE_REDIS_CACHE=true`
   - Cache hits bypass MongoDB completely and return in `< 1ms`.
   - All API instances read and invalidate from the same shared Redis cache without in-memory drift.
3. **Asynchronous Decoupling (RabbitMQ Broker)**:
   - Config: `RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/`, `USE_RABBITMQ=true`
   - Non-blocking publishing onto the durable `ecommerce.events` topic exchange.
   - Heavy background jobs (receipt dispatch, email generation, accounting exports) are processed asynchronously without blocking client HTTP request threads.
4. **Resilience & Graceful Fallback**:
   - If Redis or RabbitMQ goes temporarily offline, the API automatically falls back to in-memory caching and persistent MongoDB logging without dropping traffic.

---

### How to Scale Services Live

#### 1. Spin up the Full Stack
```powershell
docker-compose up -d --build
```

#### 2. Scale API Replicas Horizontally
Run 3 concurrent, load-balanced API container instances:
```powershell
docker-compose up -d --scale api=3
```

#### 3. Inspect Live Distributed Cache (Redis)
Connect directly to Redis CLI inside the container:
```powershell
docker exec -it ecommerce_receipts_redis redis-cli
```
Helpful Redis commands:
```redis
KEYS *                    # View all active cached receipt keys
GET receipt:ORD-5001      # View serialized cached receipt payload
TTL receipt:ORD-5001      # View remaining seconds before key expiration
MONITOR                   # Stream all live cache reads and writes in real-time
```

#### 4. Monitor Message Streaming (RabbitMQ Web UI)
1. Open **[http://localhost:15672](http://localhost:15672)** in your browser.
2. Login credentials:
   - **Username**: `guest`
   - **Password**: `guest`
3. Click the **Exchanges** tab to inspect `ecommerce.events`.
4. Monitor message publish rates, message acknowledgments, and worker queues in real-time.

---

## Running with Docker (Full Microservices Stack)

| Container Name | Service | Ports | Description |
|---|---|---|---|
| `ecommerce_receipts_api` | FastAPI App | `8000:8000` | REST API, OpenAPI docs at `/docs` |
| `ecommerce_receipts_mongo` | MongoDB 7.0 | `27018:27017` | Persistent primary database |
| `ecommerce_receipts_redis` | Redis 7.2 | `6379:6379` | Distributed sub-millisecond cache |
| `ecommerce_receipts_rabbitmq` | RabbitMQ 3.13 | `5672`, `15672` | AMQP broker + Management Web Dashboard |

Seed the Docker database with realistic e-commerce data:
```powershell
docker exec -it ecommerce_receipts_api python scripts/seed_data.py
```

---

## Git Repository & Deployment

```bash
git add .
git commit -m "feat: implement distributed Redis caching, RabbitMQ event bus, and GitHub Actions CI/CD"
git branch -M main
git push -u origin main
```
Repository: [https://github.com/Venu5198/E-commerce-Receipt-Aggregation.git](https://github.com/Venu5198/E-commerce-Receipt-Aggregation.git)

---

## Full Manual Testing Guide (Swagger UI Step-by-Step)

Open the interactive API documentation at: **[http://localhost:8000/docs](http://localhost:8000/docs)**.

### Preparation: Authorizing Requests in Swagger
Endpoints protected by security will show a small **padlock icon**.
1. To authenticate, first execute **Phase 1, Step 1.1 or 1.2** to get an `access_token`.
2. Scroll to the top right of the Swagger page and click the green **"Authorize"** button.
3. Paste your token (e.g. `eyJhbGciOi...`) into the `Value` box and click **Authorize**. All subsequent calls will carry the `Authorization: Bearer <token>` header automatically.

---

### Phase 1: Authentication & RBAC

#### Step 1.1: Register a Customer User
* **Endpoint**: `POST /api/v1/auth/register`
* **Request Body**:
```json
{
  "username": "customer_sam",
  "email": "sam@example.com",
  "password": "Password123!",
  "role": "customer"
}
```
* **Expected Response**: `201 Created` with `access_token`, `role: "customer"`, and `user_id`. Copy this token.

#### Step 1.2: Register an Admin User
* **Endpoint**: `POST /api/v1/auth/register`
* **Request Body**:
```json
{
  "username": "admin_clara",
  "email": "clara@example.com",
  "password": "AdminSecret123!",
  "role": "admin"
}
```
* **Expected Response**: `201 Created` with admin token.

#### Step 1.3: User Login
* **Endpoint**: `POST /api/v1/auth/login`
* **Request Body**:
```json
{
  "username": "customer_sam",
  "password": "Password123!"
}
```
* **Expected Response**: `200 OK` with valid JWT token.

#### Step 1.4: Verify Identity (`/me`)
* **Endpoint**: `GET /api/v1/auth/me`
* Click **Authorize**, paste `customer_sam` token.
* **Expected Response**: `200 OK` with user details (`username`, `email`, `role`).

#### Step 1.5: Test Role-Based Access Control (RBAC)
* **Endpoint**: `GET /api/v1/auth/admin-only`
* **Test with `customer_sam` token**: `403 Forbidden` (`detail: Access denied. Requires one of roles: admin.`).
* **Test with `admin_clara` token**: `200 OK` (`status: "authorized"`, `username: "admin_clara"`).

---

### Phase 2: Customer Profiles Lifecycle

#### Step 2.1: Create Customer Profile
* **Endpoint**: `POST /api/v1/profiles`
* **Request Body**:
```json
{
  "user_id": "USER-2001",
  "full_name": "Samuel Jackson",
  "email": "sam.jackson@example.com",
  "phone": "+1-555-0144",
  "address": {
    "street": "100 Broadway St",
    "city": "New York",
    "state": "NY",
    "postal_code": "10001",
    "country": "USA"
  }
}
```
* **Expected Response**: `201 Created`.

#### Step 2.2: List Profiles
* **Endpoint**: `GET /api/v1/profiles?skip=0&limit=10`
* **Expected Response**: `200 OK` with total count and items list.

#### Step 2.3: Get Profile by ID
* **Endpoint**: `GET /api/v1/profiles/{user_id}`
* **Parameter**: `user_id`: `USER-2001`
* **Expected Response**: `200 OK`.

#### Step 2.4: Full Update Profile (PUT)
* **Endpoint**: `PUT /api/v1/profiles/{user_id}`
* **Parameter**: `user_id`: `USER-2001`
* **Request Body**:
```json
{
  "full_name": "Samuel L. Jackson",
  "email": "samuel.l@example.com",
  "phone": "+1-555-0999",
  "address": {
    "street": "200 Fifth Ave",
    "city": "New York",
    "state": "NY",
    "postal_code": "10010",
    "country": "USA"
  }
}
```
* **Expected Response**: `200 OK` with updated fields.

#### Step 2.5: Partial Update Profile (PATCH)
* **Endpoint**: `PATCH /api/v1/profiles/{user_id}`
* **Parameter**: `user_id`: `USER-2001`
* **Request Body**:
```json
{
  "phone": "+1-555-7777"
}
```
* **Expected Response**: `200 OK` with updated phone.

#### Step 2.6: Delete Profile
* **Endpoint**: `DELETE /api/v1/profiles/{user_id}`
* **Parameter**: `user_id`: `USER-2001`
* **Expected Response**: `204 No Content`.

---

### Phase 3: Products Catalog Lifecycle

#### Step 3.1: Create Product
* **Endpoint**: `POST /api/v1/products`
* **Request Body**:
```json
{
  "product_id": "PROD-999",
  "sku": "KEYB-MECH-RGB",
  "title": "Quantum RGB Mechanical Keyboard",
  "description": "Hot-swappable mechanical switches with per-key RGB backlighting.",
  "unit_price": 129.99,
  "currency": "USD",
  "category": "Peripherals",
  "in_stock": true
}
```
* **Expected Response**: `201 Created`.

#### Step 3.2: List Products (Filtered)
* **Endpoint**: `GET /api/v1/products?category=Peripherals&in_stock=true`
* **Expected Response**: `200 OK` with matching items.

#### Step 3.3: Get Product by ID
* **Endpoint**: `GET /api/v1/products/{product_id}`
* **Parameter**: `product_id`: `PROD-999`
* **Expected Response**: `200 OK`.

#### Step 3.4: Full Update Product (PUT)
* **Endpoint**: `PUT /api/v1/products/{product_id}`
* **Parameter**: `product_id`: `PROD-999`
* **Request Body**:
```json
{
  "sku": "KEYB-MECH-PRO",
  "title": "Quantum RGB Pro Mechanical Keyboard",
  "description": "Upgraded wireless tri-mode mechanical keyboard.",
  "unit_price": 149.99,
  "currency": "USD",
  "category": "Peripherals",
  "in_stock": true
}
```
* **Expected Response**: `200 OK`.

#### Step 3.5: Partial Update Product (PATCH)
* **Endpoint**: `PATCH /api/v1/products/{product_id}`
* **Parameter**: `product_id`: `PROD-999`
* **Request Body**:
```json
{
  "unit_price": 139.99,
  "in_stock": false
}
```
* **Expected Response**: `200 OK`.

#### Step 3.6: Delete Product
* **Endpoint**: `DELETE /api/v1/products/{product_id}`
* **Parameter**: `product_id`: `PROD-999`
* **Expected Response**: `204 No Content`.

---

### Phase 4: Orders Management Lifecycle

#### Step 4.1: Create Order
* **Endpoint**: `POST /api/v1/orders`
* **Request Body**:
```json
{
  "order_id": "ORD-6001",
  "user_id": "USER-1001",
  "status": "PENDING",
  "items": [
    {
      "product_id": "PROD-001",
      "quantity": 1,
      "unit_price": 249.99
    },
    {
      "product_id": "PROD-004",
      "quantity": 2,
      "unit_price": 45.0
    }
  ],
  "tax": 27.20,
  "shipping_fee": 15.00,
  "currency": "USD"
}
```
* **Expected Response**: `201 Created` with automatically calculated `subtotal` (339.99) and `total_amount` (382.19).

#### Step 4.2: List Orders
* **Endpoint**: `GET /api/v1/orders?status=PENDING`
* **Expected Response**: `200 OK`.

#### Step 4.3: Get Order by ID
* **Endpoint**: `GET /api/v1/orders/{order_id}`
* **Parameter**: `order_id`: `ORD-6001`
* **Expected Response**: `200 OK`.

#### Step 4.4: Update Order (PUT)
* **Endpoint**: `PUT /api/v1/orders/{order_id}`
* **Parameter**: `order_id`: `ORD-6001`
* **Request Body**:
```json
{
  "user_id": "USER-1001",
  "status": "PROCESSING",
  "items": [
    {
      "product_id": "PROD-001",
      "quantity": 2,
      "unit_price": 249.99
    }
  ],
  "tax": 39.99,
  "shipping_fee": 0.0,
  "currency": "USD"
}
```
* **Expected Response**: `200 OK` (automatically evicts any stale receipt cache for `ORD-6001`).

#### Step 4.5: Partial Update Order Status (PATCH)
* **Endpoint**: `PATCH /api/v1/orders/{order_id}`
* **Parameter**: `order_id`: `ORD-6001`
* **Request Body**:
```json
{
  "status": "COMPLETED"
}
```
* **Expected Response**: `200 OK`.

#### Step 4.6: Delete Order
* **Endpoint**: `DELETE /api/v1/orders/{order_id}`
* **Parameter**: `order_id`: `ORD-6001`
* **Expected Response**: `204 No Content`.

---

### Phase 5: Invoices & Payment Lifecycle

#### Step 5.1: Create Invoice
* **Endpoint**: `POST /api/v1/invoices`
* **Request Body**:
```json
{
  "invoice_number": "INV-2026-9001",
  "order_id": "ORD-5001",
  "payment_method": "Credit Card (Mastercard ending in 8888)",
  "payment_status": "PAID",
  "amount_paid": 367.19,
  "currency": "USD",
  "transaction_id": "txn_live_9876543210"
}
```
* **Expected Response**: `201 Created`.

#### Step 5.2: List Invoices
* **Endpoint**: `GET /api/v1/invoices?payment_status=PAID`
* **Expected Response**: `200 OK`.

#### Step 5.3: Get Invoice by ID
* **Endpoint**: `GET /api/v1/invoices/{invoice_id}`
* **Parameter**: `invoice_id`: `INV-2026-9001`
* **Expected Response**: `200 OK`.

#### Step 5.4: Full Update Invoice (PUT)
* **Endpoint**: `PUT /api/v1/invoices/{invoice_id}`
* **Parameter**: `invoice_id`: `INV-2026-9001`
* **Request Body**:
```json
{
  "order_id": "ORD-5001",
  "invoice_number": "INV-2026-9001",
  "payment_method": "Apple Pay",
  "payment_status": "PAID",
  "amount_paid": 367.19,
  "currency": "USD",
  "transaction_id": "txn_apple_44332211"
}
```
* **Expected Response**: `200 OK`.

#### Step 5.5: Partial Update Invoice (PATCH)
* **Endpoint**: `PATCH /api/v1/invoices/{invoice_id}`
* **Parameter**: `invoice_id`: `INV-2026-9001`
* **Request Body**:
```json
{
  "payment_status": "REFUNDED"
}
```
* **Expected Response**: `200 OK`.

#### Step 5.6: Delete Invoice
* **Endpoint**: `DELETE /api/v1/invoices/{invoice_id}`
* **Parameter**: `invoice_id`: `INV-2026-9001`
* **Expected Response**: `204 No Content`.

---

### Phase 6: Receipt Aggregation, Caching & Asynchronous Worker

#### Step 6.1: Get Aggregated Receipt (Cross-Collection Join)
* **Endpoint**: `GET /api/v1/orders/{order_id}/receipt`
* **Parameter**: `order_id`: `ORD-5001` (or seeded orders: `ORD-5002`, `ORD-5003`, `ORD-5004`, `ORD-5005`)
* **Expected Response**: `200 OK`
* **Inspect Data**: Combines `order`, `customer profile`, batch `$in` `products` titles/skus, and `invoice payment status`.
* **Inspect Response Headers**:
  - `X-Request-ID`: Correlation identifier (`req_...`).
  - `X-Process-Time`: Monotonic execution timing.
  - `X-RateLimit-Limit`: `120`
  - `X-RateLimit-Remaining`: Count down from 120.

#### Step 6.2: Test Caching Speed (Sub-millisecond Retrieval)
* Execute `GET /api/v1/orders/ORD-5001/receipt` a second time immediately.
* **Observe**: `X-Process-Time` drops to under `0.001s` (served directly from cache).

#### Step 6.3: Test Event-Driven Cache Invalidation
1. Run `PATCH /api/v1/orders/ORD-5001` with `{"status": "CANCELLED"}`.
2. Re-fetch `GET /api/v1/orders/ORD-5001/receipt`.
3. **Observe**: The cached receipt was evicted, recalculating from the database with the updated status.

#### Step 6.4: Dispatch Receipt Email & Audit Log (Async Worker)
* **Endpoint**: `POST /api/v1/orders/{order_id}/receipt/dispatch`
* **Parameter**: `order_id`: `ORD-5001`
* **Expected Response**: `202 Accepted`
```json
{
  "status": "queued",
  "message": "Receipt dispatch background job scheduled for order 'ORD-5001'.",
  "recipient": "alice.johnson@example.com",
  "receipt_id": "REC-ORD-5001"
}
```
* **Verification**: The API immediately responds without waiting for email transport, scheduling a background job that inserts a permanent record into the MongoDB `audit_logs` collection.
