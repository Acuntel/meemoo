"""Synthetic landmark-clip synthesis (procedural stick-figure model).

Used by generate_synthetic.py to build the committed JSONL fixtures. The
figures follow MediaPipe's 33-landmark layout with honest geometry: the
camera frame matches GMDCSA-24's laptop-on-a-desk viewpoint, the floor line
sits at y=0.90, and fall kinematics respect the research 05 §A.3 thresholds
(ballistic falls ~0.5-0.6 s, controlled lie-downs >3 s — PMC8321307).
"""
