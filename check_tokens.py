from services.token_tracker import token_tracker

print("=" * 50)
print("TOKEN USAGE STATISTICS")
print("=" * 50)

stats = token_tracker.get_cumulative_stats()
print("\n📊 Stats (JSON):")
print(stats)

print("\n" + "=" * 50)
report = token_tracker.format_cumulative_report()
print(report)
print("=" * 50)