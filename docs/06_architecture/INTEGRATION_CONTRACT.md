# Integration Contract — crypto-ai-agent

## Purpose
Record integration decisions grounded in the reviewed repository sources.

## Capability Decisions
### auth
Decision: required
Contract: The documented auth dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the auth endpoint or platform integration; no secret values are documented.
Failure mode: If auth is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured auth path or its declared runtime probe with non-sensitive evidence.
### postgres
Decision: required
Contract: The documented postgres dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the postgres endpoint or platform integration; no secret values are documented.
Failure mode: If postgres is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured postgres path or its declared runtime probe with non-sensitive evidence.
### redis
Decision: required
Contract: The documented redis dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the redis endpoint or platform integration; no secret values are documented.
Failure mode: If redis is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured redis path or its declared runtime probe with non-sensitive evidence.
### logging
Decision: required
Contract: The documented logging dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the logging endpoint or platform integration; no secret values are documented.
Failure mode: If logging is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured logging path or its declared runtime probe with non-sensitive evidence.
### notifications
Decision: required
Contract: The documented notifications dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the notifications endpoint or platform integration; no secret values are documented.
Failure mode: If notifications is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured notifications path or its declared runtime probe with non-sensitive evidence.
### ai
Decision: required
Contract: The documented ai dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the ai endpoint or platform integration; no secret values are documented.
Failure mode: If ai is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured ai path or its declared runtime probe with non-sensitive evidence.
### payments
Decision: required
Contract: The documented payments dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the payments endpoint or platform integration; no secret values are documented.
Failure mode: If payments is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured payments path or its declared runtime probe with non-sensitive evidence.
### catalog
Decision: not-applicable
Reason: crypto-ai-agent has no declared catalog dependency in the reviewed repository runtime configuration.
### orders
Decision: not-applicable
Reason: crypto-ai-agent has no declared orders dependency in the reviewed repository runtime configuration.
### warehouse
Decision: not-applicable
Reason: crypto-ai-agent has no declared warehouse dependency in the reviewed repository runtime configuration.
### invoices
Decision: not-applicable
Reason: crypto-ai-agent has no declared invoices dependency in the reviewed repository runtime configuration.
### object-storage
Decision: not-applicable
Reason: crypto-ai-agent has no declared object-storage dependency in the reviewed repository runtime configuration.
### event-bus
Decision: not-applicable
Reason: crypto-ai-agent has no declared event-bus dependency in the reviewed repository runtime configuration.
### docs-rag
Decision: required
Contract: The documented docs-rag dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the docs-rag endpoint or platform integration; no secret values are documented.
Failure mode: If docs-rag is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured docs-rag path or its declared runtime probe with non-sensitive evidence.
### monitoring
Decision: required
Contract: The documented monitoring dependency is used only through its configured runtime interface.
Configuration: Use the repository configuration and deployed manifests for the monitoring endpoint or platform integration; no secret values are documented.
Failure mode: If monitoring is unavailable, the dependent behavior is unavailable and must not fabricate a successful result.
Validation: Validate the configured monitoring path or its declared runtime probe with non-sensitive evidence.
### backups
Decision: not-applicable
Reason: crypto-ai-agent has no declared backups dependency in the reviewed repository runtime configuration.

## Data Ownership
The repository owns only the data and browser/runtime state described by its existing implementation.

## Authentication and Authorization
Authentication is only required where the reviewed configuration declares it; no local authorization contract is invented.

## Synchronous Dependencies
Required capabilities above are the complete declared dependency set for this profile.

## Asynchronous Dependencies
No asynchronous dependency is assumed unless marked required above.

## Degraded Operation
A dependency failure makes its dependent action unavailable rather than producing invented success.

## Validation
Validate the profile against repository configuration and the planning gate.
