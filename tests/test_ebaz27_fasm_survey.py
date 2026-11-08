#!/usr/bin/env python3
"""Basic synthetic test; does not validate Project X-Ray decoding."""
import importlib.util
import tempfile
from pathlib import Path

script = Path(__file__).resolve().parents[1] / "tools" / "ebaz27-fasm-survey.py"
spec = importlib.util.spec_from_file_location("ebaz27survey", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "synthetic.fasm"
    f.write_text("# comment\nCLBLL_L_X1Y2.SLICEL_X0.A6LUT.INIT[00] = 1\n"
                 "DSP_L_X3Y4.DSP_0.USE_DSP = 1\n"
                 "INT_L_X2Y2.SEEN = 1\n"
                 "unclassified evidence\n", encoding="utf-8")
    r = module.survey(f)
    assert r["tiles_with_expressed_features"] == 3, r
    assert r["feature_line_counts_by_tile_class"]["CLB"] == 1, r
    assert r["feature_line_counts_by_tile_class"]["DSP"] == 1, r
    assert r["feature_line_counts_by_tile_class"]["INTERCONNECT"] == 1, r
    assert r["unparsed_lines"] == 1, r
    assert "SAFE_FREE" not in str(r), r
print("EBAZ27 SYNTHETIC SURVEY PASS")
