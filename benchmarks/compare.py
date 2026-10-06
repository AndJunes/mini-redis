import argparse
import csv
import io
import subprocess
import sys
import time

TESTS = "ping_mbulk,set,get"
SERVERS = {
    "mini-redis": (6380, [sys.executable, "-m", "app.main", "--port", "6380"]),
    "Redis": (
        6381,
        ["redis-server", "--port", "6381", "--save", "", "--appendonly", "no"],
    ),
}


def benchmark(port, requests, clients, pipeline):
    output = subprocess.run(
        [
            "redis-benchmark",
            *("-p", str(port), "-t", TESTS, "-n", str(requests)),
            *("-c", str(clients), "-P", str(pipeline), "--csv"),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {row["test"]: row for row in csv.DictReader(io.StringIO(output))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=100_000)
    parser.add_argument("--clients", type=int, default=50)
    args = parser.parse_args()

    results = {}
    for name, (port, command) in SERVERS.items():
        server = subprocess.Popen(command, stdout=subprocess.DEVNULL)
        try:
            time.sleep(1)
            for pipeline in (1, 16):
                results[name, pipeline] = benchmark(
                    port, args.requests, args.clients, pipeline
                )
        finally:
            server.terminate()
            server.wait()

    print(f"{args.requests} requests, {args.clients} clients\n")
    print("| Command | Pipeline | mini-redis | Redis | p50 mini-redis | p50 Redis |")
    print("|---|---|---|---|---|---|")
    for pipeline in (1, 16):
        mini, redis = results["mini-redis", pipeline], results["Redis", pipeline]
        for test in mini:
            print(
                f"| {test} | {pipeline} "
                f"| {float(mini[test]['rps']):,.0f} req/s "
                f"| {float(redis[test]['rps']):,.0f} req/s "
                f"| {mini[test]['p50_latency_ms']} ms "
                f"| {redis[test]['p50_latency_ms']} ms |"
            )


if __name__ == "__main__":
    main()
