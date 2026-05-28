from agent_vfs.types import (
    Entry, BackendCapabilities,
    VFSError, NotFoundError, ConflictError, CapabilityError,
    ZoneViolationError, ValidationError, PermissionGateError,
)


def test_error_hierarchy():
    assert issubclass(NotFoundError, VFSError)
    assert issubclass(ConflictError, VFSError)
    assert issubclass(CapabilityError, VFSError)
    assert issubclass(ZoneViolationError, VFSError)
    assert issubclass(ValidationError, VFSError)
    assert issubclass(PermissionGateError, VFSError)


def test_entry_dataclass():
    e = Entry(key="foo", mtime=1.0, size=42, etag="abc")
    assert e.key == "foo"
    assert e.size == 42


def test_backend_capabilities():
    c = BackendCapabilities(
        atomic_write=True, etag_native=False,
        list_consistency="strong", search=True,
        max_object_size_bytes=10_000_000,
    )
    assert c.max_object_size_bytes == 10_000_000
