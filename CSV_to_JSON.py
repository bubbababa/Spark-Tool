import math
import json
import pandas as pd
from pathlib import Path

CSV_PATH = "Preferences-Grid view (4).csv"

TEAM_SIZE_TARGET = 8
MIN_TEAM_SIZE = 4
MAX_SECTIONS_PER_TEAM = 2
SWAP_PASSES = 2
DEFAULT_PROJECT_CAPACITY = 24

CHOICE_COLUMNS = [
    "1st Choice Project",
    "2nd Choice Project",
    "3rd Choice Project",
    "4th Choice Project",
    "5th Choice Project",
]


def build_json_for_course(df: pd.DataFrame, course: str, semester: str) -> dict:
    sub = df[(df["Course"] == course) & (df["Semester"] == semester)].copy()

    students = []
    projects = set()

    for _, row in sub.iterrows():
        buid = row["BUID"]
        name = row["Full Name"]

        # Use BUID as prefId (unique per student)
        pref_id = buid

        # Primary section
        primary_section = row.get("Discussion Section", None)
        if isinstance(primary_section, float) and math.isnan(primary_section):
            primary_section = None

        # Additional sections (comma-separated)
        additional_raw = row.get("Additional Discussion Section Availability", "")
        if isinstance(additional_raw, float) and math.isnan(additional_raw):
            additional_raw = ""

        additional_sections = [s.strip() for s in str(additional_raw).split(",") if s.strip()]

        # All possible sections for that student
        sections = []
        for s in additional_sections:
            sections.append(s)

        # Choices array
        choices = []
        for rank, col in enumerate(CHOICE_COLUMNS, start=1):
            proj = row.get(col, None)
            if isinstance(proj, float) and math.isnan(proj):
                continue
            proj = str(proj).strip()
            if not proj:
                continue

            projects.add(proj)
            choices.append(
                {
                    "projectId": proj,
                    "projectName": proj,
                    "rank": rank
                }
            )

        students.append(
            {
                "prefId": pref_id,
                "buid": buid,
                "studentName": name,
                "choices": choices,
                "sectionId": primary_section,
                "sectionIds": sections
            }
        )

    # Simple capacities object: same cap for every project in this course
    capacities = {
        proj: DEFAULT_PROJECT_CAPACITY for proj in sorted(projects)
    }

    json_obj = {
        "students": students,
        "capacities": capacities,
        "options": {
            "teamSizeTarget": TEAM_SIZE_TARGET,
            "minTeamSize": MIN_TEAM_SIZE,
            "maxSectionsPerTeam": MAX_SECTIONS_PER_TEAM,
            "swapPasses": SWAP_PASSES,
        },
    }

    return json_obj


def main():
    df = pd.read_csv(CSV_PATH)

    out_dir = Path("class_json")
    out_dir.mkdir(exist_ok=True)

    course_semesters = (
        df[["Course", "Semester"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["Course", "Semester"])
    )
    for _, row in course_semesters.iterrows():
        course = row["Course"]
        semester = row["Semester"]

        obj = build_json_for_course(df, course, semester)

        safe_course = course.replace("/", "_")
        safe_semester = semester.replace(" ", "_")
        out_path = out_dir / f"{safe_course}__{safe_semester}.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)

        print(f"Wrote JSON for course {course!r}, semester {semester!r} to {out_path}")

    print("Done.")


if __name__ == "__main__":
    main()
