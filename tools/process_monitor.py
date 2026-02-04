#!/usr/bin/env python3
# Copyright 2024 The peek Authors.
# Licensed under the MIT License.

"""Process Monitor - Monitor CPU, Memory, GPU, and VRAM usage.

A command-line tool for monitoring process resources with real-time
visualization and report generation capabilities.

Usage:
    # Monitor current process in real-time
    python process_monitor.py

    # Monitor specific PID
    python process_monitor.py --pid 1234

    # Monitor multiple PIDs
    python process_monitor.py --pids 1234,5678,9012

    # Monitor for 60 seconds and save HTML report
    python process_monitor.py --pid 1234 --duration 60 --output report.html

    # Monitor indefinitely until Ctrl+C, then save report
    python process_monitor.py --pid 1234 --duration 0 --output report.html

    # Monitor and save JSON data
    python process_monitor.py --pid 1234 --duration 30 --output data.json --format json

    # Run a command and monitor it
    python process_monitor.py --command "python train.py --epochs 10"

Examples:
    # Monitor training script with GPU, save report when done
    python process_monitor.py --command "python train.py" --output training_report.html

    # Monitor multiple processes (e.g., distributed training)
    python process_monitor.py --pids 1234,5678 --duration 0 --output multi_report.html

    # Indefinite monitoring with report generation on Ctrl+C
    python process_monitor.py --pid 1234 --duration 0 --output report.html

    # Quick 10-second snapshot
    python process_monitor.py --pid $(pgrep -f myapp) --duration 10 --output snapshot.html
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path for development
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from peek.os.monitor import (
        ProcessMonitor,
        ProcessStats,
        MonitorConfig,
        MonitorVisualizer,
        RealtimeChart,
        MultiProcessMonitor,
        MultiProcessStats,
        MultiProcessVisualizer,
        MultiProcessRealtimeChart,
    )
except ImportError as e:
    print(f"Error: Could not import peek.os.monitor: {e}")
    print("Make sure you have installed peek: pip install -e .")
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Monitor process CPU, Memory, GPU, and VRAM usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Target specification
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--pid",
        type=int,
        help="Process ID to monitor (default: current process)",
    )
    target_group.add_argument(
        "--pids",
        type=str,
        help="Comma-separated list of PIDs to monitor (e.g., '1234,5678,9012')",
    )
    target_group.add_argument(
        "--command",
        "-c",
        type=str,
        help="Command to run and monitor",
    )

    # Duration and interval
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=0,
        help="Monitoring duration in seconds (0 for indefinite, Ctrl+C to stop)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=1.0,
        help="Sampling interval in seconds (default: 1.0)",
    )

    # Output options
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path (HTML report or JSON data)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["html", "json", "both"],
        default="html",
        help="Output format (default: html)",
    )

    # Display options
    parser.add_argument(
        "--realtime",
        "-r",
        action="store_true",
        default=True,
        help="Show real-time display (default: True)",
    )
    parser.add_argument(
        "--no-realtime",
        action="store_true",
        help="Disable real-time display",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode - minimal output",
    )

    # Monitoring options
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Disable GPU monitoring",
    )
    parser.add_argument(
        "--no-io",
        action="store_true",
        help="Disable I/O monitoring",
    )
    parser.add_argument(
        "--gpu-indices",
        type=str,
        help="Comma-separated GPU indices to monitor (e.g., '0,1')",
    )

    return parser.parse_args()


def print_banner():
    """Print application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                   📊 Process Monitor                          ║
║         Monitor CPU, Memory, GPU, and VRAM Usage              ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_summary(monitor: ProcessMonitor):
    """Print monitoring summary."""
    summary = monitor.get_summary()
    if not summary:
        print("No data collected.")
        return

    print("\n" + "=" * 60)
    print(" 📈 Monitoring Summary")
    print("=" * 60)
    print(f" Samples:  {summary['samples']}")
    print(f" Duration: {summary['duration_seconds']:.1f} seconds")
    print()

    cpu = summary.get("cpu_percent", {})
    print(" CPU Usage:")
    print(f"   Average: {cpu.get('avg', 0):.1f}%")
    print(f"   Max:     {cpu.get('max', 0):.1f}%")
    print(f"   Min:     {cpu.get('min', 0):.1f}%")
    print()

    mem = summary.get("memory_mb", {})
    print(" Memory Usage:")
    print(f"   Average: {mem.get('avg', 0):.1f} MB")
    print(f"   Max:     {mem.get('max', 0):.1f} MB")
    print(f"   Min:     {mem.get('min', 0):.1f} MB")
    print()

    gpu_util = summary.get("gpu_utilization", {})
    gpu_mem = summary.get("gpu_memory_mb", {})
    if gpu_util.get("max", 0) > 0 or gpu_mem.get("max", 0) > 0:
        print(" GPU Utilization:")
        print(f"   Average: {gpu_util.get('avg', 0):.1f}%")
        print(f"   Max:     {gpu_util.get('max', 0):.1f}%")
        print()
        print(" GPU Memory (VRAM):")
        print(f"   Average: {gpu_mem.get('avg', 0):.1f} MB")
        print(f"   Max:     {gpu_mem.get('max', 0):.1f} MB")
    else:
        print(" GPU: No data available")

    print("=" * 60)


def save_output(monitor: ProcessMonitor, output_path: str, format: str):
    """Save monitoring output to file."""
    history = monitor.history
    if not history:
        print("⚠️  No data to save.")
        return

    visualizer = MonitorVisualizer(history)
    base_path = Path(output_path)

    if format in ("html", "both"):
        html_path = base_path.with_suffix(".html") if format == "both" else base_path
        saved_path = visualizer.save_html(str(html_path))
        print(f"✅ HTML report saved: {saved_path}")

    if format in ("json", "both"):
        json_path = base_path.with_suffix(".json") if format == "both" else base_path
        saved_path = visualizer.save_json(str(json_path))
        print(f"✅ JSON data saved: {saved_path}")


def save_multi_output(monitor: MultiProcessMonitor, output_path: str, format: str):
    """Save multi-process monitoring output to file."""
    history = monitor.history
    if not history:
        print("⚠️  No data to save.")
        return

    visualizer = MultiProcessVisualizer(history)
    base_path = Path(output_path)

    if format in ("html", "both"):
        html_path = base_path.with_suffix(".html") if format == "both" else base_path
        saved_path = visualizer.save_html(str(html_path))
        print(f"✅ HTML report saved: {saved_path}")

    if format in ("json", "both"):
        json_path = base_path.with_suffix(".json") if format == "both" else base_path
        saved_path = visualizer.save_json(str(json_path))
        print(f"✅ JSON data saved: {saved_path}")


def print_multi_summary(monitor: MultiProcessMonitor):
    """Print multi-process monitoring summary."""
    summary = monitor.get_summary()
    if not summary:
        print("No data collected.")
        return

    print("\n" + "=" * 70)
    print(" 📈 Multi-Process Monitoring Summary")
    print("=" * 70)
    print(f" Processes: {summary.get('process_count', 0)}")
    print(f" Samples:   {summary.get('samples', 0)}")
    print(f" Duration:  {summary.get('duration_seconds', 0):.1f} seconds")
    print()

    total = summary.get("total", {})
    cpu = total.get("cpu_percent", {})
    mem = total.get("memory_mb", {})
    gpu_mem = total.get("gpu_memory_mb", {})

    print(" TOTAL Resources:")
    print(f"   CPU:    Avg {cpu.get('avg', 0):.1f}% | Max {cpu.get('max', 0):.1f}%")
    print(f"   Memory: Avg {mem.get('avg', 0):.1f} MB | Max {mem.get('max', 0):.1f} MB")
    if gpu_mem.get("max", 0) > 0:
        print(f"   VRAM:   Avg {gpu_mem.get('avg', 0):.1f} MB | Max {gpu_mem.get('max', 0):.1f} MB")
    print()

    # Per-process breakdown
    per_process = summary.get("per_process", {})
    if per_process:
        print(" Per-Process Breakdown:")
        for pid, proc_summary in per_process.items():
            name = proc_summary.get("name", "")
            proc_cpu = proc_summary.get("cpu_percent", {})
            proc_mem = proc_summary.get("memory_mb", {})
            print(f"   PID {pid} ({name}):")
            print(f"     CPU: {proc_cpu.get('avg', 0):.1f}% avg, {proc_cpu.get('max', 0):.1f}% max")
            print(f"     Mem: {proc_mem.get('avg', 0):.1f} MB avg, {proc_mem.get('max', 0):.1f} MB max")

    print("=" * 70)


def monitor_multiple_processes(args: argparse.Namespace, pids: list):
    """Monitor multiple processes."""
    # Parse GPU indices
    gpu_indices = None
    if args.gpu_indices:
        gpu_indices = [int(i.strip()) for i in args.gpu_indices.split(",")]

    # Create config
    config = MonitorConfig(
        interval=args.interval,
        enable_gpu=not args.no_gpu,
        enable_io=not args.no_io,
        gpu_indices=gpu_indices,
    )

    # Create multi-process monitor
    try:
        monitor = MultiProcessMonitor(pids=pids, config=config)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    if not args.quiet:
        print(f"📌 Monitoring PIDs: {', '.join(str(p) for p in monitor.pids)}")
        print(f"⏱️  Interval: {args.interval}s")
        if args.duration > 0:
            print(f"⏳ Duration: {args.duration}s")
        else:
            print("⏳ Duration: Indefinite (Ctrl+C to stop)")
        print(f"🎮 GPU monitoring: {'Enabled' if monitor.gpu_available else 'Disabled/Unavailable'}")
        print()

    # Handle interrupt
    interrupted = False

    def signal_handler(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Determine display mode
    use_realtime = args.realtime and not args.no_realtime and not args.quiet

    try:
        if use_realtime and args.duration == 0:
            # Real-time display mode (indefinite)
            chart = MultiProcessRealtimeChart(monitor, refresh_interval=args.interval)
            monitor = chart.start()
        else:
            # Timed monitoring mode
            monitor.start()
            start_time = time.time()

            if use_realtime:
                chart = MultiProcessRealtimeChart(monitor, refresh_interval=args.interval)
                while not interrupted:
                    elapsed = time.time() - start_time
                    if args.duration > 0 and elapsed >= args.duration:
                        break
                    history = monitor.history
                    if history:
                        chart._draw_frame(history[-1])
                    time.sleep(args.interval)
            else:
                # Quiet mode
                while not interrupted:
                    elapsed = time.time() - start_time
                    if args.duration > 0 and elapsed >= args.duration:
                        break
                    if not args.quiet:
                        if args.duration > 0:
                            sys.stdout.write(
                                f"\r⏳ Collecting... {elapsed:.0f}/{args.duration:.0f}s"
                            )
                        else:
                            sys.stdout.write(
                                f"\r⏳ Collecting... {elapsed:.0f}s (Ctrl+C to stop)"
                            )
                        sys.stdout.flush()
                    time.sleep(args.interval)

            monitor.stop()

    except Exception as e:
        print(f"\n❌ Error during monitoring: {e}")
        monitor.stop()
        sys.exit(1)

    # Print summary
    if not args.quiet:
        print_multi_summary(monitor)

    # Save output
    if args.output:
        save_multi_output(monitor, args.output, args.format)

    return monitor


def monitor_process(args: argparse.Namespace, pid: int):
    """Monitor a process."""
    # Parse GPU indices
    gpu_indices = None
    if args.gpu_indices:
        gpu_indices = [int(i.strip()) for i in args.gpu_indices.split(",")]

    # Create config
    config = MonitorConfig(
        interval=args.interval,
        enable_gpu=not args.no_gpu,
        enable_io=not args.no_io,
        gpu_indices=gpu_indices,
    )

    # Create monitor
    try:
        monitor = ProcessMonitor(pid=pid, config=config)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    if not args.quiet:
        print(f"📌 Monitoring PID: {pid}")
        print(f"⏱️  Interval: {args.interval}s")
        if args.duration > 0:
            print(f"⏳ Duration: {args.duration}s")
        else:
            print("⏳ Duration: Indefinite (Ctrl+C to stop)")
        print(f"🎮 GPU monitoring: {'Enabled' if monitor.gpu_available else 'Disabled/Unavailable'}")
        print()

    # Handle interrupt
    interrupted = False

    def signal_handler(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Determine display mode
    use_realtime = args.realtime and not args.no_realtime and not args.quiet

    try:
        if use_realtime and args.duration == 0:
            # Real-time display mode (indefinite)
            # Ctrl+C to stop and generate report
            chart = RealtimeChart(monitor, refresh_interval=args.interval)
            monitor = chart.start()  # Returns monitor with collected data
        else:
            # Timed monitoring mode
            monitor.start()
            start_time = time.time()

            if use_realtime:
                # Show progress with periodic updates
                chart = RealtimeChart(monitor, refresh_interval=args.interval)
                while not interrupted:
                    elapsed = time.time() - start_time
                    if args.duration > 0 and elapsed >= args.duration:
                        break
                    history = monitor.history
                    if history:
                        chart._draw_frame(history[-1])
                    time.sleep(args.interval)
            else:
                # Quiet mode - just collect data
                while not interrupted:
                    elapsed = time.time() - start_time
                    if args.duration > 0 and elapsed >= args.duration:
                        break
                    if not args.quiet:
                        if args.duration > 0:
                            sys.stdout.write(
                                f"\r⏳ Collecting... {elapsed:.0f}/{args.duration:.0f}s"
                            )
                        else:
                            sys.stdout.write(
                                f"\r⏳ Collecting... {elapsed:.0f}s (Ctrl+C to stop)"
                            )
                        sys.stdout.flush()
                    time.sleep(args.interval)

            monitor.stop()

    except Exception as e:
        print(f"\n❌ Error during monitoring: {e}")
        monitor.stop()
        sys.exit(1)

    # Print summary
    if not args.quiet:
        print_summary(monitor)

    # Save output
    if args.output:
        save_output(monitor, args.output, args.format)

    return monitor


def run_and_monitor(args: argparse.Namespace):
    """Run a command and monitor it."""
    if not args.quiet:
        print(f"🚀 Running command: {args.command}")
        print()

    # Start the subprocess
    try:
        process = subprocess.Popen(
            args.command,
            shell=True,
            stdout=subprocess.PIPE if args.quiet else None,
            stderr=subprocess.PIPE if args.quiet else None,
        )
    except Exception as e:
        print(f"❌ Failed to start command: {e}")
        sys.exit(1)

    # Monitor the process
    args_copy = argparse.Namespace(**vars(args))
    args_copy.pid = process.pid

    # If no duration specified, monitor until process exits
    if args.duration == 0:
        args_copy.duration = float("inf")

    try:
        monitor = monitor_process(args_copy, process.pid)
    except Exception as e:
        print(f"\n❌ Monitoring error: {e}")
        process.terminate()
        sys.exit(1)

    # Wait for process to complete
    return_code = process.poll()
    if return_code is None:
        if not args.quiet:
            print("\n⏳ Waiting for process to complete...")
        process.wait()
        return_code = process.returncode

    if not args.quiet:
        print(f"\n✅ Process exited with code: {return_code}")

    return monitor


def main():
    """Main entry point."""
    args = parse_args()

    if not args.quiet:
        print_banner()

    if args.command:
        # Run command and monitor
        run_and_monitor(args)
    elif args.pids:
        # Monitor multiple processes
        pids = [int(p.strip()) for p in args.pids.split(",")]
        monitor_multiple_processes(args, pids)
    else:
        # Monitor single process
        pid = args.pid or os.getpid()
        monitor_process(args, pid)


if __name__ == "__main__":
    main()
