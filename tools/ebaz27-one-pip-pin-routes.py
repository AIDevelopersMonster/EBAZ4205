#!/usr/bin/env python3
"""EBAZ-27.16: bounded ONE-INT-PIP physical pin-to-pin route witnesses.

Reads private EBAZ-27.13 directed PIP graph CSV/JSON and EBAZ-27.15
ALWAYS-PPIP pin contact CSV/JSON; produces local JSON/CSV for candidate
paths of the form site-pin -> ALWAYS PPIP(s) -> fixed wire net ->
one factory-configured INT PIP -> fixed wire net -> ALWAYS PPIP(s) -> site-pin.

A candidate is NOT a recovered RTL net, proof a BEL is used, or a
validated functional link. No NAND/FPGA writes. Never publish full factory
derived route files.
"""
import argparse
from collections import Counter,defaultdict
import csv,hashlib,json
from pathlib import Path

PREFIX="ebaz27-one-pip-pin-routes"
FIELDS=["src_tile","src_site","src_site_type","src_pin","src_fixed_net",
        "pip_tile","pip_source_wire","pip_dest_wire","pip_metadata_status",
        "dst_fixed_net","dst_tile","dst_site","dst_site_type","dst_pin",
        "src_always_path","dst_always_path","interpretation"]


def load_json(p):
    with p.open("r",encoding="utf-8") as f: return json.load(f)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def net_ids(v):
    if not v: return ()
    vals=tuple(int(x) for x in v.split(";"))
    if any(n<0 for n in vals): raise ValueError("negative net id")
    return vals


def validate(graph,bridge,graph_csv,graph_json,bridge_csv,bridge_json):
    if graph.get("status")!="INT_PIP_FIXED_WIRE_GRAPH_PARTIAL_NOT_NETLIST":
        raise ValueError("STOP: unverified graph JSON")
    if bridge.get("status")!="ALWAYS_PPIP_BRIDGES_OBSERVED_PARTIAL_PHYSICAL_ONLY":
        raise ValueError("STOP: bridge report not a positive PARTIAL evidence report")
    inp=bridge.get("input",{})
    if inp.get("graph_csv_sha256")!=sha(graph_csv) or inp.get("graph_json_sha256")!=sha(graph_json):
        raise ValueError("STOP: bridge input graph SHA mismatch")
    if inp.get("factory_fasm_sha256")!=graph["inputs"]["factory_fasm_sha256"]:
        raise ValueError("STOP: factory FASM SHA mismatch")
    if graph["active_int_pips"]!=171971:
        raise ValueError("STOP: unexpected factory INT PIP census")


def load_contacts(path,max_per_net):
    """Keep bounded, deterministically selected pin candidates per net."""
    drivers=defaultdict(list)
    receivers=defaultdict(list)
    counts=Counter()
    with path.open("r",encoding="utf-8",newline="") as f:
        reader=csv.DictReader(f)
        need={"tile","site","site_type","pin","pin_wire","contact_class",
              "inbound_fixed_net_ids","outbound_fixed_net_ids",
              "inbound_sample_path","outbound_sample_path"}
        if not need.issubset(reader.fieldnames or []):
            raise ValueError("STOP: wrong site contacts CSV schema")
        for row in reader:
            counts["pin_rows"]+=1
            src_nets=net_ids(row["outbound_fixed_net_ids"])
            dst_nets=net_ids(row["inbound_fixed_net_ids"])
            if row["contact_class"] in ("NO_PIN_WIRE_DEFINED","NO_INT_FIXED_NET_BRIDGE_WITH_ALWAYS_ONLY") and (src_nets or dst_nets):
                raise ValueError("STOP: no-contact pin has assigned fixed net")
            if src_nets and row["contact_class"] not in ("DIRECT_INT_FIXED_NET_CONTACT","ALWAYS_PPIP_BRIDGE_FROM_PIN","ALWAYS_PPIP_BRIDGE_BOTH_DIRECTIONS"):
                raise ValueError("STOP: outbound net with mismatched contact class")
            if dst_nets and row["contact_class"] not in ("DIRECT_INT_FIXED_NET_CONTACT","ALWAYS_PPIP_BRIDGE_TO_PIN","ALWAYS_PPIP_BRIDGE_BOTH_DIRECTIONS"):
                raise ValueError("STOP: inbound net with mismatched contact class")
            for net in src_nets:
                if len(drivers[net])<max_per_net:
                    drivers[net].append(row.copy())
                else: counts["driver_candidates_capped"]+=1
            for net in dst_nets:
                if len(receivers[net])<max_per_net:
                    receivers[net].append(row.copy())
                else: counts["receiver_candidates_capped"]+=1
            counts["source_net_memberships"]+=len(src_nets)
            counts["destination_net_memberships"]+=len(dst_nets)
    return drivers,receivers,counts


def candidates(graph_csv, drivers,receivers,max_examples):
    counts=Counter()
    samples=[]
    with graph_csv.open("r",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f)
        require={"tile","from_fixed_net","to_fixed_net","source_wire","destination_wire","metadata_status","netlist_status"}
        if not require.issubset(r.fieldnames or []):
            raise ValueError("STOP: graph PIP CSV schema mismatch")
        for pip in r:
            counts["pips_seen"]+=1
            if pip["netlist_status"]!="PARTIAL_INT_ROUTING_ONLY" or pip["metadata_status"] not in ("EXACT_PIP_MATCH","BIDIRECTIONAL_REVERSED_PIP_MATCH"):
                raise ValueError("STOP: graph edge not verified")
            source=int(pip["from_fixed_net"])
            target=int(pip["to_fixed_net"])
            sources=drivers.get(source,())
            targets=receivers.get(target,())
            if not sources or not targets:continue
            counts["pips_with_end_to_end_candidates"]+=1
            counts["bounded_pin_pairs"]+=len(sources)*len(targets)
            if len(samples)>=max_examples: continue
            for a in sources:
                for b in targets:
                    if len(samples)>=max_examples: break
                    if a["tile"]==b["tile"] and a["site"]==b["site"] and a["pin"]==b["pin"]:
                        counts["self_pin_sample_skipped"]+=1
                        continue
                    samples.append({
                        "src_tile":a["tile"],"src_site":a["site"],
                        "src_site_type":a["site_type"],"src_pin":a["pin"],
                        "src_fixed_net":source,
                        "pip_tile":pip["tile"],"pip_source_wire":pip["source_wire"],
                        "pip_dest_wire":pip["destination_wire"],
                        "pip_metadata_status":pip["metadata_status"],
                        "dst_fixed_net":target,
                        "dst_tile":b["tile"],"dst_site":b["site"],
                        "dst_site_type":b["site_type"],"dst_pin":b["pin"],
                        "src_always_path":a["outbound_sample_path"],
                        "dst_always_path":b["inbound_sample_path"],
                        "interpretation":"ONE_INT_PIP_PHYSICAL_CANDIDATE_NOT_LOGICAL_NET",
                    })
                if len(samples)>=max_examples:break
    return samples,counts


def self_test():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as d:
        d=Path(d)
        a=d/"pins.csv";b=d/"pips.csv"
        with a.open("w",encoding="utf-8",newline="") as f:
            names=["tile","site","site_type","pin","pin_wire","contact_class","inbound_fixed_net_ids","outbound_fixed_net_ids","inbound_sample_path","outbound_sample_path"]
            w=csv.DictWriter(f,fieldnames=names);w.writeheader()
            for tile,site,pin,klass,inn,out in (
                ("CLB_X0Y0","SLICE_X0Y0","AQ","ALWAYS_PPIP_BRIDGE_FROM_PIN","","7"),
                ("CLB_X1Y0","SLICE_X1Y0","A2","ALWAYS_PPIP_BRIDGE_TO_PIN","9",""),
                ("CLB_X2Y0","SLICE_X2Y0","A2","NO_INT_FIXED_NET_BRIDGE_WITH_ALWAYS_ONLY","","")
            ):
                w.writerow(dict(tile=tile,site=site,site_type="SLICEL",pin=pin,pin_wire=pin,contact_class=klass,inbound_fixed_net_ids=inn,outbound_fixed_net_ids=out,inbound_sample_path="",outbound_sample_path=""))
        with b.open("w",encoding="utf-8",newline="") as f:
            cols=["tile","from_fixed_net","to_fixed_net","source_wire","destination_wire","metadata_status","netlist_status"]
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
            w.writerow(dict(tile="INT_L_X0Y0",from_fixed_net=7,to_fixed_net=9,source_wire="SRC",destination_wire="DST",metadata_status="EXACT_PIP_MATCH",netlist_status="PARTIAL_INT_ROUTING_ONLY"))
        drivers,receivers,counts=load_contacts(a,3)
        rows,stat=candidates(b,drivers,receivers,5)
        assert len(rows)==1 and rows[0]["src_pin"]=="AQ" and rows[0]["dst_pin"]=="A2"
        assert stat["pips_with_end_to_end_candidates"]==1
        assert 9 not in drivers and 7 not in receivers
    print("EBAZ27_ONE_PIP_PIN_ROUTE_SYNTHETIC_TEST_PASS")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph-csv",type=Path)
    p.add_argument("--graph-json",type=Path)
    p.add_argument("--bridges-csv",type=Path)
    p.add_argument("--bridges-json",type=Path)
    p.add_argument("--outdir",type=Path)
    p.add_argument("--max-per-net",type=int,default=4)
    p.add_argument("--max-examples",type=int,default=40)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test: self_test();return
    if not all((a.graph_csv,a.graph_json,a.bridges_csv,a.bridges_json,a.outdir)):
        p.error("graph CSV/JSON, bridges CSV/JSON and outdir required")
    if a.max_per_net<1 or a.max_per_net>32 or a.max_examples<1 or a.max_examples>1000:
        p.error("bounded max-per-net (1..32) and max-examples (1..1000) required")
    if not all(x.is_file() for x in (a.graph_csv,a.graph_json,a.bridges_csv,a.bridges_json)):
        p.error("source evidence missing")
    if not a.outdir.is_dir():p.error("output directory missing")
    graph=load_json(a.graph_json);bridge=load_json(a.bridges_json)
    validate(graph,bridge,a.graph_csv,a.graph_json,a.bridges_csv,a.bridges_json)
    drivers,receivers,cc=load_contacts(a.bridges_csv,a.max_per_net)
    if cc["pin_rows"] != bridge["counts"]["pin_definitions"]:
        raise ValueError("STOP: pin count differs from EBAZ-27.15 report")
    print("EBAZ27.16 EVIDENCE VERIFIED: %d pins, %d known INT PIPs" %
          (cc["pin_rows"],graph["active_int_pips"]),flush=True)
    sample,pc=candidates(a.graph_csv,drivers,receivers,a.max_examples)
    if pc["pips_seen"]!=graph["active_int_pips"]:
        raise ValueError("STOP: incomplete graph CSV")
    report={
        "status":"ONE_INT_PIP_CANDIDATE_PATHS_ONLY" if sample else "NO_ONE_PIP_SAMPLES_FOUND",
        "source_sha256":{
            "graph_csv":sha(a.graph_csv),"graph_json":sha(a.graph_json),
            "bridges_csv":sha(a.bridges_csv),"bridges_json":sha(a.bridges_json),
            "factory_fasm":graph["inputs"]["factory_fasm_sha256"]},
        "max_per_fixed_net":a.max_per_net,
        "max_examples":a.max_examples,
        "pin_census":dict(cc),"pip_census":dict(pc),
        "sample_paths":sample,
        "limitations":[
            "An observed path is site-pin contact -> fixed net -> ONE decoded INT PIP -> fixed net -> site-pin contact.",
            "Only documented ALWAYS PPIPs appear at site-pin contacts. DEFAULT/HINT excluded.",
            "Candidates do not prove that a site primitive drives or consumes the path in the factory design.",
            "Other programmed INT PIPs may precede/follow sampled edge: paths are NOT complete netlists.",
            "Site-pin direction is inferred only from ALWAYS PIP geometry, not from BEL function.",
            "Per-net sampling is capped and may undercount path alternatives.",
            "No claim about Ethernet/AXI/ASIC, occupancy, timing, or SAFE_FREE FPGA resources.",
        ]}
    j=a.outdir/(PREFIX+".json");c=a.outdir/(PREFIX+".csv")
    with c.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(sample)
    j.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("ONE-INT-PIP EVIDENCE")
    for k in ("source_net_memberships","destination_net_memberships","driver_candidates_capped","receiver_candidates_capped"):
        print("%s: %d" % (k,cc[k]))
    for k in ("pips_seen","pips_with_end_to_end_candidates","bounded_pin_pairs","self_pin_sample_skipped"):
        print("%s: %d" % (k,pc[k]))
    print("SAMPLE PATHS:",len(sample))
    for row in sample[:8]:
        print("  %s/%s.%s -> %s.%s.%s -> %s/%s.%s" % (
            row["src_tile"],row["src_site"],row["src_pin"],row["pip_tile"],
            row["pip_source_wire"],row["pip_dest_wire"],
            row["dst_tile"],row["dst_site"],row["dst_pin"]))
    print("JSON:",j)
    print("CSV:",c)
    if sample:
        print("EBAZ27_ONE_PIP_PIN_ROUTE_PASS (PHYSICAL CANDIDATES ONLY; NOT NETLIST)")
    else:
        print("EBAZ27_ONE_PIP_PIN_ROUTE_PARTIAL (NO CANDIDATES)")


if __name__=="__main__":
    main()
