#!/usr/bin/env python3
"""EBAZ-27.17: bounded multi-PIP physical route witness search.

READ-ONLY. Uses EBAZ-27.13 configured INT PIP graph and EBAZ-27.15
site pin -> ALWAYS PPIP bridge mappings. Finds 2..max-hops directed
INT-PIP chains from one site-pin-side fixed net to another in DIFFERENT
physical tiles. No HINT/DEFAULT and no unobserved programmable PIP edges.

These are physical path candidates, NOT proven active BEL-to-BEL signal
nets, inferred occupancy, full netlists, timing, or SAFE_FREE areas.
Factory-derived CSV/JSON outputs remain private to the local WSL.
"""
import argparse
from collections import Counter, defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path

PREFIX = "ebaz27-multi-pip-routes"
OUT_FIELDS = (
    "source_tile", "source_site", "source_site_type", "source_pin",
    "destination_tile", "destination_site", "destination_site_type",
    "destination_pin", "pip_count", "fixed_net_chain",
    "pip_tile_chain", "pip_wire_chain", "source_always_path",
    "destination_always_path", "interpretation",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def js(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ids(value):
    if not value:
        return ()
    return tuple(int(x) for x in value.split(";"))


def validate(g, b, gc, gj, bc, bj):
    if g.get("status") != "INT_PIP_FIXED_WIRE_GRAPH_PARTIAL_NOT_NETLIST":
        raise ValueError("STOP: unexpected graph status")
    if b.get("status") != "ALWAYS_PPIP_BRIDGES_OBSERVED_PARTIAL_PHYSICAL_ONLY":
        raise ValueError("STOP: unexpected PPIP bridge status")
    if b.get("input", {}).get("graph_csv_sha256") != sha(gc) or \
            b.get("input", {}).get("graph_json_sha256") != sha(gj):
        raise ValueError("STOP: graph/bridge input SHA mismatch")
    if g.get("active_int_pips") != 171971:
        raise ValueError("STOP: graph INT PIP census mismatch")
    if g.get("inputs", {}).get("factory_fasm_sha256") != b.get("input", {}).get("factory_fasm_sha256"):
        raise ValueError("STOP: factory FASM identity mismatch")


def load_graph(path, expected):
    out = defaultdict(list)
    rows = 0
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        need = {"tile", "from_fixed_net", "to_fixed_net",
                "source_wire", "destination_wire", "metadata_status", "netlist_status"}
        if not need.issubset(r.fieldnames or []):
            raise ValueError("STOP: graph CSV columns missing")
        for p in r:
            rows += 1
            if p["netlist_status"] != "PARTIAL_INT_ROUTING_ONLY" or \
                    p["metadata_status"] not in (
                        "EXACT_PIP_MATCH", "BIDIRECTIONAL_REVERSED_PIP_MATCH"):
                raise ValueError("STOP: invalid PIP graph edge")
            a, b = int(p["from_fixed_net"]), int(p["to_fixed_net"])
            if a == b:
                raise ValueError("STOP: PIP collapsed onto own fixed net")
            out[a].append((b, p["tile"], p["source_wire"], p["destination_wire"]))
    if rows != expected:
        raise ValueError("STOP: graph CSV PIP count mismatch")
    return out


def load_pin_contacts(path, expected_count):
    drivers, receivers = defaultdict(list), defaultdict(list)
    source_seen, sink_seen = set(), set()
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        needed = {"tile", "site", "site_type", "pin", "pin_wire",
                  "contact_class", "inbound_fixed_net_ids",
                  "outbound_fixed_net_ids", "inbound_sample_path", "outbound_sample_path"}
        if not needed.issubset(reader.fieldnames or []):
            raise ValueError("STOP: pin bridge CSV columns missing")
        for p in reader:
            row_count += 1
            out_ids = ids(p["outbound_fixed_net_ids"])
            in_ids = ids(p["inbound_fixed_net_ids"])
            klass = p["contact_class"]
            if out_ids and klass not in ("ALWAYS_PPIP_BRIDGE_FROM_PIN",
                                          "ALWAYS_PPIP_BRIDGE_BOTH_DIRECTIONS",
                                          "DIRECT_INT_FIXED_NET_CONTACT"):
                raise ValueError("STOP: incompatible outbound contact class")
            if in_ids and klass not in ("ALWAYS_PPIP_BRIDGE_TO_PIN",
                                         "ALWAYS_PPIP_BRIDGE_BOTH_DIRECTIONS",
                                         "DIRECT_INT_FIXED_NET_CONTACT"):
                raise ValueError("STOP: incompatible inbound contact class")
            for n in out_ids:
                key = (n, p["tile"], p["site"], p["pin"])
                if key not in source_seen:
                    drivers[n].append(p)
                    source_seen.add(key)
            for n in in_ids:
                key = (n, p["tile"], p["site"], p["pin"])
                if key not in sink_seen:
                    receivers[n].append(p)
                    sink_seen.add(key)
    if row_count != expected_count:
        raise ValueError("STOP: contact row count mismatch")
    return drivers, receivers, row_count


def choose_sources(drivers, limit):
    """Sample spatially dispersed input sources, rather than first CSV rows."""
    groups = defaultdict(list)
    for net, pins in drivers.items():
        # One representative source pin per fixed net, grouped by tile type and x-band.
        p = pins[0]
        tile = p["tile"]
        tile_type = p["site_type"]
        # Alternating hash-free deterministic coarse spatial distribution.
        import re
        m = re.search(r"_X(\d+)Y(\d+)$", tile)
        x, y = (int(m[1]), int(m[2])) if m else (0, 0)
        groups[(tile_type, x // 10, y // 20)].append((net, p))
    keys = sorted(groups)
    for v in groups.values():
        v.sort(key=lambda item: (item[1]["tile"], item[1]["site"], item[1]["pin"], item[0]))
    chosen = []
    i = 0
    while len(chosen) < limit:
        advanced = False
        for key in keys:
            if i < len(groups[key]):
                chosen.append(groups[key][i])
                advanced = True
                if len(chosen) >= limit:
                    break
        if not advanced:
            break
        i += 1
    return chosen


def search(adjacency, sources, receivers, max_hops, max_visited_per_source,
           max_examples):
    counts = Counter()
    examples = []
    # Use BFS on fixed-net components. All graph transitions are configured INT PIPs.
    for start, sp in sources:
        counts["source_nets_attempted"] += 1
        queue = deque([start])
        # Track one shortest witness per fixed net, including predecessor and edge.
        pred = {start: None}
        depth = {start: 0}
        stop = False
        while queue:
            curr = queue.popleft()
            hops = depth[curr]
            if 2 <= hops <= max_hops and curr in receivers:
                for dp in receivers[curr]:
                    if sp["tile"] == dp["tile"]:
                        counts["same_tile_candidates_skipped"] += 1
                        continue
                    counts["different_tile_candidates"] += 1
                    if len(examples) >= max_examples:
                        continue
                    verts = [curr]
                    pip_edges = []
                    u = curr
                    while pred[u] is not None:
                        prev, edge = pred[u]
                        pip_edges.append(edge)
                        verts.append(prev)
                        u = prev
                    verts.reverse()
                    pip_edges.reverse()
                    examples.append({
                        "source_tile": sp["tile"], "source_site": sp["site"],
                        "source_site_type": sp["site_type"], "source_pin": sp["pin"],
                        "destination_tile": dp["tile"], "destination_site": dp["site"],
                        "destination_site_type": dp["site_type"], "destination_pin": dp["pin"],
                        "pip_count": len(pip_edges),
                        "fixed_net_chain": ";".join(map(str, verts)),
                        "pip_tile_chain": ";".join(e[1] for e in pip_edges),
                        "pip_wire_chain": ";".join(e[2] + "->" + e[3] for e in pip_edges),
                        "source_always_path": sp["outbound_sample_path"],
                        "destination_always_path": dp["inbound_sample_path"],
                        "interpretation": "PARTIAL_PHYSICAL_PATH_ONLY_NOT_PROVEN_BEL_ACTIVITY",
                    })
            if hops >= max_hops:
                continue
            for b, tile, src, dst in adjacency.get(curr, ()):
                if b in pred:
                    continue
                pred[b] = (curr, (b, tile, src, dst))
                depth[b] = hops + 1
                if len(pred) > max_visited_per_source:
                    counts["source_searches_capped"] += 1
                    stop = True
                    break
                queue.append(b)
            if stop:
                break
        counts["reached_fixed_nets_total"] += len(pred)
    return examples, counts


def self_test():
    src = {7: [{"tile":"CLB_X0Y0","site":"SLICE_X0Y0","site_type":"SLICEL",
                "pin":"AQ","outbound_sample_path":"PIP_A"}]}
    dst = {11: [{"tile":"CLB_X2Y0","site":"SLICE_X2Y0","site_type":"SLICEL",
                 "pin":"A2","inbound_sample_path":"PIP_B"}]}
    edges = {7:[(9,"INT_X0Y0","a","b")],9:[(11,"INT_X1Y0","c","d")]}
    output,counts = search(edges,[(7,src[7][0])],dst,3,20,10)
    assert len(output)==1 and output[0]["pip_count"]==2
    assert output[0]["fixed_net_chain"]=="7;9;11"
    same = {11:[{**dst[11][0],"tile":"CLB_X0Y0"}]}
    output2, counts2=search(edges,[(7,src[7][0])],same,3,20,10)
    assert not output2 and counts2["same_tile_candidates_skipped"]==1
    print("EBAZ27_MULTIPIP_ROUTE_SYNTHETIC_TEST_PASS")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph-csv",type=Path)
    ap.add_argument("--graph-json",type=Path)
    ap.add_argument("--bridges-csv",type=Path)
    ap.add_argument("--bridges-json",type=Path)
    ap.add_argument("--outdir",type=Path)
    ap.add_argument("--max-sources",type=int,default=96)
    ap.add_argument("--max-hops",type=int,default=4)
    ap.add_argument("--max-visited-per-source",type=int,default=25000)
    ap.add_argument("--max-examples",type=int,default=40)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:
        self_test()
        return
    if not all((a.graph_csv,a.graph_json,a.bridges_csv,a.bridges_json,a.outdir)):
        ap.error("graph and bridge CSV/JSON plus outdir are required")
    if not all(p.is_file() for p in (a.graph_csv,a.graph_json,a.bridges_csv,a.bridges_json)):
        ap.error("required evidence files are missing")
    if not a.outdir.is_dir():
        ap.error("outdir must exist")
    if not (1 <= a.max_sources <= 1000 and 2 <= a.max_hops <= 8
            and 100 <= a.max_visited_per_source <= 200000
            and 1 <= a.max_examples <= 1000):
        ap.error("limits out of supported range")
    graph, bridge = js(a.graph_json), js(a.bridges_json)
    validate(graph,bridge,a.graph_csv,a.graph_json,a.bridges_csv,a.bridges_json)
    adj = load_graph(a.graph_csv,graph["active_int_pips"])
    drivers,receivers,row_count=load_pin_contacts(
        a.bridges_csv,bridge["counts"]["pin_definitions"])
    sources=choose_sources(drivers,a.max_sources)
    print("EBAZ27.17 INPUT VERIFIED: %d INT PIPs; %d source fixed nets; %d sink fixed nets; %d selected sources" %
          (graph["active_int_pips"],len(drivers),len(receivers),len(sources)),flush=True)
    samples,counts=search(adj,sources,receivers,a.max_hops,a.max_visited_per_source,a.max_examples)
    report={
        "status":"MULTIPIP_CANDIDATES_PARTIAL_PHYSICAL_ONLY" if samples else "MULTIPIP_DIAGNOSTIC_NO_SAMPLES",
        "inputs":{"graph_csv_sha256":sha(a.graph_csv),"graph_json_sha256":sha(a.graph_json),
                  "bridges_csv_sha256":sha(a.bridges_csv),"bridges_json_sha256":sha(a.bridges_json),
                  "factory_fasm_sha256":graph["inputs"]["factory_fasm_sha256"]},
        "bounds":{"max_sources":a.max_sources,"max_hops":a.max_hops,
                  "max_visited_per_source":a.max_visited_per_source,
                  "max_examples":a.max_examples},
        "counts":dict(counts),
        "examples":samples,
        "limitations":[
            "BFS represents one shortest path per source net to each visited net, not all available physical routes.",
            "Only programmed INT PIPs appear in graph; ALWAYS PPIPs connect pins to fixed nets.",
            "DEFAULT/HINT/non-INT programmed PIPs, BEL internals and PS/EMIO functional behavior remain outside model.",
            "A candidate is NOT proof that a physical site is used or any cell drives the observed connection.",
            "Bounded/dispersed source selection, max hops and max visited nodes exclude many legitimate paths.",
            "No Ethernet, AXI, ASIC functional attribution, timing, complete netlist, or SAFE_FREE claims.",
        ]
    }
    output_json=a.outdir/(PREFIX+".json")
    output_csv=a.outdir/(PREFIX+".csv")
    with output_csv.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(samples)
    output_json.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("EBAZ27 MULTIPIP PATH EVIDENCE")
    for key in ("source_nets_attempted","different_tile_candidates",
                "same_tile_candidates_skipped","source_searches_capped",
                "reached_fixed_nets_total"):
        print("%s: %d" % (key,counts[key]))
    print("SAMPLES:",len(samples))
    for item in samples[:8]:
        print(" %s/%s.%s -> [%d PIPs] -> %s/%s.%s" % (
            item["source_tile"],item["source_site"],item["source_pin"],
            item["pip_count"],item["destination_tile"],
            item["destination_site"],item["destination_pin"]))
    print("JSON:",output_json)
    print("CSV:",output_csv)
    if samples:
        print("EBAZ27_MULTIPIP_PATHS_PASS (PHYSICAL CANDIDATES; NOT NETLIST)")
    else:
        print("EBAZ27_MULTIPIP_PATHS_PARTIAL (NO CROSS-TILE SAMPLES)")


if __name__=="__main__":
    main()
