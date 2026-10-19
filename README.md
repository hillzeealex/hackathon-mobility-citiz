# Hackathon Mobility Citiz

## Installation

Python 3.11 ou plus (pandas 3 ne marche pas en dessous).

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Données

Le dossier `data/` n'est pas versionné. Les sources et les liens de téléchargement sont dans [SOURCES.md](SOURCES.md).

## Notebook Fabric

`fabric/01_ingestion.ipynb` tourne dans Microsoft Fabric : les écritures Spark/Delta et les chemins `/lakehouse/...` ne marchent pas en local.
