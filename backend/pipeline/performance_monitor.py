"""
Performance Monitor - Real-time performance tracking
Monitors CPU, RAM, GPU, Disk I/O, and processing speed
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

import psutil

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Try to import GPU monitoring
try:
    import GPUtil

    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    print("⚠️  GPUtil not available - GPU monitoring disabled")


class PerformanceMonitor:
    """Real-time performance monitoring"""

    def __init__(self, output_file="performance_log.json"):
        self.output_file = output_file
        self.start_time = time.time()
        self.samples = []
        self.running = True

        # Get process info
        self.process = psutil.Process()

        # Initialize counters
        self.last_net_io = psutil.net_io_counters()
        self.last_disk_io = psutil.disk_io_counters()

        print("🔍 Performance Monitor Started")
        print(f"📊 Output: {output_file}")
        print(f"💻 CPU Cores: {psutil.cpu_count()} ({psutil.cpu_count(logical=False)} physical)")
        print(f"🧠 Total RAM: {psutil.virtual_memory().total / (1024**3):.1f} GB")

        if GPU_AVAILABLE:
            gpus = GPUtil.getGPUs()
            if gpus:
                print(f"🎮 GPU: {gpus[0].name} ({gpus[0].memoryTotal} MB)")
            else:
                print("🎮 GPU: Not detected")

        print("\n" + "=" * 60)
        print("Monitoring... (CTRL+C to stop)")
        print("=" * 60 + "\n")

    def get_snapshot(self):
        """Get current performance snapshot"""
        snapshot = {"timestamp": datetime.now().isoformat(), "elapsed_seconds": time.time() - self.start_time}

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        snapshot["cpu"] = {
            "total_percent": cpu_percent,
            "per_core": cpu_per_core,
            "freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
        }

        # Memory metrics
        memory = psutil.virtual_memory()
        snapshot["memory"] = {
            "total_gb": memory.total / (1024**3),
            "used_gb": memory.used / (1024**3),
            "available_gb": memory.available / (1024**3),
            "percent": memory.percent,
        }

        # Process-specific memory
        process_memory = self.process.memory_info()
        snapshot["process"] = {
            "memory_mb": process_memory.rss / (1024**2),
            "cpu_percent": self.process.cpu_percent(interval=0.1),
            "threads": self.process.num_threads(),
        }

        # Disk metrics
        current_disk = psutil.disk_io_counters()
        if current_disk and self.last_disk_io:
            snapshot["disk"] = {
                "read_mb_s": (current_disk.read_bytes - self.last_disk_io.read_bytes) / (1024**2),
                "write_mb_s": (current_disk.write_bytes - self.last_disk_io.write_bytes) / (1024**2),
            }
            self.last_disk_io = current_disk

        # Network metrics
        current_net = psutil.net_io_counters()
        if current_net and self.last_net_io:
            snapshot["network"] = {
                "sent_mb_s": (current_net.bytes_sent - self.last_net_io.bytes_sent) / (1024**2),
                "recv_mb_s": (current_net.bytes_recv - self.last_net_io.bytes_recv) / (1024**2),
            }
            self.last_net_io = current_net

        # GPU metrics
        if GPU_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    snapshot["gpu"] = {
                        "name": gpu.name,
                        "memory_used_mb": gpu.memoryUsed,
                        "memory_total_mb": gpu.memoryTotal,
                        "memory_percent": gpu.memoryUtil * 100,
                        "gpu_percent": gpu.load * 100,
                        "temperature_c": gpu.temperature,
                    }
            except Exception as e:
                snapshot["gpu"] = {"error": str(e)}

        return snapshot

    def print_summary(self, snapshot):
        """Print current performance summary"""
        elapsed = snapshot["elapsed_seconds"]
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)

        print(f"\r⏱️  {hours:02d}:{minutes:02d}:{seconds:02d} | ", end="")
        print(f"CPU: {snapshot['cpu']['total_percent']:5.1f}% | ", end="")
        print(f"RAM: {snapshot['memory']['percent']:5.1f}% ({snapshot['memory']['used_gb']:.1f}GB) | ", end="")

        if "gpu" in snapshot and "memory_percent" in snapshot["gpu"]:
            print(f"GPU: {snapshot['gpu']['gpu_percent']:5.1f}% ({snapshot['gpu']['memory_used_mb']:.0f}MB) | ", end="")

        if "disk" in snapshot:
            print(f"Disk: R:{snapshot['disk']['read_mb_s']:.1f} W:{snapshot['disk']['write_mb_s']:.1f} MB/s", end="")

        print("", end="", flush=True)

    async def monitor_loop(self, interval=1.0):
        """Main monitoring loop"""
        try:
            while self.running:
                snapshot = self.get_snapshot()
                self.samples.append(snapshot)
                self.print_summary(snapshot)

                # Save every 10 samples
                if len(self.samples) % 10 == 0:
                    self.save_samples()

                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")

        finally:
            self.save_samples()
            self.print_final_stats()

    def save_samples(self):
        """Save samples to file"""
        with open(self.output_file, "w") as f:
            json.dump(
                {"start_time": datetime.fromtimestamp(self.start_time).isoformat(), "samples": self.samples},
                f,
                indent=2,
            )

    def print_final_stats(self):
        """Print final statistics"""
        if not self.samples:
            return

        print("\n\n" + "=" * 60)
        print("📊 FINAL PERFORMANCE STATISTICS")
        print("=" * 60)

        # Calculate averages
        avg_cpu = sum(s["cpu"]["total_percent"] for s in self.samples) / len(self.samples)
        avg_memory = sum(s["memory"]["percent"] for s in self.samples) / len(self.samples)
        max_cpu = max(s["cpu"]["total_percent"] for s in self.samples)
        max_memory = max(s["memory"]["percent"] for s in self.samples)

        print(f"\n⏱️  Duration: {self.samples[-1]['elapsed_seconds']:.1f} seconds")
        print(f"📊 Samples: {len(self.samples)}")

        print("\n💻 CPU:")
        print(f"  Average: {avg_cpu:.1f}%")
        print(f"  Peak: {max_cpu:.1f}%")

        print("\n🧠 Memory:")
        print(f"  Average: {avg_memory:.1f}%")
        print(f"  Peak: {max_memory:.1f}%")
        print(f"  Peak Usage: {max(s['memory']['used_gb'] for s in self.samples):.1f} GB")

        # GPU stats if available
        gpu_samples = [s for s in self.samples if "gpu" in s and "gpu_percent" in s["gpu"]]
        if gpu_samples:
            avg_gpu = sum(s["gpu"]["gpu_percent"] for s in gpu_samples) / len(gpu_samples)
            avg_gpu_mem = sum(s["gpu"]["memory_percent"] for s in gpu_samples) / len(gpu_samples)
            max_gpu = max(s["gpu"]["gpu_percent"] for s in gpu_samples)
            max_gpu_mem = max(s["gpu"]["memory_percent"] for s in gpu_samples)

            print("\n🎮 GPU:")
            print(f"  Average Load: {avg_gpu:.1f}%")
            print(f"  Peak Load: {max_gpu:.1f}%")
            print(f"  Average Memory: {avg_gpu_mem:.1f}%")
            print(f"  Peak Memory: {max_gpu_mem:.1f}%")

        # Disk I/O stats
        disk_samples = [s for s in self.samples if "disk" in s]
        if disk_samples:
            total_read = sum(s["disk"]["read_mb_s"] for s in disk_samples)
            total_write = sum(s["disk"]["write_mb_s"] for s in disk_samples)

            print("\n💾 Disk I/O:")
            print(f"  Total Read: {total_read:.1f} MB")
            print(f"  Total Write: {total_write:.1f} MB")
            print(f"  Avg Read: {total_read / len(disk_samples):.1f} MB/s")
            print(f"  Avg Write: {total_write / len(disk_samples):.1f} MB/s")

        print(f"\n📁 Log saved to: {self.output_file}")
        print("=" * 60 + "\n")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Performance Monitor")
    parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds")
    parser.add_argument("--output", type=str, default="performance_log.json", help="Output file")
    args = parser.parse_args()

    monitor = PerformanceMonitor(output_file=args.output)
    await monitor.monitor_loop(interval=args.interval)


if __name__ == "__main__":
    asyncio.run(main())
