import argparse
import json

from chatbot.learning_store import export_finetune_jsonl


def main():
    parser = argparse.ArgumentParser(description="Export fine-tuning dataset from chatbot learning logs.")
    parser.add_argument(
        "--output",
        default="chatbot/learning_data/finetune_dataset.jsonl",
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--min-rating",
        type=int,
        default=4,
        help="Minimum feedback rating to include examples (1-5).",
    )
    args = parser.parse_args()

    result = export_finetune_jsonl(args.output, min_rating=args.min_rating)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
