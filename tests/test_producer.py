from producer import parse_hdfs_line


def test_parse_hdfs_line_extracts_fields():
    parsed = parse_hdfs_line(
        "081109 203615 148 INFO dfs.DataNode: PacketResponder 1 for block terminating"
    )
    assert parsed["level"] == "INFO"
    assert parsed["component"] == "dfs.DataNode"
    assert "PacketResponder" in parsed["message"]


def test_parse_hdfs_line_rejects_invalid_input():
    assert parse_hdfs_line("not an HDFS log") is None
