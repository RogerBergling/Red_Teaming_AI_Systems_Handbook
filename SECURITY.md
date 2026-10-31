# Security policy

## Reporting a vulnerability

Please report vulnerabilities in the **build pipeline or repository tooling**
privately through GitHub's *Report a vulnerability* button on the repository's
Security tab. Do not open a public issue for an unpatched vulnerability.

Reports about the build are in scope: dependency compromise, arbitrary code
execution while rendering, path traversal in the build scripts, publishing
pipeline weaknesses and leaked secrets. Reports about the educational attack
techniques described in the book are not vulnerabilities in this repository.

## Testing the techniques in this book

The handbook is offensive-security training material. Only use its techniques
against systems you own or have explicit written permission to test. See the
authorisation and ethics section of the handbook before running anything.

## Supported versions

The repository is a book, not a supported application. Security fixes are made
on `main`; use the latest commit.
