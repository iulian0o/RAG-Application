import argparse
import csv
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", type=Path)
    args = parser.parse_args()

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "dataset",
            "run_id",
            "adapter_sha256",
            "source_sha256",
            "index_settings",
            "group",
            "k",
            "hit_rate",
            "evidence_recall",
            "complete_evidence_rate",
        ]
    )

    hashes_by_dataset = {}

    for path in args.results:
        run = json.loads(path.read_text(encoding="utf-8"))

        if run["status"] != "completed":
            raise ValueError(f"{path.name} is not a clean completed run.")

        dataset_id = run["dataset_id"]
        hashes = (run["adapter_sha256"], run["source_sha256"])

        previous = hashes_by_dataset.setdefault(dataset_id, hashes)
        if previous != hashes:
            raise ValueError(f"Question sets changed for {dataset_id}.")

        settings = [
            {
                "document_id": index["document_id"],
                "chunk_size": index["chunk_size"],
                "overlap": index["overlap"],
                "model_name": index["model_name"],
            }
            for index in run["snapshot"]["indexes"]
        ]

        groups = {"overall": run["summary"], **run["by_type"]}

        for group, summary in groups.items():
            for cutoff, metrics in summary["metrics"].items():
                writer.writerow(
                    [
                        dataset_id,
                        run["run_id"],
                        run["adapter_sha256"],
                        run["source_sha256"],
                        json.dumps(settings, separators=(",", ":")),
                        group,
                        cutoff,
                        metrics["hit_rate"],
                        metrics["evidence_recall"],
                        metrics["complete_evidence_rate"],
                    ]
                )


if __name__ == "__main__":
    main()