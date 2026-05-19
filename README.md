# PCR Lab Data

## Setup

1. Install `uv`:
   https://docs.astral.sh/uv/getting-started/installation/

2. From the repository root:

```bash
uv venv --seed
uv sync --group notebook
```

This creates `.venv` and seeds it with `pip`.
No manual activation is needed.

## Data

- `notebooks/00_etl.ipynb` downloads raw Zenodo files, parses YAML to Parquet, and saves to `data/processed/`.
- `notebooks/01_m1_eda.ipynb` reads the processed Parquet files (fast).

## VS Code

Install the `Python` and `Jupyter` extensions in VS Code.

Practical flow:

1. Run:

```bash
uv venv --seed
uv sync --group notebook
```

2. Open the repo in VS Code.

3. Open a notebook.

4. In the notebook, choose:
- `Select Kernel`
- `Python Environments`
- the project `.venv` interpreter

Paths:
- Linux/macOS: `.venv/bin/python`
- Windows: `.venv\\Scripts\\python.exe`

`ipykernel` is already included in the project notebook dependencies.

If the kernel does not appear, run:

```bash
uv run python -m ipykernel install --user --name pcr-lab-data --display-name "pcr-lab-data"
```

Then select `pcr-lab-data` in the notebook kernel picker.

## Browser JupyterLab

If someone wants the notebook in the browser instead of VS Code:

```bash
uv run jupyter lab
```

## Fallback: pip

If `uv` does not work on someone else's machine:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
jupyter lab
```

Python version: `3.12`

Notebook stack:
`pandas`, `numpy`, `matplotlib`, `seaborn`, `pyyaml`, `pyarrow`, `tqdm`, `scikit-learn`, `umap-learn`, `jupyterlab`, `ipykernel`

## Layout

- `data/processed/` prepared parquet files
- `data/raw/` raw Zenodo files
- `notebooks/00_etl.ipynb` ETL: YAML -> Parquet (run once)
- `notebooks/01_m1_eda.ipynb` Milestone 1: EDA + wykresy
- `reports/` milestone reports
- `results/m1/` milestone 1 figures

## Attribution

- Source: `PCR Lab Data` on Zenodo
- Link: https://zenodo.org/records/11617408
