"""SnapshotStore — persists PipelineSnapshotDocuments to Cosmos DB.

In file mode (STORAGE_BACKEND=file) snapshots are written as JSON files
under a 'snapshots/' sibling to the sessions directory.  In Cosmos mode
they live in a dedicated 'snapshots' container within the same DB.
"""
from __future__ import annotations

import json
import pathlib
import uuid

from server.snapshot.models import PipelineSnapshotDocument


class FileSnapshotStore:
    """File-backed snapshot store for local development (STORAGE_BACKEND=file)."""

    def __init__(self, snapshots_dir: pathlib.Path) -> None:
        self.snapshots_dir = snapshots_dir
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def upsert(self, doc: PipelineSnapshotDocument) -> None:
        path = self.snapshots_dir / f"{doc.week_start}.json"
        path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")

    def get_by_week_start(self, week_start: str) -> PipelineSnapshotDocument | None:
        path = self.snapshots_dir / f"{week_start}.json"
        if not path.exists():
            return None
        return PipelineSnapshotDocument(**json.loads(path.read_text(encoding="utf-8")))

    def get_latest(self) -> PipelineSnapshotDocument | None:
        files = sorted(self.snapshots_dir.glob("*.json"), reverse=True)
        if not files:
            return None
        return PipelineSnapshotDocument(**json.loads(files[0].read_text(encoding="utf-8")))


class CosmosSnapshotStore:
    """Cosmos-backed snapshot store."""

    CONTAINER_NAME = "snapshots"

    def __init__(self, connection_string: str, verify_ssl: bool = True) -> None:
        from azure.cosmos import CosmosClient, PartitionKey
        client = CosmosClient.from_connection_string(
            connection_string, connection_verify=verify_ssl
        )
        db = client.create_database_if_not_exists("victros")
        self._container = db.create_container_if_not_exists(
            id=self.CONTAINER_NAME,
            partition_key=PartitionKey(path="/week_start"),
        )

    def upsert(self, doc: PipelineSnapshotDocument) -> None:
        data = doc.model_dump()
        self._container.upsert_item(data)

    def get_by_week_start(self, week_start: str) -> PipelineSnapshotDocument | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        try:
            doc = self._container.read_item(doc["snapshot_id"], partition_key=week_start)
            return PipelineSnapshotDocument(**doc)
        except CosmosResourceNotFoundError:
            return None

    def get_latest(self) -> PipelineSnapshotDocument | None:
        items = list(self._container.query_items(
            query="SELECT TOP 1 * FROM c ORDER BY c.week_start DESC",
            enable_cross_partition_query=True,
        ))
        if not items:
            return None
        return PipelineSnapshotDocument(**items[0])
