import logging
import json
import psutil
from typing import Dict, Any
from tools.base import BaseTool

logger = logging.getLogger("jarvis.tools.system_stats")

class SystemStatsTool(BaseTool):
    """
    Fetches real-time host system resource utilization metrics.
    """
    @property
    def name(self) -> str:
        return "system_stats"

    @property
    def description(self) -> str:
        return "Fetches host system resource utilization metrics, including CPU, RAM, disk, and GPU information."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }

    async def run(self, **kwargs) -> str:
        stats = {}
        
        # 1. CPU stats
        try:
            stats["cpu"] = {
                "utilization_percent": psutil.cpu_percent(interval=0.1),
                "logical_cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
                "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else "N/A"
            }
        except Exception as e:
            stats["cpu"] = {"error": f"Failed to fetch CPU stats: {e}"}

        # 2. RAM stats
        try:
            virtual_mem = psutil.virtual_memory()
            stats["ram"] = {
                "total_gb": round(virtual_mem.total / (1024**3), 2),
                "available_gb": round(virtual_mem.available / (1024**3), 2),
                "used_gb": round(virtual_mem.used / (1024**3), 2),
                "utilization_percent": virtual_mem.percent
            }
        except Exception as e:
            stats["ram"] = {"error": f"Failed to fetch RAM stats: {e}"}

        # 3. Disk stats
        try:
            # Check partition representing root or current working dir
            disk_usage = psutil.disk_usage("/")
            stats["disk"] = {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "utilization_percent": disk_usage.percent
            }
        except Exception as e:
            stats["disk"] = {"error": f"Failed to fetch disk stats: {e}"}

        # 4. GPU stats (Nvidia hardware passthrough check)
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                stats["gpu"] = []
                for gpu in gpus:
                    stats["gpu"].append({
                        "name": gpu.name,
                        "load_percent": round(gpu.load * 100, 2),
                        "memory_used_mb": gpu.memoryUsed,
                        "memory_total_mb": gpu.memoryTotal,
                        "temperature_celsius": gpu.temperature
                    })
            else:
                stats["gpu"] = "No Nvidia GPUs found or accessible"
        except ImportError:
            stats["gpu"] = "GPUtil library not imported/installed"
        except Exception as e:
            stats["gpu"] = {"error": f"Failed to fetch GPU stats: {e}"}

        return json.dumps(stats, indent=2)
