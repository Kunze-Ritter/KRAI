"""
Performance Analyzer - Analyze performance logs
Creates detailed report from performance_log.json
"""

import json
import sys


def analyze_performance(log_file="performance_log.json"):
    """Analyze performance log and create report"""

    print("\n" + "=" * 80)
    print("📊 PERFORMANCE ANALYSIS REPORT")
    print("=" * 80)

    # Load log file
    try:
        with open(log_file) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {log_file} not found!")
        print("Run performance_monitor.py first to create the log.")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: {log_file} is not valid JSON!")
        return

    samples = data.get("samples", [])
    if not samples:
        print("❌ No samples found in log file!")
        return

    start_time = data.get("start_time")
    print(f"\n📅 Start Time: {start_time}")
    print(f"📊 Total Samples: {len(samples)}")
    print(
        f"⏱️  Duration: {samples[-1]['elapsed_seconds']:.1f} seconds ({samples[-1]['elapsed_seconds']/60:.1f} minutes)"
    )

    # CPU Analysis
    print("\n" + "-" * 80)
    print("💻 CPU PERFORMANCE")
    print("-" * 80)

    cpu_values = [s["cpu"]["total_percent"] for s in samples]
    print(f"Average: {sum(cpu_values)/len(cpu_values):6.1f}%")
    print(f"Min:     {min(cpu_values):6.1f}%")
    print(f"Max:     {max(cpu_values):6.1f}%")

    # CPU usage distribution
    low = sum(1 for v in cpu_values if v < 30)
    medium = sum(1 for v in cpu_values if 30 <= v < 70)
    high = sum(1 for v in cpu_values if v >= 70)

    print("\nUsage Distribution:")
    print(f"  Low (<30%):     {low:4d} samples ({low/len(cpu_values)*100:5.1f}%)")
    print(f"  Medium (30-70%): {medium:4d} samples ({medium/len(cpu_values)*100:5.1f}%)")
    print(f"  High (>70%):     {high:4d} samples ({high/len(cpu_values)*100:5.1f}%)")

    # Memory Analysis
    print("\n" + "-" * 80)
    print("🧠 MEMORY PERFORMANCE")
    print("-" * 80)

    mem_values = [s["memory"]["percent"] for s in samples]
    mem_gb_values = [s["memory"]["used_gb"] for s in samples]

    print(f"Average: {sum(mem_values)/len(mem_values):6.1f}% ({sum(mem_gb_values)/len(mem_gb_values):5.1f} GB)")
    print(f"Min:     {min(mem_values):6.1f}% ({min(mem_gb_values):5.1f} GB)")
    print(f"Max:     {max(mem_values):6.1f}% ({max(mem_gb_values):5.1f} GB)")

    # Memory trend
    first_half = mem_values[: len(mem_values) // 2]
    second_half = mem_values[len(mem_values) // 2 :]
    trend = sum(second_half) / len(second_half) - sum(first_half) / len(first_half)

    if abs(trend) < 1:
        trend_text = "Stable ✅"
    elif trend > 0:
        trend_text = f"Increasing ⬆️ (+{trend:.1f}%)"
    else:
        trend_text = f"Decreasing ⬇️ ({trend:.1f}%)"

    print(f"\nMemory Trend: {trend_text}")

    # GPU Analysis (if available)
    gpu_samples = [s for s in samples if "gpu" in s and "gpu_percent" in s["gpu"]]
    if gpu_samples:
        print("\n" + "-" * 80)
        print("🎮 GPU PERFORMANCE")
        print("-" * 80)

        gpu_load = [s["gpu"]["gpu_percent"] for s in gpu_samples]
        gpu_mem = [s["gpu"]["memory_percent"] for s in gpu_samples]
        gpu_mem_mb = [s["gpu"]["memory_used_mb"] for s in gpu_samples]

        print("GPU Load:")
        print(f"  Average: {sum(gpu_load)/len(gpu_load):6.1f}%")
        print(f"  Min:     {min(gpu_load):6.1f}%")
        print(f"  Max:     {max(gpu_load):6.1f}%")

        print("\nGPU Memory:")
        print(f"  Average: {sum(gpu_mem)/len(gpu_mem):6.1f}% ({sum(gpu_mem_mb)/len(gpu_mem_mb):6.0f} MB)")
        print(f"  Min:     {min(gpu_mem):6.1f}% ({min(gpu_mem_mb):6.0f} MB)")
        print(f"  Max:     {max(gpu_mem):6.1f}% ({max(gpu_mem_mb):6.0f} MB)")

        # GPU utilization
        idle = sum(1 for v in gpu_load if v < 10)
        active = sum(1 for v in gpu_load if v >= 10)

        print("\nGPU Utilization:")
        print(f"  Idle (<10%):  {idle:4d} samples ({idle/len(gpu_load)*100:5.1f}%)")
        print(f"  Active (≥10%): {active:4d} samples ({active/len(gpu_load)*100:5.1f}%)")

    # Disk I/O Analysis
    disk_samples = [s for s in samples if "disk" in s]
    if disk_samples:
        print("\n" + "-" * 80)
        print("💾 DISK I/O PERFORMANCE")
        print("-" * 80)

        total_read = sum(s["disk"]["read_mb_s"] for s in disk_samples)
        total_write = sum(s["disk"]["write_mb_s"] for s in disk_samples)

        print(f"Total Read:  {total_read:8.1f} MB")
        print(f"Total Write: {total_write:8.1f} MB")
        print(f"\nAverage Read:  {total_read/len(disk_samples):6.2f} MB/s")
        print(f"Average Write: {total_write/len(disk_samples):6.2f} MB/s")

        max_read = max(s["disk"]["read_mb_s"] for s in disk_samples)
        max_write = max(s["disk"]["write_mb_s"] for s in disk_samples)

        print(f"\nPeak Read:  {max_read:6.2f} MB/s")
        print(f"Peak Write: {max_write:6.2f} MB/s")

    # Process Analysis
    print("\n" + "-" * 80)
    print("⚙️  PROCESS PERFORMANCE")
    print("-" * 80)

    process_mem = [s["process"]["memory_mb"] for s in samples]
    process_cpu = [s["process"]["cpu_percent"] for s in samples]

    print("Process Memory:")
    print(f"  Average: {sum(process_mem)/len(process_mem):7.1f} MB")
    print(f"  Min:     {min(process_mem):7.1f} MB")
    print(f"  Max:     {max(process_mem):7.1f} MB")

    print("\nProcess CPU:")
    print(f"  Average: {sum(process_cpu)/len(process_cpu):6.1f}%")
    print(f"  Max:     {max(process_cpu):6.1f}%")

    # Performance Score
    print("\n" + "-" * 80)
    print("🏆 PERFORMANCE SCORE")
    print("-" * 80)

    # Calculate scores (0-100)
    cpu_score = 100 - (sum(cpu_values) / len(cpu_values))  # Lower is better
    mem_stable_score = 100 - abs(trend) * 10  # More stable is better

    if gpu_samples:
        gpu_util_score = sum(gpu_load) / len(gpu_load)  # Higher is better (good utilization)
    else:
        gpu_util_score = 0

    overall_score = cpu_score * 0.4 + mem_stable_score * 0.3 + gpu_util_score * 0.3

    print(f"\nCPU Efficiency:   {cpu_score:5.1f}/100 {'🟢' if cpu_score > 70 else '🟡' if cpu_score > 50 else '🔴'}")
    print(
        f"Memory Stability: {mem_stable_score:5.1f}/100 {'🟢' if mem_stable_score > 90 else '🟡' if mem_stable_score > 70 else '🔴'}"
    )

    if gpu_samples:
        print(
            f"GPU Utilization:  {gpu_util_score:5.1f}/100 {'🟢' if gpu_util_score > 50 else '🟡' if gpu_util_score > 20 else '🔴'}"
        )

    print(f"\n{'='*30}")
    print(f"Overall Score: {overall_score:5.1f}/100")
    print(f"{'='*30}")

    if overall_score >= 80:
        print("✨ Excellent performance!")
    elif overall_score >= 60:
        print("👍 Good performance")
    elif overall_score >= 40:
        print("⚠️  Fair performance - consider optimization")
    else:
        print("❌ Poor performance - optimization needed")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    log_file = sys.argv[1] if len(sys.argv) > 1 else "performance_log.json"
    analyze_performance(log_file)
