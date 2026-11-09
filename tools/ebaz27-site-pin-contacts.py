#!/usr/bin/env python3
"""EBAZ-27.14: site-pin contact with an independently verified fixed-wire graph.

Read-only. Labels (tile,wire) from the EBAZ-27.13 INT graph are propagated
through unconditional tileconn wiring ONLY. Pin wires are attached when an
actual fixed-wire vertex from the previous graph is reached; sites/BELs are
not claimed occupied or functionally connected. Unknown/non-INT programmable
PIPs, hidden defaults and unresolved bits are not traversed.

Outputs remain local/private. Does not modify any .bit, NAND or FPGA.
"""
import argparse
from collections import Counter, defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

PREFIX = "ebaz27-site-pin-contacts"
DEFAULT_TILE_TYPES = (
    "CLBLL_L", "CLBLL_R", "CLBLM_L", "CLBLM_R",
    "BRAM_L", "BRAM_R", "RIOB33", "RIOI3",
)
XY_RE = re.compile(r"_X([0-9]+)Y([0-9]+)$")
COLUMNS = [
    "tile", "tile_type", "site_name", "site_type", "generic_site",
    "pin", "tile_wire", "fixed_net_id", "mapping_status", "contact_status",
    "interpretation",
]


def load_json(path):
    if not path.is_file():
        raise ValueError("STOP: required JSON missing: " + str(path))
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixed_index(tileconn):
    """Build adjacency in both directions; these edges are NOT programmable."""
    idx = defaultdict(list)
    for item in tileconn:
        types = item["tile_types"]
        dx, dy = item["grid_deltas"]
        for w_a, w_b in item["wire_pairs"]:
            w_a, w_b = sys.intern(w_a), sys.intern(w_b)
            idx[(types[0], w_a)].append((dx, dy, types[1], w_b))
            idx[(types[1], w_b)].append((-dx, -dy, types[0], w_a))
    return idx


def seed_labels(graph_csv, graph_json):
    labels = {}
    counts = Counter()
    with graph_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {
            "tile", "source_wire", "destination_wire", "from_fixed_net",
            "to_fixed_net", "metadata_status", "netlist_status",
        }
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("STOP: EBAZ-27.13 graph CSV schema mismatch")
        for row in reader:
            counts["pips"] += 1
            if row["netlist_status"] != "PARTIAL_INT_ROUTING_ONLY":
                raise ValueError("STOP: graph CSV contains unverified routing")
            if row["metadata_status"] not in (
                "EXACT_PIP_MATCH", "BIDIRECTIONAL_REVERSED_PIP_MATCH"):
                raise ValueError("STOP: graph CSV PIP not matched to X-Ray metadata")
            for role, wire_key, id_key in (
                ("src", "source_wire", "from_fixed_net"),
                ("dst", "destination_wire", "to_fixed_net"),
            ):
                net_id = int(row[id_key])
                if net_id < 0:
                    raise ValueError("STOP: negative fixed net id")
                node = (row["tile"], sys.intern(row[wire_key]))
                previous = labels.get(node)
                if previous is not None and previous != net_id:
                    raise ValueError("STOP: graph CSV assigns conflicting nets to " + repr(node))
                labels[node] = net_id
            counts[row["metadata_status"]] += 1
    if counts["pips"] != graph_json["active_int_pips"]:
        raise ValueError("STOP: graph CSV PIP count differs from graph JSON")
    if len(labels) != graph_json["int_pip_wire_endpoints"]:
        raise ValueError("STOP: graph CSV wire endpoints differ from graph JSON")
    if set(labels.values()) != set(range(graph_json["collapsed_fixed_wire_nets"])):
        raise ValueError("STOP: graph CSV fixed-net labels are missing or not contiguous")
    return labels, counts


def propagate(labels, grid, conn, max_nodes):
    coord_to_tile = {}
    for name, m in grid.items():
        xy = (m["grid_x"], m["grid_y"])
        if xy in coord_to_tile:
            raise ValueError("STOP: duplicate tilegrid coordinates " + str(xy))
        coord_to_tile[xy] = name
    index = fixed_index(conn)
    queue = deque(labels)
    initial = len(labels)
    verified_links = 0
    while queue:
        tile, wire = queue.popleft()
        info = grid.get(tile)
        if not info:
            raise ValueError("STOP: unknown tile from graph CSV: " + tile)
        x, y, typ = info["grid_x"], info["grid_y"], info["type"]
        net_id = labels[(tile, wire)]
        for dx, dy, target_type, target_wire in index.get((typ, wire), ()):
            other_tile = coord_to_tile.get((x + dx, y + dy))
            if other_tile is None or grid[other_tile]["type"] != target_type:
                continue
            other = (other_tile, target_wire)
            existing = labels.get(other)
            if existing is None:
                labels[other] = net_id
                queue.append(other)
                if len(labels) > max_nodes:
                    raise ValueError("STOP: fixed-wire vertex safety limit exceeded")
            elif existing != net_id:
                raise ValueError(
                    "STOP: graph-derived labels disagree across fixed tileconn wire: %r -> %r" %
                    ((tile, wire), other)
                )
            if (tile, wire) < other:
                verified_links += 1
    return {
        "initial_pip_wire_endpoints": initial,
        "total_fixed_wire_vertices": len(labels),
        "additional_wire_vertices_from_fixed_closure": len(labels) - initial,
        "fixed_tileconn_links_in_closure": verified_links,
    }


def site_coordinates(name):
    m = XY_RE.search(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def resolve_sites(generic_sites, site_names):
    """Model Project X-Ray's per-prefix coordinate origin, fail closed.

    Generic tile_type sites give relative coords and site type, while tilegrid
    gives absolute site names and types. Resolve by prefix-specific origin.
    Fallback only for a uniquely matching type, like Project X-Ray itself.
    """
    out = []
    for generic in generic_sites:
        prefix = generic["prefix"]
        typ = generic["type"]
        coords = []
        for name in site_names:
            if name.startswith(prefix + "_") and site_coordinates(name) is not None:
                coords.append(site_coordinates(name))
        if coords:
            origin_x = min(x for x, _ in coords)
            origin_y = min(y for _, y in coords)
        else:
            origin_x = origin_y = 0
        expected = "%s_X%dY%d" % (
            prefix, origin_x + int(generic["x_coord"]),
            origin_y + int(generic["y_coord"])
        )
        if site_names.get(expected) == typ:
            out.append((generic, expected, "COORDINATE_CONFIRMED"))
            continue
        by_type = [n for n, t in site_names.items() if t == typ]
        if len(by_type) == 1:
            out.append((generic, by_type[0], "UNIQUE_TYPE_FALLBACK"))
        else:
            out.append((generic, "", "SITE_MAPPING_UNRESOLVED"))
    return out


def collect_contacts(grid, labels, tile_types_dir, chosen_types, output_file):
    counts = Counter()
    site_counts = defaultdict(Counter)
    samples = defaultdict(list)
    tiles_by_type = defaultdict(list)
    for tile, meta in grid.items():
        if meta.get("type") in chosen_types:
            tiles_by_type[meta["type"]].append((tile, meta))
    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for typ in chosen_types:
            tiles = tiles_by_type[typ]
            if not tiles:
                raise ValueError("STOP: selected tile type absent from grid: " + typ)
            path = tile_types_dir / ("tile_type_" + typ + ".json")
            desc = load_json(path)
            if desc.get("tile_type") != typ:
                raise ValueError("STOP: tile-type metadata mismatch: " + typ)
            generic_sites = desc.get("sites")
            if not isinstance(generic_sites, list):
                raise ValueError("STOP: missing tile site descriptions: " + typ)
            for tile, meta in tiles:
                names = meta.get("sites") or {}
                matched = resolve_sites(generic_sites, names)
                counts["tiles_checked"] += 1
                for site, site_name, mapping_status in matched:
                    counts["site_definitions"] += 1
                    counts["mapping_" + mapping_status] += 1
                    pins = site.get("site_pins", {})
                    for pin, pin_desc in pins.items():
                        if isinstance(pin_desc, dict):
                            wire = pin_desc.get("wire")
                        elif isinstance(pin_desc, str):
                            wire = pin_desc
                        else:
                            wire = None
                        wire = wire or ""
                        counts["pin_definitions"] += 1
                        if not site_name:
                            contact = "SITE_MAPPING_UNRESOLVED"
                            fixed_net = ""
                        elif not wire:
                            contact = "NO_PIN_WIRE_DEFINED"
                            fixed_net = ""
                        else:
                            net = labels.get((tile, wire))
                            if net is None:
                                contact = "NO_FIXED_NET_CONTACT"
                                fixed_net = ""
                            else:
                                contact = "PIN_TOUCHES_INT_SEEDED_FIXED_NET"
                                fixed_net = net
                        counts[contact] += 1
                        site_counts[site["type"]][contact] += 1
                        if len(samples[site["type"]]) < 6:
                            samples[site["type"]].append({
                                "tile": tile, "site": site_name,
                                "pin": pin, "wire": wire,
                                "fixed_net_id": fixed_net,
                                "contact": contact,
                            })
                        writer.writerow({
                            "tile": tile, "tile_type": typ, "site_name": site_name,
                            "site_type": site["type"],
                            "generic_site": site["name"],
                            "pin": pin, "tile_wire": wire,
                            "fixed_net_id": fixed_net,
                            "mapping_status": mapping_status,
                            "contact_status": contact,
                            "interpretation": "TOUCH_ONLY_NOT_PROVEN_USED",
                        })
    return counts, site_counts, samples


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph-csv", type=Path, required=True)
    p.add_argument("--graph-json", type=Path, required=True)
    p.add_argument("--device-db", type=Path, required=True,
                   help="Path to prjxray-db/zynq7/xc7z010")
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--tile-types", default=",".join(DEFAULT_TILE_TYPES),
                   help="Comma-separated tile types with site metadata to examine")
    p.add_argument("--max-nodes", type=int, default=900000)
    a = p.parse_args()
    if not a.graph_csv.is_file() or not a.graph_json.is_file():
        p.error("missing graph evidence")
    if not a.device_db.is_dir() or not a.outdir.is_dir():
        p.error("missing X-Ray device database or output dir")
    selected = tuple(x.strip() for x in a.tile_types.split(",") if x.strip())
    if not selected or len(selected) != len(set(selected)):
        p.error("tile types must be unique and non-empty")
    if a.max_nodes < 100:
        p.error("max-nodes too small")
    graph = load_json(a.graph_json)
    if graph.get("status") != "INT_PIP_FIXED_WIRE_GRAPH_PARTIAL_NOT_NETLIST":
        raise ValueError("STOP: source graph lacks verified status")
    grid_file = a.device_db / "tilegrid.json"
    conn_file = a.device_db / "tileconn.json"
    if graph.get("inputs", {}).get("tilegrid_sha256") != digest(grid_file):
        raise ValueError("STOP: tilegrid changed since graph generation")
    if graph.get("inputs", {}).get("tileconn_sha256") != digest(conn_file):
        raise ValueError("STOP: tileconn changed since graph generation")
    grid = load_json(grid_file)
    conn = load_json(conn_file)
    labels, pipcounts = seed_labels(a.graph_csv, graph)
    print("EBAZ27.14 SOURCE GRAPH VERIFIED: %d INT PIPs" % pipcounts["pips"], flush=True)
    recheck = propagate(labels, grid, conn, a.max_nodes)
    for key, value in recheck.items():
        if value != graph[key]:
            raise ValueError("STOP: fixed-net closure mismatch %s: %s != %s" %
                             (key, value, graph[key]))
    print("EBAZ27.14 FIXED-WIRE CLOSURE VERIFIED: %d vertices, %d fixed nets" %
          (len(labels), graph["collapsed_fixed_wire_nets"]), flush=True)
    csv_path = a.outdir / (PREFIX + ".csv")
    counts, sites, samples = collect_contacts(
        grid, labels, a.device_db.parent, selected, csv_path
    )
    report = {
        "status": "PIN_CONTACTS_PARTIAL_EVIDENCE_ONLY",
        "input": {
            "factory_fasm_sha256": graph["inputs"]["factory_fasm_sha256"],
            "source_graph_json_sha256": digest(a.graph_json),
            "source_graph_csv_sha256": digest(a.graph_csv),
            "tilegrid_sha256": digest(grid_file),
            "tileconn_sha256": digest(conn_file),
        },
        "fixed_graph_closure_revalidated": recheck,
        "tile_types_checked": list(selected),
        "counts": dict(counts),
        "site_type_counts": {k: dict(v) for k, v in sorted(sites.items())},
        "site_type_samples": dict(samples),
        "limitations": [
            "Contact means a physical site pin wire is a member of an INT-seeded fixed net.",
            "Contact is not evidence of used LUT/FF/BRAM/IOB or netlist functionality.",
            "NO_FIXED_NET_CONTACT means the INT-seeded partial graph does not reach this pin.",
            "Unmodeled non-INT PIPs, site internals, unknown bits and defaults may connect additional paths.",
            "Duplicate RAMB18/RAMBFIFO36 site definitions are alternatives and not additive capacity.",
            "No Ethernet/AXI/ASIC classification or SAFE_FREE allocation can be inferred.",
        ],
    }
    json_path = a.outdir / (PREFIX + ".json")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print("SITE TYPE | PIN DEFINITIONS | CONTACT WITH INT FIXED NET | NO CONTACT | NO WIRE")
    for typ, tally in sorted(sites.items()):
        total = sum(tally.values())
        print("%s | %d | %d | %d | %d" % (
            typ, total, tally["PIN_TOUCHES_INT_SEEDED_FIXED_NET"],
            tally["NO_FIXED_NET_CONTACT"], tally["NO_PIN_WIRE_DEFINED"]))
    print("TOTAL PIN DEFINITIONS:", counts["pin_definitions"])
    print("SITE INSTANCES UNRESOLVED:", counts["mapping_SITE_MAPPING_UNRESOLVED"])
    print("CONTACTS:", counts["PIN_TOUCHES_INT_SEEDED_FIXED_NET"])
    print("JSON:", json_path)
    print("CSV:", csv_path)
    if counts["mapping_SITE_MAPPING_UNRESOLVED"]:
        print("EBAZ27_SITE_PIN_CONTACTS_PARTIAL (UNRESOLVED SITE MAPPING)")
    else:
        print("EBAZ27_SITE_PIN_CONTACTS_PASS (PARTIAL GRAPH; NOT UTILIZATION/NETLIST)")


if __name__ == "__main__":
    main()
