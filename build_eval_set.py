"""Build a 50-case labeled benchmark covering matches and safe refusals."""

import json

POSITIVE_CASES = {
    "INC-001": [
        "DataNode got exception while serving block to peer node",
        "dfs.DataNode DataXceiver exception serving blk_883 to 10.2.1.9",
        "HDFS peer transfer socket timed out while sending replicated block",
        "Multiple DataNodes failed while serving blocks during replication",
        "Block transfer to receiving DataNode stalled and write timed out",
        "WARN DataXceiver Got exception while serving blk_1024",
    ],
    "INC-002": [
        "nova imagecache reports Unknown base file repeatedly",
        "Unknown base file under /var/lib/nova/instances/_base",
        "Nova compute image cache manager cannot find tracked base image",
        "Missing cached base image warning repeats every forty seconds",
        "libvirt imagecache stale tracking entry references deleted base",
        "WARNING nova.virt.libvirt.imagecache Unknown base file hash",
    ],
    "INC-003": [
        "Repeated SSH authentication failures from one external IP",
        "sshd authentication failure targeting root many times",
        "Possible SSH brute force scan with dozens of failed logins",
        "Linux host reports repeated failed SSH attempts for common users",
        "PAM authentication failures from a single remote address",
        "authentication failure logname uid=0 tty=NODEVssh rhost=203.0.113.8",
    ],
    "INC-004": [
        "NameSystem chooseTarget not able to place enough replicas",
        "HDFS reports under replicated blocks after DataNode restart",
        "NameNode cannot satisfy replication factor during maintenance",
        "Several DataNodes restarted together and block replicas are under count",
        "BLOCK chooseTarget failed to place sufficient replicas",
        "Replication monitor behind after batch DataNode restart",
    ],
    "INC-005": [
        "Nova GET servers detail request took 7.8 seconds",
        "OpenStack instance list API latency increased during peak load",
        "GET /v2/project/servers/detail status 200 time 5.4",
        "Nova API slow query listing tenant instances",
        "Instance detail endpoint latency rose from milliseconds to seconds",
        "OpenStack servers detail query performs slowly for large tenant",
    ],
    "INC-006": [
        "Spark executor silently restarted with fresh signal handler log",
        "CoarseGrainedExecutorBackend registered signal handlers again mid job",
        "YARN executor container disappeared and restarted without application error",
        "Spark job sees new executor startup but no preceding exception",
        "Executor was preempted by higher priority YARN queue",
        "INFO executor registered signal handlers after silent restart",
    ],
    "INC-007": [
        "Kafka consumer lag increased after broker restart and leader election",
        "Offset commit failed while consumer coordinator was unavailable",
        "Consumer group rebalanced and lag spiked after partition leadership moved",
    ],
    "INC-008": [
        "Kubernetes pods entered CrashLoopBackOff because ConfigMap key was missing",
        "Back-off restarting failed container after deployment rollout",
        "Required environment variable from ConfigMap was absent in namespace",
    ],
    "INC-009": [
        "PostgreSQL reports remaining connection slots are reserved during nightly job",
        "API cannot get DB connections while batch workers are running",
        "PgBouncer pool saturated because job opened too many database connections",
    ],
    "INC-010": [
        "Redis cache started evicting keys after memory limit was reached",
        "Cache hit rate dropped and Redis maxmemory eviction increased",
        "Large cached responses without TTL caused Redis memory pressure",
    ],
    "INC-011": [
        "Nginx upstream timed out while reading response header",
        "Users see 504 gateway timeout because application workers are saturated",
        "Application blocked on downstream calls and Nginx timed out",
    ],
    "INC-012": [
        "Airflow scheduler heartbeat exception stopped DAG scheduling",
        "DAGs are not queued after metadata database failover",
        "Airflow scheduler lost database heartbeat and tasks stopped launching",
    ],
    "INC-013": [
        "Elasticsearch high disk watermark exceeded and replicas are unassigned",
        "Index health yellow because shard allocation is blocked by disk usage",
        "Data node crossed disk watermark after log traffic spike",
    ],
    "INC-014": [
        "S3 PutObject failed with ExpiredToken after workers ran for hours",
        "Ingestion workers cached temporary IAM credentials too long",
        "AWS upload failed because session token expired",
    ],
    "INC-015": [
        "Celery workers cannot connect to RabbitMQ and queue backlog grows",
        "Task queue depth increases while workers keep stale broker connections",
        "RabbitMQ broker failover left Celery consumers disconnected",
    ],
    "INC-016": [
        "Prometheus scrape returns 404 for metrics after service port rename",
        "Dashboards miss service metrics because ServiceMonitor scraped old endpoint",
        "Kubernetes ServiceMonitor selector no longer matches metrics endpoint",
    ],
    "INC-017": [
        "CoreDNS plugin errors show UDP timeout resolving service name",
        "Pods intermittently cannot resolve internal service DNS",
        "Stale CoreDNS upstream resolver state after node network interruption",
    ],
    "INC-018": [
        "GitHub Actions job failed with no space left on device",
        "CI runner disk filled during Docker layer extraction",
        "Dependency install failed because ephemeral runner storage was exhausted",
    ],
}

NEGATIVE_CASES = [
    "Payment gateway returned HTTP 503 during checkout",
    "React build cannot resolve components Header module",
    "iOS application crashed while opening the camera",
    "Customer password reset email was not delivered",
    "Android checkout button is hidden below the keyboard",
    "DNS provider failed to resolve the public marketing domain",
    "Fraud model feature pipeline produced null scores",
    "Salesforce webhook signature validation failed",
    "Browser CORS policy blocked an analytics request",
    "Stripe webhook replay protection rejected a duplicate event",
    "Figma design export lost component constraints",
    "Mobile push notifications delayed by APNs feedback service",
    "Warehouse ETL produced duplicate customer rows",
    "CRM lead assignment rule routed all leads to one owner",
    "Third party geocoding API returned invalid coordinates",
    "Feature flag targeted the wrong beta cohort",
    "PDF invoice renderer clipped the final table row",
    "Search autocomplete returns stale product names",
    "Email unsubscribe link produced a 410 response",
]


def build_cases():
    cases = []
    for incident_id, triggers in POSITIVE_CASES.items():
        domain = {
            "INC-001": "HDFS", "INC-002": "OpenStack", "INC-003": "Linux",
            "INC-004": "HDFS", "INC-005": "OpenStack", "INC-006": "Spark",
            "INC-007": "Kafka", "INC-008": "Kubernetes", "INC-009": "PostgreSQL",
            "INC-010": "Redis", "INC-011": "Nginx", "INC-012": "Airflow",
            "INC-013": "Elasticsearch", "INC-014": "AWS S3", "INC-015": "Celery",
            "INC-016": "Prometheus", "INC-017": "CoreDNS", "INC-018": "GitHub Actions",
        }[incident_id]
        for trigger in triggers:
            cases.append({
                "trigger": trigger,
                "expected_incident": incident_id,
                "domain": domain,
                "ground_truth": f"The anomaly should retrieve and match {incident_id}.",
            })
    cases.extend({
        "trigger": trigger,
        "expected_incident": None,
        "domain": "novel",
        "ground_truth": "No matching incident exists; the system should escalate.",
    } for trigger in NEGATIVE_CASES)
    return cases


if __name__ == "__main__":
    test_cases = build_cases()
    with open("data/eval_set.json", "w") as handle:
        json.dump(test_cases, handle, indent=2)
    positives = len(test_cases) - len(NEGATIVE_CASES)
    print(f"Built {len(test_cases)} cases: {positives} known incidents and {len(NEGATIVE_CASES)} novel incidents")
