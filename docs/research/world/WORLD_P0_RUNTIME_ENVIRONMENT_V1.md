# WORLD P0 Canonical Runtime Environment V1

Status: VERIFIED REPRODUCIBLE ENVIRONMENT

## Identity

Canonical package inventory:

`requirements/world-p0-canonical-cu118.txt`

SHA-256:

`a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf`

Package count: 60

## Runtime

- Python: 3.12.3
- torch: 2.7.1+cu118
- torch CUDA runtime: 11.8
- cuDNN: 90100
- transformers: 5.16.1
- peft: 0.20.0
- lm-format-enforcer: 0.11.3
- tokenizers: 0.23.1
- safetensors: 0.8.0
- accelerate: 1.14.0
- GPU used for canonical verification: NVIDIA A40
- compute capability: 8.6

## Reconstruction

Create a clean Python 3.12 environment, then install with PyPI plus the
PyTorch CUDA 11.8 wheel index:

    python3 -m venv <venv>
    <venv>/bin/python -m pip install --upgrade pip==26.2.1
    <venv>/bin/python -m pip install \
      --extra-index-url https://download.pytorch.org/whl/cu118 \
      -r requirements/world-p0-canonical-cu118.txt

## Verification

A clean reconstruction on the canonical A40 machine produced:

- package count: 60
- exact `pip freeze --all | LC_ALL=C sort` SHA-256 match
- torch: 2.7.1+cu118
- CUDA runtime: 11.8
- cuDNN: 90100
- CUDA available: true
- GPU: NVIDIA A40
- CUDA 13 residual packages: 0

The reconstructed freeze was byte-identical to the original execution
environment freeze.

## Historical lockfile note

The repository `uv.lock` at the pre-P0 research revision resolved
`torch 2.13.0+cu130` in a clean sync and therefore did not exactly reconstruct
the historical canonical FA-v1 execution environment.

This document and the canonical requirements inventory explicitly bind the
runtime used for P0 V1. Historical evidence is not relabeled or modified.
