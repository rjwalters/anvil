"""Bower market-convergence figure (v2 vintage)."""

import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.set_title("2026 TAM: $54B+ convergence")
ax.set_xlabel("Year")
ax.set_ylabel("TAM ($B)")

plt.savefig("market-convergence.pdf")
