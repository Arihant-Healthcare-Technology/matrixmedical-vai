"""
DEPRECATED MODULE

This directory contains deprecated scripts that are no longer actively maintained.
These scripts were the original implementation before the modern CLI was introduced.

Migration Guide:
================

| Deprecated Script           | Modern CLI Equivalent           |
|-----------------------------|--------------------------------|
| run-bill-batch.py           | ukg-bill batch sync            |
| run-ap-batch.py             | ukg-bill ap batch              |
| process-bill-payment.py     | ukg-bill ap process            |
| upsert-bill-invoice.py      | ukg-bill ap upsert invoice     |
| upsert-bill-entity.py       | ukg-bill sync user             |
| upsert-bill-vendor.py       | ukg-bill ap upsert vendor      |
| build-bill-invoice.py       | ukg-bill build invoice         |
| build-bill-entity.py        | ukg-bill build user            |
| build-bill-vendor.py        | ukg-bill build vendor          |
| orchestrate_people_import.py| ukg-bill batch sync            |

Usage:
======
All functionality from these scripts has been migrated to the CLI.
Run 'ukg-bill --help' for available commands.

Note:
=====
These scripts will be removed in a future major version release.
Please migrate to the CLI commands as soon as possible.
"""

import warnings

warnings.warn(
    "The deprecated module contains legacy scripts that will be removed in a future version. "
    "Please use the 'ukg-bill' CLI commands instead. Run 'ukg-bill --help' for more information.",
    DeprecationWarning,
    stacklevel=2
)
