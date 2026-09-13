# ADR 0001: Data Mapper domain model over Django ORM persistence records

- Status: Accepted
- Date: 2026-09-06

## Context

Strata uses Django primarily for its mature web stack, migrations,
authentication/authorization integration, Django Admin, and django-unfold.
Django ORM exposes Active Record-style APIs (`Model.objects`, instance
`.save()`/`.delete()`), but the project does not want persistence behavior on
its domain entities or spread through application code.

Replacing Django ORM with SQLAlchemy would provide a more native Data Mapper
model but would substantially weaken/duplicate Django Admin model metadata,
ModelForms, migrations, permissions, relationship integration, and transaction
conventions, or require two ORMs against the same schema.

## Decision

Retain Django ORM strictly as an infrastructure persistence adapter.

- Domain entities are plain Python objects and never subclass `models.Model`.
- Django ORM classes are persistence records, preferably named `*Record`.
- Explicit mappers convert records to/from domain entities.
- Repository interfaces expose aggregates/entities to application code.
- Unit of Work ports express transaction boundaries; Django implementations use
  `transaction.atomic()` internally.
- Read/query services may use optimized ORM/SQL internally and return immutable
  DTOs/read models rather than hydrating entities unnecessarily.
- Django Admin may register persistence records, but custom business operations
  invoke application use cases rather than implementing Active Record workflows.
- Import Linter enforces framework/infrastructure independence where expressible.

## Consequences

Benefits:
- domain/application code is persistence-ignorant and easy to unit test;
- persistence and provider changes remain localized;
- Django migrations/Admin/Unfold remain fully usable;
- transaction ownership is explicit;
- read paths can still be optimized pragmatically.

Costs:
- explicit mapping/repository/UoW code is required;
- Django Admin needs careful adapter glue for business operations;
- record/entity duplication is intentional and must be kept synchronized by
  tests and migrations.

## Reconsider when

Reopen this decision only if Django Admin/ORM integration stops being a core
requirement or a concrete use case demonstrates that maintaining Django records
plus mappers costs more than replacing the persistence/admin stack. Do not add
SQLAlchemy as a second ORM merely for isolated convenience.
