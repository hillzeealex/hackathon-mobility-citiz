"""Les scripts d'ingestion restent exécutables depuis n'importe quel dossier courant."""
import subprocess
import sys

from src.common.config import ROOT

INGEST = ROOT / "src" / "ingest"


def run(script, *args, cwd):
    return subprocess.run([sys.executable, str(INGEST / script), *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def test_download_all_list(tmp_path):
    r = run("download_all.py", "--list", cwd=tmp_path)
    assert r.returncode == 0 and "citiz" in r.stdout.split()


def test_default_paths_point_to_repo(tmp_path):
    for script in ("download_all.py", "collect_gbfs_status.py"):
        r = run(script, "--help", cwd=tmp_path)
        assert r.returncode == 0
    from src.ingest import collect_gbfs_status, download_all
    assert download_all.ROOT == ROOT and collect_gbfs_status.ROOT == ROOT


def test_check_data_on_fake_tree(tmp_path):
    raw = tmp_path / "raw"
    (raw / "insee").mkdir(parents=True)
    (raw / "insee" / "bpe25.parquet").write_bytes(b"PAR1" + b"\0" * 2000 + b"PAR1")
    (raw / "insee" / "filosofi2021_carreaux_200m_gpkg.zip").write_text("<!DOCTYPE html><html>404</html>")
    (raw / "manifest.csv").write_text(
        "categorie,source,url,fichier,taille,statut,date\ninsee,x,u,f,1,ok,d\n", encoding="utf-8")
    r = run("check_data.py", "--raw", str(raw), "--deep", cwd=tmp_path)
    report = (raw / "check_report.md").read_text(encoding="utf-8")
    assert r.returncode == 1  # HTML à la place du zip -> ❌
    assert "page HTML" in report
    assert "bpe25.parquet | 2 Ko, parquet OK" in report
