# NetPulse: SRE Telemetry & Observability Stack

NetPulse is a production-grade internal telemetry API and observability pipeline designed to monitor network latency and uptime for external domains. It demonstrates enterprise infrastructure principles including reverse proxying, application server concurrency, connection pooling, and multi-layered OSI telemetry visualization.

## Live Observability Dashboard
![NetPulse Dashboard](dashboard.png)

## Architecture (3-Tier + Observability)

1. **Layer 1: Web Server / Reverse Proxy (Nginx)**
   * Binds to Port 80.
   * Handles raw TCP connections and strictly forwards traffic to the internal App Server.
2. **Layer 2: Application Server (Gunicorn & Flask)**
   * Binds to Port 5000 (Localhost restricted).
   * Utilizes a Master-Worker architecture (`--workers 3`) to prevent single-threaded blocking during network latency checks.
   * **Upgraded Telemetry:** Bypasses standard ICMP firewalls by executing raw TCP socket connections (Layer 4) and HTTP status code validation (Layer 7).
3. **Layer 3: Database Engine (PostgreSQL)**
   * Binds to Port 5432.
   * Accessed via a restricted service account (`sre_user`).
   * Implements TCP Connection Pooling to prevent database connection exhaustion under heavy load.
4. **Layer 4: Observability (Grafana)**
   * Directly queries the PostgreSQL data warehouse independently of the API.
   * Features real-time state timelines, HTTP response distributions, and visual threshold alerting for network jitter.

## Core SRE Features Engineered

* **Cascading Failure Protection (Hard Timeouts):** Implemented strict application-side database timeouts. If the PostgreSQL storage layer degrades, the Python worker threads will violently drop the connection after 3000ms rather than hanging, protecting the API from resource exhaustion.
* **Graceful Degradation:** If the database crashes, the API catches the exception, completes the network telemetry check, and returns a `207 Multi-Status` detailing the partial infrastructure failure.
* **Zero-Downtime Migrations:** The schema was evolved in real-time to capture TCP and DB latency metrics without dropping legacy table data.
* **Process Isolation & Input Sanitization:** The application utilizes regex-based payload validation to protect the underlying OS from command injection vulnerabilities.