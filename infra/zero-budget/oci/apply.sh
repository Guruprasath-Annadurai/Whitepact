#!/bin/sh
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

# Closed on purpose. A later reviewed change has to replace this script
# after owner authorization and independent Antigravity review. There is
# no environment-variable bypass.
echo "whitepact zero-budget authorization gate is closed" >&2
echo "refusing terraform apply, terraform destroy, and any provider mutation" >&2
echo "status: not staging GO; not production ready; no resources provisioned" >&2
exit 2
