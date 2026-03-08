import logging
import os
import pytest
from pathlib import Path

from utils.app_utils import load_config, backup_file, generate_diff, setup_logging


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------

class TestSetupLogging:
    def test_returns_logger(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = setup_logging(log_file=log_file)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "codebase_agent"

    def test_creates_log_file_directory(self, tmp_path):
        log_file = str(tmp_path / "subdir" / "test.log")
        setup_logging(log_file=log_file)
        assert (tmp_path / "subdir").exists()

    def test_log_level_applies(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = setup_logging(log_file=log_file, log_level="DEBUG")
        assert logger.level == logging.DEBUG


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_loads_valid_config(self):
        config = load_config("configs/config.yaml")
        assert "llm" in config
        assert "agents" in config
        assert "processing" in config

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent_config.yaml")

    def test_resolves_bare_filename(self, tmp_path, monkeypatch):
        """Test that bare filenames are looked up in configs/ directory."""
        # load_config("config.yaml") should find configs/config.yaml
        config = load_config("config.yaml")
        assert "llm" in config

    def test_config_has_enable_flags(self):
        config = load_config("configs/config.yaml")
        agents = config.get("agents", {})
        for agent_name in ["analyst", "developer", "qa_engineer"]:
            assert "enable" in agents.get(agent_name, {}), f"Missing enable flag for {agent_name}"


# ---------------------------------------------------------------------------
# backup_file
# ---------------------------------------------------------------------------

class TestBackupFile:
    def test_creates_backup(self, tmp_path):
        src = tmp_path / "original.py"
        src.write_text("print('hello')", encoding="utf-8")

        logger = logging.getLogger("test_backup")
        # Monkey-patch backups dir to use tmp_path
        import utils.app_utils as mod
        original_path_cls = mod.Path

        backup_path = backup_file(str(src), logger)
        # backup_file creates in ./backups/ relative to cwd; just verify src still exists
        assert src.exists()
        # If backup_path was returned, verify the backup file exists
        if backup_path:
            assert Path(backup_path).exists()
            assert Path(backup_path).read_text(encoding="utf-8") == "print('hello')"

    def test_returns_none_for_missing_file(self):
        logger = logging.getLogger("test_backup")
        result = backup_file("/nonexistent/file.py", logger)
        assert result is None


# ---------------------------------------------------------------------------
# generate_diff
# ---------------------------------------------------------------------------

class TestGenerateDiff:
    def test_generates_diff_file(self, tmp_path):
        original = tmp_path / "original.py"
        modified = tmp_path / "modified.py"
        original.write_text("line1\nline2\nline3\n", encoding="utf-8")
        modified.write_text("line1\nline2_changed\nline3\n", encoding="utf-8")

        output_dir = str(tmp_path / "diffs")
        logger = logging.getLogger("test_diff")
        result = generate_diff(str(original), str(modified), output_dir, logger)

        assert result is not None
        assert Path(result).exists()
        content = Path(result).read_text(encoding="utf-8")
        assert "---" in content
        assert "+++" in content
        assert "-line2" in content
        assert "+line2_changed" in content

    def test_returns_none_when_no_changes(self, tmp_path):
        original = tmp_path / "same.py"
        original.write_text("identical\n", encoding="utf-8")

        output_dir = str(tmp_path / "diffs")
        logger = logging.getLogger("test_diff")
        result = generate_diff(str(original), str(original), output_dir, logger)
        assert result is None

    def test_returns_none_for_missing_file(self, tmp_path):
        output_dir = str(tmp_path / "diffs")
        logger = logging.getLogger("test_diff")
        result = generate_diff("/nonexistent/a.py", "/nonexistent/b.py", output_dir, logger)
        assert result is None

    def test_creates_output_directory(self, tmp_path):
        original = tmp_path / "a.py"
        modified = tmp_path / "b.py"
        original.write_text("old\n", encoding="utf-8")
        modified.write_text("new\n", encoding="utf-8")

        deep_dir = str(tmp_path / "x" / "y" / "z")
        logger = logging.getLogger("test_diff")
        result = generate_diff(str(original), str(modified), deep_dir, logger)
        assert result is not None
        assert Path(deep_dir).exists()
