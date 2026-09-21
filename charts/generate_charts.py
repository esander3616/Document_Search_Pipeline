import pg8000.native
import matplotlib.pyplot as plt
import numpy as np

conn = pg8000.native.Connection(
    user="admin", password="YourTestPass123!",
    host="capstone-redshift.cnsdmrdqgxxb.us-east-1.redshift.amazonaws.com",
    port=5439, database="dev"
)

rows = conn.run("SELECT segment, COUNT(*) FROM customers GROUP BY segment ORDER BY segment")
segments = [r[0] for r in rows]
counts = [r[1] for r in rows]

plt.figure(figsize=(8, 5))
plt.bar(segments, counts, color="#2b6cb0")
plt.title("Customer Count by Segment")
plt.ylabel("Customers")
plt.tight_layout()
plt.savefig("charts/chart1_customers_by_segment.png", dpi=150)
plt.close()

rows = conn.run("""
    SELECT segment,
           SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
           COUNT(*) AS total
    FROM customers GROUP BY segment ORDER BY segment
""")
targets = {"Enterprise": 2.0, "Mid-Market": 4.0, "SMB": 6.5, "Self-Serve": 9.0}
segs = [r[0] for r in rows]
actual = [round(r[1] / r[2] * 100, 2) for r in rows]
target_vals = [targets[s] for s in segs]

x = np.arange(len(segs))
width = 0.35
plt.figure(figsize=(9, 5))
plt.bar(x - width/2, actual, width, label="Actual churn %", color="#c53030")
plt.bar(x + width/2, target_vals, width, label="Target churn %", color="#38a169")
plt.xticks(x, segs)
plt.ylabel("Monthly churn rate (%)")
plt.title("Actual vs. Documented Target Churn Rate by Segment")
plt.legend()
plt.tight_layout()
plt.savefig("charts/chart2_churn_vs_target.png", dpi=150)
plt.close()

conn.close()
print("Both charts saved")
