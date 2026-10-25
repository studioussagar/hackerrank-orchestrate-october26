"""Main entry point for Ghost Data Still Exists deletion audit agent.

Executes the audit pipeline on evaluation requests (dataset/deletion_requests.csv)
or sample requests (dataset/sample_deletion_requests.csv) and writes output.csv
to the repository root strictly conforming to the challenge contract.
"""

import argparse
import os
import sys
import time
import pandas as pd

# Add repo root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from code.engine import AuditEngine
from code.evidence_loader import EvidenceLoader
from code.identity import IdentityResolver
from code.serializer import save_output_csv


def run_pipeline(input_path: str, output_path: str, is_sample: bool = False) -> None:
    """Runs the deletion-audit agent on the specified input dataset."""
    start_time = time.time()
    print(f"=== Ghost Data Still Exists: Starting Deletion Audit ===")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")

    # 1. Ingest identities and audit log
    print("Loading user identities and audit log...")
    identity_resolver = IdentityResolver(
        identities_path="dataset/user_identities.csv",
        audit_log_path="dataset/user_audit_log.csv"
    )

    # 2. Ingest evidence files
    print("Loading and indexing evidence files...")
    evidence_loader = EvidenceLoader(
        manifest_path="dataset/evidence_files.csv",
        base_evidence_dir="dataset"
    )
    evidence_loader.load_all(identity_resolver)

    # 3. Initialize engine
    engine = AuditEngine(identity_resolver, evidence_loader)

    # 4. Load requests
    requests_df = pd.read_csv(input_path)
    total_requests = len(requests_df)
    print(f"Auditing {total_requests} requests...")

    results = []
    status_counts = {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0}

    for idx, row in requests_df.iterrows():
        req_dict = row.to_dict()
        res = engine.audit_case(req_dict)
        results.append(res)
        status = res["deletion_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    # 5. Save canonical output CSV
    print(f"Writing canonical output to {output_path}...")
    save_output_csv(results, output_path=output_path)

    elapsed = time.time() - start_time
    print(f"=== Completed in {elapsed:.2f}s ===")
    print(f"Processed: {len(results)} rows")
    print(f"Status distribution: {status_counts}")


def main():
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists Deletion Audit Agent")
    parser.add_argument("--sample", action="store_true", help="Run on sample_deletion_requests.csv")
    parser.add_argument("--input", type=str, default=None, help="Custom input CSV path")
    parser.add_argument("--output", type=str, default="output.csv", help="Output CSV path")
    args = parser.parse_args()

    if args.sample:
        input_path = args.input or "dataset/sample_deletion_requests.csv"
        output_path = args.output if args.output != "output.csv" else "sample_run_output.csv"
        is_sample = True
    else:
        input_path = args.input or "dataset/deletion_requests.csv"
        output_path = args.output
        is_sample = False

    run_pipeline(input_path, output_path, is_sample)


if __name__ == "__main__":
    main()
