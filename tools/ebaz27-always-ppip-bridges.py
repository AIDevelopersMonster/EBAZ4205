#!/usr/bin/env python3
"""EBAZ-27.15: conservative site-pin bridges through X-Ray ALWAYS PPIPs.

Inputs are private EBAZ-27.13 graph JSON+CSV, X-Ray tilegrid/tileconn,
the X-Ray tile_type_*.json and ppips_*.db in the shared zynq7 database,
plus the unchanged EBAZ-27.14 script (for validated fixed-net closure).

The previous EBAZ-27.14 direct fixed-net contact census returned zero.
This tool asks whether physical site pins reach an INT-seeded fixed net via
1..N always-on intra-tile PIPs. It does NOT assume DEFAULT/HINT PPIPs,
or assume a programmable non-INT PIP is enabled without FASM evidence.
An always-on directed PIP is traversed in its documented direction;
never union its endpoints as if they were a shared electrical node.

Results are only physical routing-contact evidence, NOT actual LUT/FF
occupancy, BEL logic, functional Ethernet/AXI netlist, or a safe/free PL.
No writes to the device, boot media, bitstream or public factory artifacts.
"""
import argparse
from collections import Counter, defaultdict, deque
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

PREFIX = "ebaz27-always-ppip-bridges"
KINDS = ("CLBLL_L", "CLBLL_R", "CLBLM_L", "CLBLM_R", "BRAM_L", "BRAM_R", "RIOB33", "RIOI3")
CSV_COLUMNS = (
    "tile", "tile_type", "site", "site_type", "pin", "pin_wire",
    "contact_class", "inbound_fixed_net_ids", "outbound_fixed_net_ids",
    "inbound_min_hops", "outbound_min_hops", "inbound_sample_path",
    "outbound_sample_path", "interpretation"
)


def helper_module():
    path = Path(__file__).with_name("ebaz27-site-pin-contacts.py")
    if not path.is_file():
        raise ValueError("STOP: required earlier tool absent: " + str(path))
    spec = importlib.util.spec_from_file_location("ebaz27_site_pin_contacts", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_json(path):
    if not path.is_file():
        raise ValueError("STOP: missing file: " + str(path))
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_always_ppips(path, kind, meta):
    """Validate each ppips DB entry against corresponding tile_type PIP metadata."""
    if meta.get("tile_type") != kind:
        raise ValueError("STOP: tile_type mismatch: " + kind)
    available = defaultdict(list)
    for name, pip in meta.get("pips", {}).items():
        if "dst_wire" in pip and "src_wire" in pip:
            available[(pip["dst_wire"], pip["src_wire"])].append((name, pip))
    adj = defaultdict(list)
    reverse = defaultdict(list)
    counts = Counter()
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) != 2:
            raise ValueError("STOP: invalid PPIP DB record: " + s[:120])
        name, tag = parts
        if tag not in ("always", "default", "hint"):
            raise ValueError("STOP: unrecognized PPIP tag: " + tag)
        prefix, sep, rest = name.partition(".")
        wires = rest.split(".")
        if prefix != kind or not sep or len(wires) != 2:
            raise ValueError("STOP: invalid PPIP feature: " + name)
        dst, src = wires
        counts[tag] += 1
        if tag != "always":
            continue
        match = available.get((dst, src), ())
        if len(match) != 1:
            raise ValueError("STOP: ALWAYS PPIP lacks unambiguous tile_type metadata: " + name)
        physical_name, pip = match[0]
        if str(pip.get("is_directional")) != "1":
            raise ValueError("STOP: unexpected bidirectional ALWAYS PPIP: " + name)
        adj[src].append((dst, name))
        reverse[dst].append((src, name))
    if counts["always"] == 0:
        raise ValueError("STOP: no always-on PPIPs for selected type " + kind)
    return adj, reverse, dict(counts)


def walk(seed_wire, neighbors, max_hops):
    """Reach wire->(hops,ppip feature chain), traversing allowed edges only."""
    result = {seed_wire: (0, ())}
    q = deque((seed_wire,))
    while q:
        w = q.popleft()
        depth, chain = result[w]
        if depth >= max_hops:
            continue
        for next_wire, pip in neighbors.get(w, ()):
            if next_wire in result:
                continue
            result[next_wire] = (depth + 1, chain + (pip,))
            q.append(next_wire)
    return result


def choose_contacts(tile, reached, labels):
    """Net ID -> shortest witness; reached is relative to site-pin wire."""
    hits = {}
    for wire, (hops, chain) in reached.items():
        label = labels.get((tile, wire))
        if label is not None:
            old = hits.get(label)
            if old is None or hops < old[0]:
                hits[label] = (hops, chain, wire)
    return hits


def format_witness(hits, source_to_pin):
    if not hits:
        return "", "", ""
    ids = ";".join(str(x) for x in sorted(hits))
    shortest_net = min(hits, key=lambda k: (hits[k][0], k))
    hops, chain, wire = hits[shortest_net]
    # For incoming traversal we walked the reverse adjacency out of pin:
    # reorder PPIP records to show the actual source->destination direction.
    actual_path = reversed(chain) if source_to_pin else chain
    path = " | ".join(actual_path)
    if not path:
        path = "DIRECT_FIXED_WIRE:" + wire
    return ids, hops, path


def classify(inbound, outbound):
    """Classification is physical contact only, never inferred site occupancy."""
    if not inbound and not outbound:
        return "NO_INT_FIXED_NET_BRIDGE_WITH_ALWAYS_ONLY"
    if any(h[0] == 0 for h in list(inbound.values()) + list(outbound.values())):
        return "DIRECT_INT_FIXED_NET_CONTACT"
    if inbound and outbound:
        return "ALWAYS_PPIP_BRIDGE_BOTH_DIRECTIONS"
    if inbound:
        return "ALWAYS_PPIP_BRIDGE_TO_PIN"
    return "ALWAYS_PPIP_BRIDGE_FROM_PIN"


def verify_previous(graph, contacts, graph_csv, graph_json, contacts_json):
    if graph.get("status") != "INT_PIP_FIXED_WIRE_GRAPH_PARTIAL_NOT_NETLIST":
        raise ValueError("STOP: earlier graph has unexpected status")
    if contacts.get("status") != "PIN_CONTACTS_PARTIAL_EVIDENCE_ONLY":
        raise ValueError("STOP: previous site contact JSON has unexpected status")
    pin_counts = contacts.get("counts", {})
    if contacts.get("input", {}).get("source_graph_json_sha256") != digest(graph_json):
        raise ValueError("STOP: previous site contact report uses a different graph JSON")
    if contacts.get("input", {}).get("source_graph_csv_sha256") != digest(graph_csv):
        raise ValueError("STOP: previous site contact report uses a different graph CSV")
    if pin_counts.get("mapping_SITE_MAPPING_UNRESOLVED", 0):
        raise ValueError("STOP: unresolved site mappings in earlier step")
    return pin_counts


def collect(grid, labels, device_db, selected, max_hops, csv_path):
    # Load each type once. Only ALWAYS PPIPs enter adjacency.
    common = device_db.parent
    tile_info = {}
    counts_by_type = {}
    per_site = defaultdict(Counter)
    example_witnesses = defaultdict(list)
    for kind in selected:
        desc = load_json(common / ("tile_type_" + kind + ".json"))
        adj, reverse, stats = parse_always_ppips(
            common / ("ppips_" + kind.lower() + ".db"), kind, desc)
        # Re-use canonical site name resolver from EBAZ-27.14.
        pins = set()
        for site in desc["sites"]:
            for pin_desc in site.get("site_pins", {}).values():
                if isinstance(pin_desc, dict) and pin_desc.get("wire"):
                    pins.add(pin_desc["wire"])
                elif isinstance(pin_desc, str) and pin_desc:
                    pins.add(pin_desc)
        caching = {}
        for pin_wire in pins:
            caching[pin_wire] = (
                walk(pin_wire, reverse, max_hops), # predecessors: net -> pin
                walk(pin_wire, adj, max_hops),     # successors: pin -> net
            )
        tile_info[kind] = (desc, caching)
        counts_by_type[kind] = stats

    helper = helper_module()
    totals = Counter()
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for tile, info in grid.items():
            kind = info["type"]
            if kind not in selected:
                continue
            desc, cached = tile_info[kind]
            resolved = helper.resolve_sites(desc["sites"], info.get("sites") or {})
            totals["tiles_checked"] += 1
            for site, actual_name, site_status in resolved:
                totals["sites_checked"] += 1
                if not actual_name:
                    raise ValueError("STOP: unresolved site name: " + tile + ":" + site["type"])
                for pin, pin_desc in site.get("site_pins", {}).items():
                    if isinstance(pin_desc, dict):
                        wire = pin_desc.get("wire") or ""
                    elif isinstance(pin_desc, str):
                        wire = pin_desc
                    else:
                        wire = ""
                    totals["pin_definitions"] += 1
                    if not wire:
                        klass = "NO_PIN_WIRE_DEFINED"
                        in_ids = out_ids = in_depth = out_depth = in_chain = out_chain = ""
                    else:
                        inc_walk, out_walk = cached[wire]
                        inbound = choose_contacts(tile, inc_walk, labels)
                        outbound = choose_contacts(tile, out_walk, labels)
                        klass = classify(inbound, outbound)
                        in_ids, in_depth, in_chain = format_witness(inbound, source_to_pin=True)
                        out_ids, out_depth, out_chain = format_witness(outbound, source_to_pin=False)
                        if len(inbound) > 1:
                            totals["inbound_multiple_fixed_nets"] += 1
                        if len(outbound) > 1:
                            totals["outbound_multiple_fixed_nets"] += 1
                    totals[klass] += 1
                    per_site[site["type"]][klass] += 1
                    if klass not in ("NO_PIN_WIRE_DEFINED", "NO_INT_FIXED_NET_BRIDGE_WITH_ALWAYS_ONLY") \
                            and len(example_witnesses[site["type"]]) < 6:
                        example_witnesses[site["type"]].append({
                            "tile": tile, "site": actual_name, "pin": pin,
                            "wire": wire, "class": klass,
                            "inbound_net_ids": in_ids, "outbound_net_ids": out_ids,
                            "inbound_path": in_chain, "outbound_path": out_chain
                        })
                    writer.writerow({
                        "tile": tile, "tile_type": kind, "site": actual_name,
                        "site_type": site["type"], "pin": pin, "pin_wire": wire,
                        "contact_class": klass,
                        "inbound_fixed_net_ids": in_ids,
                        "outbound_fixed_net_ids": out_ids,
                        "inbound_min_hops": in_depth,
                        "outbound_min_hops": out_depth,
                        "inbound_sample_path": in_chain,
                        "outbound_sample_path": out_chain,
                        "interpretation": "PHYSICAL_CONTACT_EVIDENCE_ONLY_NOT_CELL_UTILIZATION",
                    })
    return totals, per_site, counts_by_type, example_witnesses


def self_test():
    # A controlled directed circuit: INT_NET -> input pin, output pin -> INT_NET
    m = {"tile_type": "EXAMPLE", "pips": {
        "EXAMPLE.INTWIRE->PIN": {"src_wire":"INTWIRE","dst_wire":"PIN","is_directional":"1"},
        "EXAMPLE.OUTPUT->INTWIRE": {"src_wire":"OUTPUT","dst_wire":"INTWIRE","is_directional":"1"},
        "EXAMPLE.FAKE->OTHER": {"src_wire":"FAKE","dst_wire":"OTHER","is_directional":"1"}
    }}
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "ppips_example.db"
        path.write_text("EXAMPLE.PIN.INTWIRE always\n"
                        "EXAMPLE.INTWIRE.OUTPUT always\n"
                        "EXAMPLE.OTHER.FAKE hint\n", encoding="utf-8")
        adj, rev, counts = parse_always_ppips(path, "EXAMPLE", m)
        if counts != {"always": 2, "hint": 1}:
            raise AssertionError(counts)
        labels = {("EXAMPLE_X0Y0", "INTWIRE"): 6}
        incoming = choose_contacts("EXAMPLE_X0Y0", walk("PIN", rev, 2), labels)
        outgoing = choose_contacts("EXAMPLE_X0Y0", walk("OUTPUT", adj, 2), labels)
        if set(incoming) != {6} or set(outgoing) != {6}:
            raise AssertionError((incoming, outgoing))
        if "OTHER" in walk("FAKE", adj, 4):
            raise AssertionError("HINT PPIP improperly traversed")
        if classify(incoming, {}) != "ALWAYS_PPIP_BRIDGE_TO_PIN":
            raise AssertionError("wrong classification")
        if classify({}, outgoing) != "ALWAYS_PPIP_BRIDGE_FROM_PIN":
            raise AssertionError("wrong classification")
        if choose_contacts("EXAMPLE_X0Y0", walk("PIN", adj, 2), labels):
            raise AssertionError("incorrect reverse traversal")
    print("EBAZ27_ALWAYS_BRIDGE_SYNTHETIC_TEST_PASS")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph-csv", type=Path)
    p.add_argument("--graph-json", type=Path)
    p.add_argument("--contacts-json", type=Path)
    p.add_argument("--device-db", type=Path)
    p.add_argument("--outdir", type=Path)
    p.add_argument("--max-hops", type=int, default=4)
    p.add_argument("--max-nodes", type=int, default=900000)
    p.add_argument("--tile-types", default=",".join(KINDS))
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    if not all((a.graph_csv, a.graph_json, a.contacts_json, a.device_db, a.outdir)):
        p.error("graph CSV+JSON, prior contacts JSON, device DB and outdir required")
    if not (a.graph_csv.is_file() and a.graph_json.is_file() and a.contacts_json.is_file()):
        p.error("missing prior evidence files")
    if not (a.device_db.is_dir() and a.outdir.is_dir()):
        p.error("device DB/outdir missing")
    if a.max_hops < 1 or a.max_hops > 12:
        p.error("--max-hops must be within 1..12")
    if a.max_nodes < 100:
        p.error("--max-nodes too low")
    selected = tuple(k.strip() for k in a.tile_types.split(",") if k.strip())
    if len(selected) != len(set(selected)) or any(k not in KINDS for k in selected):
        p.error("unsupported or duplicate tile types")
    graph = load_json(a.graph_json)
    contacts = load_json(a.contacts_json)
    old_counts = verify_previous(graph, contacts, a.graph_csv, a.graph_json, a.contacts_json)

    grid_path = a.device_db / "tilegrid.json"
    conn_path = a.device_db / "tileconn.json"
    if graph.get("inputs", {}).get("tilegrid_sha256") != digest(grid_path):
        raise ValueError("STOP: device tilegrid differs from graph input")
    if graph.get("inputs", {}).get("tileconn_sha256") != digest(conn_path):
        raise ValueError("STOP: device tileconn differs from graph input")
    if contacts.get("input", {}).get("tilegrid_sha256") != digest(grid_path) or \
            contacts.get("input", {}).get("tileconn_sha256") != digest(conn_path):
        raise ValueError("STOP: prior contacts use different device database")

    helper = helper_module()
    grid, conns = load_json(grid_path), load_json(conn_path)
    labels, evidence = helper.seed_labels(a.graph_csv, graph)
    closure = helper.propagate(labels, grid, conns, a.max_nodes)
    for key, value in closure.items():
        if graph.get(key) != value:
            raise ValueError("STOP: fixed-wire closure differs from prior graph: " + key)
    print("EBAZ27.15 SOURCE GRAPH AND FIXED CLOSURE VERIFIED: %d vertices, %d fixed nets" % (
        len(labels), graph["collapsed_fixed_wire_nets"]), flush=True)

    csv_path = a.outdir / (PREFIX + ".csv")
    totals, by_site, ppips, samples = collect(
        grid, labels, a.device_db, selected, a.max_hops, csv_path)
    if set(selected) == set(KINDS) and totals["pin_definitions"] != old_counts.get("pin_definitions"):
        raise ValueError("STOP: site-pin definition count differs from previous stage")
    bridged = sum(totals[k] for k in (
        "DIRECT_INT_FIXED_NET_CONTACT",
        "ALWAYS_PPIP_BRIDGE_BOTH_DIRECTIONS",
        "ALWAYS_PPIP_BRIDGE_TO_PIN",
        "ALWAYS_PPIP_BRIDGE_FROM_PIN"))
    status = ("ALWAYS_PPIP_BRIDGES_OBSERVED_PARTIAL_PHYSICAL_ONLY"
              if bridged else "DIAGNOSTIC_ZERO_BRIDGES_NOT_PASS")
    report = {
        "status": status,
        "max_hops": a.max_hops,
        "input": {
            "factory_fasm_sha256": graph["inputs"]["factory_fasm_sha256"],
            "graph_csv_sha256": digest(a.graph_csv),
            "graph_json_sha256": digest(a.graph_json),
            "contacts_json_sha256": digest(a.contacts_json),
            "tilegrid_sha256": digest(grid_path),
            "tileconn_sha256": digest(conn_path),
        },
        "previous_stage_direct_fixed_contacts": old_counts.get("PIN_TOUCHES_INT_SEEDED_FIXED_NET", 0),
        "counts": dict(totals),
        "by_site_type": {k:dict(v) for k,v in sorted(by_site.items())},
        "ppips_by_tile_type": ppips,
        "sample_witnesses": samples,
        "limitations": [
            "Only X-Ray ppips_*.db entries tagged ALWAYS are traversed.",
            "HINT/DEFAULT are excluded and never interpreted as active configured routes.",
            "Each ALWAYS PPIP is a directed intra-tile edge, never unioned as a fixed wire.",
            "Input/output meanings of site pins are not inferred from adjacency alone.",
            "Presence of a route bridge is not evidence that a primitive is occupied or that logic is enabled.",
            "Non-INT programmable PIPs, site/BEL internals, unresolved configuration bits and clocking remain unmodeled.",
            "No functional Ethernet/AXI/ASIC attribution, netlist or safe/free FPGA region.",
        ]
    }
    json_path = a.outdir / (PREFIX + ".json")
    json_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EBAZ27 ALWAYS PPIP BRIDGE EVIDENCE")
    for k in ("pin_definitions","DIRECT_INT_FIXED_NET_CONTACT",
              "ALWAYS_PPIP_BRIDGE_TO_PIN","ALWAYS_PPIP_BRIDGE_FROM_PIN",
              "ALWAYS_PPIP_BRIDGE_BOTH_DIRECTIONS",
              "NO_INT_FIXED_NET_BRIDGE_WITH_ALWAYS_ONLY","NO_PIN_WIRE_DEFINED",
              "inbound_multiple_fixed_nets","outbound_multiple_fixed_nets"):
        print("%s: %d" % (k, totals[k]))
    print("BRIDGED CONTACTS:",bridged)
    print("SAMPLE WITNESSES:")
    for typ in ("SLICEL","SLICEM","RAMB18E1","RAMBFIFO36E1","IOB33M","ILOGICE3"):
        for item in samples.get(typ, ())[:2]:
            print(" ", typ, item["tile"], item["pin"], item["class"], item["inbound_net_ids"], item["outbound_net_ids"])
    print("JSON:", json_path)
    print("CSV:", csv_path)
    if bridged:
        print("EBAZ27_ALWAYS_PPIP_BRIDGES_PASS (PARTIAL CONTACTS; NOT NETLIST/UTILIZATION)")
    else:
        print("EBAZ27_ALWAYS_PPIP_BRIDGES_PARTIAL (ZERO CONTACTS)")


if __name__ == "__main__":
    main()
