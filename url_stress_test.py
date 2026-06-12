import aiohttp
import asyncio
import time
import os
import statistics
from collections import Counter

# ================= CONFIG =================
URL = "https://server.valkontek.com/download/Bin_files/Valkonex.bin"

TOTAL_REQUESTS = 1000
TEST_CONCURRENCY = [50, 100, 150, 200, 300, 400, 500]
RUNS_PER_CONFIG = 3

SAVE_MODES = [False, True]
OUTPUT_DIR = "output"   

TIMEOUT = 120

# =========================================

def percentile_sorted(sorted_data, p):
    if not sorted_data:
        return 0
    k = int(len(sorted_data) * p / 100)
    return sorted_data[min(k, len(sorted_data) - 1)]


def analyze_stability(avg_rps, avg_lat, avg_p95, prev_rps):
    if prev_rps and avg_rps < prev_rps * 0.85:
        return "DEGRADING"
    if avg_p95 > avg_lat * 3:
        return "UNSTABLE"
    if avg_lat > 2:
        return "OVERLOADED"
    return "GOOD"


# ================= BANDWIDTH TEST =================
async def bandwidth_test():
    print("Running bandwidth baseline (10 parallel)...")

    async def fetch(session):
        async with session.get(URL) as r:
            size = 0
            async for chunk in r.content.iter_chunked(8192):
                size += len(chunk)
            return size

    start = time.time()
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[fetch(session) for _ in range(10)])
    duration = time.time() - start

    total = sum(results)
    mbps = (total * 8) / (duration * 1024 * 1024)

    print(f"Baseline throughput: {mbps:.2f} Mbps\n")
    return mbps


def write_file_sync(filepath, chunks):
    with open(filepath, "wb") as f:
        for chunk in chunks:
            f.write(chunk)


async def download_file(session, i, sem, save_files, stats):
    async with sem:
        start = time.time()

        try:
            async with session.get(URL) as response:
                code = response.status
                bytes_read = 0

                if save_files:
                    filepath = os.path.join(OUTPUT_DIR, f"file_{i}.bin")
                    chunks = []
                    async for chunk in response.content.iter_chunked(8192):
                        chunks.append(chunk)
                        bytes_read += len(chunk)
                    
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, write_file_sync, filepath, chunks)
                else:
                    async for chunk in response.content.iter_chunked(8192):
                        bytes_read += len(chunk)

                stats["bytes"] += bytes_read
                stats["codes"][code] += 1

                if code == 200:
                    stats["success"] += 1
                else:
                    stats["fail"] += 1

        except Exception as e:
            stats["fail"] += 1
            stats["codes"][f"exception: {type(e).__name__}"] += 1

        finally:
            stats["latencies"].append(time.time() - start)


async def run_test(concurrency, save_files):
    stats = {
        "success": 0,
        "fail": 0,
        "bytes": 0,
        "latencies": [],
        "codes": Counter()
    }

    if save_files:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    sem = asyncio.Semaphore(concurrency)
    connector = aiohttp.TCPConnector(limit=concurrency)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [
            download_file(session, i, sem, save_files, stats)
            for i in range(TOTAL_REQUESTS)
        ]

        start = time.time()
        await asyncio.gather(*tasks)
        end = time.time()

    total_time = end - start

    rps = TOTAL_REQUESTS / total_time
    sorted_latencies = sorted(stats["latencies"])
    avg_lat = sum(sorted_latencies) / len(sorted_latencies) if sorted_latencies else 0
    p50 = percentile_sorted(sorted_latencies, 50)
    p95 = percentile_sorted(sorted_latencies, 95)
    p99 = percentile_sorted(sorted_latencies, 99)

    mbps = (stats["bytes"] * 8) / (total_time * 1024 * 1024)

    return {
        "rps": rps,
        "lat": avg_lat,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "mbps": mbps,
        "success": stats["success"],
        "fail": stats["fail"]
    }


# ================= BENCHMARK =================
async def benchmark():
    baseline = await bandwidth_test()

    for save_files in SAVE_MODES:
        print(f"\n==============================")
        print(f"SAVE_FILES = {save_files}")
        print(f"==============================\n")

        prev_rps = None
        best_rps = 0
        best_conc = None
        breaking_point = None

        for conc in TEST_CONCURRENCY:
            runs = []

            for r in range(RUNS_PER_CONFIG):
                print(f"Running: concurrency={conc}, run={r+1}")
                res = await run_test(conc, save_files)
                runs.append(res)

            avg_rps = statistics.mean(r["rps"] for r in runs)
            avg_lat = statistics.mean(r["lat"] for r in runs)
            avg_p95 = statistics.mean(r["p95"] for r in runs)
            avg_mbps = statistics.mean(r["mbps"] for r in runs)

            std_rps = statistics.stdev(r["rps"] for r in runs) if len(runs) > 1 else 0
            efficiency = avg_rps / conc

            stability = analyze_stability(avg_rps, avg_lat, avg_p95, prev_rps)

            print(f"\n--- Concurrency {conc} ---")
            print(f"RPS: {avg_rps:.2f} (±{std_rps:.2f})")
            print(f"Latency: {avg_lat:.2f}s | P95: {avg_p95:.2f}s")
            print(f"Throughput: {avg_mbps:.2f} Mbps")
            print(f"Efficiency: {efficiency:.2f}")
            print(f"Stability: {stability}")

            # track best
            if avg_rps > best_rps:
                best_rps = avg_rps
                best_conc = conc

            # detect breaking point
            if stability in ["UNSTABLE", "OVERLOADED"] and not breaking_point:
                breaking_point = conc

            prev_rps = avg_rps

        print("\n========== SUMMARY ==========")
        print(f"Optimal concurrency: {best_conc}")
        print(f"Peak RPS: {best_rps:.2f}")
        print(f"Breaking point: {breaking_point}")
        print(f"Baseline bandwidth: {baseline:.2f} Mbps")
        print("=============================\n")


# ================= RUN =================
asyncio.run(benchmark())