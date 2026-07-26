import json

incidents = [
    {
        "id": "INC-001",
        "title": "DataNode packet serving exceptions during peer transfer",
        "log_pattern": "WARN dfs.DataNode$DataXceiver: Got exception while serving blk_* to /*",
        "system": "HDFS",
        "symptoms": "Multiple DataNodes report exceptions while serving blocks to peer nodes. Block replication appears to stall intermittently.",
        "root_cause": "Network instability or peer DataNode overload during block replication. When a receiving DataNode is slow or the network link degrades, the sending DataNode's socket write times out mid-transfer, throwing the exception.",
        "fix": "Checked network utilization on the affected rack, found a saturated top-of-rack switch during a large replication job. Throttled replication bandwidth and the exceptions dropped to baseline within 20 minutes.",
        "severity": "medium",
        "resolution_time_minutes": 35
    },
    {
        "id": "INC-002",
        "title": "Repeated Unknown base file warnings in Nova compute image cache",
        "log_pattern": "WARNING nova.virt.libvirt.imagecache: Unknown base file",
        "system": "OpenStack",
        "symptoms": "Same warning repeats every ~40 seconds for the same base image hash. No user-facing impact observed initially.",
        "root_cause": "A base image was deleted from the image cache directory while VM instances still referenced it in tracking metadata. The periodic image cache manager keeps polling for it.",
        "fix": "Confirmed no active instances depended on the missing base. Cleared the imagecache manager's stale tracking entry to stop the repeated poll.",
        "severity": "low",
        "resolution_time_minutes": 10
    },
    {
        "id": "INC-003",
        "title": "Repeated SSH authentication failures from single external IP",
        "log_pattern": "authentication failure; logname= uid=0 euid=0 tty=NODEVssh",
        "system": "Linux",
        "symptoms": "Dozens of failed SSH login attempts within a short window, all from the same external IP, targeting root and common usernames.",
        "root_cause": "Automated SSH brute-force scan from an external host, not a system fault.",
        "fix": "Confirmed no successful logins occurred. Added the source IP to the firewall deny list and enabled fail2ban with a 3-attempt threshold.",
        "severity": "high",
        "resolution_time_minutes": 15
    },
    {
        "id": "INC-004",
        "title": "HDFS block replication under-count after DataNode restart",
        "log_pattern": "WARN dfs.FSNamesystem: BLOCK* NameSystem.chooseTarget: Not able to place enough replicas",
        "system": "HDFS",
        "symptoms": "NameNode reports under-replicated blocks after a batch of DataNodes were restarted for maintenance.",
        "root_cause": "More DataNodes were restarted simultaneously than the replication factor could tolerate.",
        "fix": "Paused remaining restarts, let the replication monitor catch up, then resumed restarts one node at a time.",
        "severity": "medium",
        "resolution_time_minutes": 45
    },
    {
        "id": "INC-005",
        "title": "Nova API elevated response latency during instance list queries",
        "log_pattern": "GET /v2/*/servers/detail ... time: [3-9].[0-9]+",
        "system": "OpenStack",
        "symptoms": "GET servers/detail requests that normally take 0.25s start taking 3-9 seconds during peak load.",
        "root_cause": "Unindexed join across instances and instance_metadata tables causing a full table scan as tenant instance counts grew.",
        "fix": "Added a composite index on project_id and deleted columns. Query time dropped from 3-9s back to under 0.3s.",
        "severity": "high",
        "resolution_time_minutes": 60
    },
    {
        "id": "INC-006",
        "title": "Spark executor silent restart with no error logged",
        "log_pattern": "INFO executor.CoarseGrainedExecutorBackend: Registered signal handlers",
        "system": "Spark",
        "symptoms": "Executor restarts mid-job with a fresh startup log line but no preceding error.",
        "root_cause": "YARN preempted the executor container to reclaim resources for a higher-priority queue job.",
        "fix": "Cross-referenced YARN logs, confirmed container preemption. No fix needed, documented as expected behavior in the runbook.",
        "severity": "low",
        "resolution_time_minutes": 20
    },
]

with open("data/incidents.json", "w") as f:
    json.dump(incidents, f, indent=2)

print(f"Wrote {len(incidents)} incidents to data/incidents.json")
for inc in incidents:
    print(f"  {inc['id']} [{inc['severity']:6}] {inc['title']}")
