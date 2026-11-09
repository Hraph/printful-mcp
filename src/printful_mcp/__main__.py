"""Allow running the package as a module: python -m printful_mcp

Every CLI option can also be set through an environment variable, which is
how the Docker image is configured:

    MCP_TRANSPORT       stdio | http | sse            (default: stdio)
    MCP_HOST            bind address                  (default: 127.0.0.1)
    MCP_PORT            bind port                     (default: 8000)
    MCP_ALLOWED_HOSTS   comma-separated Host headers accepted by the HTTP
                        transport (DNS-rebinding protection), e.g.
                        "localhost:*,printful-mcp:*". Empty = protection
                        disabled when binding a non-loopback address.
"""

import argparse
import os
import sys

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def parse_args():
    """Parse CLI arguments (defaults come from environment variables)."""
    parser = argparse.ArgumentParser(description="Printful MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport type: stdio (default, for Cursor/Claude), http (for HTTP clients), sse (legacy). "
        "Env: MCP_TRANSPORT",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host to bind HTTP server (default: 127.0.0.1). Env: MCP_HOST",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Port for HTTP server (default: 8000). Env: MCP_PORT",
    )
    parser.add_argument(
        "--allowed-hosts",
        default=os.getenv("MCP_ALLOWED_HOSTS"),
        help="Comma-separated list of allowed Host headers for HTTP transports "
        "(e.g. 'localhost:*,printful-mcp:*'). Env: MCP_ALLOWED_HOSTS",
    )
    return parser.parse_args()


def configure_transport_security(mcp, host: str, allowed_hosts: str | None) -> None:
    """Align DNS-rebinding protection with the actual bind address.

    FastMCP enables the protection at construction time for its default host
    (127.0.0.1) and does not update it when ``settings.host`` changes later,
    which would reject every request whose Host header is not localhost, e.g.
    from another container on a Docker network.
    """
    try:
        from mcp.server.transport_security import TransportSecuritySettings
    except ImportError:  # Older mcp versions without transport security
        return

    if allowed_hosts:
        hosts = [h.strip() for h in allowed_hosts.split(",") if h.strip()]
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=[f"http://{h}" for h in hosts] + [f"https://{h}" for h in hosts],
        )
    elif host not in LOOPBACK_HOSTS:
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )


def main():
    """Entry point for the MCP server."""
    args = parse_args()

    # Import server module
    from .server import mcp

    # Check for API key
    if not os.getenv("PRINTFUL_API_KEY"):
        print("Error: PRINTFUL_API_KEY environment variable is required", file=sys.stderr)
        print("Get your API key from: https://www.printful.com/dashboard/api", file=sys.stderr)
        sys.exit(1)

    # Configure HTTP settings by modifying mcp.settings directly
    if args.transport in ("http", "sse"):
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        configure_transport_security(mcp, args.host, args.allowed_hosts)
        print(f"Starting {args.transport.upper()} server on http://{args.host}:{args.port}", file=sys.stderr)

    # Run the server with selected transport
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "http":
        mcp.run(transport="streamable-http")
    elif args.transport == "sse":
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
