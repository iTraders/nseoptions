# -*- encoding: utf-8 -*-

"""
CLI Launcher for the NSE Options Web Dashboard

A standalone entry point that boots the FastAPI/uvicorn backend which
serves the ReactJS dashboard. The file mirrors the conventions of the
sibling :file:`main.py` (the ``sys.path`` append and the ``--no-verify``
SSL toggle) so it runs in-place from the repository root:

    python dashboard.py --symbol NIFTY --port 8000

A proper ``nseoptions`` console-script entry point is intentionally left
for a later iteration; this launcher keeps the dashboard runnable today.

@author:  Debmalya Pramanik
@version: v0.0.1
"""

import os     # miscellaneous os interfaces
import sys    # configuring python runtime environment

import argparse # argument parser for additional controls

# ! append the root (this file) directory to the system path, mirroring
# ! main.py so the in-place `nseoptions` package is importable as-is
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import nseoptions.dashboard as dashboard # https://github.com/iTraders/nseoptions

if __name__ == "__main__":
    # ..versionadded:: 2025-10-15 - CLI Argument Parse for Controls
    parser = argparse.ArgumentParser(description = "NSE Options Dashboard Launcher")

    parser.add_argument("--symbol", default = "NIFTY", type = str, help = "Index/stock symbol, e.g. NIFTY.")
    parser.add_argument("--expiry", default = None, type = str, help = "Default expiry DD-MMM-YYYY (nearest if unset).")
    parser.add_argument("--host", default = "127.0.0.1", type = str, help = "Server bind host.")
    parser.add_argument("--port", default = 8000, type = int, help = "Server bind port.")
    parser.add_argument("--interval", default = 30, type = int, help = "NSE poll interval, in seconds.")
    parser.add_argument("--nstrikes", default = 20, type = int, help = "Strikes above/below the ATM to serve.")
    parser.add_argument("--symbols", default = None, nargs = "+", type = str, help = "Downloadable symbols for Fetch Data (default: indices).")
    parser.add_argument("--max-concurrent", dest = "max_concurrent", default = 3, type = int, help = "Cap on concurrent NSE fetches.")
    parser.add_argument("--dev", action = "store_true", help = "Dev mode: enable CORS for the Vite dev server, skip the SPA.")
    parser.add_argument(
        "--no-verify",
        dest = "verify",
        action = "store_false",
        help = "SSL Verification, Defaults to False."
    )
    parser.set_defaults(verify = False)

    # ? get arguments from the argparse controller - use in forward
    args = parser.parse_args()

    dashboard.launch(
        symbol = args.symbol.upper(),
        expiry = args.expiry,
        host = args.host,
        port = args.port,
        verify = args.verify,
        interval = args.interval,
        nstrikes = args.nstrikes,
        symbols = args.symbols,
        max_concurrent = args.max_concurrent,
        dev = args.dev
    )
