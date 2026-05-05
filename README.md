# NetPulse: SRE Telemetry API

NetPulse is a production-grade internal telemetry API designed to monitor network latency and uptime for external domains. It is built to demonstrate enterprise infrastructure principles including reverse proxying, application server concurrency, and database connection pooling.

## Architecture (3-Tier)
1. **Layer 1: Web Server / Reverse Proxy (Nginx)**
   - Binds to Port 80.
   - Handles raw TCP connections and strictly forwards traffic to the internal App Server.
2. **Layer 2: Application Server (Gunicorn & Flask)**
   - Binds to Port 5000 (Localhost restricted).
   - Utilizes a Master-Worker architecture (`--workers 3`) to prevent single-threaded blocking during network latency checks.
   - Executes OS-level ICMP network pings via Python subprocesses.
3. **Layer 3: Database Engine (PostgreSQL)**
   - Binds to Port 5432.
   - Accessed via a restricted service account (`sre_user`).
   - Implements **TCP Connection Pooling** (1-5 active connections) to prevent database connection exhaustion under heavy load.

## Core SRE Features
* **Graceful Degradation:** If the PostgreSQL database crashes, the API catches the exception, completes the network telemetry check, and returns a `207 Multi-Status` detailing the partial infrastructure failure.
* **Structured Logging:** Outputs strict JSON-formatted logs ready for ingestion by tools like Datadog, Splunk, or AWS CloudWatch.
* **Process Isolation:** The application cannot execute shell injections; it strictly parses standard output from the Ubuntu kernel network stack.

## Usage
**POST /api/telemetry**
```bash
curl -X POST http://<server_ip>/api/telemetry \
-H "Content-Type: application/json" \
-d '{"domain": "amazon.de"}'
