# Changelog

## 0.2.0

- Poll every 10 seconds by default; configurable from 5–600 seconds.
- Explicit post-connect pairing, cached per adapter/proxy during runtime.
- Adapter/proxy selection, preserving remote backend routing.
- Automatic connection/pairing failover before any operation begins; never replay failed writes.
- Cached-service BLE clients and bundled integration brand images.
- 23 offline protocol/transport tests and GitHub Actions CI.
- Record user-confirmed first-generation GE pairing, night mode, ice-making and bin-removed control. New proxy changes require live validation.

## 0.1.0

- Initial experimental integration with controls, status, diagnostics and manual installation.
