"""测试 search/scanner.py — 目录扫描器"""

from search.scanner import scan_directory, scan_projects, is_plc_related_file


class TestScanDirectory:
    def test_scan_empty_dir(self, tmp_path):
        result = scan_directory(str(tmp_path))
        assert result == []

    def test_scan_with_plc_files(self, tmp_path):
        (tmp_path / "block.scl").write_text("FUNCTION_BLOCK test")
        (tmp_path / "tags.csv").write_text("Name,Address")
        (tmp_path / "config.xml").write_text("<root/>")
        (tmp_path / "readme.md").write_text("# Readme")  # 不应被扫描

        result = scan_directory(str(tmp_path))
        assert len(result) == 3
        exts = {r["ext"] for r in result}
        assert ".scl" in exts
        assert ".csv" in exts
        assert ".xml" in exts

    def test_scan_excludes_dirs(self, tmp_path):
        excluded = tmp_path / "node_modules"
        excluded.mkdir()
        (excluded / "test.scl").write_text("FUNCTION test")

        result = scan_directory(str(tmp_path))
        assert len(result) == 0

    def test_scan_nonexistent_dir(self):
        result = scan_directory("/nonexistent/path")
        assert result == []


class TestScanProjects:
    def test_scan_multiple_dirs(self, tmp_path):
        d1 = tmp_path / "proj1"
        d2 = tmp_path / "proj2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "a.scl").write_text("test")
        (d2 / "b.scl").write_text("test")

        result = scan_projects([str(d1), str(d2)])
        assert len(result) == 2

    def test_deduplication(self, tmp_path):
        (tmp_path / "file.scl").write_text("test")
        result = scan_projects([str(tmp_path), str(tmp_path)])
        assert len(result) == 1


class TestIsPlcRelated:
    def test_plc_extensions(self):
        assert is_plc_related_file("motor.scl")
        assert is_plc_related_file("tags.csv")
        assert is_plc_related_file("block.xml")
        assert not is_plc_related_file("readme.md")
        assert not is_plc_related_file("app.py")
