import matplotlib.pyplot as plt

# X axis
concurrency = [50, 100, 150, 200, 300, 400, 500]

# ===== WITHOUT FILE SAVING =====
rps_no_save = [221.92, 263.13, 216.73, 228.54, 220.63, 194.09, 201.11]
lat_no_save = [0.22, 0.37, 0.61, 0.77, 1.15, 1.79, 1.74]
p95_no_save = [0.42, 0.73, 1.35, 1.80, 2.56, 4.40, 3.91]

# ===== WITH FILE SAVING =====
rps_save = [241.46, 168.37, 160.75, 194.95, 237.57, 212.51, 245.25]
lat_save = [0.20, 0.51, 0.80, 0.93, 1.09, 1.53, 1.65]
p95_save = [0.34, 1.28, 1.96, 2.17, 2.14, 3.60, 3.66]

# ===============================
# 1. RPS GRAPH
# ===============================
plt.figure()
plt.plot(concurrency, rps_no_save, marker='o', label='No Save')
plt.plot(concurrency, rps_save, marker='o', label='Save')
plt.xlabel("Concurrency")
plt.ylabel("RPS")
plt.title("RPS vs Concurrency")
plt.legend()
plt.grid()
plt.show()

# ===============================
# 2. LATENCY GRAPH
# ===============================
plt.figure()
plt.plot(concurrency, lat_no_save, marker='o', label='No Save Avg Latency')
plt.plot(concurrency, lat_save, marker='o', label='Save Avg Latency')
plt.xlabel("Concurrency")
plt.ylabel("Latency (seconds)")
plt.title("Latency vs Concurrency")
plt.legend()
plt.grid()
plt.show()

# ===============================
# 3. P95 GRAPH (IMPORTANT)
# ===============================
plt.figure()
plt.plot(concurrency, p95_no_save, marker='o', label='No Save P95')
plt.plot(concurrency, p95_save, marker='o', label='Save P95')
plt.xlabel("Concurrency")
plt.ylabel("P95 Latency (seconds)")
plt.title("P95 Latency vs Concurrency")
plt.legend()
plt.grid()
plt.show()