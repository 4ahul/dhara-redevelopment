import json
from pathlib import Path

from networkx.readwrite import json_graph

data = json.loads(Path("graphify-out/graph.json").read_text())
G = json_graph.node_link_graph(data, edges="links")

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print()

# Mapping/template related nodes
mapping_terms = [
    "mapping",
    "template",
    "cell",
    "report",
    "yaml",
    "33_7",
    "mapper",
    "report_generator",
]
print("=== MAPPING/TEMPLATE NODES ===")
for _nid, ndata in G.nodes(data=True):
    label = ndata.get("label", "")
    sf = ndata.get("source_file", "")
    if any(t in label.lower() or t in sf.lower() for t in mapping_terms):
        print(f"  {label} | {sf}")

print()
# Service nodes
service_terms = [
    "pr_card",
    "aviation",
    "reckoner",
    "rag_service",
    "mcgm",
    "dp_remarks",
    "orchestrator",
    "site_analysis",
    "report_generator",
]
print("=== SERVICE NODES ===")
seen = set()
for _nid, ndata in G.nodes(data=True):
    label = ndata.get("label", "")
    sf = ndata.get("source_file", "")
    for t in service_terms:
        if t in sf.lower() and sf not in seen:
            seen.add(sf)
            print(f"  {label} | {sf}")
            break

print()
# Print all communities
print("=== COMMUNITY LABELS ===")
communities = {}
for _nid, ndata in G.nodes(data=True):
    c = ndata.get("community", ndata.get("cluster", "?"))
    if c not in communities:
        communities[c] = []
    communities[c].append(ndata.get("label", _nid))

for cid, members in sorted(communities.items(), key=lambda x: -len(x[1])):
    print(
        f"  Community {cid} ({len(members)} nodes): {', '.join(members[:5])}{'...' if len(members) > 5 else ''}"
    )
