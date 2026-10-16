"""Explicit, manual upload: python sync_supabase.py [--check]."""
import argparse

from supabase_store import StoreError, SupabaseStore, build_snapshot, get_config


def main():
    parser = argparse.ArgumentParser(description="Sync Creator Insights artifacts to Supabase")
    parser.add_argument("--check", action="store_true", help="Check connection without uploading")
    args = parser.parse_args()
    try:
        config = get_config()
        if config is None:
            raise StoreError("Set SUPABASE_URL and SUPABASE_SECRET_KEY in .env first.")
        store = SupabaseStore(config)
        store.check()
        if args.check:
            print("Supabase connection verified.")
            return
        snapshot = build_snapshot()
        identifier = store.sync(snapshot)
        print(f"Saved {snapshot['row_count']} posts. Snapshot: {identifier}")
    except (StoreError, OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
