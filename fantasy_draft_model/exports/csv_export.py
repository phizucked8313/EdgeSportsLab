"""CSV output for EdgeIQ draft-book tables."""

from pathlib import Path


CSV_FILENAMES = {
    "Top 300": "top_300.csv",
    "QB": "qb.csv",
    "RB": "rb.csv",
    "WR": "wr.csv",
    "TE": "te.csv",
    "K": "k.csv",
    "DEF": "def.csv",
    "BLKWDW Picks": "blk_wdw_picks.csv",
}


def write_csv_tables(tables, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, table in tables.items():
        path = output_dir / CSV_FILENAMES[name]
        table.to_csv(path, index=False)
        paths.append(path)
    return paths
