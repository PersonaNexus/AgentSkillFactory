"""Tests for configuration management."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentforge.config import AgentForgeConfig, load_config, save_config


class TestAgentForgeConfig:
    def test_defaults(self):
        config = AgentForgeConfig()
        assert config.api_key == ""
        assert config.default_model == "claude-sonnet-4-20250514"
        assert config.output_dir == "."
        assert config.default_culture is None
        assert config.batch_parallel == 1

    def test_custom_values(self):
        config = AgentForgeConfig(
            api_key="sk-test-key",
            default_model="claude-haiku-4-5-20251001",
            output_dir="./agents",
            default_culture="startup_innovative",
            batch_parallel=4,
        )
        assert config.api_key == "sk-test-key"
        assert config.batch_parallel == 4

    def test_batch_parallel_min(self):
        config = AgentForgeConfig(batch_parallel=1)
        assert config.batch_parallel == 1


class TestLoadConfig:
    def test_load_from_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "api_key": "sk-test",
            "default_model": "claude-haiku-4-5-20251001",
            "output_dir": "/tmp/agents",
            "batch_parallel": 2,
        }))

        config = load_config(config_file)
        assert config.api_key == "sk-test"
        assert config.default_model == "claude-haiku-4-5-20251001"
        assert config.batch_parallel == 2

    def test_load_missing_file(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.api_key == ""
        assert config.default_model == "claude-sonnet-4-20250514"

    def test_load_empty_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = load_config(config_file)
        assert config.api_key == ""

    def test_load_invalid_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- just a list")
        config = load_config(config_file)
        assert config.api_key == ""


class TestSaveConfig:
    def test_save_and_reload(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        original = AgentForgeConfig(
            api_key="sk-saved",
            default_model="claude-haiku-4-5-20251001",
            batch_parallel=3,
        )

        save_config(original, config_file)
        assert config_file.exists()

        loaded = load_config(config_file)
        assert loaded.api_key == "sk-saved"
        assert loaded.default_model == "claude-haiku-4-5-20251001"
        assert loaded.batch_parallel == 3

    def test_save_creates_parent_dirs(self, tmp_path):
        config_file = tmp_path / "nested" / "dir" / "config.yaml"
        save_config(AgentForgeConfig(), config_file)
        assert config_file.exists()

    def test_save_restricts_permissions(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        save_config(AgentForgeConfig(api_key="secret"), config_file)
        # Check file permissions are 0o600
        perms = config_file.stat().st_mode & 0o777
        assert perms == 0o600
