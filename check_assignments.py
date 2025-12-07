import json
import sys

def main():
    data = json.load(sys.stdin)

    students = data.get("assigned", [])

    total_assigned = len(students)
    total_unassigned = len(data.get("unassigned", []))
    got_first = 0
    got_top3 = 0

    for s in students:
        rank_of_assigned = s.get("rank")

        if rank_of_assigned == 1:
            got_first += 1
        if rank_of_assigned <= 3:
            got_top3 += 1

    # Avoid division by zero
    if total_assigned == 0:
        print("No assigned students found.")
        return

    print(f"Students with assignments counted: {total_assigned}")
    print(f"Got 1st choice: {got_first} ({got_first / total_assigned * 100:.1f}%)")
    print(f"Got top-3 choice: {got_top3} ({got_top3 / total_assigned * 100:.1f}%)")
    print()
    print(f"Total unassigned students: {total_unassigned}")


if __name__ == "__main__":
    main()
