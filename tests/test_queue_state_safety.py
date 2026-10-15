"""Queue state safety: the dual-upload queue must survive concurrent writers
and a corrupt file without silently losing queued deliverables."""
import json
import subprocess
import sys

import pytest

from scripts import uploader


def test_concurrent_enqueue_from_two_processes_keeps_both_entries(tmp_path, monkeypatch):
    queue_file = tmp_path / "dual_queue.json"
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(queue_file))
    code = (
        "import sys; sys.path.insert(0, {root!r}); "
        "from scripts import uploader; "
        "uploader.QUEUE_FILE = sys.argv[2]; "
        "from scripts.uploader import enqueue_dual_upload; "
        "enqueue_dual_upload(sys.argv[1], 'meta.json', 'test')"
    ).format(root=uploader.ROOT)
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(tmp_path / f"video_{i}.mp4"), str(queue_file)]
        )
        for i in range(2)
    ]
    for p in procs:
        assert p.wait() == 0
    items = json.loads(queue_file.read_text(encoding="utf-8"))
    paths = {it["video_path"] for it in items}
    assert paths == {str(tmp_path / "video_0.mp4"), str(tmp_path / "video_1.mp4")}


def test_enqueue_is_atomic_when_the_write_fails(tmp_path, monkeypatch):
    queue_file = tmp_path / "dual_queue.json"
    first = [{"id": "queue_1", "video_path": "a.mp4", "status": "PENDING_DUAL_SYNC"}]
    queue_file.write_text(json.dumps(first), encoding="utf-8")
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(queue_file))
    real_dump = json.dump

    def failing_dump(obj, fh, *a, **k):
        real_dump(obj, fh, *a, **k)
        fh.flush()
        raise OSError("disk full")

    monkeypatch.setattr(uploader.json, "dump", failing_dump)
    with pytest.raises(OSError):
        uploader.enqueue_dual_upload("b.mp4", "m.json", "test")
    # The previous queue state survives untouched; no torn temp file is left.
    assert json.loads(queue_file.read_text(encoding="utf-8")) == first
    leftovers = [
        p.name for p in tmp_path.iterdir()
        if p.name != "dual_queue.json" and not p.name.endswith(".lock")
    ]
    assert leftovers == []


def test_corrupt_queue_file_is_backed_up_and_recovered(tmp_path, monkeypatch):
    queue_file = tmp_path / "dual_queue.json"
    queue_file.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(queue_file))
    entry = uploader.enqueue_dual_upload("b.mp4", "m.json", "quota")
    items = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(items) == 1 and items[0]["video_path"] == "b.mp4"
    assert entry["status"] == "PENDING_DUAL_SYNC"
    backups = [p for p in tmp_path.iterdir() if ".corrupt-" in p.name]
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not json"


def test_get_dual_queue_reports_empty_on_corrupt_file_without_touching_it(tmp_path, monkeypatch):
    queue_file = tmp_path / "dual_queue.json"
    queue_file.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(queue_file))
    assert uploader.get_dual_queue() == []
    assert queue_file.read_text(encoding="utf-8") == "{broken"


def test_duplicate_video_is_not_enqueued_twice(tmp_path, monkeypatch):
    queue_file = tmp_path / "dual_queue.json"
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(queue_file))
    first = uploader.enqueue_dual_upload("a.mp4", "m.json", "one")
    second = uploader.enqueue_dual_upload("a.mp4", "m.json", "two")
    assert first["video_path"] == second["video_path"]
    items = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(items) == 1


def test_enqueue_refuses_to_write_when_the_corrupt_backup_fails(tmp_path, monkeypatch):
    """A corrupt queue whose backup cannot be created must stop the enqueue:
    the original file is preserved and never silently replaced."""
    queue_file = tmp_path / "dual_queue.json"
    queue_file.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(queue_file))

    def failing_replace(src, dst, *a, **k):
        raise OSError("backup failed")

    monkeypatch.setattr(uploader.os, "replace", failing_replace)
    with pytest.raises(RuntimeError):
        uploader.enqueue_dual_upload("b.mp4", "m.json", "quota")
    # The corrupt file survives untouched; nothing was written over it.
    assert queue_file.read_text(encoding="utf-8") == "{not json"
    leftovers = [
        p.name for p in tmp_path.iterdir()
        if p.name != "dual_queue.json" and not p.name.endswith(".lock")
    ]
    assert leftovers == []


@pytest.mark.skipif(uploader.fcntl is None, reason="POSIX-only cross-process lock")
def test_enqueue_aborts_when_the_cross_process_lock_cannot_be_taken(tmp_path, monkeypatch):
    """On POSIX, a failed lock is fatal: enqueue must abort instead of
    continuing unlocked and reopening the lost-update race."""
    queue_file = tmp_path / "dual_queue.json"
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(queue_file))

    class LockedOut:
        LOCK_EX = 2

        @staticmethod
        def flock(fd, op):
            raise OSError("lock held elsewhere")

    monkeypatch.setattr(uploader, "fcntl", LockedOut)
    with pytest.raises(RuntimeError):
        uploader.enqueue_dual_upload("b.mp4", "m.json", "test")
    # The refused enqueue must not have written anything.
    assert not queue_file.exists()
    leftovers = [p.name for p in tmp_path.iterdir() if not p.name.endswith(".lock")]
    assert leftovers == []


def test_enqueue_without_fcntl_falls_back_to_the_in_process_lock(tmp_path, monkeypatch):
    """Non-POSIX platforms (no fcntl) keep working under the in-process mutex."""
    queue_file = tmp_path / "dual_queue.json"
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(queue_file))
    monkeypatch.setattr(uploader, "fcntl", None)
    entry = uploader.enqueue_dual_upload("b.mp4", "m.json", "non-posix")
    assert entry["status"] == "PENDING_DUAL_SYNC"
    items = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(items) == 1 and items[0]["video_path"] == "b.mp4"
