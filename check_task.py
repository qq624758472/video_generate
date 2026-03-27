import json
import sys

import test


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python3 check_task.py <task_id>")
        raise SystemExit(1)

    generator = test.VideoGenerator(
        api_key=test.API_KEY,
        base_url=test.BASE_URL,
    )
    data = generator.get_task_status(sys.argv[1])
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
