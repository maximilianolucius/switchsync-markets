# Security Policy

This is a research repository of **synthetic** numerical experiments. It contains no
network services, no credentials, no user data, and no real market data. The runtime
risk surface is limited to executing local Python that performs numerical simulation.

## Scope

- **In scope:** issues where running the provided code could execute unintended code
  (e.g. an unsafe deserialization path), or where a dependency in `requirements.lock.txt`
  has a known advisory relevant to this code.
- **Out of scope:** trading/financial risk, market-data handling (there is none), and
  performance/accuracy of the scientific results (report those as normal issues).

## Reporting

Open a private security advisory via the repository's GitHub "Security" tab, or a
regular issue for non-sensitive reports. There is no separate embargo process for a
project of this scope.

## Notes

- Configuration is data-only JSON loaded with the standard `json` module (no `pickle`,
  no `eval`, no arbitrary-code config).
- The bundled PDF (`docs/research/sources/…`) is a third-party arXiv document; treat its
  provenance per its own terms (see `docs/LICENSE_BLOCKER.md`).
