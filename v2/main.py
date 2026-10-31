"""Main entry point for Ghost Data Still Exists Version 2 (ML Augmented Agent).

Runs local Scikit-Learn NLP intent classification and evidence scoring models
to audit platform data deletions with zero external API calls or network latency.
"""

import argparse
import os
import sys
import time
import pandas as pd

# Add repo root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v2.evidence_loader import EvidenceLoader
from v2.identity import IdentityResolver
from v2.ml_engine import MLAuditEngine
from v2.serializer import save_output_csv


def run_pipeline(input_path: str, output_path: str, is_sample: bool = False) -> None:
    """Executes the Version 2 ML-based deletion audit pipeline."""
    start_time = time.time()
    print("=== Ghost Data Still Exists: Version 2 (ML Augmented Engine) ===")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")

    # 1. Load identities and audit logs
    print("Loading user identities and historical audit logs...")
    identity_resolver = IdentityResolver(
        identities_path="dataset/user_identities.csv",
        audit_log_path="dataset/user_audit_log.csv"
    )

    # 2. Ingest evidence files
    print("Loading and indexing evidence files across systems...")
    evidence_loader = EvidenceLoader(
        manifest_path="dataset/evidence_files.csv",
        base_evidence_dir="dataset"
    )
    evidence_loader.load_all(identity_resolver)

    # 3. Initialize ML Engine
    print("Initializing Scikit-Learn NLP intent classifier & evidence scorer...")
    engine = MLAuditEngine(identity_resolver, evidence_loader)

    # 4. Process requests
    requests_df = pd.read_csv(input_path)
    total_requests = len(requests_df)
    print(f"Executing ML inference on {total_requests} requests...")

    results = []
    status_counts = {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0}

    for _, row in requests_df.iterrows():
        req_dict = row.to_dict()
        res = engine.audit_case(req_dict)
        results.append(res)
        status = res["deletion_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    # 5. Save canonical output CSV
    print(f"Serializing canonical output to {output_path}...")
    save_output_csv(results, output_path=output_path)

    elapsed = time.time() - start_time
    print(f"=== v2 ML Pipeline Finished in {elapsed:.2f}s ===")
    print(f"Processed: {len(results)} rows ({len(results)/elapsed:.1f} requests/sec)")
    print(f"Status distribution: {status_counts}")
    print("External API Calls: 0 | Token Cost: $0.00 (100% Local Inference)")


def main():
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists: Version 2 (ML Agent)")
    parser.add_argument("--sample", action="store_true", help="Run on sample_deletion_requests.csv")
    parser.add_argument("--input", type=str, default=None, help="Custom input CSV path")
    parser.add_argument("--output", type=str, default="output_v2.csv", help="Output CSV path")
    args = parser.parse_args()

    if args.sample:
        input_path = args.input or "dataset/sample_deletion_requests.csv"
        output_path = args.output if args.output != "output_v2.csv" else "sample_run_output_v2.csv"
        is_sample = True
    else:
        input_path = args.input or "dataset/deletion_requests.csv"
        output_path = args.output
        is_sample = False

    run_pipeline(input_path, output_path, is_sample)


if __name__ == "__main__":
    main()
