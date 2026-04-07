import csv
from collections import Counter, defaultdict

INPUT_CSV = "evaluation_results.csv"

label_counter = Counter()
type_label_counter = defaultdict(Counter)
retrieval_counter = Counter()
type_retrieval_counter = defaultdict(Counter)

with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        qtype = row["type"].strip().lower()
        label = row["label"].strip().lower()
        retrieval = row["retrieval_overall"].strip().lower()

        label_counter[label] += 1
        type_label_counter[qtype][label] += 1

        retrieval_counter[retrieval] += 1
        type_retrieval_counter[qtype][retrieval] += 1

print("=" * 80)
print("OVERALL ANSWER LABELS")
print("=" * 80)
for k, v in label_counter.items():
    print(f"{k}: {v}")

print("\n" + "=" * 80)
print("OVERALL RETRIEVAL SIGNALS")
print("=" * 80)
for k, v in retrieval_counter.items():
    print(f"{k}: {v}")

print("\n" + "=" * 80)
print("BY QUESTION TYPE - ANSWER LABELS")
print("=" * 80)
for qtype, counter in type_label_counter.items():
    print(f"\n[{qtype}]")
    for k, v in counter.items():
        print(f"  {k}: {v}")

print("\n" + "=" * 80)
print("BY QUESTION TYPE - RETRIEVAL SIGNALS")
print("=" * 80)
for qtype, counter in type_retrieval_counter.items():
    print(f"\n[{qtype}]")
    for k, v in counter.items():
        print(f"  {k}: {v}")