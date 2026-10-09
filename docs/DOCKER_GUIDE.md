# Complete Docker Mastery Guide (Hands-On with E-commerce Backend)

---

## 1. What Docker Is
Docker is an open-source platform that packages an application and all its dependencies (system libraries, Python packages, runtimes, configurations) into a standardized, isolated unit called a **container**.
* **Key Concept**: Unlike Virtual Machines (VMs) which emulate hardware and run heavy guest operating systems, Docker containers share the host OS kernel and isolate processes using Linux kernel primitives (`namespaces` for isolation, `cgroups` for resource limits).

---

## 2. Why Docker Is Used
1. **Eliminates "It works on my machine"**: Guarantees identical execution across development, staging, CI/CD runners, and production servers.
2. **Resource Efficiency**: Boots in milliseconds and uses megabytes of RAM instead of gigabytes required by hypervisors/VMs.
3. **Dependency Isolation**: Prevents dependency clashes (e.g., Python 3.11 vs Python 3.14 on the host machine).
4. **Microservice Scalability**: Allows independent horizontal scaling (`--scale api=3`).

---

## 3. Docker Architecture

```
┌────────────────────────────────────────────────────────┐
│                      Docker Client                     │
│           (CLI commands: docker run, build, etc.)      │
└───────────────────────────┬────────────────────────────┘
                            │ REST API over socket
┌───────────────────────────▼────────────────────────────┐
│                   Docker Host (Daemon)                 │
│                                                        │
│   ┌───────────────┐  ┌──────────────────┐  ┌─────────┐ │
│   │ Image Cache   │  │ Running          │  │ Volumes │ │
│   │ (Layers)      │  │ Containers       │  │ & Nets  │ │
│   └───────────────┘  └──────────────────┘  └─────────┘ │
└───────────────────────────▲────────────────────────────┘
                            │ Pulls / Pushes
┌───────────────────────────┴────────────────────────────┐
│                    Docker Registry                     │
│               (Docker Hub, AWS ECR, etc.)              │
└────────────────────────────────────────────────────────┘
```

* **Client**: The `docker` CLI tool you invoke in terminal.
* **Daemon (`dockerd`)**: The background service managing containers, images, networks, and storage volumes.
* **Registry**: Remote store where Docker images are published (e.g., Docker Hub).

---

## 4. Docker Images vs Containers
* **Image**: An immutable, read-only template with layers containing application code, runtime, and files. Think of an Image as a **Class** or a blueprint.
* **Container**: A live, runnable instance of an Image with a thin writable layer on top. Think of a Container as an **Object** instantiated from a Class.

---

## 5. Docker Hub
Public and private cloud registry where images are stored and shared.
* Standard official images: `mongo:7.0`, `redis:7.2-alpine`, `rabbitmq:3.13-management-alpine`.
* Tag syntax: `repository:tag` (e.g., `python:3.11-slim`).

---

## 6. Installing Docker
* **Windows**: Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) (requires WSL 2 backend).
* **Linux (Ubuntu/Debian)**: `curl -fsSL https://get.docker.com | sh` followed by `sudo usermod -aG docker $USER`.
* **macOS**: Install Docker Desktop for Mac (Apple Silicon / Intel).

---

## 7. Basic Docker Commands

```powershell
docker --version                    # Check Docker CLI & Daemon version
docker pull python:3.11-slim         # Download an image from Docker Hub
docker images                       # List all images stored locally
docker ps                           # List actively running containers
docker ps -a                        # List all containers (running & stopped)
docker stop <container_id_or_name>  # Gracefully stop a running container
docker start <container_id_or_name> # Start a stopped container
docker rm <container_id_or_name>    # Delete a stopped container
docker rmi <image_id_or_name>       # Delete a local image
```

---

## 8. Running Your First Container

```powershell
# Runs an ephemeral container that prints output and exits
docker run --rm hello-world

# Run an interactive Python container
docker run -it --rm python:3.11-slim python -c "print('Antigravity Container Running!')"
```

---

## 9. Port Mapping (`-p <HostPort>:<ContainerPort>`)
By default, container networks are isolated from your workstation. Port forwarding exposes the internal container port to a port on your host:
```powershell
# Binds host port 8000 to internal container port 8000
docker run -d -p 8000:8000 --name test_api ecommerce-receipts-api:latest
```
* If mapped as `-p 8080:8000`: You visit `http://localhost:8080` on your browser, which forwards to port 8000 inside the container.

---

## 10. Container Lifecycle

```
[docker create] ──> [docker start] ──> [Running]
                          │                 │
                      (failure)       [docker stop]
                          │                 │
                          ▼                 ▼
                    [Exited / Dead] <── [Stopped]
                          │
                     [docker rm]
                          │
                          ▼
                      (Deleted)
```

---

## 11. Dockerfile Anatomy (Line-by-Line)

Reference from [Dockerfile](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/Dockerfile):

```dockerfile
# 1. Base image for build phase
FROM python:3.11-slim AS builder

WORKDIR /build

# 2. Prevent bytecode writes & enable unbuffered standard I/O
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# 3. Install compiler packages needed for bcrypt/wheels
RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*

# 4. Copy and build wheels into user local directory
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 5. Final slim runtime phase (Multi-Stage)
FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PATH="/home/appuser/.local/bin:${PATH}"

# 6. Install minimal curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# 7. Security: Create dedicated unprivileged non-root user
RUN addgroup --system --gid 1001 appgroup && adduser --system --uid 1001 --ingroup appgroup --home /home/appuser appuser

# 8. Copy pre-built dependencies from builder stage
COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
COPY --chown=appuser:appgroup . .

# 9. Switch to non-root user
USER appuser
EXPOSE 8000

# 10. Periodic health monitoring
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 11. Entrypoint startup command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 12. Building Custom Images

```powershell
# Build image from local Dockerfile and tag it
docker build -t ecommerce-receipts-api:v1 .

# Build without using cached layers (clean build)
docker build --no-cache -t ecommerce-receipts-api:latest .
```

---

## 13. `.dockerignore`
Prevents local workstation files from being copied into the build context, reducing build latency and avoiding secret leakage.
* In our project [`.dockerignore`](file:///c:/devops/E-commerce%20Receipt%20Aggregation%20API/.dockerignore):
  - `.git`, `.gitignore` (source control metadata)
  - `__pycache__`, `*.pyc` (host OS bytecode)
  - `.env` (prevents baking local secrets into image layers)
  - `venv/`, `.venv/` (host virtual environments)

---

## 14. Environment Variables
Inject configuration into containers without touching source code:
```powershell
# Inline variable
docker run -e MONGO_URI="mongodb://mongo:27017" -e APP_PORT=8000 -p 8000:8000 ecommerce-receipts-api

# Load from file
docker run --env-file .env -p 8000:8000 ecommerce-receipts-api
```

---

## 15. Container Logs

```powershell
# View entire console logs
docker logs ecommerce_receipts_api

# Stream logs live in real-time
docker logs -f ecommerce_receipts_api

# Tail the last 50 log lines with timestamps
docker logs -f --tail=50 -t ecommerce_receipts_api
```

---

## 16. Executing Commands Inside Running Containers

```powershell
# Run a one-off command inside the API container
docker exec ecommerce_receipts_api python scripts/seed_data.py

# Open an interactive shell inside container
docker exec -it ecommerce_receipts_api sh

# Connect to Redis CLI inside Redis container
docker exec -it ecommerce_receipts_redis redis-cli ping
```

---

## 17. Docker Volumes (Data Persistence)
Containers are ephemeral by default (if destroyed, data inside is erased). Volumes provide persistent storage:
* **Named Volumes**: Managed by Docker in host storage (`docker volume ls`).
  - Example: `mongo_data:/data/db` preserves all MongoDB documents when container is restarted or updated.
* **Bind Mounts**: Maps a path on your host directly into the container.
  - Example: `.:/app` maps source code live into the container for instant hot-reload during development.

---

## 18. Docker Networks
Enables inter-container communication via an isolated internal bridge network:
* **Default Bridge**: Legacy; requires manual linking.
* **User-Defined Bridge** (`receipt_network`): Built-in DNS resolution.
  - In our code, FastAPI connects to `mongodb://mongo:27017`, `redis://redis:6379`, and `amqp://rabbitmq:5672` using container service names directly.

---

## 19. Docker Compose
A tool for defining and running multi-container Docker applications via a single YAML file (`docker-compose.yml`).
```powershell
docker-compose up -d --build   # Build images and start all 4 containers in background
docker-compose ps              # Check status and health of all services
docker-compose stop            # Stop running containers without deleting them
docker-compose down            # Stop and remove containers, networks
docker-compose down -v         # Stop and delete containers, networks, AND persistent volumes
```

---

## 20. FastAPI + MongoDB Multi-Container Stack

Our complete stack runs:
1. `ecommerce_receipts_mongo` (MongoDB 7.0 database)
2. `ecommerce_receipts_redis` (Redis 7.2 distributed cache)
3. `ecommerce_receipts_rabbitmq` (RabbitMQ 3.13 message broker)
4. `ecommerce_receipts_api` (FastAPI backend service)

* Order of startup: `depends_on` with `condition: service_healthy` ensures the API only boots when MongoDB, Redis, and RabbitMQ have all passed health checks.

---

## 21. Testing via Swagger & Postman
* **Swagger UI**: Visit `http://localhost:8000/docs`. Click **Authorize**, paste Bearer token, execute endpoints.
* **Postman**: Import `postman/receipt_api_collection.json`. Set `baseUrl` to `http://localhost:8000`.

---

## 22. Debugging Docker Applications

1. **Check Container Status**: `docker-compose ps` (verify if `healthy`, `starting`, or `unhealthy`).
2. **Inspect Error Logs**: `docker-compose logs --tail=100 api`
3. **Inspect Exit Code**: `docker inspect --format='{{.State.ExitCode}}' <container>`
4. **Inspect Network Connectivity**:
   ```powershell
   docker exec -it ecommerce_receipts_api curl -v http://mongo:27017
   ```
5. **Inspect Live Resources**: `docker stats` (diagnose OOM/memory leaks or 100% CPU spikes).

---

## 23. Docker System Cleanup

```powershell
# Remove all stopped containers, unused networks, and dangling images
docker system prune -f

# Remove all unused images, volumes, and containers (Deep clean)
docker system prune -a --volumes -f
```

---

## 24. Top Docker Interview Questions & Answers

1. **Q: What is the difference between `CMD` and `ENTRYPOINT` in a Dockerfile?**
   - *A*: `ENTRYPOINT` defines the executable that always runs, while `CMD` provides default arguments that can be easily overridden when running `docker run <image> <override_args>`.
2. **Q: What is a Multi-Stage Docker build and why use it?**
   - *A*: It allows using multiple `FROM` instructions in a single Dockerfile. Early stages compile code or install heavy SDKs; the final stage copies only the required binaries. This keeps production images lean and secure.
3. **Q: Why should containers not run as the `root` user?**
   - *A*: If an attacker gains shell execution inside a root container, any container breakout vulnerability grants them root privileges on the host operating system.
4. **Q: What is the difference between `ADD` and `COPY`?**
   - *A*: `COPY` only copies files from the local host into the container. `ADD` can download files from URLs and automatically extract `.tar.gz` archives. Best practice is to use `COPY` for predictability.
5. **Q: How do containers communicate with each other in Docker Compose?**
   - *A*: Docker Compose creates a user-defined bridge network with automatic embedded DNS. Containers communicate using service names (e.g., `http://mongo:27017`) as hostnames.
