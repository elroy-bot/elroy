import time
from pathlib import Path

import pytest

from elroy.core.ctx import ElroyContext
from elroy.repository.background_ingestion.operations import (
    create_background_ingestion_config,
    delete_background_ingestion_config,
    get_include_exclude_patterns,
    mark_scan_completed,
    update_background_ingestion_config,
)
from elroy.repository.background_ingestion.queries import (
    get_active_background_ingestion_config,
    get_background_ingestion_config,
)
from elroy.repository.background_ingestion.tools import (
    get_background_ingestion_status,
    remove_background_ingestion,
    setup_background_ingestion,
)


def test_create_background_ingestion_config(ctx: ElroyContext, tmpdir: str):
    """Test creating a background ingestion configuration."""
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()

    config = create_background_ingestion_config(
        ctx=ctx,
        watch_directory=str(watch_dir),
        recursive=True,
        include_patterns=["*.md", "*.txt"],
        exclude_patterns=["*.log"],
    )

    assert config.user_id == ctx.user_id
    assert config.watch_directory == str(watch_dir.resolve())
    assert config.is_active == True
    assert config.recursive == True
    assert config.include_patterns == "*.md,*.txt"
    assert config.exclude_patterns == "*.log"
    assert config.last_scan_status == "pending"


def test_create_config_invalid_directory(ctx: ElroyContext):
    """Test creating config with invalid directory raises error."""
    with pytest.raises(ValueError, match="Directory does not exist"):
        create_background_ingestion_config(ctx=ctx, watch_directory="/non/existent/path")


def test_create_config_duplicate_raises_error(ctx: ElroyContext, tmpdir: str):
    """Test creating duplicate config raises error."""
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()

    # Create first config
    create_background_ingestion_config(ctx=ctx, watch_directory=str(watch_dir))

    # Attempt to create second config should fail
    with pytest.raises(ValueError, match="Background ingestion configuration already exists"):
        create_background_ingestion_config(ctx=ctx, watch_directory=str(watch_dir))


def test_update_background_ingestion_config(ctx: ElroyContext, tmpdir: str):
    """Test updating background ingestion configuration."""
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()

    # Create initial config
    config = create_background_ingestion_config(ctx=ctx, watch_directory=str(watch_dir))
    original_updated_at = config.updated_at

    # Wait a bit to ensure updated_at changes
    time.sleep(0.1)

    # Update config
    updated_config = update_background_ingestion_config(
        ctx=ctx,
        is_active=False,
        include_patterns=["*.py"],
    )

    assert updated_config.id == config.id
    assert updated_config.is_active == False
    assert updated_config.include_patterns == "*.py"
    assert updated_config.recursive == True  # Should remain unchanged
    assert updated_config.updated_at > original_updated_at


def test_update_nonexistent_config_raises_error(ctx: ElroyContext):
    """Test updating nonexistent config raises error."""
    with pytest.raises(ValueError, match="No background ingestion configuration exists"):
        update_background_ingestion_config(ctx=ctx, is_active=False)


def test_get_include_exclude_patterns():
    """Test parsing include/exclude patterns."""
    from elroy.db.db_models import BackgroundIngestionConfig

    config = BackgroundIngestionConfig(
        user_id=1,
        watch_directory="/test",
        is_active=True,
        recursive=True,
        include_patterns="*.md, *.txt,*.py ",
        exclude_patterns=" *.log,*.tmp , *.bak",
        last_scan_status="pending",
    )

    include_patterns, exclude_patterns = get_include_exclude_patterns(config)

    assert include_patterns == ["*.md", "*.txt", "*.py"]
    assert exclude_patterns == ["*.log", "*.tmp", "*.bak"]


def test_get_include_exclude_patterns_empty():
    """Test parsing empty patterns."""
    from elroy.db.db_models import BackgroundIngestionConfig

    config = BackgroundIngestionConfig(
        user_id=1,
        watch_directory="/test",
        is_active=True,
        recursive=True,
        include_patterns="",
        exclude_patterns="",
        last_scan_status="pending",
    )

    include_patterns, exclude_patterns = get_include_exclude_patterns(config)

    assert include_patterns == []
    assert exclude_patterns == []


def test_mark_scan_completed(ctx: ElroyContext, tmpdir: str):
    """Test marking scan as completed."""
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()

    config = create_background_ingestion_config(ctx=ctx, watch_directory=str(watch_dir))
    assert config.last_full_scan is None
    assert config.last_scan_status == "pending"

    mark_scan_completed(ctx, success=True)

    updated_config = get_background_ingestion_config(ctx)
    assert updated_config.last_full_scan is not None
    assert updated_config.last_scan_status == "success"

    mark_scan_completed(ctx, success=False)

    updated_config = get_background_ingestion_config(ctx)
    assert updated_config.last_scan_status == "error"


def test_delete_background_ingestion_config(ctx: ElroyContext, tmpdir: str):
    """Test deleting background ingestion configuration."""
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()

    # Create config
    create_background_ingestion_config(ctx=ctx, watch_directory=str(watch_dir))
    assert get_background_ingestion_config(ctx) is not None

    # Delete config
    success = delete_background_ingestion_config(ctx)
    assert success == True
    assert get_background_ingestion_config(ctx) is None

    # Delete nonexistent config
    success = delete_background_ingestion_config(ctx)
    assert success == False


def test_get_active_background_ingestion_config(ctx: ElroyContext, tmpdir: str):
    """Test getting active background ingestion configuration."""
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()

    # No config initially
    assert get_active_background_ingestion_config(ctx) is None

    # Create active config
    create_background_ingestion_config(ctx=ctx, watch_directory=str(watch_dir))
    active_config = get_active_background_ingestion_config(ctx)
    assert active_config is not None
    assert active_config.is_active == True

    # Deactivate config
    update_background_ingestion_config(ctx=ctx, is_active=False)
    assert get_active_background_ingestion_config(ctx) is None


def test_setup_background_ingestion_tool(ctx: ElroyContext, tmpdir: str):
    """Test setup_background_ingestion tool."""
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()

    result = setup_background_ingestion(
        ctx=ctx, directory=str(watch_dir), recursive=True, include_patterns="*.md,*.txt", exclude_patterns="*.log"
    )

    assert "Background ingestion enabled" in result
    assert str(watch_dir) in result

    # Verify config was created
    config = get_background_ingestion_config(ctx)
    assert config is not None
    assert config.include_patterns == "*.md,*.txt"
    assert config.exclude_patterns == "*.log"


def test_setup_background_ingestion_duplicate(ctx: ElroyContext, tmpdir: str):
    """Test setup tool with existing config."""
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()

    # Create first config
    setup_background_ingestion(ctx=ctx, directory=str(watch_dir))

    # Try to create second config
    result = setup_background_ingestion(ctx=ctx, directory=str(watch_dir))
    assert "already configured" in result


def test_get_background_ingestion_status_tool(ctx: ElroyContext, tmpdir: str):
    """Test get_background_ingestion_status tool."""
    # No config initially
    result = get_background_ingestion_status(ctx)
    assert "not configured" in result

    # Create config
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()
    setup_background_ingestion(ctx=ctx, directory=str(watch_dir), include_patterns="*.md")

    result = get_background_ingestion_status(ctx)
    assert "enabled" in result
    assert str(watch_dir) in result
    assert "*.md" in result


def test_remove_background_ingestion_tool(ctx: ElroyContext, tmpdir: str):
    """Test remove_background_ingestion tool."""
    # Remove nonexistent config
    result = remove_background_ingestion(ctx)
    assert "No background ingestion configuration found" in result

    # Create and remove config
    watch_dir = Path(tmpdir) / "watch_dir"
    watch_dir.mkdir()
    setup_background_ingestion(ctx=ctx, directory=str(watch_dir))

    result = remove_background_ingestion(ctx)
    assert "removed completely" in result
    assert get_background_ingestion_config(ctx) is None
