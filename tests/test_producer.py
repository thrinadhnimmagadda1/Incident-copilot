from producer import parse_hdfs_line, parse_log_line, parse_openstack_line


def test_parse_hdfs_line_extracts_fields():
    parsed = parse_hdfs_line(
        "081109 203615 148 INFO dfs.DataNode: PacketResponder 1 for block terminating"
    )
    assert parsed["level"] == "INFO"
    assert parsed["component"] == "dfs.DataNode"
    assert "PacketResponder" in parsed["message"]


def test_parse_hdfs_line_rejects_invalid_input():
    assert parse_hdfs_line("not an HDFS log") is None


def test_parse_openstack_line_extracts_cloud_fields():
    parsed = parse_openstack_line(
        'nova-api.log.1.2017-05-16_13:53:08 2017-05-16 00:00:00.008 25746 '
        'INFO nova.osapi_compute.wsgi.server '
        '[req-38101a0b-2096-447d-96ea-a692162415ae user tenant - - -] '
        '10.11.10.1 "GET /v2/tenant/servers/detail HTTP/1.1" '
        "status: 200 len: 1893 time: 0.2477829"
    )

    assert parsed["source"] == "OpenStack"
    assert parsed["level"] == "INFO"
    assert parsed["component"] == "nova.osapi_compute.wsgi.server"
    assert parsed["status_code"] == 200
    assert parsed["latency_seconds"] == 0.2477829
    assert parsed["request_id"] == "req-38101a0b-2096-447d-96ea-a692162415ae"


def test_parse_log_line_routes_by_source():
    parsed = parse_log_line(
        "081109 203615 148 INFO dfs.DataNode: PacketResponder 1 for block terminating",
        source="HDFS",
    )

    assert parsed["component"] == "dfs.DataNode"
