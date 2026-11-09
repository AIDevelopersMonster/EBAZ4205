#!/usr/bin/env python3
"""EBAZ-27.13: conservative INT-PIP / fixed-wire connectivity graph (read-only).

Inputs: private EBAZ-27.12 PIP-evidence CSV+JSON, Project X-Ray tilegrid +
tileconn. We UNION wires connected by unconditional tileconn links, then
OVERLAY only observed, directionally-oriented FASM INT PIP features.

This yields a PARTIAL physical route graph, NOT an RTL/netlist, not proof of
site occupation or an FPGA region being free. The graph omits non-INT PIPs,
site/BEL internals, configuration defaults, unrecognized bits and timing.
Never writes FPGA, NAND, bitstream or public repository evidence.
"""
import argparse
from collections import Counter, defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path
import sys

FASM_SHA256 = "f22e32fc1608a9cee8ce30757b7d8f2856b3a307492534b02aafa7b90738b66b"
EXPECTED_INT_PIPS = 171971
PREFIX = "ebaz27-int-physical-graph"


class UnionFind:
    def __init__(self):
        self.parents = {}
        self.size = {}

    def add(self, node):
        if node not in self.parents:
            self.parents[node] = node
            self.size[node] = 1
            return True
        return False

    def find(self, node):
        p = self.parents
        root = node
        while p[root] != root:
            root = p[root]
        while p[node] != root:
            nxt = p[node]
            p[node] = root
            node = nxt
        return root

    def union(self, a, b):
        pa = self.find(a)
        pb = self.find(b)
        if pa == pb:
            return False
        if self.size[pa] < self.size[pb]:
            pa, pb = pb, pa
        self.parents[pb] = pa
        self.size[pa] += self.size[pb]
        del self.size[pb]
        return True


def load_json(path):
    with path.open("r", encoding="utf-8") as fd:
        return json.load(fd)


def make_fixed_index(conns):
    """Index unconditional tileconn wire links. tileconn is not a PIP list."""
    idx = defaultdict(list)
    for c in conns:
        typ = c["tile_types"]
        dx, dy = c["grid_deltas"]
        for src, dst in c["wire_pairs"]:
            src, dst = sys.intern(src), sys.intern(dst)
            idx[(typ[0], src)].append((dx, dy, typ[1], dst))
            idx[(typ[1], dst)].append((-dx, -dy, typ[0], src))
    return idx


def read_pips(csv_path, evidence):
    """Require complete EBAZ-27.12 metadata resolution; no guessed PIP edges."""
    rows = []
    counts = Counter()
    with csv_path.open("r", encoding="utf-8", newline="") as fd:
        reader = csv.DictReader(fd)
        needed = {"tile", "tile_type", "source_wire", "destination_wire", "pip_metadata_status",
                  "pip_directional", "pip_pseudo", "pip_feature"}
        if not needed.issubset(reader.fieldnames or []):
            raise ValueError("STOP: missing required PIP evidence CSV columns")
        for row in reader:
            counts["rows"] += 1
            status = row["pip_metadata_status"]
            if status not in ("EXACT_PIP_MATCH", "BIDIRECTIONAL_REVERSED_PIP_MATCH"):
                raise ValueError("STOP: unresolved PIP at row %d: %s" % (counts["rows"], status))
            if row["pip_pseudo"] != "0":
                raise ValueError("STOP: pseudo-PIP cannot be assumed to be an active switch")
            if row["pip_directional"] not in ("0", "1"):
                raise ValueError("STOP: unknown PIP directional property")
            if status == "BIDIRECTIONAL_REVERSED_PIP_MATCH" and row["pip_directional"] != "0":
                raise ValueError("STOP: reversed metadata accepted for directional PIP")
            typ = row["tile_type"]
            if typ not in ("INT_L", "INT_R"):
                raise ValueError("STOP: non-INT row")
            src, dst = row["source_wire"], row["destination_wire"]
            tile = row["tile"]
            if not src or not dst or row["pip_feature"] != tile + "." + dst + "." + src:
                raise ValueError("STOP: PIP feature fields do not match: %s" % row["pip_feature"])
            rows.append((tile, sys.intern(src), sys.intern(dst), typ, status))
            counts[status] += 1
            counts["INT_" + typ[-1]] += 1

    metadata = evidence.get("metadata_checks", {})
    if evidence.get("status") != "INT_PIP_METADATA_AND_FIXED_NEIGHBOR_EVIDENCE_ONLY":
        raise ValueError("STOP: invalid evidence JSON status")
    if evidence.get("factory_fasm_sha256") != FASM_SHA256:
        raise ValueError("STOP: evidence JSON factory FASM checksum mismatch")
    if evidence.get("observed_int_pip_feature_count") != len(rows):
        raise ValueError("STOP: CSV row count differs from JSON evidence")
    if metadata.get("exact_metadata_matches", 0) != counts["EXACT_PIP_MATCH"]:
        raise ValueError("STOP: exact matches differ between CSV and JSON")
    if metadata.get("bidirectional_reversed_matches", 0) != counts["BIDIRECTIONAL_REVERSED_PIP_MATCH"]:
        raise ValueError("STOP: reversed matches differ between CSV and JSON")
    if metadata.get("missing_metadata_matches", 0) or metadata.get("ambiguous_metadata_matches", 0):
        raise ValueError("STOP: unresolved metadata mismatches remain")
    if len(set((tile, src, dst) for tile, src, dst, _, _ in rows)) != len(rows):
        raise ValueError("STOP: duplicate PIP rows in CSV")
    return rows, counts


def analyze(tilegrid, conns, pips, max_nodes):
    coords = {}
    for name, m in tilegrid.items():
        xy = (m["grid_x"], m["grid_y"])
        if xy in coords:
            raise ValueError("STOP: two tiles have the same grid coordinate: %s" % (xy,))
        coords[xy] = name
    idx = make_fixed_index(conns)
    uf = UnionFind()
    q = deque()
    feature_tiles = Counter()
    for tile, src, dst, typ, status in pips:
        if tile not in tilegrid or tilegrid[tile]["type"] != typ:
            raise ValueError("STOP: tile name/type not in tilegrid: " + tile)
        feature_tiles[tile] += 1
        for wire in (src, dst):
            node = (tile, wire)
            if uf.add(node):
                q.append(node)
    initial_count = len(uf.parents)
    fixed_connections = 0
    new_fixed_nodes = 0
    fixed_edges_to_non_int = 0
    # Only follow unconditional, physically defined wire connections,
    # without crossing optional/programmed PIPs. Continue through all
    # intermediate tiles, even those not mentioned in FASM.
    while q:
        tile, wire = q.popleft()
        tm = tilegrid[tile]
        x, y, typ = tm["grid_x"], tm["grid_y"], tm["type"]
        for dx, dy, target_typ, target_wire in idx.get((typ, wire), ()):
            next_tile = coords.get((x + dx, y + dy))
            if next_tile is None or tilegrid[next_tile]["type"] != target_typ:
                continue
            node = (tile, wire)
            next_node = (next_tile, target_wire)
            if uf.add(next_node):
                q.append(next_node)
                new_fixed_nodes += 1
                if len(uf.parents) > max_nodes:
                    raise ValueError("STOP: --max-nodes exceeded during fixed-wire closure; "
                                     "no partial graph is emitted: %d" % len(uf.parents))
            uf.union(node, next_node)
            # Endpoints are visited in both directions. Count once.
            if node < next_node:
                fixed_connections += 1
                if typ not in ("INT_L", "INT_R") or target_typ not in ("INT_L", "INT_R"):
                    fixed_edges_to_non_int += 1
    # Normalize fixed-wire node groups; directed edge is a programmed INT PIP.
    component_id = {}
    component_member_count = Counter()
    kinds_per_component = defaultdict(set)
    for node in uf.parents:
        root = uf.find(node)
        component_member_count[root] += 1
        kinds_per_component[root].add(tilegrid[node[0]]["type"])
    fixed_roots = sorted(component_member_count, key=lambda x: (x[0], x[1]))
    for i, root in enumerate(fixed_roots):
        component_id[root] = i

    edges = []
    in_degree, out_degree = Counter(), Counter()
    active_int_pips_internal_fixed_node = 0
    for tile, src, dst, typ, status in pips:
        a = component_id[uf.find((tile, src))]
        b = component_id[uf.find((tile, dst))]
        # Do not silently treat a bidirectional physical PIP as two active
        # PIPs. FASM carries one configured orientation, SRC -> DST.
        if a == b:
            active_int_pips_internal_fixed_node += 1
        edges.append({"tile": tile, "from_fixed_net": a, "to_fixed_net": b,
                      "source_wire": src, "destination_wire": dst,
                      "metadata_status": status, "netlist_status": "PARTIAL_INT_ROUTING_ONLY"})
        out_degree[a] += 1
        in_degree[b] += 1
    components_with_non_int = sum(
        1 for x in kinds_per_component.values() if x.difference(("INT_L", "INT_R"))
    )
    summary = {
        "status": "INT_PIP_FIXED_WIRE_GRAPH_PARTIAL_NOT_NETLIST",
        "active_int_pips": len(edges),
        "tiles_with_active_int_pips": len(feature_tiles),
        "int_pip_wire_endpoints": initial_count,
        "additional_wire_vertices_from_fixed_closure": new_fixed_nodes,
        "total_fixed_wire_vertices": len(uf.parents),
        "fixed_tileconn_links_in_closure": fixed_connections,
        "fixed_tileconn_links_to_non_int_tiles": fixed_edges_to_non_int,
        "collapsed_fixed_wire_nets": len(fixed_roots),
        "collapsed_nets_touching_non_int_tile_types": components_with_non_int,
        "active_pips_with_same_source_target_fixed_net": active_int_pips_internal_fixed_node,
        "unique_source_fixed_nets": len(out_degree),
        "unique_destination_fixed_nets": len(in_degree),
        "max_programmed_outdegree": max(out_degree.values(), default=0),
        "max_programmed_indegree": max(in_degree.values(), default=0),
        "supply_or_tieoff_are_not_functional_net_labels": True,
        "limitations": [
            "This is a partial physical routing graph: fixed tileconn nets and observed INT PIPs only.",
            "No non-INT programmable switchbox PIPs are decoded or overlaid.",
            "No CLB LUT/FF pin, BRAM interface, PS7 EMIO, IOB pad or site internal paths are connected.",
            "No full user-cell netlist, no Ethernet/AXI net attribution and no real utilization.",
            "No edge is inferred from absence of a FASM feature or from unknown bits.",
            "Every active PIP has one FASM-defined direction; bidirectional hardware does not imply both configured directions.",
            "No SAFE_FREE region inference. Factory bitstream is not modified.",
        ],
    }
    return summary, edges


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-csv", type=Path, required=True)
    p.add_argument("--evidence-json", type=Path, required=True)
    p.add_argument("--device-db", type=Path, required=True,
                   help="Path to prjxray-db/zynq7/xc7z010")
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--max-nodes", type=int, default=900000,
                   help="Stop safely when fixed-wire closure exceeds this node count")
    args = p.parse_args()
    if not args.evidence_csv.is_file() or not args.evidence_json.is_file():
        p.error("PIP evidence files missing")
    if not args.device_db.is_dir() or not args.outdir.is_dir():
        p.error("device DB or output directory missing")
    if args.max_nodes < 100:
        p.error("--max-nodes must be at least 100")

    evidence = load_json(args.evidence_json)
    grid_path = args.device_db / "tilegrid.json"
    conn_path = args.device_db / "tileconn.json"
    grid, conns = load_json(grid_path), load_json(conn_path)
    if evidence.get("tilegrid_sha256") != hashlib.sha256(grid_path.read_bytes()).hexdigest():
        raise ValueError("STOP: device tilegrid hash differs from PIP evidence")
    if evidence.get("tileconn_sha256") != hashlib.sha256(conn_path.read_bytes()).hexdigest():
        raise ValueError("STOP: device tileconn hash differs from PIP evidence")
    pips, counts = read_pips(args.evidence_csv, evidence)
    if len(pips) != EXPECTED_INT_PIPS:
        raise ValueError("STOP: expected exact XC7Z010 171971 INT FASM feature count; got %d" % len(pips))
    print("EBAZ27 INPUT VERIFIED: %d INT PIPs, %d reverse-bidirectional" % (
        len(pips), counts["BIDIRECTIONAL_REVERSED_PIP_MATCH"]), flush=True)
    summary, edges = analyze(grid, conns, pips, args.max_nodes)
    summary["inputs"] = {
        "factory_fasm_sha256": evidence["factory_fasm_sha256"],
        "pip_evidence_csv_sha256": hashlib.sha256(args.evidence_csv.read_bytes()).hexdigest(),
        "pip_evidence_json_sha256": hashlib.sha256(args.evidence_json.read_bytes()).hexdigest(),
        "tilegrid_sha256": evidence["tilegrid_sha256"],
        "tileconn_sha256": evidence["tileconn_sha256"],
    }
    json_path = args.outdir / (PREFIX + ".json")
    csv_path = args.outdir / (PREFIX + ".csv")
    # Only publish after complete integrity/closure checks.
    with csv_path.open("w", newline="", encoding="utf-8") as fd:
        columns = ["tile", "from_fixed_net", "to_fixed_net", "source_wire",
                   "destination_wire", "metadata_status", "netlist_status"]
        writer = csv.DictWriter(fd, fieldnames=columns)
        writer.writeheader()
        writer.writerows(edges)
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("EBAZ27 INT PHYSICAL GRAPH")
    for key in ("active_int_pips", "tiles_with_active_int_pips", "int_pip_wire_endpoints",
                "additional_wire_vertices_from_fixed_closure", "total_fixed_wire_vertices",
                "fixed_tileconn_links_in_closure", "fixed_tileconn_links_to_non_int_tiles",
                "collapsed_fixed_wire_nets", "collapsed_nets_touching_non_int_tile_types",
                "active_pips_with_same_source_target_fixed_net"):
        print("%s: %s" % (key, summary[key]))
    print("JSON:", json_path)
    print("CSV:", csv_path)
    if summary["active_pips_with_same_source_target_fixed_net"]:
        print("WARNING: some active PIPs connect endpoints within one fixed net; investigate")
        print("EBAZ27_INT_GRAPH_PARTIAL_CHECK (NOT NETLIST)")
    else:
        print("EBAZ27_INT_GRAPH_PASS (PARTIAL ROUTING ONLY; NOT NETLIST)")


if __name__ == "__main__":
    main()
