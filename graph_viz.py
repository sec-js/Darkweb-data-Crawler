"""
graph_viz.py
Reads {keyword}_edges.csv produced by Darkweb.py and renders an
interactive Plotly force-directed graph of .onion link relationships.

Usage:
    python graph_viz.py --keyword ransomware

Dependencies:
    pip install networkx plotly pandas python-louvain openpyxl
"""

import argparse
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from urllib.parse import urlparse

# ── CLI ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Visualize .onion link graph from Darkweb.py output")
parser.add_argument("--keyword", required=True, help="Same keyword used in Darkweb.py")
args = parser.parse_args()
keyword = args.keyword

# ── Load edge list ────────────────────────────────────────────────────────────
try:
    df = pd.read_csv(f"{keyword}_edges.csv")
except FileNotFoundError:
    print(f"[!] Could not find '{keyword}_edges.csv'. Run Darkweb.py first with the same keyword.")
    exit(1)

print(f"[+] Loaded {len(df)} edges for keyword: '{keyword}'")

# ── Build directed graph ──────────────────────────────────────────────────────
G = nx.DiGraph()

for _, row in df.iterrows():
    src_parsed = urlparse(str(row["source"]))
    tgt_parsed = urlparse(str(row["target"]))
    src = src_parsed.netloc or str(row["source"])
    tgt = tgt_parsed.netloc or str(row["target"])
    weight = int(row["keyword_count"]) if not pd.isna(row["keyword_count"]) else 0

    if not G.has_node(src):
        G.add_node(src, node_type="seed", count=0)
    if not G.has_node(tgt):
        G.add_node(tgt, node_type="onion", count=weight)
    else:
        G.nodes[tgt]["count"] = G.nodes[tgt].get("count", 0) + weight

    if G.has_edge(src, tgt):
        G[src][tgt]["weight"] += weight
    else:
        G.add_edge(src, tgt, weight=weight)

print(f"[+] Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ── Community detection (Louvain on undirected copy) ─────────────────────────
try:
    from community import best_partition
    partition = best_partition(G.to_undirected())
    nx.set_node_attributes(G, partition, "community")
    num_communities = max(partition.values()) + 1
    print(f"[+] {num_communities} communities detected")
except ImportError:
    nx.set_node_attributes(G, 0, "community")
    num_communities = 1
    print("[!] python-louvain not installed — install with: pip install python-louvain")
    print("    Continuing without community coloring.")

# ── Layout ────────────────────────────────────────────────────────────────────
pos = nx.spring_layout(G, seed=42, k=1.5)

# ── Colour palette ────────────────────────────────────────────────────────────
PALETTE = [
    "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
    "#FFA15A", "#19D3F3", "#FF6692", "#B6E880"
]

# ── Edge trace ────────────────────────────────────────────────────────────────
edge_x, edge_y = [], []
for u, v in G.edges():
    x0, y0 = pos[u]
    x1, y1 = pos[v]
    edge_x += [x0, x1, None]
    edge_y += [y0, y1, None]

edge_trace = go.Scatter(
    x=edge_x, y=edge_y,
    mode="lines",
    line=dict(width=0.8, color="#888"),
    hoverinfo="none",
    name="Links"
)

# ── Node traces (one per community for legend grouping) ───────────────────────
node_traces = []
communities = sorted(set(nx.get_node_attributes(G, "community").values()))

for comm in communities:
    nodes_in_comm = [n for n, d in G.nodes(data=True) if d.get("community") == comm]
    x_vals, y_vals, texts, sizes, symbols = [], [], [], [], []

    for node in nodes_in_comm:
        x, y = pos[node]
        x_vals.append(x)
        y_vals.append(y)
        deg = G.in_degree(node)
        count = G.nodes[node].get("count", 0)
        node_type = G.nodes[node].get("node_type", "onion")
        sizes.append(max(10, 8 + deg * 4))
        symbols.append("diamond" if node_type == "seed" else "circle")
        texts.append(
            f"<b>{node}</b><br>"
            f"In-links: {deg}<br>"
            f"Keyword hits: {count}<br>"
            f"Type: {node_type}<br>"
            f"Community: {comm}"
        )

    color = PALETTE[comm % len(PALETTE)]
    node_traces.append(go.Scatter(
        x=x_vals, y=y_vals,
        mode="markers",
        marker=dict(
            size=sizes,
            color=color,
            symbol=symbols,
            line=dict(width=1, color="#222")
        ),
        text=texts,
        hoverinfo="text",
        name=f"Cluster {comm}"
    ))

# ── Assemble figure ───────────────────────────────────────────────────────────
fig = go.Figure(
    data=[edge_trace] + node_traces,
    layout=go.Layout(
        title=dict(
            text=f"<b>.onion Link Graph — keyword: <i>{keyword}</i></b>",
            font=dict(size=18, color="#eee")
        ),
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        font=dict(color="#eee"),
        showlegend=True,
        hovermode="closest",
        margin=dict(b=20, l=5, r=5, t=60),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        legend=dict(
            bgcolor="#16213e",
            bordercolor="#444",
            borderwidth=1
        )
    )
)

out_html = f"{keyword}_graph.html"
fig.write_html(out_html)
print(f"[+] Interactive graph saved -> {out_html}")
fig.show()
