"""CPU/Memory MCP Server — exposes system monitoring tools via FastMCP (stdio)."""

import datetime
import json

import psutil
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cpu-memory-monitor")


@mcp.tool()
def get_cpu_usage() -> str:
    """Return the current overall CPU usage percentage (sampled over 1 second)."""
    cpu_pct = psutil.cpu_percent(interval=1)
    return json.dumps({"cpu_percent": cpu_pct})


@mcp.tool()
def get_memory_usage() -> str:
    """Return RAM usage stats: total, used, available (in GB) and usage percent."""
    mem = psutil.virtual_memory()
    return json.dumps(
        {
            "total_gb": round(mem.total / 1e9, 2),
            "used_gb": round(mem.used / 1e9, 2),
            "available_gb": round(mem.available / 1e9, 2),
            "percent": mem.percent,
        }
    )


@mcp.tool()
def get_cpu_per_core() -> str:
    """Return per-core CPU usage percentages (sampled over 1 second)."""
    per_core = psutil.cpu_percent(interval=1, percpu=True)
    return json.dumps({"per_core_percent": per_core, "core_count": len(per_core)})


@mcp.tool()
def get_top_processes(n: int = 5) -> str:
    """Return the top N processes sorted by CPU usage (name, pid, cpu_percent, memory_percent)."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    top = sorted(procs, key=lambda x: x["cpu_percent"] or 0, reverse=True)[:n]
    return json.dumps({"top_processes": top})


@mcp.tool()
def get_system_info() -> str:
    """Return a combined system snapshot: CPU usage, core count, RAM stats, and uptime."""
    cpu_pct = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time
    return json.dumps(
        {
            "cpu_percent": cpu_pct,
            "cpu_cores": psutil.cpu_count(),
            "ram_total_gb": round(mem.total / 1e9, 2),
            "ram_used_gb": round(mem.used / 1e9, 2),
            "ram_percent": mem.percent,
            "uptime_hours": round(uptime.total_seconds() / 3600, 1),
        }
    )


if __name__ == "__main__":
    mcp.run()  # stdio transport (blocking)
