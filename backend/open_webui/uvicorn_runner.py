from __future__ import annotations

import argparse
import asyncio

import uvicorn


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run Open WebUI via a thin uvicorn wrapper.')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default=8080, type=int)
    parser.add_argument('--forwarded-allow-ips', default='')
    parser.add_argument('--workers', default='', type=str)
    parser.add_argument('--ws', default='', type=str)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    run_kwargs: dict[str, object] = {
        'app': 'open_webui.main:app',
        'host': args.host,
        'port': args.port,
    }

    if args.forwarded_allow_ips:
        run_kwargs['forwarded_allow_ips'] = args.forwarded_allow_ips

    if args.workers:
        run_kwargs['workers'] = int(args.workers)

    if args.ws:
        run_kwargs['ws'] = args.ws

    try:
        uvicorn.run(**run_kwargs)
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
