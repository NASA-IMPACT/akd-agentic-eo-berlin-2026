"""List tools and call a few. Usage: python test.py [http://127.0.0.1:8000/mcp]"""
import asyncio
import json
import sys

from fastmcp import Client


async def main(url: str) -> None:
    async with Client(url) as c:
        tools = await c.list_tools()
        print(f"{len(tools)} tools:", sorted(t.name for t in tools))
        for name, args in [("geocode", {"query": "Conselice, Italy"}),
                           ("reverse_geocode", {"lat": 44.51, "lon": 11.83}),
                           ("search_gdacs_events", {"eventlist": "FL"})]:
            r = await c.call_tool(name, args)
            data = r.data if getattr(r, "data", None) is not None else (r.content[0].text if r.content else r)
            print(f"{name}: {str(data)[:220]}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp"))
