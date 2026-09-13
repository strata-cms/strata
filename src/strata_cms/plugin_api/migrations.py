"""Pure in-memory migration support for persisted content schemas."""

from collections.abc import Callable
from dataclasses import dataclass

from strata_cms.domain.revision import RevisionData
from strata_cms.plugin_api.errors import (
    InvalidSchemaMigrationError,
    UnsupportedSchemaVersionError,
)

type SchemaMigrationFunction = Callable[[RevisionData], RevisionData]


@dataclass(frozen=True, slots=True)
class SchemaMigration:
    """One pure migration between adjacent persisted schema versions."""

    from_version: int
    to_version: int
    migrate: SchemaMigrationFunction

    def __post_init__(self) -> None:
        """Require positive adjacent versions for deterministic chains."""
        if self.from_version < 1 or self.to_version != self.from_version + 1:
            raise InvalidSchemaMigrationError(
                "Schema migrations must move exactly one positive version forward."
            )


@dataclass(frozen=True, slots=True)
class SchemaMigrationSet:
    """Validated collection of pure adjacent schema migrations."""

    migrations: tuple[SchemaMigration, ...] = ()

    def validate_for(self, current_version: int) -> None:
        """Require one unbroken migration path from version 1 to current."""
        if current_version < 1:
            raise InvalidSchemaMigrationError(
                "Current schema version must be positive."
            )

        by_source: dict[int, SchemaMigration] = {}
        for migration in self.migrations:
            if migration.from_version in by_source:
                raise InvalidSchemaMigrationError(
                    f"Duplicate migration from version {migration.from_version}."
                )
            by_source[migration.from_version] = migration

        expected_sources = set(range(1, current_version))
        actual_sources = set(by_source)
        if actual_sources != expected_sources:
            missing = sorted(expected_sources - actual_sources)
            extra = sorted(actual_sources - expected_sources)
            details: list[str] = []
            if missing:
                details.append(f"missing sources {missing}")
            if extra:
                details.append(f"unexpected sources {extra}")
            raise InvalidSchemaMigrationError(
                "Schema migration path must cover every version from 1 to "
                f"{current_version}: {', '.join(details)}."
            )

    def migrate(
        self,
        data: RevisionData,
        *,
        from_version: int,
        to_version: int,
    ) -> RevisionData:
        """Upgrade one historical snapshot in memory without mutating storage."""
        if from_version < 1:
            raise UnsupportedSchemaVersionError(
                "Persisted schema version must be positive."
            )
        if from_version > to_version:
            raise UnsupportedSchemaVersionError(
                f"Schema version {from_version} is newer than supported version "
                f"{to_version}."
            )
        if from_version == to_version:
            return data

        by_source = {migration.from_version: migration for migration in self.migrations}
        current = data
        for version in range(from_version, to_version):
            migration = by_source.get(version)
            if migration is None:  # defensive if an invalid definition escaped build
                raise InvalidSchemaMigrationError(
                    f"No migration from schema version {version} to {version + 1}."
                )
            current = migration.migrate(current)
        return current
