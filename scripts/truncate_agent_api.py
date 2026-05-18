f = r"C:\Users\haast\Docker\KRAI-minimal\backend\api\agent_api.py"
lines = open(f, encoding="utf-8").readlines()
# Keep only first 441 lines (index 0-440)
open(f, "w", encoding="utf-8").writelines(lines[:441])
result = open(f, encoding="utf-8").readlines()
print(f"Done. Line count: {len(result)}")
print(f"Last line: {result[-1]!r}")
