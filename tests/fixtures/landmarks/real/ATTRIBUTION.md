# Real landmark fixtures: sources, licenses, and modifications

The JSONL files under this directory are DERIVED DATA: MediaPipe Pose Full
(BlazePose GHUM, mediapipe 0.10.21, model_complexity=1) landmark sequences
extracted from a curated subset of two public fall-detection video datasets.
No video frames or images from either dataset are stored in this repository;
raw videos live only in the gitignored tests/fixtures/clips/raw/ directory.

Modifications applied to the extracted landmark sequences (see
tests/fixtures/extract_landmarks.py and tests/fixtures/bake_real.py):

- frames decimated to 15 fps (the pipeline's ACTIVE-tier inference rate)
- landmark coordinates rounded (x/y to 3 decimals, z/visibility to 2)
- per-clip annotation headers added (floor line, rest zones, ground-truth
  label, lighting, expected detector behavior) from
  tests/fixtures/labels/real_annotations.json
- fall clips carry a disclosed synthetic TAIL-HOLD line (`{"type": "hold"}`)
  because the source recordings stop seconds after impact while the subject
  is still on the floor; every held frame is a repeat of the last real frame
  and the header states tail_start_t / tail_hold_s

## gmdcsa24/ — GMDCSA-24 (MIT License)

- Source: https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos
- DOI: 10.5281/zenodo.12921216
- License: MIT License, Copyright (c) 2024 Ekram Alam (full text ships with
  the dataset; fetched to tests/fixtures/clips/raw/gmdcsa24/LICENSE)
- Cite: E. Alam, A. Sufian, P. Dutta, M. Leo, I. A. Hameed, "GMDCSA24: A
  Dataset for Human Fall Detection in Videos", Data in Brief (2024).
- Subset used: 22 of 160 clips (12 falls, 10 ADLs) across all 4 subjects,
  chosen to cover day / night / lights-off lighting, ballistic and slow
  falls, bed lie-downs, floor lie-downs, floor exercise, and get-ups.

## caucafall/ — CAUCAFall (CC BY 4.0)

- Source: https://data.mendeley.com/datasets/7w7fccy7ky/4
- DOI: 10.17632/7w7fccy7ky.4
- License: Creative Commons Attribution 4.0 International
  (https://creativecommons.org/licenses/by/4.0)
- Credit: Jose Camilo Eraso Guerrero, Elena Munoz Espana, Mariela Munoz
  Anasco, Jesus Pinto (Universidad del Cauca / Universidad de la Amazonia),
  "Dataset CAUCAFall", Mendeley Data, V4 (2022).
- Changes were made: see the modification list above (landmark extraction,
  decimation, annotation, tail-hold). This notice is the CC BY 4.0
  "indicate if changes were made" statement.
- Subset used: 13 of 100 activity videos (7 falls, 6 ADLs) from Subject 1
  (natural light ~210 lux), Subject 6 (0 lux, IR camera), and Subject 8
  (artificial light ~125 lux).

Licensing rationale for bundling derived data from exactly these two
datasets: docs/research/ report 05 §B.1. Neither dataset's subjects are
identifiable from landmark coordinates (privacy note: research 05 §A.6).
