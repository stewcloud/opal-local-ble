# Changelog

## 0.2.1

- Initial setup scans and lists matching Opals by name, address and signal strength, with Scan again and manual entry. Configured and unrelated devices are excluded.
- Remove the runtime pairing cache: authenticate each fresh BLE connection.
- Retry authentication-rejected reads once on the same connection; never replay commands.
- Add discovery/selection and authentication regression coverage (35 tests total).
- Addresses the observed proxy Insufficient authentication error path; physical proxy verification remains required.

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
